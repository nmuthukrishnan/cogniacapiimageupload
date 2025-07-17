
# Camera Status Fetcher

This Python script fetches camera information from the Cogniac API, checks for media availability, and writes the results to an Excel file.

## Prerequisites

Before running the script, ensure you have the following:
- Python 3.x installed
- The following Python libraries installed:
  - `requests`
  - `pandas`
  - `openpyxl`

You can install the required libraries using the following:

```bash
pip install requests pandas openpyxl
```

## Configuration

1. **Cogniac API Credentials:**
   Replace the following placeholders in the script with your Cogniac credentials:
   - `Cogniac username`
   - `Cogniac password`

2. **API Base URL:**
   The API base URL is set to `"https://api.cogniac.io/1"`, which is the base URL for accessing the Cogniac API.

3. **Output File:**
   The script saves the camera data to an Excel file named `camera_status.xlsx`. If the file already exists, it will create a new file with a timestamp (e.g., `camera_status_2025-07-17_12-30-45.xlsx`).

## Script Steps

1. **Get Tenant ID:**
   The script fetches the tenant ID associated with the Cogniac account.

2. **Get Access Token:**
   An access token is retrieved from the Cogniac API using the tenant ID for authentication.

3. **Fetch Network Cameras:**
   The script retrieves the list of cameras associated with the account.

4. **Check Media:**
   For each camera, the script checks if there is footage available using the `subject_uid` of the camera.

5. **Build DataFrame:**
   The camera details (camera name, connection status, and footage availability) are stored in a pandas DataFrame.

6. **Save Data to Excel:**
   The camera data is saved to an Excel file using the `openpyxl` engine.

## Example Output

The Excel file will contain the following columns:
- **Cameras name:** The name or ID of the camera.
- **Connected to an app:** Whether the camera is connected (Yes/No).
- **Footage in Cogniac:** Whether there is media (footage) available for the camera (Yes/No/Unknown).

## Usage

Run the script as follows:

```bash
python camera_status.py
```

This will output an Excel file with the camera status information in the same directory.

## Cogniac Documentation

For more details on how to interact with the Cogniac API, refer to the official documentation: [Cogniac Documentation](https://support.cogniac.ai/docs)

