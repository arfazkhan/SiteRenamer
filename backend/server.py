from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone
import shutil
import zipfile
import aiofiles
import re


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create uploads directory
UPLOADS_DIR = ROOT_DIR / 'uploads'
UPLOADS_DIR.mkdir(exist_ok=True)

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
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


# Default component names
DEFAULT_COMPONENT_NAMES = [
    "Antenna Front View",
    "Antenna Side View",
    "Antenna Top View",
    "Cable Routing",
    "Equipment Rack",
    "Power Connection",
    "Grounding System",
    "Site Overview",
    "Mounting Hardware",
    "Weather Proofing",
    "Signal Meter Reading",
    "Installation Label",
    "Safety Equipment"
]


def apply_naming_format(format_str: str, site_id: str, category: str, component_name: str) -> str:
    """Apply the naming format with the provided values"""
    # Sanitize component name
    safe_component = component_name.replace(' ', '_').replace('/', '_')
    
    # Replace placeholders
    result = format_str.replace('{site_id}', site_id)
    result = result.replace('{category}', category.lower())
    result = result.replace('{component_name}', safe_component)
    
    # Remove any remaining invalid characters
    result = re.sub(r'[^a-zA-Z0-9_-]', '_', result)
    
    return result


@api_router.get("/")
async def root():
    return {"message": "Antenna Site Image Sorter API"}


@api_router.get("/component-names")
async def get_component_names():
    """Get the current list of component names"""
    config = await db.component_names.find_one({}, {"_id": 0})
    if not config:
        # Initialize with defaults
        config_obj = ComponentNames(names=DEFAULT_COMPONENT_NAMES)
        doc = config_obj.model_dump()
        doc['updated_at'] = doc['updated_at'].isoformat()
        await db.component_names.insert_one(doc)
        return {"names": DEFAULT_COMPONENT_NAMES}
    return {"names": config.get('names', DEFAULT_COMPONENT_NAMES)}


@api_router.put("/component-names")
async def update_component_names(input: ComponentNamesUpdate):
    """Update the list of component names"""
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
    """Get the current category names"""
    config = await db.category_names.find_one({}, {"_id": 0})
    if not config:
        # Initialize with defaults
        config_obj = CategoryNames()
        doc = config_obj.model_dump()
        doc['updated_at'] = doc['updated_at'].isoformat()
        await db.category_names.insert_one(doc)
        return {"categories": {"alpha": "Alpha", "beta": "Beta", "gamma": "Gamma"}}
    return {"categories": config.get('categories', {"alpha": "Alpha", "beta": "Beta", "gamma": "Gamma"})}


@api_router.put("/category-names")
async def update_category_names(input: CategoryNamesUpdate):
    """Update the category names"""
    config_obj = CategoryNames(categories=input.categories)
    doc = config_obj.model_dump()
    doc['updated_at'] = doc['updated_at'].isoformat()
    
    await db.category_names.delete_many({})
    await db.category_names.insert_one(doc)
    return {"categories": input.categories, "message": "Category names updated successfully"}


@api_router.get("/naming-format")
async def get_naming_format():
    """Get the current naming format"""
    config = await db.naming_format.find_one({}, {"_id": 0})
    if not config:
        # Initialize with default
        config_obj = NamingFormat()
        doc = config_obj.model_dump()
        doc['updated_at'] = doc['updated_at'].isoformat()
        await db.naming_format.insert_one(doc)
        return {"format": "{site_id}_{category}_{component_name}"}
    return {"format": config.get('format', "{site_id}_{category}_{component_name}")}


@api_router.put("/naming-format")
async def update_naming_format(input: NamingFormatUpdate):
    """Update the naming format"""
    # Validate that format contains at least one placeholder
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
    """Upload an image for a specific site, category, and component"""
    if category.lower() not in ['alpha', 'beta', 'gamma']:
        raise HTTPException(status_code=400, detail="Category must be alpha, beta, or gamma")
    
    # Get naming format
    naming_config = await db.naming_format.find_one({}, {"_id": 0})
    format_str = naming_config.get('format', "{site_id}_{category}_{component_name}") if naming_config else "{site_id}_{category}_{component_name}"
    
    # Create directory structure
    site_dir = UPLOADS_DIR / site_id / category.lower()
    site_dir.mkdir(parents=True, exist_ok=True)
    
    # Get file extension
    ext = Path(file.filename).suffix
    
    # Apply naming format
    filename_without_ext = apply_naming_format(format_str, site_id, category, component_name)
    new_filename = f"{filename_without_ext}{ext}"
    
    file_path = site_dir / new_filename
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
    
    # Update database
    site = await db.sites.find_one({"site_id": site_id}, {"_id": 0})
    
    uploaded_image = {
        "component_name": component_name,
        "filename": new_filename,
        "uploaded_at": datetime.now(timezone.utc).isoformat()
    }
    
    if not site:
        # Create new site
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
        # Update existing site
        category_found = False
        for cat in site.get('categories', []):
            if cat['category'] == category.lower():
                # Remove old image for this component if exists
                old_images = [img for img in cat['images'] if img['component_name'] == component_name]
                if old_images:
                    # Delete old file
                    old_file_path = site_dir / old_images[0]['filename']
                    if old_file_path.exists():
                        old_file_path.unlink()
                
                cat['images'] = [img for img in cat['images'] if img['component_name'] != component_name]
                cat['images'].append(uploaded_image)
                category_found = True
                break
        
        if not category_found:
            if 'categories' not in site:
                site['categories'] = []
            site['categories'].append({
                "category": category.lower(),
                "images": [uploaded_image]
            })
        
        site['updated_at'] = datetime.now(timezone.utc).isoformat()
        await db.sites.update_one({"site_id": site_id}, {"$set": site})
    
    return {
        "message": "Image uploaded successfully",
        "filename": new_filename,
        "component_name": component_name
    }


@api_router.get("/sites/{site_id}/category/{category}")
async def get_category_images(site_id: str, category: str):
    """Get all uploaded images for a specific site and category"""
    site = await db.sites.find_one({"site_id": site_id}, {"_id": 0})
    
    if not site:
        return {"images": []}
    
    for cat in site.get('categories', []):
        if cat['category'] == category.lower():
            return {"images": cat['images']}
    
    return {"images": []}


@api_router.get("/sites/{site_id}/download")
async def download_site_images(site_id: str):
    """Download all images for a site as a ZIP file"""
    site_dir = UPLOADS_DIR / site_id
    
    if not site_dir.exists():
        raise HTTPException(status_code=404, detail="No images found for this site")
    
    # Create ZIP file
    zip_path = UPLOADS_DIR / f"{site_id}.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for category in ['alpha', 'beta', 'gamma']:
            category_dir = site_dir / category
            if category_dir.exists():
                for file_path in category_dir.iterdir():
                    if file_path.is_file():
                        arcname = f"{site_id}/{category}/{file_path.name}"
                        zipf.write(file_path, arcname=arcname)
    
    return FileResponse(
        path=zip_path,
        filename=f"{site_id}_images.zip",
        media_type='application/zip'
    )


# Include the router in the main app
app.include_router(api_router)

# Mount static files for serving uploaded images
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()