import urllib.request
import json
import zipfile
import os
import sys

api_url = "https://api.github.com/repos/joncampbell123/dosbox-x/releases/latest"

if not os.path.exists("dosbox"):
    print("Fetching release info...")
    try:
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read())
            
        download_url = None
        for asset in data.get("assets", []):
            if "win64" in asset["name"].lower() and asset["name"].endswith(".zip"):
                download_url = asset["browser_download_url"]
                break
        
        if not download_url:
            print("Could not find suitable Windows zip.")
            sys.exit(1)
            
        print(f"Downloading from {download_url}...")
        req = urllib.request.Request(download_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open("dosbox.zip", 'wb') as out_file:
            out_file.write(response.read())
            
        print("Extracting...")
        with zipfile.ZipFile("dosbox.zip", 'r') as zip_ref:
            zip_ref.extractall("dosbox")
        print("Extracted.")
    except Exception as e:
        print(f"Error: {e}")
else:
    print("DOSBox already exists.")
