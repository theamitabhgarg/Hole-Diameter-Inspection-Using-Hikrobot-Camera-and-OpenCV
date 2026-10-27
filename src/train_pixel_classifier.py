"""Derive a simple pixel-diameter sorting threshold from the labelled image folders.

This uses existing folder labels as training labels; it is not a dimensional calibration.
"""
import json, statistics
from pathlib import Path
import cv2
from config import IMAGES_DIR, SETTINGS_FILE, LABEL_FOLDERS, SUPPORTED_EXTENSIONS
from measure import measure_hole


def main():
    distributions = {}
    for folder in LABEL_FOLDERS:
        p = IMAGES_DIR / folder
        vals = []
        if p.exists():
            for path in sorted(p.iterdir()):
                if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    img = cv2.imread(str(path))
                    try:
                        m = measure_hole(img)
                        vals.append(2*m["radius_px"])
                    except Exception as e:
                        print(f"Skipped {path.name}: {e}")
        if not vals:
            raise SystemExit(f"No successful diameter measurements in {p}. Inspect overlays/settings first.")
        distributions[folder] = vals

    med22 = statistics.median(distributions["22mm"])
    med24 = statistics.median(distributions["24mm"])
    low22, high22 = min(distributions["22mm"]), max(distributions["22mm"])
    low24, high24 = min(distributions["24mm"]), max(distributions["24mm"])
    if med22 == med24:
        threshold = None
        overlap = True
    else:
        threshold = (med22 + med24) / 2
        overlap = max(low22, low24) >= min(high22, high24)

    settings = {
        "median_px_22mm": med22, "median_px_24mm": med24,
        "range_px_22mm": [low22, high22], "range_px_24mm": [low24, high24],
        "pixel_threshold_between_classes": threshold,
        "observed_pixel_ranges_overlap": overlap,
        "warning": "Prototype sorting threshold derived from labelled folders; not a physical calibration or validated inspection decision."
    }
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    print(json.dumps(settings, indent=2))
    print(f"Saved {SETTINGS_FILE}")
    if overlap:
        print("WARNING: observed class pixel ranges overlap. Simple threshold may misclassify images.")
    if threshold is None:
        print("ERROR: class medians are identical; no usable threshold from this detector.")


if __name__ == "__main__":
    main()
