"""
Higgsfield Image Enhancement Automation
Uses Playwright to automate image enhancement via the Higgsfield website.
"""

import os
import time
import shutil
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

load_dotenv()

ENHANCEMENT_PROMPT = """Use the exact attached [PRODUCT] photo as the reference image.

IMPORTANT: Extract and recreate ONLY the [PRODUCT] from the reference. Do NOT include or recreate any other items or background elements (e.g., furniture, packaging, props, décor, room setting, flooring, walls, curtains, reflections, or people).

Generate a hyper-realistic studio product image of the same [PRODUCT], keeping it 100% identical to the reference:
- Design and proportions
- Dimensions (height/thickness/depth where applicable)
- Surface pattern / texture / stitching / seams / joints (as applicable)
- Panel lines, edges, trims, and detailing
- Colour accuracy and tone
- Materials and finish (fabric / leather / wood grain / metal / glass etc.)
- Corners, curves, structure, and overall shape

Place the [PRODUCT] perfectly centred, straight-on front-facing, floating slightly above a pure white background (clean studio cut-out style).

Add a soft, natural shadow directly beneath the [PRODUCT] for realistic grounding (no harsh or dramatic shadows).

Lighting must be even, bright, professional studio/showroom lighting, like premium e-commerce product photography, with no colour shifts, no harsh highlights, and no dark areas.

Strict exclusions:
No background scene, no environment, no props, no accessories, no reflections, no text, no logos, no branding, no watermark.

Ultra-sharp focus, clean edges, accurate material texture, realistic depth and clarity.

Format: Square Resolution: 1080 × 1080 px"""

HIGGSFIELD_URL = "https://higgsfield.ai"
LOGIN_URL = f"{HIGGSFIELD_URL}/login"
IMAGE_TOOL_URL = f"{HIGGSFIELD_URL}/image"


