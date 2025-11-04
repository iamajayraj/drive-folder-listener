from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .database import SessionLocal, NotificationChannel
from .google_drive import GoogleDriveService

scheduler = AsyncIOScheduler()

async def renew_channels():
    """Renew notification channels that are about to expire."""
    db = SessionLocal()
    drive_service = GoogleDriveService()
    
    try:
        # Find channels expiring in next 6 hours
        expiration_threshold = datetime.utcnow() + timedelta(hours=6)
        channels = db.query(NotificationChannel).filter(
            NotificationChannel.expiration <= expiration_threshold
        ).all()
        
        for channel in channels:
            try:
                # Stop existing watch
                await drive_service.stop_watch(channel.channel_id, channel.folder_id)
                
                # Setup new watch
                new_channel = await drive_service.setup_watch(channel.folder_id)
                
                # Update database
                channel.channel_id = new_channel['channel_id']
                channel.expiration = new_channel['expiration']
                db.commit()
                
                print(f"Renewed channel for folder {channel.folder_id}")
            except Exception as e:
                print(f"Error renewing channel {channel.channel_id}: {str(e)}")
                db.rollback()
    finally:
        db.close()

def start_scheduler():
    scheduler.add_job(renew_channels, 'interval', hours=12)
    scheduler.start()
