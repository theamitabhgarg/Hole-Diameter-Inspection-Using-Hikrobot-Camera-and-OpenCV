
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

IMAGES_DIR = ROOT / "images"
OUTPUT_DIR = ROOT / "output"
SETTINGS_FILE = ROOT / "project_settings.json"

# Initial ROI around the central black hole.
# Format: (x, y, width, height)
# Based on the two sample images; verify against the other images.
ROI = None

BLUR_KERNEL = 5

# Thresholding settings
THRESHOLD_MODE = "otsu"  # "otsu" or "adaptive"
ADAPTIVE_BLOCK_SIZE = 31
ADAPTIVE_C = 5

# Candidate filtering
MIN_CONTOUR_AREA = 100
MIN_CIRCULARITY = 0.45

# Physical calibration is not yet available.
PIXELS_PER_MM = None

LABEL_FOLDERS = {
    "22mm": 22.0,
    "24mm": 24.0,
}

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"
}
