from fastapi import FastAPI, BackgroundTasks, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pathlib import Path
import shutil
from typing import Optional

from .config import settings
from .database import get_db, init_db, ProcessedFile, NotificationChannel
from .google_drive import GoogleDriveService
from .dify_client import DifyClient
from .scheduler import start_scheduler

from time import time

app = FastAPI(title="Drive Monitor API")
drive_service = GoogleDriveService()
dify_client = DifyClient()

# Track files being processed
processing_files = set()

# Debounce settings
LAST_CHECK_TIME = {}
DEBOUNCE_INTERVAL = 5  # seconds

@app.on_event("startup")
async def startup_event():
    # Create database tables
    init_db()
    
    # Create temp directory if it doesn't exist
    settings.TEMP_DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)
    
    # Start the scheduler
    start_scheduler()

@app.on_event("shutdown")
async def shutdown_event():
    # Clean up temp directory
    if settings.TEMP_DOWNLOAD_PATH.exists():
        shutil.rmtree(settings.TEMP_DOWNLOAD_PATH)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/setup")
async def setup_monitoring(
    folder_id: str,
    db: Session = Depends(get_db)
):
    try:
        print(f"Attempting to setup monitoring for folder: {folder_id}")
        
        # Verify drive service is initialized
        if not drive_service or not drive_service.service:
            raise Exception("Google Drive service not properly initialized")
            
        # Setup webhook notification
        channel = await drive_service.setup_watch(folder_id)
        print(f"Successfully created watch channel: {channel}")
        
        # Store channel info
        db_channel = NotificationChannel(
            channel_id=channel['channel_id'],
            folder_id=channel['folder_id'],
            expiration=channel['expiration']
        )
        db.add(db_channel)
        db.commit()
        
        return {"message": "Monitoring setup successfully", "channel": channel}
    except Exception as e:
        print(f"Error in setup_monitoring: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

import asyncio

async def process_file(
    file_id: str,
    file_name: str,
    db: Session
):
    """Background task to process a new file."""
    temp_path = settings.TEMP_DOWNLOAD_PATH / file_name
    
    try:
        # Check if file is already being processed
        if file_id in processing_files:
            print(f"[INFO] File {file_name} is already in process")
            return
            
        # Mark file as being processed
        processing_files.add(file_id)
            
        # Check if file was already processed
        existing = db.query(ProcessedFile).filter_by(file_id=file_id).first()
        if existing:
            return
        
        # Download file with delay
        print(f"[INFO] Processing {file_name}...")
        await asyncio.sleep(2)  # Wait 2 seconds before download
        success = await drive_service.download_file(file_id, str(temp_path))
        if not success:
            print(f"[ERROR] Failed to download: {file_name}")
            return
        
        # Upload to Dify
        document_id = await dify_client.upload_file(temp_path)
        if not document_id:
            print(f"[ERROR] Failed to upload to Dify: {file_name}")
            return
        
        # Mark as processed
        db_file = ProcessedFile(file_id=file_id, file_name=file_name)
        db.add(db_file)
        db.commit()
        
        print(f"Successfully processed file: {file_name}")
    except Exception as e:
        print(f"Error processing file {file_name}: {str(e)}")
        db.rollback()
    finally:
        # Remove from processing set
        try:
            processing_files.remove(file_id)
        except KeyError:
            # File was already removed by another process
            pass
        # Cleanup temp file
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception as e:
                print(f"[WARN] Failed to clean up {file_name}: {e}")

@app.post("/webhook")
async def drive_webhook(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_goog_channel_id: Optional[str] = Header(None),
    x_goog_resource_state: Optional[str] = Header(None)
):
    print(f"Received webhook notification - Channel: {x_goog_channel_id}, State: {x_goog_resource_state}")
    
    if not x_goog_channel_id or not x_goog_resource_state:
        print("Missing required headers in webhook request")
        raise HTTPException(status_code=400, detail="Missing required headers")
    
    # Handle sync notification immediately
    if x_goog_resource_state == "sync":
        return JSONResponse(status_code=200, content={"status": "sync acknowledged"})
        
    # Ignore trash state notifications
    if x_goog_resource_state == "trash":
        return JSONResponse(status_code=200, content={"status": "trash ignored"})
        
    try:
        # Get active channel with minimal query
        channel = db.query(NotificationChannel.folder_id)\
            .filter_by(channel_id=x_goog_channel_id)\
            .first()
            
        if not channel:
            return JSONResponse(status_code=200, content={"status": "ignored"})
            
    except Exception as e:
        print(f"[WARN] Database error: {str(e)}")
        # Return success to prevent Google from retrying
        return JSONResponse(status_code=200, content={"status": "error"})
    
    # Check debounce
    current_time = time()
    last_check = LAST_CHECK_TIME.get(channel.folder_id, 0)
    
    if current_time - last_check < DEBOUNCE_INTERVAL:
        return JSONResponse(
            status_code=200,
            content={"status": "debounced"}
        )
    
    LAST_CHECK_TIME[channel.folder_id] = current_time
    
    print(f"[INFO] Checking folder: {channel.folder_id} (Last check: {int(current_time - last_check)}s ago)")
    new_files = await drive_service.list_new_files(channel.folder_id)
    print(f"Found {len(new_files)} files in folder")
    
    # Filter out already processed files
    processed_ids = {f[0] for f in db.query(ProcessedFile.file_id).all()}
    new_files = [f for f in new_files if f['id'] not in processed_ids]
    print(f"Found {len(new_files)} new unprocessed files")
        
    try:
        # Process new files in background
        for file in new_files:
            background_tasks.add_task(
                process_file,
                file['id'],
                file['name'],
                db
            )
        
        return JSONResponse(
            status_code=200,
            content={"status": "processing", "files": len(new_files)}
        )
    except Exception as e:
        print(f"[ERROR] Failed to process files: {str(e)}")
        return JSONResponse(status_code=200, content={"status": "error"})