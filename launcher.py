import os
import subprocess
import sys
import requests


# Function to get the latest version tag from GitHub API
def get_latest_version(latest_version_url):
    response = requests.get(latest_version_url)
    response.raise_for_status()
    latest_release = response.json()
    return latest_release['tag_name'].strip()  # Trim any extra spaces


# Function to get the current version of the app by running it with '--version'
def get_current_version(app_exe_path):
    result = subprocess.run([app_exe_path, "--version"], capture_output=True, text=True)
    return result.stdout.strip()  # Trim spaces or newline characters


# Function to check if an update is available
def check_for_update(current_version, latest_version_url):
    latest_version = get_latest_version(latest_version_url)

    # Normalize both versions by stripping any "v" prefix
    current_version_normalized = current_version.lstrip("v")  # Remove "v" if it exists
    latest_version_normalized = latest_version.lstrip("v")

    return latest_version_normalized != current_version_normalized  # Compare normalized versions


def main():
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    app_exe_path = os.path.join(app_dir, "GF_Data.exe")
    current_version = get_current_version(app_exe_path)  # Get the current app version
    owner = "MDMAinsley"
    repo = "feesnfees"
    latest_version_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    updater_path = os.path.join(app_dir, "GF_Updater.exe")

    try:
        # Check for update and run updater if needed
        if check_for_update(current_version, latest_version_url):
            print("LAUNCHER: Update available. Running updater...")
            subprocess.run([updater_path], check=True)
        else:
            print("LAUNCHER: No update available. Starting application...")
            subprocess.run([app_exe_path], check=True)

    except Exception as e:
        print(f"LAUNCHER: Error: {e}")


if __name__ == "__main__":
    main()
