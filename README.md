# thenisaa-nova

Generate and upgrade product images using the [Higgsfield AI](https://higgsfield.ai/) API.

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and add your Higgsfield API key:

```bash
cp .env.example .env
# then edit .env and set HF_KEY=your_api_key
```

Get your API key from [cloud.higgsfield.ai](https://cloud.higgsfield.ai/).

---

## Batch product photo upgrade — `generate_product_photos.py`

Takes a folder of raw/low-quality product photos and generates **two variations per photo**:

| Variation | Description | Format |
|-----------|-------------|--------|
| **SKU** | Hyper-realistic studio cut-out on pure white background | `1:1` (1080 × 1080) |
| **Lifestyle** | Scandinavian interior scene with ASEAN family | `16:9` |

### Usage

```bash
# Generate both SKU + lifestyle for all photos in a folder
python generate_product_photos.py --input-dir raw_photos/

# All photos share the same product type (overrides filename-based label)
python generate_product_photos.py --input-dir raw_photos/ --product-type "3-seater fabric sofa"

# Generate only SKU photos
python generate_product_photos.py --input-dir raw_photos/ --sku-only

# Generate only lifestyle photos
python generate_product_photos.py --input-dir raw_photos/ --lifestyle-only

# Save results to a custom directory
python generate_product_photos.py --input-dir raw_photos/ --output-dir results/
```

### Output structure

```
output/
├── product_a/
│   ├── sku_20260224_103045.png
│   └── lifestyle_20260224_103112.png
├── product_b/
│   ├── sku_20260224_103201.png
│   └── lifestyle_20260224_103238.png
└── ...
```

Each product gets its own subfolder named after the source filename (without extension).

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--input-dir` | *(required)* | Folder of raw product photos |
| `--product-type` | *(from filename)* | Product label injected into prompts (e.g. `sofa`) |
| `--output-dir` | `output/` | Root folder for generated images |
| `--sku-only` | — | Generate only SKU photos |
| `--lifestyle-only` | — | Generate only lifestyle photos |

### Supported input formats

`.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`

---

## Single image generation — `generate_images.py`

Generate a single image from a text prompt.

```bash
# Basic usage
python generate_images.py --prompt "A serene lake at sunset with mountains"

# With custom options
python generate_images.py \
  --prompt "A futuristic city skyline at night" \
  --resolution 4K \
  --aspect-ratio 16:9

# Interactive mode (no --prompt flag)
python generate_images.py

# Print URL only, skip saving
python generate_images.py --prompt "A golden forest" --no-save
```

| Option | Default | Description |
|--------|---------|-------------|
| `--prompt` | *(interactive)* | Text description of the image |
| `--resolution` | `2K` | Output resolution: `1K`, `2K`, `4K` |
| `--aspect-ratio` | `16:9` | Aspect ratio: `1:1`, `4:3`, `3:4`, `16:9`, `9:16`, `21:9` |
| `--camera-fixed` | `False` | Fix the camera position |
| `--output-dir` | `output/` | Directory to save generated images |
| `--no-save` | `False` | Print URL only; do not download image |
