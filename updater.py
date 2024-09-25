import os
import shutil
import sys
import requests
from zipfile import ZipFile
import subprocess


def download_latest_version(download_url, download_path):
    response = requests.get(download_url, stream=True)
    response.raise_for_status()
    with open(download_path, 'wb') as out_file:
        shutil.copyfileobj(response.raw, out_file)


def extract_zip(zip_path, extract_to):
    with ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)


def main():
    owner = "MDMAinsley"
    repo = "get_crypto_fees"
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    zip_download_path = os.path.join(app_dir, "latest_version.zip")
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

    try:
        print("UPDATER: Fetching latest release info from GitHub...")
        response = requests.get(url)
        response.raise_for_status()
        latest_release = response.json()
        latest_version = latest_release['tag_name']

        # Find the zip asset to download
        zip_asset_name = f"v{latest_version}.zip"
        download_url = None

        for asset in latest_release['assets']:
            if asset['name'] == zip_asset_name:
                download_url = asset['browser_download_url']
                break

        if not download_url:
            raise Exception(f"UPDATER: No zip asset matching {zip_asset_name} found.")

        print(f"UPDATER: Downloading latest version {latest_version}...")
        download_latest_version(download_url, zip_download_path)
        print("UPDATER: Download complete.")

        print("UPDATER: Extracting new version files...")
        extract_zip(zip_download_path, app_dir)
        print("UPDATER: Extraction complete.")

        # Remove the zip file after extraction
        os.remove(zip_download_path)

        # Relaunch the updated launcher to handle updater replacement and app start
        print("UPDATER: Relaunching launcher to complete update...")
        launcher_path = os.path.join(app_dir, "GF_Launcher.exe")
        subprocess.run([launcher_path], check=True)

    except Exception as e:
        print(f"UPDATER: Error during update: {e}")


if __name__ == "__main__":
    main()
