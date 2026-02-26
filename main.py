"""
Higgsfield Image Enhancement Pipeline
--------------------------------------
1. Downloads images from Google Drive
2. Enhances each image via Higgsfield browser automation
3. Saves enhanced images to output_images/
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def main():
    print("=" * 60)
    print("  Higgsfield Image Enhancement Pipeline")
    print("=" * 60)
    print()

    # Step 1: Download images from Google Drive
    print("STEP 1: Downloading images from Google Drive...")
    print("-" * 40)

    from download_gdrive import download_folder_images

    folder_id = os.getenv("GDRIVE_FOLDER_ID", "1eBUnPzjfHvyQTDldDhhYgGhlkCiKqomn")
    input_dir = os.getenv("INPUT_IMAGES_DIR", "input_images")

    # Check if images already downloaded
    input_path = Path(input_dir)
    supported_ext = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
    existing_images = [
        str(p)
        for p in sorted(input_path.rglob("*"))
        if p.is_file() and p.suffix.lower() in supported_ext
    ] if input_path.exists() else []

    if existing_images:
        print(f"Found {len(existing_images)} existing image(s) in '{input_dir}'")
        print("Skipping download. Delete the input_images/ folder to re-download.")
        image_paths = existing_images
    else:
        try:
            image_paths = download_folder_images(folder_id, input_dir)
        except Exception as e:
            print(f"ERROR downloading images: {e}")
            sys.exit(1)

    if not image_paths:
        print("No images to process. Exiting.")
        sys.exit(1)

    print(f"\nReady to process {len(image_paths)} image(s)")

    # Step 2: Enhance images via Higgsfield
    print("\nSTEP 2: Enhancing images via Higgsfield...")
    print("-" * 40)

    # Check credentials
    email = os.getenv("HIGGSFIELD_EMAIL")
    password = os.getenv("HIGGSFIELD_PASSWORD")

    if not email or not password:
        print("ERROR: Missing Higgsfield credentials!")
        print()
        print("Please do the following:")
        print("  1. Copy .env.example to .env:")
        print("       cp .env.example .env")
        print("  2. Edit .env and fill in:")
        print("       HIGGSFIELD_EMAIL=your_email@example.com")
        print("       HIGGSFIELD_PASSWORD=your_password")
        print()
        sys.exit(1)

    from higgsfield_automation import main as enhance_main

    results = enhance_main(image_paths)

    if not results:
        print("Enhancement failed.")
        sys.exit(1)

    # Final summary
    print("\n" + "=" * 60)
    print("  Pipeline Complete!")
    print("=" * 60)
    success = sum(1 for v in results.values() if v is not None)
    total = len(results)
    print(f"  Processed: {total} image(s)")
    print(f"  Enhanced:  {success} image(s)")
    print(f"  Failed:    {total - success} image(s)")
    output_dir = os.getenv("OUTPUT_IMAGES_DIR", "output_images")
    print(f"  Output:    {Path(output_dir).resolve()}/")
    print()


if __name__ == "__main__":
    main()
