#!/usr/bin/env python3
"""
wix_to_shopify.py
─────────────────
Converts a Wix Stores product CSV export into a Shopify product CSV that can
be imported via Shopify Admin → Products → Import.

How to export from Wix:
  Dashboard → Wix Stores → Products → ⋮ (top-right) → Export Products

How to import into Shopify:
  Shopify Admin → Products → Import → Choose the output CSV this script produces

Usage:
  python migration/wix_to_shopify.py \
      --input  data/wix_products.csv \
      --output data/shopify_products.csv \
      --vendor "Mega Home Furnishing"
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path


# ── Shopify CSV column order (official Shopify product import format) ─────────
SHOPIFY_COLS = [
    "Handle", "Title", "Body (HTML)", "Vendor", "Product Category", "Type",
    "Tags", "Published",
    "Option1 Name", "Option1 Value",
    "Option2 Name", "Option2 Value",
    "Option3 Name", "Option3 Value",
    "Variant SKU", "Variant Grams", "Variant Inventory Tracker",
    "Variant Inventory Qty", "Variant Inventory Policy",
    "Variant Fulfillment Service", "Variant Price", "Variant Compare At Price",
    "Variant Requires Shipping", "Variant Taxable", "Variant Barcode",
    "Image Src", "Image Position", "Image Alt Text",
    "Gift Card", "SEO Title", "SEO Description",
    "Variant Image", "Variant Weight Unit", "Cost per item", "Status",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert a product name into a URL-safe Shopify handle."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def kg_to_grams(value: str) -> str:
    """Convert a weight string (assumed kg) to grams as a string."""
    try:
        return str(int(float(value) * 1000))
    except (ValueError, TypeError):
        return "0"


def parse_additional_images(raw: str) -> list[str]:
    """
    Parse the Wix 'additionalMedia' field which contains semicolon-separated
    or JSON-formatted image URLs.
    """
    if not raw or raw.strip() == "":
        return []

    # Try JSON array first (some Wix exports use this)
    raw = raw.strip()
    if raw.startswith("["):
        try:
            items = json.loads(raw)
            return [i.get("src", i) if isinstance(i, dict) else str(i)
                    for i in items]
        except json.JSONDecodeError:
            pass

    # Fall back to semicolon-separated list
    return [url.strip() for url in raw.split(";") if url.strip()]


def parse_product_options(raw: str) -> list[dict]:
    """
    Parse Wix productOptions field.
    Expected format (JSON): [{"name": "Color", "choices": ["White", "Grey"]}]
    Returns list of dicts with 'name' and 'choices' keys.
    """
    if not raw or raw.strip() in ("", "[]"):
        return []
    try:
        opts = json.loads(raw)
        return opts if isinstance(opts, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def parse_product_attributes(raw: str) -> list[dict]:
    """
    Parse Wix productAttributes field (variants).
    Expected format (JSON): [{"sku": "SKU-001", "price": "299", ...}]
    """
    if not raw or raw.strip() in ("", "[]"):
        return []
    try:
        attrs = json.loads(raw)
        return attrs if isinstance(attrs, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def calculate_compare_price(price: str, discount_mode: str,
                             discount_value: str) -> str:
    """
    Wix stores original price and a discount.
    Shopify expects compareAtPrice = original, price = final.
    Returns compare_at_price as a string (or '' if no discount).
    """
    try:
        p = float(price)
        d = float(discount_value) if discount_value else 0.0
    except (ValueError, TypeError):
        return ""

    if discount_mode == "PERCENT" and d > 0:
        original = p / (1 - d / 100)
        return f"{original:.2f}"
    elif discount_mode == "AMOUNT" and d > 0:
        original = p + d
        return f"{original:.2f}"
    return ""


def wix_status_to_shopify(visible: str, import_hidden_as_draft: bool) -> str:
    """Map Wix 'visible' to Shopify 'Status'."""
    if visible.strip().lower() in ("true", "1", "yes"):
        return "active"
    return "draft" if import_hidden_as_draft else "active"


# ── Core conversion ───────────────────────────────────────────────────────────

class WixToShopifyConverter:
    def __init__(self, vendor: str = "Mega Home Furnishing",
                 import_hidden_as_draft: bool = True):
        self.vendor = vendor
        self.import_hidden_as_draft = import_hidden_as_draft
        self._converted = 0
        self._skipped = 0

    def _base_row(self) -> dict:
        """Return an empty Shopify row with all required columns."""
        return {col: "" for col in SHOPIFY_COLS}

    def _product_first_row(self, wix_row: dict, handle: str,
                           options: list[dict]) -> dict:
        """Build the primary product row from a Wix product-level record."""
        row = self._base_row()
        row["Handle"] = handle
        row["Title"] = wix_row.get("name", "").strip()
        row["Body (HTML)"] = wix_row.get("description", "").strip()
        row["Vendor"] = self.vendor
        row["Type"] = wix_row.get("collection", "").strip()
        row["Tags"] = wix_row.get("collection", "").strip()
        row["Published"] = "TRUE"
        row["Gift Card"] = "FALSE"

        # Options (up to 3)
        for i, opt in enumerate(options[:3], start=1):
            row[f"Option{i} Name"] = opt.get("name", f"Option {i}")
            choices = opt.get("choices", [])
            row[f"Option{i} Value"] = choices[0] if choices else "Default"

        # Default option when no variants defined
        if not options:
            row["Option1 Name"] = "Title"
            row["Option1 Value"] = "Default Title"

        # Variant fields
        row["Variant SKU"] = wix_row.get("sku", "").strip()
        row["Variant Grams"] = kg_to_grams(wix_row.get("weight", "0"))
        row["Variant Weight Unit"] = "kg"
        row["Variant Inventory Tracker"] = "shopify"
        row["Variant Inventory Qty"] = wix_row.get("inventory", "0").strip()
        row["Variant Inventory Policy"] = "deny"
        row["Variant Fulfillment Service"] = "manual"
        row["Variant Price"] = wix_row.get("price", "0").strip()
        row["Variant Compare At Price"] = calculate_compare_price(
            wix_row.get("price", "0"),
            wix_row.get("discountMode", ""),
            wix_row.get("discountValue", ""),
        )
        row["Variant Requires Shipping"] = "TRUE"
        row["Variant Taxable"] = "TRUE"
        row["Cost per item"] = wix_row.get("cost", "").strip()

        # Main image
        row["Image Src"] = wix_row.get("productImageUrl", "").strip()
        row["Image Position"] = "1"
        row["Image Alt Text"] = row["Title"]

        row["Status"] = wix_status_to_shopify(
            wix_row.get("visible", "true"),
            self.import_hidden_as_draft,
        )
        return row

    def _additional_image_row(self, handle: str, image_url: str,
                               position: int) -> dict:
        """Build a Shopify image-only row for extra product images."""
        row = self._base_row()
        row["Handle"] = handle
        row["Image Src"] = image_url
        row["Image Position"] = str(position)
        return row

    def _variant_row(self, handle: str, variant: dict,
                     options: list[dict]) -> dict:
        """Build a Shopify variant row from a Wix productAttributes item."""
        row = self._base_row()
        row["Handle"] = handle

        # Map option values for this variant
        variant_opts = variant.get("optionChoices", {})
        for i, opt in enumerate(options[:3], start=1):
            opt_name = opt.get("name", "")
            row[f"Option{i} Name"] = opt_name
            row[f"Option{i} Value"] = variant_opts.get(opt_name, "")

        row["Variant SKU"] = variant.get("sku", "").strip()
        row["Variant Price"] = str(variant.get("price", "0")).strip()
        row["Variant Compare At Price"] = ""  # Wix variants don't export this
        row["Variant Grams"] = kg_to_grams(str(variant.get("weight", "0")))
        row["Variant Weight Unit"] = "kg"
        row["Variant Inventory Tracker"] = "shopify"
        row["Variant Inventory Qty"] = str(variant.get("inventory", "0"))
        row["Variant Inventory Policy"] = "deny"
        row["Variant Fulfillment Service"] = "manual"
        row["Variant Requires Shipping"] = "TRUE"
        row["Variant Taxable"] = "TRUE"
        row["Variant Image"] = variant.get("variantImageUrl", "").strip()
        return row

    def convert_row(self, wix_row: dict) -> list[dict]:
        """
        Convert one Wix product CSV row into one or more Shopify rows.
        Returns an empty list for non-Product rows (e.g. Wix fieldType=Variant).
        """
        field_type = wix_row.get("fieldType", "Product").strip()
        if field_type != "Product":
            return []

        title = wix_row.get("name", "").strip()
        if not title:
            self._skipped += 1
            return []

        handle = slugify(title)
        options = parse_product_options(wix_row.get("productOptions", ""))
        variants = parse_product_attributes(wix_row.get("productAttributes", ""))
        additional_images = parse_additional_images(
            wix_row.get("additionalMedia", "")
        )

        rows = []

        # ── 1. Primary product row ────────────────────────────────────────────
        rows.append(self._product_first_row(wix_row, handle, options))

        # ── 2. Additional variant rows ────────────────────────────────────────
        for variant in variants:
            rows.append(self._variant_row(handle, variant, options))

        # ── 3. Additional image rows ──────────────────────────────────────────
        for pos, img_url in enumerate(additional_images, start=2):
            rows.append(self._additional_image_row(handle, img_url, pos))

        self._converted += 1
        return rows

    def convert(self, input_path: str, output_path: str) -> None:
        """Convert the full Wix CSV file and write Shopify CSV."""
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not input_path.exists():
            print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)

        print(f"Reading Wix CSV: {input_path}")

        with input_path.open(newline="", encoding="utf-8-sig") as in_f, \
             output_path.open("w", newline="", encoding="utf-8") as out_f:

            reader = csv.DictReader(in_f)
            writer = csv.DictWriter(out_f, fieldnames=SHOPIFY_COLS)
            writer.writeheader()

            for wix_row in reader:
                for shopify_row in self.convert_row(wix_row):
                    writer.writerow(shopify_row)

        print(f"✓ Converted {self._converted} products "
              f"({self._skipped} skipped) → {output_path}")


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert Wix product CSV → Shopify product CSV"
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to Wix exported products CSV (e.g. data/wix_products.csv)"
    )
    parser.add_argument(
        "--output", default="data/shopify_products.csv",
        help="Output path for Shopify import CSV"
    )
    parser.add_argument(
        "--vendor", default="Mega Home Furnishing",
        help="Vendor name to set on all products"
    )
    parser.add_argument(
        "--keep-hidden", action="store_true",
        help="Import Wix hidden products as 'active' instead of 'draft'"
    )
    args = parser.parse_args()

    converter = WixToShopifyConverter(
        vendor=args.vendor,
        import_hidden_as_draft=not args.keep_hidden,
    )
    converter.convert(args.input, args.output)


if __name__ == "__main__":
    main()
