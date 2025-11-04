from typing import Optional
import httpx
import asyncio
from pathlib import Path

from .config import settings

class DifyClient:
    def __init__(self):
        self.base_url = settings.DIFY_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {settings.DIFY_API_KEY}"
        }
    
    async def upload_file(self, file_path: Path, retries: int = 3) -> Optional[str]:
        """Upload a file to Dify dataset."""
        url = f"{self.base_url}/datasets/{settings.DIFY_DATASET_ID}/document/create-by-file"
        
        for attempt in range(retries):
            try:
                if attempt > 0:
                    print(f"[INFO] Retry {attempt + 1}/{retries}")
                async with httpx.AsyncClient() as client:
                    with open(file_path, "rb") as f:
                        files = {"file": (file_path.name, f, "application/octet-stream")}
                        response = await client.post(
                            url,
                            headers=self.headers,
                            files=files,
                            timeout=60.0  # Increased timeout for large files
                        )
                        
                        if response.status_code != 200:
                            if attempt == retries - 1:
                                print(f"[ERROR] Dify API error: {response.status_code} - {response.text}")
                                return None
                            continue
                            
                        result = response.json()
                        return result.get("id")
                        
            except Exception as e:
                if attempt == retries - 1:
                    print(f"[ERROR] Dify upload failed: {str(e)}")
                    return None
                await asyncio.sleep(2)  # Wait before retry
                continue
        return None