class HighgsfieldAutomation:
    def __init__(
        self,
        output_dir: str = "output_images",
        slow_mo: int = 100,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.slow_mo = slow_mo

    def _wait_and_click(self, page: Page, selector: str, timeout: int = 30000):
        """Wait for element and click it."""
        page.wait_for_selector(selector, timeout=timeout)
        page.click(selector)

    def _login(self, page: Page):
        """Open Higgsfield and wait for the user to log in manually."""
        print("Opening Higgsfield login page...")
        page.goto(LOGIN_URL, wait_until="networkidle")
        time.sleep(2)

        print()
        print("=" * 60)
        print("  ACTION REQUIRED - Please log in to Higgsfield")
        print("=" * 60)
        print()
        print("  1. Look at the browser window that just opened")
        print("  2. Click 'Sign in with Google'")
        print("  3. Choose your Google account and complete login")
        print("  4. Once you are inside the Higgsfield dashboard,")
        print("     come back here and press ENTER to continue.")
        print()
        input("  Press ENTER after you have logged in >>> ")
        print()
        print("Continuing automation...")
        time.sleep(2)

    def _navigate_to_image_tool(self, page: Page):
        """Navigate to the Higgsfield Image tool."""
        print("Navigating to Image tool...")
        page.goto(IMAGE_TOOL_URL, wait_until="networkidle", timeout=30000)
        time.sleep(3)
        print(f"Navigated to: {IMAGE_TOOL_URL}")

    def _upload_image(self, page: Page, image_path: str):
        """Upload the reference image."""
        print(f"Uploading image: {image_path}")

        # Try file input selectors
        file_input_selectors = [
            'input[type="file"]',
            'input[accept*="image"]',
        ]

        for selector in file_input_selectors:
            try:
                file_input = page.query_selector(selector)
                if file_input:
                    file_input.set_input_files(image_path)
                    print(f"Uploaded via: {selector}")
                    time.sleep(3)
                    return True
            except Exception as e:
                print(f"File input {selector} failed: {e}")
                continue

        # Try drag-and-drop zone
        drop_selectors = [
            '[data-testid*="upload"]',
            '[data-testid*="drop"]',
            '.upload-area',
            '.drop-zone',
            'div[role="button"]:has-text("upload")',
            'div:has-text("Upload")',
            'button:has-text("Upload")',
            'label:has-text("Upload")',
        ]

        for selector in drop_selectors:
            try:
                element = page.query_selector(selector)
                if element:
                    # Look for hidden file input nearby
                    file_input = page.query_selector('input[type="file"]')
                    if file_input:
                        file_input.set_input_files(image_path)
                        print(f"Uploaded via drop zone + file input")
                        time.sleep(3)
                        return True

                    # Click to trigger file picker
                    element.click()
                    time.sleep(1)

                    # After clicking, try finding file input again
                    file_input = page.query_selector('input[type="file"]')
                    if file_input:
                        file_input.set_input_files(image_path)
                        time.sleep(3)
                        return True
            except Exception as e:
                print(f"Drop zone {selector} failed: {e}")
                continue

        print("Could not find upload mechanism - please check Higgsfield UI")
        return False

    def _enter_prompt(self, page: Page, prompt: str):
        """Enter the enhancement prompt."""
        print("Entering enhancement prompt...")

        prompt_selectors = [
            'textarea[placeholder*="prompt" i]',
            'textarea[placeholder*="describe" i]',
            'textarea[placeholder*="enter" i]',
            'textarea',
            'div[contenteditable="true"]',
            'input[placeholder*="prompt" i]',
            '[data-testid*="prompt"]',
        ]

        for selector in prompt_selectors:
            try:
                element = page.query_selector(selector)
                if element:
                    element.click()
                    time.sleep(0.5)
                    # Clear existing content
                    page.keyboard.press("Control+a")
                    page.keyboard.press("Delete")
                    # Type the prompt
                    element.fill(prompt)
                    print(f"Entered prompt using: {selector}")
                    time.sleep(1)
                    return True
            except Exception as e:
                print(f"Prompt selector {selector} failed: {e}")
                continue

        print("Could not find prompt input")
        return False

    def _trigger_generation(self, page: Page):
        """Click the generate/enhance button."""
        print("Triggering image generation...")

        generate_selectors = [
            'button:has-text("Generate")',
            'button:has-text("Enhance")',
            'button:has-text("Create")',
            'button:has-text("Run")',
            'button:has-text("Submit")',
            'button[type="submit"]',
            '[data-testid*="generate"]',
            '[data-testid*="submit"]',
        ]

        for selector in generate_selectors:
            try:
                element = page.query_selector(selector)
                if element and element.is_enabled():
                    element.click()
                    print(f"Clicked generate button: {selector}")
                    return True
            except Exception as e:
                print(f"Generate selector {selector} failed: {e}")
                continue

        print("Could not find generate button")
        return False

    def _wait_for_result(self, page: Page, timeout: int = 300) -> str | None:
        """Wait for the generated image and return its URL."""
        print("Waiting for image generation to complete...")
        print(f"This may take up to {timeout} seconds...")

        start_time = time.time()
        last_image_count = 0

        while time.time() - start_time < timeout:
            try:
                # Look for newly generated/result images
                result_selectors = [
                    'img[src*="blob:"]',
                    'img[src*="result"]',
                    'img[src*="output"]',
                    'img[src*="generated"]',
                    '[data-testid*="result"] img',
                    '.result-image img',
                    '.generated-image img',
                ]

                for selector in result_selectors:
                    imgs = page.query_selector_all(selector)
                    if len(imgs) > last_image_count:
                        # New image appeared
                        new_img = imgs[-1]
                        src = new_img.get_attribute("src")
                        if src:
                            print(f"Found result image: {src[:80]}...")
                            return src
                        last_image_count = len(imgs)

                # Check for loading indicators to know we're still processing
                loading_selectors = [
                    '.loading',
                    '.spinner',
                    '[data-testid*="loading"]',
                    'button:has-text("Generating")',
                    'button:has-text("Processing")',
                ]
                is_loading = any(
                    page.query_selector(s) for s in loading_selectors
                )

                if not is_loading and time.time() - start_time > 30:
                    # Not loading and some time passed - check for any new images
                    all_imgs = page.query_selector_all("img")
                    if len(all_imgs) > last_image_count:
                        new_img = all_imgs[-1]
                        src = new_img.get_attribute("src")
                        if src and not src.endswith(".svg"):
                            return src

                time.sleep(5)
                print(f"Still waiting... ({int(time.time() - start_time)}s elapsed)")

            except Exception as e:
                print(f"Error while waiting: {e}")
                time.sleep(5)

        print("Timed out waiting for result")
        return None

    def _download_result(
        self, page: Page, image_name: str, result_url: str | None
    ) -> str | None:
        """Download the enhanced image."""
        output_path = self.output_dir / image_name

        # First try: look for a download button
        download_selectors = [
            'button:has-text("Download")',
            'a[download]',
            'a:has-text("Download")',
            '[data-testid*="download"]',
            'button[aria-label*="download" i]',
        ]

        for selector in download_selectors:
            try:
                element = page.query_selector(selector)
                if element:
                    with page.expect_download(timeout=30000) as download_info:
                        element.click()
                    download = download_info.value
                    download.save_as(str(output_path))
                    print(f"Downloaded via button to: {output_path}")
                    return str(output_path)
            except Exception as e:
                print(f"Download button {selector} failed: {e}")
                continue

        # Second try: right-click on result image to save
        if result_url:
            try:
                import requests
                response = requests.get(result_url, timeout=60)
                if response.status_code == 200:
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                    print(f"Downloaded via URL to: {output_path}")
                    return str(output_path)
            except Exception as e:
                print(f"URL download failed: {e}")

        # Third try: screenshot the result area as fallback
        try:
            result_img = page.query_selector(
                '[data-testid*="result"] img, .result-image img, .generated-image img'
            )
            if result_img:
                result_img.screenshot(path=str(output_path))
                print(f"Saved screenshot of result to: {output_path}")
                return str(output_path)
        except Exception as e:
            print(f"Screenshot fallback failed: {e}")

        return None

    def enhance_image(self, image_path: str, page: Page) -> str | None:
        """
        Enhance a single image using Higgsfield.

        Args:
            image_path: Path to the input image
            page: Playwright page instance

        Returns:
            Path to the enhanced image, or None if failed
        """
        image_name = Path(image_path).name
        print(f"\n{'='*60}")
        print(f"Processing: {image_name}")
        print(f"{'='*60}")

        try:
            # Navigate back to create/image tool for each image
            self._navigate_to_image_tool(page)
            time.sleep(2)

            # Upload image
            uploaded = self._upload_image(page, image_path)
            if not uploaded:
                print(f"Failed to upload {image_name}")
                return None

            # Enter prompt
            self._enter_prompt(page, ENHANCEMENT_PROMPT)

            # Generate
            triggered = self._trigger_generation(page)
            if not triggered:
                print(f"Failed to trigger generation for {image_name}")
                return None

            # Wait for result
            result_url = self._wait_for_result(page)

            # Download result
            output_stem = Path(image_path).stem
            output_name = f"{output_stem}_enhanced.png"
            result_path = self._download_result(page, output_name, result_url)

            if result_path:
                print(f"Successfully enhanced: {image_name} -> {result_path}")
            else:
                print(f"Could not save result for: {image_name}")

            return result_path

        except Exception as e:
            print(f"Error processing {image_name}: {e}")
            return None

    def run(self, image_paths: list[str]) -> dict[str, str | None]:
        """
        Run the enhancement automation for all images.

        Args:
            image_paths: List of paths to input images

        Returns:
            Dict mapping input paths to output paths (None if failed)
        """
        results = {}

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                slow_mo=self.slow_mo,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )

            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

            page = context.new_page()

            try:
                # Login once
                self._login(page)

                # Process each image
                for i, image_path in enumerate(image_paths, 1):
                    print(f"\nProcessing image {i}/{len(image_paths)}: {image_path}")
                    result = self.enhance_image(image_path, page)
                    results[image_path] = result
                    time.sleep(2)

            except Exception as e:
                print(f"Fatal error during automation: {e}")
                # Take screenshot for debugging
                try:
                    page.screenshot(path="debug_screenshot.png")
                    print("Debug screenshot saved to: debug_screenshot.png")
                except Exception:
                    pass

            finally:
                context.close()
                browser.close()

        return results


