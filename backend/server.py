from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Iterable
from datetime import datetime, timezone
import os
import uuid
import re
import aiofiles
import zipfile
import logging
import tempfile
from contextlib import asynccontextmanager

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection (Atlas-compatible)
mongo_url = os.environ.get('MONGO_URL')
if not mongo_url:
    raise RuntimeError("MONGO_URL not set. Add your MongoDB Atlas connection string to backend/.env or set it in the environment")
# Trim surrounding whitespace and quotes which commonly appear when copying env values from some UIs
mongo_url = mongo_url.strip()
if (mongo_url.startswith('"') and mongo_url.endswith('"')) or (mongo_url.startswith("'") and mongo_url.endswith("'")):
    mongo_url = mongo_url[1:-1]

client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)

# Read and sanitize DB_NAME
raw_db_name = os.environ.get('DB_NAME', 'site_renamer')
db_name = str(raw_db_name).strip()
if (db_name.startswith('"') and db_name.endswith('"')) or (db_name.startswith("'") and db_name.endswith("'")):
    # strip surrounding quotes
    db_name = db_name[1:-1]
# Defensive: remove accidental trailing/leading whitespace and control chars
db_name = db_name.strip()
if '"' in db_name or "'" in db_name:
    # If quotes remain inside the name, log and raise a clear error
    raise RuntimeError(f"DB_NAME contains invalid quote characters after sanitization: {db_name!r}. Remove quotes from the environment variable.")

db = client[db_name]

# Production / operational settings (can be tuned via env)
MAX_UPLOAD_SIZE = int(os.environ.get('MAX_UPLOAD_SIZE', 10 * 1024 * 1024))  # 10 MiB default
ALLOWED_EXTENSIONS = set(x.lower() for x in os.environ.get('ALLOWED_EXTENSIONS', '.jpg,.jpeg,.png,.gif,.bmp,.tiff').split(','))

# Parse CORS origins (comma-separated). Empty or '*' => allow all
raw_cors = os.environ.get('CORS_ORIGINS', '*')
if raw_cors.strip() == '*' or raw_cors.strip() == '':
    # Use a list with '*' so Starlette's CORSMiddleware understands "allow all"
    CORS_ORIGINS: Iterable[str] = ["*"]
else:
    CORS_ORIGINS = [o.strip() for o in raw_cors.split(',') if o.strip()]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify DB connection and prepare indexes at startup
    try:
        await client.admin.command("ping")
        logger.info("Connected to MongoDB (%s)", db_name)
        # Ensure an index on site_id exists for quick lookups (idempotent)
        try:
            await db.sites.create_index("site_id", unique=True)
            logger.info("Ensured index on sites.site_id")
        except Exception:
            logger.exception("Could not create index on sites.site_id (may already exist or insufficient permissions)")
    except Exception as e:
        logger.exception("Failed to connect to MongoDB: %s", e)
        # re-raise to stop startup
        raise

    # Detect running on Vercel (serverless) where filesystem is ephemeral
    vercel_detected = bool(os.environ.get('VERCEL') or os.environ.get('VERCEL_URL') or os.environ.get('VERCEL_ENV') or os.environ.get('NOW_REGION'))
    if vercel_detected:
        logger.warning("Running on Vercel or similar serverless environment. Filesystem is ephemeral — uploaded files will not persist between invocations.")

    try:
        yield
    finally:
        # Clean shutdown
        client.close()

app = FastAPI(lifespan=lifespan)
api_router = APIRouter(prefix="/api")


@app.middleware("http")
async def ensure_mongo_client_middleware(request, call_next):
    """Middleware to make the Motor client resilient in serverless environments.

    Some serverless invocations reuse process state where an AsyncIOMotorClient
    may be bound to a previous/closed event loop. This middleware pings the
    client and on failure recreates the global `client` and `db` objects so
    handlers can continue to use the `db` variable defined at module level.
    """
    global client, db
    try:
        # quick ping; if it raises we'll recreate the client
        await client.admin.command("ping")
    except Exception as e:
        logger.warning("MongoDB ping failed in middleware (%s). Recreating client.", e)
        try:
            client.close()
        except Exception:
            pass
        # Recreate client bound to the current event loop
        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
        db = client[db_name]
    response = await call_next(request)
    return response

# Create uploads directory
VERCEL_DETECTED = bool(os.environ.get('VERCEL') or os.environ.get('VERCEL_URL') or os.environ.get('VERCEL_ENV') or os.environ.get('NOW_REGION'))

# Use ephemeral /tmp when running on Vercel (no persistent writable project dir there)
if VERCEL_DETECTED:
    UPLOADS_DIR = Path(os.environ.get('UPLOADS_DIR', tempfile.gettempdir())) / 'site_renamer_uploads'
