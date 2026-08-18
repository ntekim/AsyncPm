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
WORKER_URL = "http://localhost:8000"

SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"⚠️ [Drive Watcher] anthronomic-386bc9b08b38_service_account.json missing in worker-python! Place it at: {SERVICE_ACCOUNT_FILE}")
        return None
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def watch_drive_folder():
    service = get_drive_service()
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
                    res = requests.post(f"{WORKER_URL}/process-audio?meeting_id=DRIVE-{file_name}", files=files)
                    print(f"  ✅ Sent audio file to AsyncPM worker: {res.json().get('message')}")

                elif file_name.endswith(('.txt', '.vtt', '.json')) or 'text' in mime_type or 'plain' in mime_type:
                    text_content = file_bytes.decode('utf-8', errors='ignore')
                    payload = {"meeting_id": f"DRIVE-{file_name}", "transcript": text_content, "source": "google_drive"}
                    res = requests.post(f"{WORKER_URL}/process-transcript", json=payload)
                    print(f"  ✅ Sent text transcript to AsyncPM worker: {res.json().get('message')}")

                # Mark as processed
                processed_file_ids.add(file_id)

        except Exception as e:
            print(f"❌ [Drive Watcher Error] {str(e)}")

        time.sleep(5)  # Check every 5 seconds

if __name__ == "__main__":
    watch_drive_folder()