def main(image_paths: list[str] | None = None):
    """Run the Higgsfield automation."""
    output_dir = os.getenv("OUTPUT_IMAGES_DIR", "output_images")
    slow_mo = int(os.getenv("SLOW_MO", "100"))

    if not image_paths:
        # Look for images in the input directory
        input_dir = os.getenv("INPUT_IMAGES_DIR", "input_images")
        input_path = Path(input_dir)
        if not input_path.exists():
            print(f"ERROR: Input directory '{input_dir}' does not exist")
            print("Run download_gdrive.py first to download images")
            return None

        supported_ext = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
        image_paths = [
            str(p)
            for p in sorted(input_path.rglob("*"))
            if p.is_file() and p.suffix.lower() in supported_ext
        ]

        if not image_paths:
            print(f"ERROR: No images found in '{input_dir}'")
            return None

    print(f"Found {len(image_paths)} image(s) to process")

    automation = HighgsfieldAutomation(
        output_dir=output_dir,
        slow_mo=slow_mo,
    )

    results = automation.run(image_paths)

    # Print summary
    print(f"\n{'='*60}")
    print("ENHANCEMENT SUMMARY")
    print(f"{'='*60}")
    success_count = sum(1 for v in results.values() if v is not None)
    print(f"Total: {len(results)} | Success: {success_count} | Failed: {len(results) - success_count}")
    print()
    for input_path, output_path in results.items():
        status = "OK" if output_path else "FAILED"
        print(f"  [{status}] {Path(input_path).name}")
        if output_path:
            print(f"         -> {output_path}")

    return results


if __name__ == "__main__":
    main()
