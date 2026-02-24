#!/usr/bin/env python3
"""
run_migration.py
────────────────
Orchestrates the full Wix → Shopify migration:

  Step 1  Convert Wix CSV → Shopify CSV  (wix_to_shopify.py)
  Step 2  Upload Shopify CSV products via Admin API  (shopify_api.py)
  Step 3  Create custom collections and assign products
  Step 4  Create static pages (About Us, Gallery, Locate Us, Contact)
  Step 5  Build navigation menus (header + footer) to mirror xclusivehome.sg
  Step 6  Upload theme settings (config/settings_data.json) to the Vast theme

Prerequisites
─────────────
1. Copy migration/config.example.py → migration/config.py and fill in:
     - SHOPIFY_STORE_URL
     - SHOPIFY_ACCESS_TOKEN
2. Export products from Wix:
     Wix Dashboard → Stores → Products → ⋮ → Export → save to data/wix_products.csv
3. Install dependencies:
     pip install -r migration/requirements.txt

Run:
  python migration/run_migration.py
"""

import csv
import json
import sys
from pathlib import Path

# ── Resolve project root so imports work when run from any directory ──────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from migration.shopify_api import ShopifyClient, ShopifyAPIError
    from migration.wix_to_shopify import WixToShopifyConverter
except ImportError as exc:
    print(f"[ERROR] Could not import migration modules: {exc}")
    sys.exit(1)

try:
    import migration.config as cfg  # type: ignore
except ModuleNotFoundError:
    print(
        "[ERROR] migration/config.py not found.\n"
        "        Copy migration/config.example.py → migration/config.py\n"
        "        and fill in your Shopify credentials."
    )
    sys.exit(1)

DATA_DIR = ROOT / "data"
THEME_DIR = ROOT / "theme"
WIX_CSV = DATA_DIR / "wix_products.csv"
SHOPIFY_CSV = DATA_DIR / "shopify_products.csv"
SETTINGS_JSON = THEME_DIR / "config" / "settings_data.json"
INDEX_JSON = THEME_DIR / "templates" / "index.json"


# ── Step helpers ──────────────────────────────────────────────────────────────

