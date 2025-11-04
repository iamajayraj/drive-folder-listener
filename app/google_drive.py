from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.auth.transport.requests import Request

from .config import settings

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

class GoogleDriveService:
    def __init__(self):
        try:
            if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
                # Use JSON content from environment variable
                import json
                from io import StringIO
                service_account_info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
                credentials = service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=SCOPES
                )
            else:
                # Fallback to file
                print(f"Initializing Google Drive service with credentials from file: {settings.GOOGLE_SERVICE_ACCOUNT_FILE}")
                credentials = service_account.Credentials.from_service_account_file(
                    str(settings.GOOGLE_SERVICE_ACCOUNT_FILE),
                    scopes=SCOPES
                )
            self.service = build('drive', 'v3', credentials=credentials)
            print("Successfully initialized Google Drive service")
        except Exception as e:
            print(f"Error initializing Google Drive service: {str(e)}")
            raise
    
    async def setup_watch(self, folder_id: str) -> Dict[str, Any]:
        """Setup webhook notification for a folder."""
        try:
            print(f"Setting up watch for folder: {folder_id}")
            
            # First verify folder exists and is accessible
            try:
                self.service.files().get(fileId=folder_id).execute()
                print(f"Successfully verified folder access: {folder_id}")
            except Exception as e:
                raise Exception(f"Cannot access folder. Make sure the folder exists and is shared with the service account. Error: {str(e)}")
            
            channel_id = f"channel_{folder_id}_{int(datetime.utcnow().timestamp())}"
            expiration = int((datetime.utcnow() + timedelta(days=7)).timestamp() * 1000)
            
            body = {
                'id': channel_id,
                'type': 'web_hook',
                'address': settings.WEBHOOK_URL,
                'expiration': expiration
            }
            
            print(f"Sending watch request with body: {body}")
            response = self.service.files().watch(
                fileId=folder_id,
                body=body
            ).execute()
            print(f"Watch response: {response}")
            
            return {
                'channel_id': response['id'],
                'folder_id': folder_id,
                'expiration': datetime.fromtimestamp(int(response['expiration']) / 1000)
            }
        except Exception as e:
            print(f"Error in setup_watch: {str(e)}")
            raise
    
    async def list_new_files(self, folder_id: str, time_window: int = 300) -> List[Dict[str, Any]]:
        """List files created in the last time_window seconds."""
        query_time = (datetime.utcnow() - timedelta(seconds=time_window)).isoformat('T') + 'Z'
        
        query = f"'{folder_id}' in parents and createdTime > '{query_time}'"
        
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, createdTime, mimeType)',
            includeItemsFromAllDrives=True,
            supportsAllDrives=True
        ).execute()
        
        return results.get('files', [])
    
    async def download_file(self, file_id: str, destination_path: str) -> bool:
        """Download a file from Drive to local storage."""
        try:
            request = self.service.files().get_media(fileId=file_id)
            with open(destination_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            return True
        except Exception as e:
            print(f"Error downloading file {file_id}: {str(e)}")
            return False
    
    async def stop_watch(self, channel_id: str, resource_id: str) -> bool:
        """Stop watching a folder."""
        try:
            body = {
                'id': channel_id,
                'resourceId': resource_id
            }
            self.service.channels().stop(body=body).execute()
            return True
        except Exception as e:
            print(f"Error stopping watch: {str(e)}")
            return False
