# Mega Home Furnishing → Shopify Migration

Migrate **megahomefurnishing.com.sg** (Wix) to a new Shopify store using the
**Vast** theme (by Omni Themes / Maximize), styled to match the layout of
[xclusivehome.sg](https://www.xclusivehome.sg/).

---

## Repository Structure

```
thenisaa-nova/
├── migration/
│   ├── config.example.py       ← Copy to config.py and fill credentials
│   ├── requirements.txt        ← Python dependencies
│   ├── wix_to_shopify.py       ← Convert Wix CSV → Shopify CSV
│   ├── shopify_api.py          ← Shopify Admin REST API client
│   └── run_migration.py        ← Full migration orchestrator (run this)
├── theme/
│   ├── config/
│   │   └── settings_data.json  ← Vast theme global settings (colours, fonts…)
│   └── templates/
│       └── index.json          ← Homepage template sections (xclusivehome layout)
├── data/                       ← Put your Wix export CSV here (git-ignored)
└── README.md
```

---

## Quick-Start Guide

### Prerequisites

| Requirement | Where to get it |
|---|---|
| Python 3.11+ | https://python.org |
| Shopify store with **Vast** theme installed | Shopify Admin → Online Store → Themes |
| Shopify Admin API access token | Shopify Admin → Apps → App & sales channel settings → Develop apps |

---

### Step 1 – Install Python dependencies

```bash
cd thenisaa-nova
pip install -r migration/requirements.txt
```

---

### Step 2 – Configure credentials

```bash
cp migration/config.example.py migration/config.py
```

Open `migration/config.py` and fill in:

```python
SHOPIFY_STORE_URL    = "your-store.myshopify.com"
SHOPIFY_ACCESS_TOKEN = "shpat_xxxxxxxxxxxxxxxxxxxx"
DEFAULT_VENDOR       = "Mega Home Furnishing"
```

> **How to get an Admin API access token**
> 1. Shopify Admin → Settings → Apps and sales channels
> 2. Click **Develop apps** → **Create an app**
> 3. Under *Configuration*, enable these **Admin API scopes**:
>    - `read_products`, `write_products`
>    - `read_collections`, `write_collections`
>    - `read_content`, `write_content`
>    - `read_themes`, `write_themes`
>    - `read_online_store_navigation`, `write_online_store_navigation`
> 4. Click **Install app** → copy the **Admin API access token** shown once.

---

### Step 3 – Export products from Wix

1. Log in to your **Wix dashboard** → **Wix Stores** → **Products**
2. Click the **⋮ (More actions)** button (top right) → **Export Products**
3. Save the downloaded file as **`data/wix_products.csv`** inside this repo folder.

---

### Step 4 – Run the migration

```bash
python migration/run_migration.py
```

This runs 6 steps automatically:

| Step | What it does |
|---|---|
| 1 | Converts `data/wix_products.csv` → `data/shopify_products.csv` |
| 2 | Creates all products in your Shopify store via Admin API |
| 3 | Creates 10 collections (Sofas, Beds, Dining…) and assigns products |
| 4 | Creates 6 pages (About Us, Gallery, Locate Us, Contact, Delivery, Warranty) |
| 5 | Builds **Main Menu** and **Footer Menu** matching xclusivehome.sg navigation |
| 6 | Pushes `theme/config/settings_data.json` + `theme/templates/index.json` to your active Vast theme |

---

### Step 5 – Review and customise in Shopify Admin

After migration:

1. **Shopify Admin → Online Store → Themes → Customize**
2. The homepage will have these sections in order (xclusivehome.sg layout):

   | Section | Description |
   |---|---|
   | Announcement Bar | "Free delivery on orders above $500" |
   | Hero Slideshow (3 slides) | Full-width banner with CTA buttons |
   | Shop by Category (3×2 grid) | Sofas, Beds, Dining, Coffee Tables, TV Consoles, Wardrobes |
   | Value Propositions (4 icons) | Free Delivery, Quality, Assembly, Warranty |
   | New Arrivals (product grid) | 8 products from *new-arrivals* collection |
   | Customise Banner | Image + text + "Book a Showroom Visit" CTA |
   | Bestsellers (product carousel) | 8 products from *sofas* collection |
   | Gallery (6-image grid) | Links to collections and gallery page |
   | Showroom CTA | Image + text + "Get Directions" button |
   | Newsletter | Email sign-up with dark background |

3. **Add your images** – click each section in the theme editor and upload banner/gallery images.
4. **Update contact details** – edit pages via Shopify Admin → Online Store → Pages.

---

### Optional: Convert CSV only (without API import)

```bash
python migration/wix_to_shopify.py \
    --input  data/wix_products.csv \
    --output data/shopify_products.csv \
    --vendor "Mega Home Furnishing"
```

Then import `data/shopify_products.csv` manually:
**Shopify Admin → Products → Import → Upload CSV**.

---

## Theme Colour Palette (Vast / xclusivehome.sg inspired)

| Token | Hex | Use |
|---|---|---|
| Background 1 | `#ffffff` | Main page background |
| Background 2 | `#f5f0eb` | Alternate section background (warm off-white) |
| Text | `#1a1a1a` | All body text |
| Accent 1 (Gold) | `#b08d57` | Buttons, highlights |
| Accent 2 (Brown) | `#8b6f47` | Hover states |
| Announcement bar | `#1a1a1a` | Top bar background |

---

## Navigation Structure (mirrors xclusivehome.sg)

**Main Menu (header)**
- Home
- Sofas
- Beds & Bedframes
- Dining Tables
- Coffee Tables
- TV Consoles
- Wardrobes & Storage
- Mattresses
- All Products
- Gallery
- About Us
- Locate Us

**Footer Menu**
- About Us · Contact Us · Delivery & Assembly · Warranty & Returns · Locate Us · Gallery

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError: config` | Run `cp migration/config.example.py migration/config.py` and fill in credentials |
| `403 Forbidden` from Shopify API | Check API scopes – all 5 write scopes must be enabled |
| `429 Too Many Requests` | Script retries automatically with exponential back-off |
| Wix CSV not found | Place Wix export at `data/wix_products.csv` |
| Images not showing after import | Images must be publicly accessible URLs – Wix image URLs should work directly |
| Theme sections look wrong | In Shopify Theme Editor, reset the homepage template and re-apply `theme/templates/index.json` via the migration script |

---

## Data Security

- **`migration/config.py`** is git-ignored – never commit API tokens
- **`data/`** directory is git-ignored – product CSVs stay local
