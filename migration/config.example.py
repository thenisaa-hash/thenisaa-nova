# ─────────────────────────────────────────────────────────────────────────────
# Copy this file to config.py and fill in your actual values.
# NEVER commit config.py – it is listed in .gitignore.
# ─────────────────────────────────────────────────────────────────────────────

# ── New Shopify store (destination) ──────────────────────────────────────────
SHOPIFY_STORE_URL = "your-new-store.myshopify.com"   # without https://
SHOPIFY_ACCESS_TOKEN = "shpat_xxxxxxxxxxxxxxxxxxxx"   # Admin API access token

# Vendor name that will appear on all imported products
DEFAULT_VENDOR = "Mega Home Furnishing"

# ── Wix export file paths (source) ───────────────────────────────────────────
# Export path: Wix dashboard → Stores → Products → ⋮ → Export
WIX_PRODUCTS_CSV = "data/wix_products.csv"

# ── Optional: Shopify Payments tax settings ───────────────────────────────────
CURRENCY = "SGD"          # ISO 4217 currency code
WEIGHT_UNIT = "kg"        # kg | lb | oz | g

# ── Migration behaviour ───────────────────────────────────────────────────────
# If True, products already in Shopify (matched by SKU) will be updated.
UPDATE_EXISTING = False
# If True, products from Wix that have visible=False will be imported as Draft.
IMPORT_HIDDEN_AS_DRAFT = True
