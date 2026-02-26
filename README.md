# Higgsfield Image Enhancement Pipeline

Automates downloading product images from Google Drive and enhancing them via the [Higgsfield](https://app.higgsfield.ai) website using browser automation (Playwright).

## What it does

1. **Downloads** all images from your Google Drive folder
2. **Opens** Higgsfield in a browser (visible, non-headless by default)
3. **Logs in** with your credentials
4. **Uploads** each image and applies your product enhancement prompt
5. **Downloads** the enhanced result to `output_images/`

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in your Higgsfield login:

```env
HIGGSFIELD_EMAIL=your_email@example.com
HIGGSFIELD_PASSWORD=your_password_here
```

The Google Drive folder ID is already pre-filled from your link.

### 3. Run the pipeline

```bash
python main.py
```

This will:
- Download images from your Google Drive folder into `input_images/`
- Open a browser window and log into Higgsfield
- Process each image with the product studio prompt
- Save results to `output_images/`

---

## Run steps individually

**Only download images:**
```bash
python download_gdrive.py
```

**Only enhance images** (after downloading):
```bash
python higgsfield_automation.py
```

---

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `HIGGSFIELD_EMAIL` | *(required)* | Your Higgsfield login email |
| `HIGGSFIELD_PASSWORD` | *(required)* | Your Higgsfield password |
| `GDRIVE_FOLDER_ID` | Pre-filled | Google Drive folder ID |
| `INPUT_IMAGES_DIR` | `input_images` | Where downloaded images are saved |
| `OUTPUT_IMAGES_DIR` | `output_images` | Where enhanced images are saved |
| `HEADLESS` | `false` | Set `true` to run browser invisibly |
| `SLOW_MO` | `100` | Milliseconds between browser actions |

---

## Enhancement Prompt

The prompt used for each image instructs Higgsfield to:

- Extract **only the product** from the reference photo
- Generate a **hyper-realistic studio shot** at 1080×1080 px
- Use **pure white background** with soft shadow
- Apply **professional e-commerce lighting**
- Remove all backgrounds, props, and branding

---

## Troubleshooting

- **Login fails**: Verify credentials in `.env`. Run with `HEADLESS=false` to watch the browser.
- **Upload fails**: Higgsfield may have updated their UI. A debug screenshot is saved as `debug_screenshot.png` on errors.
- **Google Drive download fails**: Make sure the folder is shared publicly ("Anyone with the link").
- **Generation times out**: Increase the timeout in `higgsfield_automation.py` (`_wait_for_result` method).
