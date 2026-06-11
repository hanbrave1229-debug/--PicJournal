from fastapi import APIRouter

from app.api.v1 import scan, photos, duplicates, thumbnails, scoring, dashboard, persons, albums, trash, config, diary

router = APIRouter()

router.include_router(scan.router,       prefix="/scan",       tags=["scan"])
router.include_router(photos.router,     prefix="/photos",     tags=["photos"])
router.include_router(duplicates.router, prefix="/duplicates", tags=["duplicates"])
router.include_router(thumbnails.router, prefix="/thumbnails", tags=["thumbnails"])
router.include_router(scoring.router,    prefix="/scoring",    tags=["scoring"])
router.include_router(dashboard.router,  prefix="/dashboard",  tags=["dashboard"])
router.include_router(persons.router,    prefix="/persons",    tags=["persons"])
router.include_router(albums.router,     prefix="/albums",     tags=["albums"])
router.include_router(trash.router,      prefix="/trash",      tags=["trash"])
router.include_router(config.router,     prefix="/config",     tags=["config"])
router.include_router(diary.router,      prefix="/diaries",    tags=["diaries"])
