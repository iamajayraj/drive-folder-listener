# Google Drive Monitor API

A FastAPI application that monitors a Google Drive folder for new files and automatically uploads them to Dify AI.

## Features

- Monitor specific Google Drive folders (including subfolders) for new files
- Automatically download new files and upload them to Dify AI
- Use Google Drive Push Notifications (webhooks) for real-time updates
- Track processed files to prevent duplicates
- Automatic renewal of notification channels

## Setup

1. Create a Google Cloud Project and enable the Drive API
2. Create a Service Account and download the JSON key file
3. Share the target Drive folder with the service account email

### Environment Variables

Create a `.env` file in the root directory:

```env
# Google Drive
GOOGLE_SERVICE_ACCOUNT_FILE=path/to/service-account.json

# Dify
DIFY_API_KEY=your_api_key
DIFY_DATASET_ID=your_dataset_id

# App
WEBHOOK_URL=https://your-domain.com/webhook
DATABASE_URL=sqlite:///./app.db
TEMP_DOWNLOAD_PATH=./temp
```

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Running Locally

1. Start ngrok:
```bash
ngrok http 8000
```

2. Update WEBHOOK_URL in .env with your ngrok URL

3. Start the server:
```bash
uvicorn app.main:app --reload
```

## API Endpoints

### POST /setup
Start monitoring a folder
```json
{
    "folder_id": "your_folder_id"
}
```

### POST /webhook
Receive Google Drive notifications (called by Google)

### GET /health
Health check endpoint

## Architecture

- FastAPI for the web framework
- SQLite for storing processed files and channel info
- APScheduler for channel renewal
- Background tasks for file processing
- Async/await for better performance

## Error Handling

- Basic error handling and logging
- Retry mechanism for Dify uploads
- Automatic cleanup of temporary files
- Database transaction management

## Development

The project uses:
- Type hints for better code quality
- Async/await for non-blocking operations
- SQLAlchemy for database operations
- Pydantic for settings management
