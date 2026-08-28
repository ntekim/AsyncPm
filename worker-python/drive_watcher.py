import os
import time
import io
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from dotenv import load_dotenv

load_dotenv()

# Configuration
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "anthronomic-386bc9b08b38_service_account.json")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
WORKER_URL = "https://asyncpm-worker-600733122592.us-central1.run.app"

SCOPES = ['https://www.googleapis.com/auth/drive']

async def get_drive_service():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"⚠️ [Drive Watcher] anthronomic-386bc9b08b38_service_account.json missing in worker-python! Place it at: {SERVICE_ACCOUNT_FILE}")
        return None
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

async def watch_drive_folder():
    service = await get_drive_service()
    if not service or not DRIVE_FOLDER_ID:
        print("⚠️ [Drive Watcher] Missing SERVICE_ACCOUNT_FILE or GOOGLE_DRIVE_FOLDER_ID in .env")
        return

    print(f"📁 [Google Drive Watcher] Active! Monitoring folder ID: '{DRIVE_FOLDER_ID}' for new transcripts...")
    processed_file_ids = set()

    while True:
        try:
            # Query non-trashed files inside target folder
            query = f"'{DRIVE_FOLDER_ID}' in parents and trashed = false"
            results = service.files().list(q=query, fields="files(id, name, mimeType)").execute()
            items = results.get('files', [])

            for item in items:
                file_id = item['id']
                file_name = item['name']
                mime_type = item['mimeType']

                if file_id in processed_file_ids:
                    continue

                print(f"\n📥 [Drive Watcher] Detected NEW File in Google Drive: '{file_name}' ({mime_type})")
                
                # Download File
                request = service.files().get_media(fileId=file_id)
                file_buffer = io.BytesIO()
                downloader = MediaIoBaseDownload(file_buffer, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                
                file_bytes = file_buffer.getvalue()

                # Dispatch to Audio or Text pipeline based on extension/mime
                if file_name.endswith(('.mp3', '.m4a', '.wav')) or 'audio' in mime_type:
                        files = {'file': (file_name, file_bytes, mime_type)}
                        print(f"  🚀 Forwarding audio to {WORKER_URL}/process-universal...")
                        res = await requests.post(f"{WORKER_URL}/process-universal?meeting_id=DRIVE-{file_name}", files=files)
                        
                elif file_name.endswith(('.txt', '.vtt', '.json')) or 'text' in mime_type or 'plain' in mime_type:
                    text_content = file_bytes.decode('utf-8', errors='ignore')
                    payload = {"meeting_id": f"DRIVE-{file_name}", "transcript": text_content, "source": "google_drive"}
                    print(f"  🚀 Forwarding transcript to {WORKER_URL}/process-universal...")
                    res = await requests.post(f"{WORKER_URL}/process-universal", json=payload)

                # Check if server replied with success or error text
                if res.status_code == 200:
                    try:
                        msg = res.json().get('message', 'Done')
                        print(f"  ✅ Success: {msg}")
                    except:
                        print(f"  ✅ Success (Non-JSON response): {res.text}")
                else:
                    print(f"  ❌ Worker returned Status {res.status_code}: {res.text}")

        except requests.exceptions.RequestException as req_err:
                print(f"  ❌ HTTP Request failed: {req_err}")

        time.sleep(5)  # Check every 5 seconds

if __name__ == "__main__":
    watch_drive_folder()