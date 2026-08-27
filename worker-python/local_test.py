import requests

url = "http://localhost:8000/process-universal"
payload = {
    "meeting_id": "LOCAL-TEST-00190",
    "transcript": "Alice (PM): Quick standup. Bob, we need a critical security patch for the payment gateway immediately. Priority is High. Charlie, please update the footer alignment, low priority. Deadline for the release is this Friday."
}

print("🚀 Sending test transcript to local FastAPI server...")
response = requests.post(url, json=payload)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")