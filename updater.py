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
    current_exe_path = os.path.join(app_dir, "Get_Fees.exe")
    download_path = os.path.join(app_dir, "latest_version.exe")
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

    try:
        print("Fetching latest release info from GitHub...")
        response = requests.get(url)
        response.raise_for_status()
        latest_release = response.json()
        latest_version = latest_release['tag_name']
        if latest_release['assets']:
            download_url = latest_release['assets'][0]['browser_download_url']
        else:
            raise Exception("No assets found in the latest release")

        print(f"Downloading latest version {latest_version}...")
        download_latest_version(download_url, download_path)
        print("Download complete.")

        print("Replacing old version with the new version...")
        os.remove(current_exe_path)
        shutil.move(download_path, current_exe_path)
        print("Update complete.")

        os.startfile(current_exe_path)
        print("Application restarted.")

    except Exception as e:
        print(f"Error during update: {e}")


if __name__ == "__main__":
    main()
