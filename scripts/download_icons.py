import json
import os
import shutil
import ssl
import urllib.request
import zipfile

# Target directory for icons
ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons")


def download_lucide_icons():
    print(f"Preparing to download Lucide icons to {ICONS_DIR}...")

    # 1. Clear existing icons (optional, but good for a clean slate)
    if os.path.exists(ICONS_DIR):
        print("Cleaning up existing icons...")
        shutil.rmtree(ICONS_DIR)
    os.makedirs(ICONS_DIR)

    # 2. Find latest release URL
    print("Fetching latest release info from GitHub...")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/lucide-icons/lucide/releases/latest",
            headers={"User-Agent": "PieMenu-Installer"},
        )
        with urllib.request.urlopen(req, context=ctx) as response:  # noqa: S310
            data = json.loads(response.read().decode())
            zip_url = data["zipball_url"]
            tag_name = data["tag_name"]
            print(f"Latest version: {tag_name}")

    except Exception as e:
        print(f"Failed to fetch release info: {e}")
        return

    # 3. Download Zip
    zip_path = os.path.join(ICONS_DIR, "lucide.zip")
    print(f"Downloading {zip_url}...")
    try:
        with (
            urllib.request.urlopen(zip_url, context=ctx) as response,  # noqa: S310
            open(zip_path, "wb") as out_file,
        ):
            shutil.copyfileobj(response, out_file)
    except Exception as e:
        print(f"Download failed: {e}")
        return

    # 4. Extract SVGs
    print("Extracting icons...")
    count = 0
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # zip structure is usually lucide-icons-lucide-HASH/icons/*.svg
            for member in zip_ref.namelist():
                if member.endswith(".svg") and "/icons/" in member and "lucide" in member:
                    filename = os.path.basename(member)
                    if not filename:
                        continue

                    target_path = os.path.join(ICONS_DIR, filename)

                    # Read, replace color, and write
                    with zip_ref.open(member) as source:
                        content = source.read().decode("utf-8")

                    # Replace currentColor with white
                    content = content.replace('stroke="currentColor"', 'stroke="#FFFFFF"')

                    with open(target_path, "w", encoding="utf-8") as target:
                        target.write(content)

                    count += 1
    except Exception as e:
        print(f"Extraction failed: {e}")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

    print(f"Successfully downloaded and extracted {count} icons.")


if __name__ == "__main__":
    download_lucide_icons()
