import requests
import pandas as pd
import os
from datetime import datetime

# === CONFIGURATION ===
username = "Cogniac username"  # 🔁 Replace with your Cogniac username
password = "Cogniac password"  # 🔁 Replace with your Cogniac password
API_BASE = "https://api.cogniac.io/1"

# === TIMESTAMP FOR FILE ===
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
base_file = "camera_status.xlsx"
if os.path.exists(base_file):
    EXCEL_FILE = f"camera_status_{timestamp}.xlsx"
else:
    EXCEL_FILE = base_file

# === STEP 1: Get Tenant ID ===
print("🔐 Getting tenant ID...")
tenants_resp = requests.get(f"{API_BASE}/users/current/tenants", auth=(username, password))
tenants_resp.raise_for_status()
tenant_id = tenants_resp.json()['tenants'][0]['tenant_id']

# === STEP 2: Get Access Token ===
print("🔑 Getting access token...")
token_resp = requests.get(f"{API_BASE}/token", params={"tenant_id": tenant_id}, auth=(username, password))
token_resp.raise_for_status()
access_token = token_resp.json()['access_token']
headers = {"Authorization": f"Bearer {access_token}"}

# === STEP 3: Fetch Network Cameras ===
print("📡 Fetching all network cameras...")
camera_resp = requests.get(f"{API_BASE}/tenants/current/networkCameras", headers=headers)
camera_resp.raise_for_status()
cameras = camera_resp.json().get("data", camera_resp.json())

# === STEP 4: Function to Check Media ===
def has_media(subject_uid, headers):
    media_url = f"{API_BASE}/media/search"
    payload = {
        "subject_uid": subject_uid,
        "size": 1
    }
    response = requests.post(media_url, headers=headers, json=payload)
    if response.status_code == 200:
        media = response.json().get("media", [])
        return "Yes" if media else "No"
    else:
        return "Unknown"

# === STEP 5: Build DataFrame ===
camera_data = []
for cam in cameras:
    name = cam.get("camera_name", cam.get("network_camera_id"))
    connected = "Yes" if cam.get("active") else "No"
    subject_uid = cam.get("subject_uid")
    footage = has_media(subject_uid, headers) if subject_uid else "Unknown"

    camera_data.append({
        "Cameras name": name,
        "Connected to an app": connected,
        "Footage in Cogniac": footage
    })

df = pd.DataFrame(camera_data)

# === Write to Excel ===
print(f"📁 Writing data to file: {EXCEL_FILE}")
with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
    df.to_excel(writer, index=False, sheet_name="Cameras")

print("✅ Done! Data saved to Excel.")