def step(n: int, label: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  Step {n}: {label}")
    print(f"{'─'*60}")


def convert_csv() -> None:
    step(1, "Convert Wix CSV → Shopify CSV")
    if not WIX_CSV.exists():
        print(f"[SKIP] {WIX_CSV} not found – skipping conversion.")
        return
    converter = WixToShopifyConverter(
        vendor=cfg.DEFAULT_VENDOR,
        import_hidden_as_draft=getattr(cfg, "IMPORT_HIDDEN_AS_DRAFT", True),
    )
    converter.convert(str(WIX_CSV), str(SHOPIFY_CSV))


def import_products(client: ShopifyClient) -> dict[str, int]:
    """
    Read the converted Shopify CSV and create/update products via API.
    Returns a mapping of {handle: shopify_product_id}.
    """
    step(2, "Import products into Shopify")

    if not SHOPIFY_CSV.exists():
        print(f"[SKIP] {SHOPIFY_CSV} not found – skipping product import.")
        return {}

    update_existing = getattr(cfg, "UPDATE_EXISTING", False)

    # Cache existing products keyed by SKU → product_id
    existing_by_sku: dict[str, int] = {}
    if update_existing:
        print("  Fetching existing products for update matching …")
        for p in client.list_products(fields="id,variants"):
            for v in p.get("variants", []):
                if v.get("sku"):
                    existing_by_sku[v["sku"]] = p["id"]

    # Group CSV rows by Handle – each group = one product
    products_rows: dict[str, list[dict]] = {}
    with SHOPIFY_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            handle = row["Handle"]
            if handle:
                products_rows.setdefault(handle, [])
            if handle:
                products_rows[handle].append(row)

    handle_to_id: dict[str, int] = {}
    created = updated = skipped = 0

    for handle, rows in products_rows.items():
        main = rows[0]
        if not main.get("Title"):
            # This is an image-only continuation row – skip as a standalone
            continue

        # Check if this product already exists by SKU
        sku = main.get("Variant SKU", "")
        existing_id = existing_by_sku.get(sku) if update_existing else None

        # Build images list from all rows that have Image Src
        images = [
            {"src": r["Image Src"], "alt": r.get("Image Alt Text", "")}
            for r in rows if r.get("Image Src")
        ]

        # Parse options
        options = []
        for i in range(1, 4):
            opt_name = main.get(f"Option{i} Name", "").strip()
            if opt_name and opt_name not in ("", "Title"):
                options.append({"name": opt_name, "values": []})

        # Build variants list from rows that have a Variant Price
        variants = []
        for r in rows:
            if not r.get("Variant Price"):
                continue
            variant: dict = {
                "price": r["Variant Price"],
                "sku": r.get("Variant SKU", ""),
                "grams": int(r.get("Variant Grams") or 0),
                "weight_unit": r.get("Variant Weight Unit", "kg"),
                "inventory_management": r.get("Variant Inventory Tracker") or None,
                "inventory_quantity": int(r.get("Variant Inventory Qty") or 0),
                "inventory_policy": r.get("Variant Inventory Policy", "deny"),
                "fulfillment_service": r.get("Variant Fulfillment Service", "manual"),
                "requires_shipping": r.get("Variant Requires Shipping", "TRUE") == "TRUE",
                "taxable": r.get("Variant Taxable", "TRUE") == "TRUE",
            }
            compare = r.get("Variant Compare At Price", "").strip()
            if compare:
                variant["compare_at_price"] = compare
            cost = r.get("Cost per item", "").strip()
            if cost:
                variant["cost"] = cost
            # Option values
            for i, opt in enumerate(options, start=1):
                val = r.get(f"Option{i} Value", "").strip()
                if val:
                    variant[f"option{i}"] = val
                    if val not in opt["values"]:
                        opt["values"].append(val)
            variants.append(variant)

        if not variants:
            # No valid variants found – create a default
            variants = [{
                "price": main.get("Variant Price", "0"),
                "option1": "Default Title",
            }]

        payload = {
            "title": main["Title"],
            "body_html": main.get("Body (HTML)", ""),
            "vendor": main.get("Vendor", cfg.DEFAULT_VENDOR),
            "product_type": main.get("Type", ""),
            "tags": main.get("Tags", ""),
            "status": main.get("Status", "active"),
            "images": images,
            "variants": variants,
        }
        if options:
            payload["options"] = options

        try:
            if existing_id:
                payload["id"] = existing_id
                result = client.update_product(existing_id, payload)
                handle_to_id[handle] = result["id"]
                updated += 1
                print(f"  [updated] {main['Title']}")
            else:
                result = client.create_product(payload)
                handle_to_id[handle] = result["id"]
                created += 1
                print(f"  [created] {main['Title']}")
        except ShopifyAPIError as exc:
            print(f"  [ERROR]   {main['Title']}: {exc}")
            skipped += 1

    print(f"\n  Products: {created} created, {updated} updated, {skipped} errors")
    return handle_to_id


def create_collections(client: ShopifyClient,
                        handle_to_id: dict[str, int]) -> dict[str, int]:
    """
    Create standard furniture collections matching xclusivehome.sg categories,
    then assign products based on their Type/Tags.
    Returns mapping of {collection_title: collection_id}.
    """
    step(3, "Create collections & assign products")

    # Collections to create – matching Mega Home / xclusivehome.sg categories
    desired_collections = [
        "Sofas",
        "Beds & Bedframes",
        "Dining Tables",
        "Coffee Tables",
        "TV Consoles",
        "Wardrobes & Storage",
        "Mattresses",
        "Feature Walls",
        "New Arrivals",
        "Sale",
    ]

    # Fetch existing collections to avoid duplicates
    existing = {c["title"]: c["id"] for c in client.list_custom_collections()}
    collection_ids: dict[str, int] = {}

    for title in desired_collections:
        if title in existing:
            collection_ids[title] = existing[title]
            print(f"  [exists]  {title}")
        else:
            try:
                result = client.create_custom_collection(title)
                collection_ids[title] = result["id"]
                print(f"  [created] {title}")
            except ShopifyAPIError as exc:
                print(f"  [ERROR]   {title}: {exc}")

    # Map product types to collection titles
    type_to_collection = {
        "sofa": "Sofas",
        "couch": "Sofas",
        "bed": "Beds & Bedframes",
        "bedframe": "Beds & Bedframes",
        "dining": "Dining Tables",
        "coffee table": "Coffee Tables",
        "tv console": "TV Consoles",
        "wardrobe": "Wardrobes & Storage",
        "storage": "Wardrobes & Storage",
        "mattress": "Mattresses",
        "feature wall": "Feature Walls",
    }

    if not SHOPIFY_CSV.exists():
        return collection_ids

    # Read the CSV to find product types and assign
    assigned = 0
    with SHOPIFY_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            handle = row.get("Handle", "")
            product_type = row.get("Type", "").lower()
            tags = row.get("Tags", "").lower()
            product_id = handle_to_id.get(handle)
            if not product_id or not row.get("Title"):
                continue

            for keyword, col_title in type_to_collection.items():
                if keyword in product_type or keyword in tags:
                    col_id = collection_ids.get(col_title)
                    if col_id:
                        try:
                            client.add_product_to_collection(col_id, product_id)
                            assigned += 1
                        except ShopifyAPIError:
                            pass  # May already be assigned
                    break  # Only assign to the first matching collection

    print(f"\n  {assigned} product-collection assignments made")
    return collection_ids


def create_pages(client: ShopifyClient) -> dict[str, int]:
    """Create standard informational pages."""
    step(4, "Create static pages")

    pages_to_create = [
        {
            "title": "About Us",
            "handle": "aboutus",
            "body_html": """
<h2>About Mega Home Furnishing</h2>
<p>Welcome to Mega Home Furnishing – Singapore's trusted destination for quality
home furniture. We offer an extensive collection of sofas, beds, dining sets,
wardrobes, and more, crafted to transform your living space.</p>
<p>Visit our showroom to experience our products in person, or browse our online
catalogue for the best furniture deals in Singapore.</p>
""".strip(),
        },
        {
            "title": "Gallery",
            "handle": "gallery",
            "body_html": """
<h2>Gallery</h2>
<p>Browse our gallery to see our furniture collections styled in real home settings.
Get inspired and find the perfect pieces for your space.</p>
""".strip(),
        },
        {
            "title": "Locate Us",
            "handle": "locate-us",
            "body_html": """
<h2>Find Our Showroom</h2>
<p>We welcome you to visit our showroom to experience our furniture collections
first-hand.</p>
<h3>Showroom Details</h3>
<ul>
  <li><strong>Address:</strong> Singapore (see Google Maps below)</li>
  <li><strong>Opening Hours:</strong> 11:30 am – 9:00 pm daily</li>
</ul>
<p>For enquiries, please call or WhatsApp us.</p>
""".strip(),
        },
        {
            "title": "Contact Us",
            "handle": "contact",
            "body_html": """
<h2>Contact Us</h2>
<p>We'd love to hear from you. Reach out for product enquiries, customisation
options, or to book a showroom appointment.</p>
<ul>
  <li><strong>Email:</strong> contact@megahomefurnishing.com.sg</li>
  <li><strong>Opening Hours:</strong> 11:30 am – 9:00 pm</li>
</ul>
""".strip(),
        },
        {
            "title": "Delivery & Assembly",
            "handle": "delivery-assembly",
            "body_html": """
<h2>Delivery & Assembly</h2>
<p>We provide professional delivery and assembly services across Singapore.
Our team will ensure your furniture is set up safely and correctly in your home.</p>
<h3>Delivery Information</h3>
<ul>
  <li>Delivery lead times vary by product – check individual product pages.</li>
  <li>Standard delivery is available island-wide.</li>
  <li>White-glove assembly service available upon request.</li>
</ul>
""".strip(),
        },
        {
            "title": "Warranty & Returns",
            "handle": "warranty-returns",
            "body_html": """
<h2>Warranty & Returns</h2>
<p>All our products come with a manufacturer's warranty. Please contact us within
7 days of delivery if you experience any issues.</p>
<h3>Warranty Coverage</h3>
<ul>
  <li>Structural defects are covered for 1 year from date of delivery.</li>
  <li>Fabric and upholstery: 6 months warranty.</li>
</ul>
<p>For warranty claims or returns, please email us with your order number and
photos of the issue.</p>
""".strip(),
        },
    ]

    existing_pages = {p["handle"]: p["id"] for p in client.list_pages()}
    page_ids: dict[str, int] = {}
    created = skipped = 0

    for page_info in pages_to_create:
        handle = page_info["handle"]
        if handle in existing_pages:
            page_ids[handle] = existing_pages[handle]
            print(f"  [exists]  {page_info['title']}")
            skipped += 1
        else:
            try:
                result = client.create_page(
                    title=page_info["title"],
                    body_html=page_info["body_html"],
                    handle=handle,
                )
                page_ids[handle] = result["id"]
                print(f"  [created] {page_info['title']}")
                created += 1
            except ShopifyAPIError as exc:
                print(f"  [ERROR]   {page_info['title']}: {exc}")

    print(f"\n  Pages: {created} created, {skipped} already existed")
    return page_ids


def create_navigation(client: ShopifyClient,
                       collection_ids: dict[str, int],
                       page_ids: dict[str, int]) -> None:
    """
    Build header and footer navigation menus mirroring xclusivehome.sg.
    """
    step(5, "Create navigation menus")

    # ── Header (main) menu ────────────────────────────────────────────────────
    header_items = [
        # Home – http_link
        {"title": "Home", "type": "http_link", "url": "/"},
    ]

    # Collections with dropdown items
    collection_links = [
        ("Sofas", "Sofas"),
        ("Beds & Bedframes", "Beds & Bedframes"),
        ("Dining Tables", "Dining Tables"),
        ("Coffee Tables", "Coffee Tables"),
        ("TV Consoles", "TV Consoles"),
        ("Wardrobes & Storage", "Wardrobes & Storage"),
        ("Mattresses", "Mattresses"),
    ]
    for label, col_title in collection_links:
        col_id = collection_ids.get(col_title)
        if col_id:
            header_items.append({
                "title": label,
                "type": "collection_link",
                "subject_id": col_id,
            })
        else:
            header_items.append({
                "title": label,
                "type": "http_link",
                "url": f"/collections/{label.lower().replace(' ', '-')}",
            })

    # Shop All
    header_items.append({"title": "All Products", "type": "http_link",
                          "url": "/collections/all"})

    # Gallery, About, Locate Us
    for label, handle in [("Gallery", "gallery"),
                           ("About Us", "aboutus"),
                           ("Locate Us", "locate-us")]:
        pid = page_ids.get(handle)
        if pid:
            header_items.append({
                "title": label, "type": "page_link", "subject_id": pid,
            })
        else:
            header_items.append({
                "title": label, "type": "http_link",
                "url": f"/pages/{handle}",
            })

    # ── Footer menu ───────────────────────────────────────────────────────────
    footer_items = []
    for label, handle in [
        ("About Us", "aboutus"),
        ("Contact Us", "contact"),
        ("Delivery & Assembly", "delivery-assembly"),
        ("Warranty & Returns", "warranty-returns"),
        ("Locate Us", "locate-us"),
        ("Gallery", "gallery"),
    ]:
        pid = page_ids.get(handle)
        if pid:
            footer_items.append({
                "title": label, "type": "page_link", "subject_id": pid,
            })
        else:
            footer_items.append({
                "title": label, "type": "http_link",
                "url": f"/pages/{handle}",
            })

    existing_menus = {m["handle"]: m["id"] for m in client.list_menus()}

    for title, handle, items in [
        ("Main Menu", "main-menu", header_items),
        ("Footer Menu", "footer", footer_items),
    ]:
        if handle in existing_menus:
            print(f"  [exists]  {title}")
        else:
            try:
                client.create_menu(title, handle, items)
                print(f"  [created] {title}")
            except ShopifyAPIError as exc:
                print(f"  [ERROR]   {title}: {exc}")


def upload_theme_config(client: ShopifyClient) -> None:
    """
    Push theme/config/settings_data.json and theme/templates/index.json
    to the active Vast theme in Shopify.
    """
    step(6, "Upload theme configuration to Vast")

    theme = client.get_active_theme()
    if not theme:
        print("  [SKIP] No active theme found in Shopify.")
        return

    theme_id = theme["id"]
    print(f"  Active theme: '{theme['name']}' (id={theme_id})")

    assets_to_upload = [
        (SETTINGS_JSON, "config/settings_data.json"),
        (INDEX_JSON, "templates/index.json"),
    ]

    for local_path, shopify_key in assets_to_upload:
        if not local_path.exists():
            print(f"  [SKIP] {local_path} not found")
            continue
        content = local_path.read_text(encoding="utf-8")
        try:
            client.put_asset(theme_id, shopify_key, content)
            print(f"  [uploaded] {shopify_key}")
        except ShopifyAPIError as exc:
            print(f"  [ERROR]    {shopify_key}: {exc}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  Mega Home → Shopify Migration")
    print("  Target theme: Vast (Maximize / Omni Themes)")
    print("  Design target: xclusivehome.sg layout")
    print("=" * 60)

    client = ShopifyClient(
        store_url=cfg.SHOPIFY_STORE_URL,
        access_token=cfg.SHOPIFY_ACCESS_TOKEN,
    )

    # Step 1: Convert CSV
    convert_csv()

    # Step 2: Import products
    handle_to_id = import_products(client)

    # Step 3: Collections
    collection_ids = create_collections(client, handle_to_id)

    # Step 4: Pages
    page_ids = create_pages(client)

    # Step 5: Navigation
    create_navigation(client, collection_ids, page_ids)

    # Step 6: Theme config
    upload_theme_config(client)

    print("\n" + "=" * 60)
    print("  Migration complete!")
    print("  Review your Shopify admin to verify everything looks correct.")
    print("=" * 60)


if __name__ == "__main__":
    main()
