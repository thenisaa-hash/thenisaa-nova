#!/usr/bin/env python3
"""
Upload products to Shopify via Admin REST API.

Usage:
    python upload_products.py --store sofacolony.myshopify.com --token YOUR_ACCESS_TOKEN
    python upload_products.py --store sofacolony.myshopify.com --token YOUR_ACCESS_TOKEN --csv products.csv
"""

import argparse
import csv
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

API_VERSION = "2025-01"


def shopify_post(store, token, endpoint, payload):
    url = f"https://{store}/admin/api/{API_VERSION}/{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": token,
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def build_product_payload(row):
    images = []
    if row.get("Image Src") and "placeholder" not in row["Image Src"]:
        images.append({
            "src": row["Image Src"],
            "alt": row.get("Image Alt Text", ""),
            "position": int(row.get("Image Position", 1)),
        })

    variant = {
        "price": row.get("Variant Price", "0.00"),
        "sku": row.get("Variant SKU", ""),
        "inventory_management": row.get("Variant Inventory Tracker") or None,
        "inventory_policy": row.get("Variant Inventory Policy", "deny"),
        "fulfillment_service": row.get("Variant Fulfillment Service", "manual"),
        "requires_shipping": row.get("Variant Requires Shipping", "TRUE").upper() == "TRUE",
        "taxable": row.get("Variant Taxable", "TRUE").upper() == "TRUE",
        "grams": int(row.get("Variant Grams", 0)),
    }

    compare_at = row.get("Variant Compare At Price", "").strip()
    if compare_at:
        variant["compare_at_price"] = compare_at

    cost = row.get("Cost per item", "").strip()
    if cost:
        variant["cost"] = cost

    status = row.get("Status", "active").lower()

    return {
        "product": {
            "title": row["Title"],
            "body_html": row.get("Body (HTML)", ""),
            "vendor": row.get("Vendor", ""),
            "product_type": row.get("Type", ""),
            "handle": row.get("Handle", ""),
            "tags": row.get("Tags", ""),
            "published": row.get("Published", "TRUE").upper() == "TRUE",
            "status": status,
            "variants": [variant],
            "images": images,
        }
    }


def upload_products(store, token, csv_path):
    path = Path(csv_path)
    if not path.exists():
        print(f"ERROR: CSV file not found: {csv_path}")
        return

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if r.get("Handle") and r.get("Title")]

    print(f"Found {len(rows)} products to upload to {store}\n")

    success, failed = [], []

    for i, row in enumerate(rows, 1):
        title = row["Title"]
        print(f"[{i}/{len(rows)}] Uploading: {title} ... ", end="", flush=True)

        try:
            payload = build_product_payload(row)
            result = shopify_post(store, token, "products.json", payload)
            product_id = result["product"]["id"]
            print(f"OK (id={product_id})")
            success.append({"title": title, "id": product_id})
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"FAILED ({e.code}): {body[:200]}")
            failed.append({"title": title, "error": f"HTTP {e.code}: {body[:200]}"})
        except Exception as e:
            print(f"FAILED: {e}")
            failed.append({"title": title, "error": str(e)})

        # Shopify rate limit: 2 requests/sec on Basic, be safe
        if i < len(rows):
            time.sleep(0.6)

    print(f"\n--- Results ---")
    print(f"Uploaded:  {len(success)}/{len(rows)}")
    if failed:
        print(f"Failed:    {len(failed)}")
        for item in failed:
            print(f"  - {item['title']}: {item['error']}")
    else:
        print("All products uploaded successfully!")

    if success:
        print(f"\nView your products:")
        print(f"  https://{store}/admin/products")


def main():
    parser = argparse.ArgumentParser(description="Upload products to Shopify via Admin API")
    parser.add_argument("--store", required=True, help="e.g. sofacolony.myshopify.com")
    parser.add_argument("--token", required=True, help="Shopify Admin API access token")
    parser.add_argument("--csv", default="products.csv", help="Path to products CSV (default: products.csv)")
    args = parser.parse_args()

    upload_products(args.store, args.token, args.csv)


if __name__ == "__main__":
    main()
