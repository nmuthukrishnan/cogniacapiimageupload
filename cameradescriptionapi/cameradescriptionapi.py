import requests
import pandas as pd
import os
from datetime import datetime
import re

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

# === STEP 4: Function to Extract Fields from Description ===
def extract_fields(description):
    # If description is None, return "Not Available" for all fields
    if not description:
        return {
            "Use case": "Not Available",
            "Manufacturer": "Not Available",
            "Model": "Not Available",
            "Kitchen": "Not Available",
            "Line": "Not Available"
        }

    # Define regex patterns for extracting the fields from the description
    fields = {
        "Use case": r"Use case:\s*(.*?)\n",
        "Manufacturer": r"Manufacturer:\s*(.*?)\n",
        "Model": r"Model:\s*(.*?)\n",
        "Kitchen": r"Kitchen:\s*(.*?)\n",
        "Line": r"Line:\s*(.*?)(?:\n|$)"  # Match Line, even if it does not end with newline
    }

    # Extract the fields based on the regex patterns
    extracted_data = {}
    for field, pattern in fields.items():
        match = re.search(pattern, description)
        extracted_data[field] = match.group(1) if match else "Not Available"

    return extracted_data

# === STEP 5: Extract Camera Details and Format Description ===
camera_data = []
for cam in cameras:
    name = cam.get("camera_name", cam.get("network_camera_id"))
    description = cam.get("description", None)  # Extract description (can be None)

    # Extract the structured fields from the description
    fields = extract_fields(description)

    # Append the camera name and the extracted fields to the data list
    camera_data.append({
        "Camera Name": name,
        **fields  # Unpack the extracted fields into the dictionary
    })

# === STEP 6: Build DataFrame ===
df = pd.DataFrame(camera_data)

# === Write to Excel ===
print(f"📁 Writing data to file: {EXCEL_FILE}")
with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
    df.to_excel(writer, index=False, sheet_name="Cameras")

print("✅ Done! Data saved to Excel.")
