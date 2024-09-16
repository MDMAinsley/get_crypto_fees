import os
import shutil
import sys

import requests


def download_latest_version(download_url, download_path):
    response = requests.get(download_url, stream=True)
    response.raise_for_status()
    with open(download_path, 'wb') as out_file:
        shutil.copyfileobj(response.raw, out_file)


def main():
    owner = "MDMAinsley"
    repo = "feesnfees"
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    current_exe_path = os.path.join(app_dir, "GF_Data.exe")
    download_path = os.path.join(app_dir, "latest_version.exe")
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

    try:
        print("UPDATER: Fetching latest release info from GitHub...")
        response = requests.get(url)
        response.raise_for_status()
        latest_release = response.json()
        latest_version = latest_release['tag_name']

        # Find the correct asset by filtering by name
        target_asset_name = "GF_Data.exe"
        download_url = None

        for asset in latest_release['assets']:
            if target_asset_name in asset['name']:
                download_url = asset['browser_download_url']
                break

        if not download_url:
            raise Exception(f"UPDATER: No asset matching {target_asset_name} found in the latest release.")

        print(f"UPDATER: Downloading latest version {latest_version}...")
        download_latest_version(download_url, download_path)
        print("UPDATER: Download complete.")

        print("UPDATER: Replacing old version with the new version...")
        os.remove(current_exe_path)
        shutil.move(download_path, current_exe_path)
        print("UPDATER: Update complete.")

        os.startfile(current_exe_path)
        print("UPDATER: Application restarted.")

    except Exception as e:
        print(f"UPDATER: Error during update: {e}")


if __name__ == "__main__":
    main()