else:
    UPLOADS_DIR = ROOT_DIR / 'uploads'

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Models
class ComponentNames(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    names: List[str]
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ComponentNamesUpdate(BaseModel):
    names: List[str]

class CategoryNames(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    categories: Dict[str, str] = {"alpha": "Alpha", "beta": "Beta", "gamma": "Gamma"}
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CategoryNamesUpdate(BaseModel):
    categories: Dict[str, str]

class NamingFormat(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    format: str = "{site_id}_{category}_{component_name}"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class NamingFormatUpdate(BaseModel):
    format: str

class UploadedImage(BaseModel):
    component_name: str
    filename: str
    uploaded_at: str

class SiteCategory(BaseModel):
    category: str
    images: List[UploadedImage]

class Site(BaseModel):
    model_config = ConfigDict(extra="ignore")
    site_id: str
    categories: List[SiteCategory] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Defaults
DEFAULT_COMPONENT_NAMES = [
    "A6 Grounding",
    "Azimuth",
    "Clutter",
    "CPRI Grounding",
    "CPRI Termination At A6",
    "CPRI Termination At CSS",
    "Grounding At OGB Tower",
    "Installation",
    "Labelling",
    "MCB Termination",
    "Roxtec",
    "Tilt",
    "Tower Photo"
]


def apply_naming_format(format_str: str, site_id: str, category: str, component_name: str) -> str:
    """Apply the naming format with the provided values"""
    # For filenames we want to preserve spaces inside component names (per UX request)
    # but keep site_id and category compact (replace spaces with underscores).
    safe_site_id = site_id.replace(' ', '_')
    safe_category = category.replace(' ', '_').replace('/', '_')
    # For component names: keep spaces but normalize slashes; other disallowed
    # characters will be replaced below while allowing spaces to remain.
    safe_component = component_name.replace('/', '_')

    result = format_str.replace('{site_id}', safe_site_id)
    result = result.replace('{category}', safe_category)
    result = result.replace('{component_name}', safe_component)
    # Replace any remaining disallowed characters with underscores, but allow spaces
    # so component names keep their spaces.
    result = re.sub(r'[^a-zA-Z0-9_\- ]', '_', result)
    return result


def _sanitize_filename(name: str) -> str:
    # Keep letters, numbers, dash, underscore and dot (for ext). Replace others with underscore
    name = os.path.basename(name)
    # Allow spaces in filenames so component names can retain spaces.
    # Replace other disallowed characters with underscore.
    name = re.sub(r'[^a-zA-Z0-9 ._-]', '_', name)
    # Prevent names starting with dot
    if name.startswith('.'):
        name = name.lstrip('.')
    return name or 'file'


@api_router.get("/")
async def root():
    return {"message": "Antenna Site Image Sorter API"}


@api_router.get("/component-names")
async def get_component_names():
    config = await db.component_names.find_one({}, {"_id": 0})
    if not config:
        config_obj = ComponentNames(names=DEFAULT_COMPONENT_NAMES)
        doc = config_obj.model_dump()
        doc['updated_at'] = doc['updated_at'].isoformat()
        await db.component_names.insert_one(doc)
        return {"names": DEFAULT_COMPONENT_NAMES}
    return {"names": config.get('names', DEFAULT_COMPONENT_NAMES)}


@api_router.put("/component-names")
async def update_component_names(input: ComponentNamesUpdate):
    if len(input.names) < 1:
        raise HTTPException(status_code=400, detail="Must provide at least 1 component name")
    config_obj = ComponentNames(names=input.names)
    doc = config_obj.model_dump()
    doc['updated_at'] = doc['updated_at'].isoformat()
    await db.component_names.delete_many({})
    await db.component_names.insert_one(doc)
    return {"names": input.names, "message": "Component names updated successfully"}


@api_router.get("/category-names")
async def get_category_names():
    config = await db.category_names.find_one({}, {"_id": 0})
    if not config:
        config_obj = CategoryNames()
        doc = config_obj.model_dump()
        doc['updated_at'] = doc['updated_at'].isoformat()
        await db.category_names.insert_one(doc)
        return {"categories": {"alpha": "Alpha", "beta": "Beta", "gamma": "Gamma"}}
    return {"categories": config.get('categories', {"alpha": "Alpha", "beta": "Beta", "gamma": "Gamma"})}


@api_router.put("/category-names")
async def update_category_names(input: CategoryNamesUpdate):
    config_obj = CategoryNames(categories=input.categories)
    doc = config_obj.model_dump()
    doc['updated_at'] = doc['updated_at'].isoformat()
    await db.category_names.delete_many({})
    await db.category_names.insert_one(doc)
    return {"categories": input.categories, "message": "Category names updated successfully"}


@api_router.get("/naming-format")
async def get_naming_format():
    config = await db.naming_format.find_one({}, {"_id": 0})
    if not config:
        config_obj = NamingFormat()
        doc = config_obj.model_dump()
        doc['updated_at'] = doc['updated_at'].isoformat()
        await db.naming_format.insert_one(doc)
        return {"format": "{site_id}_{category}_{component_name}"}
    return {"format": config.get('format', "{site_id}_{category}_{component_name}")}


@api_router.put("/naming-format")
async def update_naming_format(input: NamingFormatUpdate):
    if not any(placeholder in input.format for placeholder in ['{site_id}', '{category}', '{component_name}']):
        raise HTTPException(status_code=400, detail="Format must contain at least one placeholder: {site_id}, {category}, or {component_name}")
    config_obj = NamingFormat(format=input.format)
    doc = config_obj.model_dump()
    doc['updated_at'] = doc['updated_at'].isoformat()
    await db.naming_format.delete_many({})
    await db.naming_format.insert_one(doc)
    return {"format": input.format, "message": "Naming format updated successfully"}


@api_router.post("/sites/{site_id}/upload")
async def upload_image(
    site_id: str,
    category: str,
    component_name: str,
    file: UploadFile = File(...)
):
    if category.lower() not in ['alpha', 'beta', 'gamma']:
        raise HTTPException(status_code=400, detail="Category must be alpha, beta, or gamma")
    naming_config = await db.naming_format.find_one({}, {"_id": 0})
    format_str = naming_config.get('format', "{site_id}_{category}_{component_name}") if naming_config else "{site_id}_{category}_{component_name}"
    site_dir = UPLOADS_DIR / site_id / category.lower()
    site_dir.mkdir(parents=True, exist_ok=True)
    # sanitize incoming filename extension and generated name
    incoming_ext = Path(file.filename).suffix.lower()
    if incoming_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type not allowed: {incoming_ext}")
    # Determine the display label for the category (if configured) and use that in file names.
    # The storage layout continues to use the lowercase category key.
    category_config = await db.category_names.find_one({}, {"_id": 0})
    if category_config and isinstance(category_config.get('categories', {}), dict):
        display_category = category_config.get('categories', {}).get(category.lower(), category)
    else:
        display_category = category

    filename_without_ext = apply_naming_format(format_str, site_id, display_category, component_name)
    safe_filename_base = _sanitize_filename(filename_without_ext)
    new_filename = f"{safe_filename_base}{incoming_ext}"
    file_path = site_dir / new_filename

    # Stream the upload to disk and enforce max size to avoid memory and disk exhaustion
    total_written = 0
    CHUNK = 64 * 1024
    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            while True:
                chunk = await file.read(CHUNK)
                if not chunk:
                    break
                total_written += len(chunk)
                if total_written > MAX_UPLOAD_SIZE:
                    # cleanup partial file
                    await out_file.close()
                    try:
                        file_path.unlink()
                    except Exception:
                        pass
                    raise HTTPException(status_code=413, detail=f"File too large. Max {MAX_UPLOAD_SIZE} bytes")
                await out_file.write(chunk)
    finally:
        await file.close()
    site = await db.sites.find_one({"site_id": site_id}, {"_id": 0})
    uploaded_image = {
        "component_name": component_name,
        "filename": new_filename,
        "uploaded_at": datetime.now(timezone.utc).isoformat()
    }
    if not site:
        site_obj = Site(
            site_id=site_id,
            categories=[{
                "category": category.lower(),
                "images": [uploaded_image]
            }]
        )
        doc = site_obj.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        doc['updated_at'] = doc['updated_at'].isoformat()
        await db.sites.insert_one(doc)
    else:
        category_found = False
        for cat in site.get('categories', []):
            if cat.get('category') == category.lower():
                cat.setdefault('images', []).append(uploaded_image)
                category_found = True
                break
        if not category_found:
            site.setdefault('categories', []).append({
                "category": category.lower(),
                "images": [uploaded_image]
            })
        site['updated_at'] = datetime.now(timezone.utc).isoformat()
        await db.sites.update_one({"site_id": site_id}, {"$set": {"categories": site['categories'], "updated_at": site['updated_at']}})
    return {
        "message": "Image uploaded successfully",
        "filename": new_filename,
        "component_name": component_name
    }


@api_router.get("/sites/{site_id}/category/{category}")
async def get_category_images(site_id: str, category: str):
    site = await db.sites.find_one({"site_id": site_id}, {"_id": 0})
    if not site:
        return {"images": []}
    for cat in site.get('categories', []):
        if cat.get('category') == category.lower():
            return {"images": cat.get('images', [])}
    return {"images": []}


@api_router.get("/sites/{site_id}/download")
async def download_site_images(site_id: str):
    site_dir = UPLOADS_DIR / site_id
    if not site_dir.exists():
        raise HTTPException(status_code=404, detail="Site not found or no uploads")
    zip_path = UPLOADS_DIR / f"{site_id}.zip"
    # Overwrite if exists
    if zip_path.exists():
        zip_path.unlink()
    # Build the ZIP using the site's metadata so filenames in the archive reflect
    # the current naming format and display category names (even if stored files
    # on disk used older naming rules).
    naming_cfg = await db.naming_format.find_one({}, {"_id": 0})
    format_str = naming_cfg.get('format', "{site_id}_{category}_{component_name}") if naming_cfg else "{site_id}_{category}_{component_name}"
    site = await db.sites.find_one({"site_id": site_id}, {"_id": 0})
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if site:
            # Iterate categories and images from metadata so we can compute archive names
            for cat in site.get('categories', []):
                cat_key = cat.get('category')
                # Determine display category if configured
                category_config = await db.category_names.find_one({}, {"_id": 0})
                if category_config and isinstance(category_config.get('categories', {}), dict):
                    display_category = category_config.get('categories', {}).get(cat_key, cat_key)
                else:
                    display_category = cat_key

                for img in cat.get('images', []):
                    fname_on_disk = img.get('filename')
                    comp_name = img.get('component_name')
                    file_path = site_dir / cat_key / fname_on_disk
                    if not file_path.exists():
                        # skip missing files
                        continue
                        # Compute the desired archive filename using current naming format
                        expected_base = apply_naming_format(format_str, site_id, display_category, comp_name)
                        expected_safe = _sanitize_filename(expected_base) + Path(fname_on_disk).suffix
                        # Use the display category as the folder name inside the archive so
                        # edited category names (e.g., "-1") appear in the ZIP instead of the
                        # internal key (e.g., "alpha"). Sanitize the display label for folder
                        # naming (replace slashes and spaces with underscores).
                        safe_display_folder = str(display_category).replace('/', '_').replace(' ', '_')
                        arcname = Path(safe_display_folder) / expected_safe
                    zipf.write(file_path, arcname)
        else:
            # Fallback: include all files on disk in their current layout
            for root, _, files in os.walk(site_dir):
                for fname in files:
                    full = Path(root) / fname
                    arcname = full.relative_to(site_dir)
                    zipf.write(full, arcname)
    return FileResponse(
        path=zip_path,
        filename=f"{site_id}_images.zip",
        media_type='application/zip'
    )


@api_router.get("/health")
async def health_check():
    """Health endpoint for quick runtime checks.

    Returns DB connectivity status, presence of required env vars, and whether
    the runtime appears to be a serverless/ephemeral environment (Vercel).
    """
    db_ok = False
    db_error = None
    try:
        await client.admin.command("ping")
        db_ok = True
    except Exception as e:
        db_error = str(e)

    env_status = {
        'MONGO_URL': bool(os.environ.get('MONGO_URL')),
        'DB_NAME': bool(os.environ.get('DB_NAME'))
    }

    vercel_detected = bool(os.environ.get('VERCEL') or os.environ.get('VERCEL_URL') or os.environ.get('VERCEL_ENV') or os.environ.get('NOW_REGION'))

    payload = {
        'status': 'ok' if db_ok else 'error',
        'db_connected': db_ok,
        'db_error': db_error,
        'env': env_status,
        'ephemeral_filesystem': vercel_detected,
        'message': 'Running on Vercel - filesystem is ephemeral; uploads will be transient' if vercel_detected else 'running'
    }
    return payload


# Include router & static
app.include_router(api_router)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# Determine whether to allow credentials based on the provided origins. Browsers
# block Access-Control-Allow-Origin: * when credentials are allowed. If the
# configured origins are wildcard, we disable credentials to avoid invalid CORS
# responses. For stricter security, set CORS_ORIGINS to the exact frontend origin
# (e.g. https://site-renamer.vercel.app) in the environment.
allow_credentials_flag = True
if len(CORS_ORIGINS) == 1 and CORS_ORIGINS[0] == '*':
    allow_credentials_flag = False

logger.info("Configured CORS_ORIGINS=%s allow_credentials=%s", CORS_ORIGINS, allow_credentials_flag)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=allow_credentials_flag,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup/shutdown are handled by the `lifespan` context manager defined near app creation.