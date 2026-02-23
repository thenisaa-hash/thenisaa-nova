# thenisaa-nova

Generate images using the [Higgsfield AI](https://higgsfield.ai/) API.

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set your Higgsfield API key:

```bash
export HF_KEY=your_api_key
```

Or create a `.env` file:

```
HF_KEY=your_api_key
```

Get your API key from [cloud.higgsfield.ai](https://cloud.higgsfield.ai/).

## Usage

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

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--prompt` | *(interactive)* | Text description of the image |
| `--resolution` | `2K` | Output resolution: `1K`, `2K`, `4K` |
| `--aspect-ratio` | `16:9` | Aspect ratio: `1:1`, `4:3`, `3:4`, `16:9`, `9:16`, `21:9` |
| `--camera-fixed` | `False` | Fix the camera position |
| `--output-dir` | `output/` | Directory to save generated images |
| `--no-save` | `False` | Print URL only; do not download image |

Generated images are saved to the `output/` directory with a timestamped filename.
