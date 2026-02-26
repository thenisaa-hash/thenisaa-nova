"""
Google Drive Image Downloader
Downloads all images from a shared Google Drive folder.
"""

import os
import sys
import gdown
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


def download_folder_images(folder_id: str, output_dir: str) -> list[str]:
    """
    Download all images from a Google Drive folder.

    Args:
        folder_id: The Google Drive folder ID
        output_dir: Local directory to save images

    Returns:
        List of paths to downloaded images
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Downloading images from Google Drive folder: {folder_id}")
    print(f"Saving to: {output_path.resolve()}")

    folder_url = f"https://drive.google.com/drive/folders/{folder_id}"

    try:
        gdown.download_folder(
            url=folder_url,
            output=str(output_path),
            quiet=False,
            use_cookies=False,
        )
    except Exception as e:
        print(f"Error downloading folder: {e}")
        print("Trying alternative download method...")
        try:
            gdown.download_folder(
                id=folder_id,
                output=str(output_path),
                quiet=False,
            )
        except Exception as e2:
            print(f"Alternative download also failed: {e2}")
            raise

    # Collect all downloaded image files
    downloaded_images = []
    for file_path in output_path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            downloaded_images.append(str(file_path))

    downloaded_images.sort()
    print(f"\nFound {len(downloaded_images)} image(s):")
    for img in downloaded_images:
        print(f"  - {img}")

    return downloaded_images


def main():
    folder_id = os.getenv("GDRIVE_FOLDER_ID", "1eBUnPzjfHvyQTDldDhhYgGhlkCiKqomn")
    output_dir = os.getenv("INPUT_IMAGES_DIR", "input_images")

    if len(sys.argv) > 1:
        folder_id = sys.argv[1]
    if len(sys.argv) > 2:
        output_dir = sys.argv[2]

    images = download_folder_images(folder_id, output_dir)

    if not images:
        print("\nNo images found in the folder.")
        sys.exit(1)

    print(f"\nSuccessfully downloaded {len(images)} image(s).")
    return images


if __name__ == "__main__":
    main()
