"""
Batch product photo upgrader using Higgsfield AI.

For each product photo in the input directory, generates two variations:
  1. SKU photo      – hyper-realistic studio cut-out on white background (1:1)
  2. Lifestyle photo – Scandinavian interior scene with ASEAN family (16:9)

Usage:
    python generate_product_photos.py --input-dir raw_photos/
    python generate_product_photos.py --input-dir raw_photos/ --product-type "sofa"
    python generate_product_photos.py --input-dir raw_photos/ --sku-only
    python generate_product_photos.py --input-dir raw_photos/ --lifestyle-only

Environment variables:
    HF_KEY  – Your Higgsfield API key (required)
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
    pass


# ── Model ─────────────────────────────────────────────────────────────────────

IMAGE_MODEL = "bytedance/seedream/v4/text-to-image"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


# ── Prompts ───────────────────────────────────────────────────────────────────

SKU_PROMPT = """\
Use the exact attached [REFERENCE PHOTO] as the reference image.
IMPORTANT: Extract and recreate ONLY the {product} from the reference. \
Do NOT include or recreate any other products or elements \
(e.g., furniture, packaging, background objects, stands, props, people, \
hands, flooring, walls, curtains, décor).
Generate a hyper-realistic studio product image of the same {product}, \
keeping 100% identical:
* Overall design, silhouette, and proportions
* Size/height/thickness (as applicable)
* Surface patterns, stitching, seams, panel lines, edge detailing
* Colour tone and material finish
* Texture and micro-details (fabric grain, leather pores, wood grain, metal sheen, etc.)
* Corners, curves, structure, and build details
Composition: Place the {product} perfectly centred, straight-on front-facing, \
and floating slightly above a pure white background (clean studio cut-out style).
Add a soft, natural shadow directly beneath the {product} for realistic grounding \
(no harsh or dramatic shadows).
Lighting: Even, bright, professional showroom lighting for premium e-commerce product \
photography. No harsh highlights, no colour shifts, no overexposure, no heavy contrast.
Strict exclusions: No background scene, no props, no accessories, no extra objects, \
no reflections, no text, no logos, no branding, no watermark.
Quality: Ultra-sharp focus, clean edges, accurate material texture, realistic depth and clarity.
Format: Square Resolution: 1080 × 1080 px\
"""

LIFESTYLE_PROMPT = """\
Use the exact attached [REFERENCE PRODUCT PHOTO] as the reference image. \
Do not change the {product} design, proportions, key detailing, colour, \
materials, or surface finish.
Generate a hyper-realistic Scandinavian-style home interior with soft natural daylight, \
light wood flooring, neutral beige/white tones, and a warm, cozy modern atmosphere \
(minimalist, uncluttered, premium catalog feel).
Placement: Place the exact same {product} in a natural, realistic position in the room, \
styled appropriately for how it's used. The {product} must be fully visible and unobstructed.
Visibility rules (very important):
* Keep the entire main surface and structure of the {product} clearly visible
* Preserve and show key details (textures, stitching, panel lines, shape, height, etc.)
* No obstruction by people, décor, props, or other objects
* If the product is normally "covered" (e.g., bed/mattress/sofa), keep it clean and \
uncovered unless the product category requires minimal styling — then allow only minimal, \
non-blocking styling (e.g., a small cushion placed away from key features)
People (optional lifestyle): Include a young ASEAN/Singaporean family (a couple with one \
young child) interacting naturally with the {product} in a gentle, authentic way \
(sitting, using, touching lightly).
* Expressions: warm, relaxed, natural smiles
* Clothing: casual, modern, home-appropriate, neutral colours, no logos
* The people must support the lifestyle story but must not dominate the image
Camera & style:
* Camera angle: slightly wide, eye-level or 3/4 angle
* Show the full {product} clearly within the environment
* Style: photorealistic, premium lifestyle catalog quality
* Lighting: soft natural daylight, balanced exposure, soft shadows
* No filters, no heavy colour grading, no unrealistic blur
Strict exclusions: No text, no logos, no watermark, no distracting clutter, \
no messy décor, no unrealistic reflections.\
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def upload_reference(image_path: Path) -> str:
    """Upload a local image to Higgsfield and return its hosted URL."""
    print(f"  Uploading reference image: {image_path.name}")
    url = higgsfield_client.upload_file(str(image_path))
    print(f"  Uploaded → {url}")
    return url


def generate_variation(
    prompt: str,
    reference_url: str,
    aspect_ratio: str,
    label: str,
) -> dict:
    """Submit one generation request, poll until done, return result dict."""
    print(f"  [{label}] Submitting request...")
    request_controller = higgsfield_client.submit(
        IMAGE_MODEL,
        arguments={
            "prompt": prompt,
            "image_url": reference_url,
            "resolution": "2K",
            "aspect_ratio": aspect_ratio,
            "camera_fixed": False,
        },
    )

    for status in request_controller.poll_request_status():
        if isinstance(status, higgsfield_client.Queued):
            print(f"  [{label}] Queued...")
        elif isinstance(status, higgsfield_client.InProgress):
            print(f"  [{label}] In progress...")
        elif isinstance(status, higgsfield_client.Completed):
            print(f"  [{label}] Completed.")
        elif isinstance(status, higgsfield_client.Failed):
            raise RuntimeError(f"[{label}] Generation failed.")
        elif isinstance(status, higgsfield_client.NSFW):
            raise ValueError(f"[{label}] Rejected: NSFW content detected.")
        elif isinstance(status, higgsfield_client.Cancelled):
            raise RuntimeError(f"[{label}] Request was cancelled.")

    return request_controller.get()


