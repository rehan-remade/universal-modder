import urllib.request
import zipfile
import os
import sys

url = "https://github.com/joncampbell123/dosbox-x/releases/download/dosbox-x-v2024.03.01/dosbox-x-mingw-win64-20240301.zip"
zip_path = "dosbox.zip"

if not os.path.exists("dosbox"):
    print("Downloading DOSBox-X...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
            out_file.write(response.read())
    except Exception as e:
        print(f"Failed to download DOSBox: {e}")
        sys.exit(1)
        
    print("Extracting...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall("dosbox")
    print("Extracted.")
else:
    print("DOSBox already exists.")
