#!/usr/bin/env python3
"""
Migration helper: rename uploaded image files so component name spaces are preserved
in filenames (matching the current naming rules).

Run from the repository root (or backend/) after verifying you have a backup of uploads/.

Example:
  python backend/migrate_fix_component_spaces.py

This script will:
 - Connect to MongoDB using MONGO_URL from backend/.env
 - Iterate all documents in `sites` collection
 - For each image entry compute the expected filename using the current naming format
 - If the expected filename differs from the stored filename, attempt to rename the file on disk
   and update the document in MongoDB. If a target filename exists, the script will append
   a numeric suffix to avoid overwriting.

Make a backup before running on production data.
"""
import os
import re
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime

ROOT = Path(__file__).parent
load_dotenv(ROOT / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'site_renamer')
UPLOADS_DIR = ROOT / 'uploads'

if not MONGO_URL:
    print('MONGO_URL not set in backend/.env - aborting')
    sys.exit(1)


def apply_naming_format(format_str: str, site_id: str, category: str, component_name: str) -> str:
    safe_site_id = site_id.replace(' ', '_')
    safe_category = category.replace(' ', '_').replace('/', '_')
    safe_component = component_name.replace('/', '_')
    result = format_str.replace('{site_id}', safe_site_id)
    result = result.replace('{category}', safe_category)
    result = result.replace('{component_name}', safe_component)
    result = re.sub(r'[^a-zA-Z0-9_\- ]', '_', result)
    return result


def _sanitize_filename(name: str) -> str:
    name = os.path.basename(name)
    name = re.sub(r'[^a-zA-Z0-9 ._-]', '_', name)
    if name.startswith('.'):
        name = name.lstrip('.')
    return name or 'file'


def unique_target(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    i = 1
    while True:
        candidate = path.with_name(f"{stem}_{i}{suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def main():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    sites = list(db.sites.find({}))
    naming_cfg = db.naming_format.find_one({}, {"_id": 0})
    format_str = naming_cfg.get('format') if naming_cfg else '{site_id}_{category}_{component_name}'

    total = 0
    renamed = 0
    for site in sites:
        site_id = site.get('site_id')
        for cat in site.get('categories', []):
            cat_key = cat.get('category')
            # Fetch display category name if available
            cat_doc = db.category_names.find_one({}, {"_id": 0})
            if cat_doc and isinstance(cat_doc.get('categories', {}), dict):
                display_category = cat_doc.get('categories', {}).get(cat_key, cat_key)
            else:
                display_category = cat_key

            for img in cat.get('images', []):
                total += 1
                comp_name = img.get('component_name')
                existing_fname = img.get('filename')
                existing_path = UPLOADS_DIR / site_id / cat_key / existing_fname
                if not existing_path.exists():
                    print(f"Missing file: {existing_path}")
                    continue

                ext = Path(existing_fname).suffix
                expected_base = apply_naming_format(format_str, site_id, display_category, comp_name)
                expected_safe = _sanitize_filename(expected_base) + ext
                if expected_safe == existing_fname:
                    continue

                target_path = UPLOADS_DIR / site_id / cat_key / expected_safe
                target_path = unique_target(target_path)
                try:
                    existing_path.rename(target_path)
                    # Update the document in MongoDB for this filename
                    db.sites.update_one(
                        {"site_id": site_id, "categories.category": cat_key, "categories.images.filename": existing_fname},
                        {"$set": {"categories.$[c].images.$[i].filename": target_path.name}},
                        array_filters=[{"c.category": cat_key}, {"i.filename": existing_fname}]
                    )
                    renamed += 1
                    print(f"Renamed {existing_fname} -> {target_path.name}")
                except Exception as e:
                    print(f"Failed to rename {existing_path} -> {target_path}: {e}")

    print(f"Processed {total} images, renamed {renamed} files")


if __name__ == '__main__':
    main()