def save_image(image_url: str, dest_path: Path) -> None:
    """Download an image from a URL and save it to dest_path."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(image_url, dest_path)


def product_label_from_path(image_path: Path, override: str | None) -> str:
    """Return the human-readable product label to inject into prompts."""
    if override:
        return override
    return image_path.stem.replace("_", " ").replace("-", " ")


# ── Core processing ───────────────────────────────────────────────────────────

def process_product(
    image_path: Path,
    product_type: str | None,
    output_dir: Path,
    gen_sku: bool,
    gen_lifestyle: bool,
) -> None:
    """Upload reference photo then generate all requested variations."""
    product_name = image_path.stem
    label = product_label_from_path(image_path, product_type)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    product_out = output_dir / product_name

    print(f"\n{'─' * 60}")
    print(f"  Product : {label}")
    print(f"  File    : {image_path.name}")
    print(f"{'─' * 60}")

    # Upload once, reuse URL for both variations
    try:
        reference_url = upload_reference(image_path)
    except Exception as exc:
        print(f"  ERROR: could not upload reference image – {exc}")
        return

    if gen_sku:
        prompt = SKU_PROMPT.format(product=label)
        try:
            result = generate_variation(prompt, reference_url, "1:1", "SKU")
            images = result.get("images", [])
            if images:
                dest = product_out / f"sku_{timestamp}.png"
                save_image(images[0]["url"], dest)
                print(f"  SKU saved      → {dest}")
            else:
                print("  WARNING: No images returned for SKU variation.")
        except Exception as exc:
            print(f"  ERROR (SKU): {exc}")

    if gen_lifestyle:
        prompt = LIFESTYLE_PROMPT.format(product=label)
        try:
            result = generate_variation(prompt, reference_url, "16:9", "Lifestyle")
            images = result.get("images", [])
            if images:
                dest = product_out / f"lifestyle_{timestamp}.png"
                save_image(images[0]["url"], dest)
                print(f"  Lifestyle saved → {dest}")
            else:
                print("  WARNING: No images returned for Lifestyle variation.")
        except Exception as exc:
            print(f"  ERROR (Lifestyle): {exc}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch-upgrade product photos and generate SKU + lifestyle variations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        metavar="DIR",
        help="Directory containing raw product photos",
    )
    parser.add_argument(
        "--product-type",
        default=None,
        metavar="TEXT",
        help=(
            "Product type description shared by all photos "
            "(e.g. 'sofa', '3-seater fabric sofa'). "
            "If omitted, the filename (without extension) is used per photo."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        metavar="DIR",
        help="Root directory for generated images (default: output/)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--sku-only",
        action="store_true",
        help="Generate only SKU (white-background) photos",
    )
    mode.add_argument(
        "--lifestyle-only",
        action="store_true",
        help="Generate only lifestyle (interior scene) photos",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Credential check
    if not os.environ.get("HF_KEY") and not (
        os.environ.get("HF_API_KEY") and os.environ.get("HF_API_SECRET")
    ):
        print("Error: Higgsfield API credentials not found.")
        print("  Set HF_KEY in your environment or in a .env file.")
        print("  Get your key at: https://cloud.higgsfield.ai/")
        sys.exit(1)

    # Input validation
    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"Error: Input directory not found: {input_dir}")
        sys.exit(1)

    images = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not images:
        print(f"No supported images found in '{input_dir}'.")
        print(f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
        sys.exit(1)

    gen_sku = not args.lifestyle_only
    gen_lifestyle = not args.sku_only
    variations = " + ".join(
        filter(None, [
            "SKU" if gen_sku else None,
            "Lifestyle" if gen_lifestyle else None,
        ])
    )

    print(f"Found {len(images)} product photo(s) in '{input_dir}'")
    print(f"Variations to generate per photo : {variations}")
    print(f"Output directory                 : {args.output_dir}/")

    output_dir = Path(args.output_dir)
    failed: list[str] = []

    for image_path in images:
        try:
            process_product(
                image_path,
                args.product_type,
                output_dir,
                gen_sku,
                gen_lifestyle,
            )
        except Exception as exc:
            print(f"  UNEXPECTED ERROR for {image_path.name}: {exc}")
            failed.append(image_path.name)

    print(f"\n{'═' * 60}")
    print(f"Done. Results saved to '{output_dir}/'")
    if failed:
        print(f"Failed photos ({len(failed)}): {', '.join(failed)}")
    print(f"{'═' * 60}")


if __name__ == "__main__":
    main()
