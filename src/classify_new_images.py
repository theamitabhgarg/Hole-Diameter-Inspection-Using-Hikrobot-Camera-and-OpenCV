"""Optional classification for new images using pixel-diameter distributions learned
from the existing labelled folders. This is only a prototype sorter, not a calibrated
millimetre measurement. Use after reviewing analyze_dataset.py outputs and overlays.
"""
import csv, json, shutil
from pathlib import Path
import cv2
from config import IMAGES_DIR, OUTPUT_DIR, SETTINGS_FILE, SUPPORTED_EXTENSIONS
from measure import measure_hole


def main():
    if not SETTINGS_FILE.exists():
        raise SystemExit("Run python src/train_pixel_classifier.py first.")
    settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    threshold_px = settings.get("pixel_threshold_between_classes")
    if threshold_px is None:
        raise SystemExit("Classifier threshold unavailable. The labelled pixel distributions may overlap.")
    input_dir = IMAGES_DIR / "to_classify"
    if not input_dir.exists():
        raise SystemExit(f"Create {input_dir} and place new images there.")
    for folder in ["22mm", "24mm", "unclassified"]:
        (OUTPUT_DIR / folder).mkdir(parents=True, exist_ok=True)
    rows = []
    for path in sorted(input_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        img = cv2.imread(str(path))
        try:
            m = measure_hole(img)
            dpx = 2*m["radius_px"]
            # Direction determined from training medians.
            if settings["median_px_22mm"] < settings["median_px_24mm"]:
                category = "22mm" if dpx < threshold_px else "24mm"
            else:
                category = "22mm" if dpx > threshold_px else "24mm"
            message = "Prototype classification from labelled pixel distributions; not mm calibration"
            shutil.copy2(path, OUTPUT_DIR[category] / path.name)
            rows.append({"filename": path.name, "diameter_px": dpx, "category": category, "note": message})
            print(f"{path.name}: {dpx:.2f}px -> {category}")
        except Exception as e:
            shutil.copy2(path, OUTPUT_DIR["unclassified"] / path.name)
            rows.append({"filename": path.name, "diameter_px": "", "category": "unclassified", "note": str(e)})
            print(f"{path.name}: unclassified ({e})")
    with (OUTPUT_DIR / "new_image_classifications.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["filename","diameter_px","category","note"])
        w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
