"""
Higgsfield Image Generation Script

Generates images using the Higgsfield AI API (higgsfield-client SDK).

Usage:
    python generate_images.py --prompt "A serene lake at sunset"
    python generate_images.py --prompt "A futuristic city" --resolution 2K --aspect-ratio 16:9
    python generate_images.py  # Interactive mode

Environment variables:
    HF_KEY  - Your Higgsfield API key (required)
"""

import argparse
import os
import sys
import urllib.request
from pathlib import Path
from datetime import datetime

try:
    import higgsfield_client
except ImportError:
    print("Error: higgsfield-client is not installed.")
    print("Run: pip install higgsfield-client")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional


IMAGE_MODEL = "bytedance/seedream/v4/text-to-image"

VALID_RESOLUTIONS = ["1K", "2K", "4K"]
VALID_ASPECT_RATIOS = ["1:1", "4:3", "3:4", "16:9", "9:16", "21:9"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate images using the Higgsfield AI API"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        help="Text prompt describing the image to generate",
    )
    parser.add_argument(
        "--resolution",
        type=str,
        default="2K",
        choices=VALID_RESOLUTIONS,
        help="Output image resolution (default: 2K)",
    )
    parser.add_argument(
        "--aspect-ratio",
        type=str,
        default="16:9",
        choices=VALID_ASPECT_RATIOS,
        help="Aspect ratio of the output image (default: 16:9)",
    )
    parser.add_argument(
        "--camera-fixed",
        action="store_true",
        default=False,
        help="Fix the camera position (default: False)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory to save generated images (default: output/)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        default=False,
        help="Print the image URL only; do not download and save the file",
    )
    return parser.parse_args()


def generate_image(prompt: str, resolution: str, aspect_ratio: str, camera_fixed: bool) -> dict:
    """Submit an image generation request and return the result."""
    print(f"Generating image for prompt: \"{prompt}\"")
    print(f"  Resolution: {resolution} | Aspect ratio: {aspect_ratio} | Camera fixed: {camera_fixed}")

    request_controller = higgsfield_client.submit(
        IMAGE_MODEL,
        arguments={
            "prompt": prompt,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "camera_fixed": camera_fixed,
        },
    )

    for status in request_controller.poll_request_status():
        if isinstance(status, higgsfield_client.Queued):
            print("  Status: Queued...")
        elif isinstance(status, higgsfield_client.InProgress):
            print("  Status: In progress...")
        elif isinstance(status, higgsfield_client.Completed):
            print("  Status: Completed.")
        elif isinstance(status, higgsfield_client.Failed):
            raise RuntimeError("Image generation failed.")
        elif isinstance(status, higgsfield_client.NSFW):
            raise ValueError("Request rejected: NSFW content detected.")
        elif isinstance(status, higgsfield_client.Cancelled):
            raise RuntimeError("Request was cancelled.")

    return request_controller.get()


def save_image(image_url: str, output_dir: str, prompt: str) -> Path:
    """Download an image from a URL and save it to output_dir."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_prompt = "".join(c if c.isalnum() or c in " _-" else "" for c in prompt)[:50].strip().replace(" ", "_")
    filename = f"{timestamp}_{safe_prompt}.png"
    file_path = output_path / filename

    print(f"  Downloading image to: {file_path}")
    urllib.request.urlretrieve(image_url, file_path)
    return file_path


def main():
    args = parse_args()

    if not os.environ.get("HF_KEY") and not (os.environ.get("HF_API_KEY") and os.environ.get("HF_API_SECRET")):
        print("Error: Higgsfield API credentials not found.")
        print("Set HF_KEY environment variable with your Higgsfield API key.")
        print("  export HF_KEY=your_api_key")
        print("Or create a .env file with HF_KEY=your_api_key")
        sys.exit(1)

    prompt = args.prompt
    if not prompt:
        print("No prompt provided. Enter your image description below.")
        print("(Press Ctrl+C to exit)")
        try:
            prompt = input("Prompt: ").strip()
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(0)

    if not prompt:
        print("Error: Prompt cannot be empty.")
        sys.exit(1)

    try:
        result = generate_image(
            prompt=prompt,
            resolution=args.resolution,
            aspect_ratio=args.aspect_ratio,
            camera_fixed=args.camera_fixed,
        )
    except higgsfield_client.HiggsfieldClientError as exc:
        print(f"Error: Higgsfield API error: {exc}")
        sys.exit(1)
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    images = result.get("images", [])
    if not images:
        print("Error: No images returned by the API.")
        sys.exit(1)

    for idx, image in enumerate(images, start=1):
        image_url = image.get("url")
        if not image_url:
            print(f"  Image {idx}: No URL in response, skipping.")
            continue

        print(f"  Image {idx} URL: {image_url}")

        if not args.no_save:
            try:
                saved_path = save_image(image_url, args.output_dir, prompt)
                print(f"  Saved to: {saved_path}")
            except Exception as exc:
                print(f"  Warning: Could not save image: {exc}")

    print("Done.")


if __name__ == "__main__":
    main()
