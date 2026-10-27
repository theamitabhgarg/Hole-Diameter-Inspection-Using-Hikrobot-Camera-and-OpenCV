from pathlib import Path
import csv
import statistics
import cv2
from measure import measure_hole, draw_diagnostic

PROJECT_DIR = Path(__file__).resolve().parent.parent
IMAGE_DIR = PROJECT_DIR / "images"
OUTPUT_DIR = PROJECT_DIR / "output"
DIAGNOSTIC_DIR = OUTPUT_DIR / "diagnostics"
for folder in (OUTPUT_DIR, DIAGNOSTIC_DIR / "22mm", DIAGNOSTIC_DIR / "24mm", DIAGNOSTIC_DIR / "unclassified"):
    folder.mkdir(parents=True, exist_ok=True)

CLASSES = {"22mm": 22.0, "24mm": 24.0}
EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
TOLERANCE_MM = 0.5


def classify_diameter(d):
    if d is None:
        return "unclassified"
    if 21.5 <= d < 22.5:
        return "22mm"
    if 23.5 <= d <= 24.5:
        return "24mm"
    return "unclassified"

measurements = []
group_pixels = {name: [] for name in CLASSES}

for folder, known_mm in CLASSES.items():
    folder_path = IMAGE_DIR / folder
    if not folder_path.is_dir():
        print(f"ERROR: Folder not found: {folder_path}")
        continue
    files = sorted(p for p in folder_path.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS)
    print(f"Reading {folder}: {len(files)} images")
    for path in files:
        image = cv2.imread(str(path))
        row = {"image": str(path.relative_to(PROJECT_DIR),), "source_folder": folder,
               "known_diameter_mm": known_mm, "diameter_px": None, "diameter_mm": None,
               "classification": "unclassified", "status": "FAILED", "error": ""}
        try:
            if image is None:
                raise ValueError("Image could not be opened")
            result = measure_hole(image)
            px = float(result["diameter_px"])
            if not (px > 0):
                raise ValueError("Invalid pixel diameter")
            group_pixels[folder].append(px)
            row.update(diameter_px=px, status="DETECTED", error="")
            # Save one diagnostic for every image; overwrite old diagnostic files.
            diagnostic = draw_diagnostic(image, result, folder)
            out_path = DIAGNOSTIC_DIR / folder / f"{path.stem}_overlay.jpg"
            if not cv2.imwrite(str(out_path), diagnostic):
                print(f"WARNING: Could not save diagnostic: {out_path}")
        except Exception as exc:
            row["error"] = str(exc)
        measurements.append(row)

if not all(group_pixels.get(name) for name in CLASSES):
    raise RuntimeError("Calibration failed: no successful measurements in one or both class folders.")

median_22_px = statistics.median(group_pixels["22mm"])
median_24_px = statistics.median(group_pixels["24mm"])
scale_22 = median_22_px / 22.0
scale_24 = median_24_px / 24.0
pixels_per_mm = (scale_22 + scale_24) / 2.0
scale_disagreement = abs(scale_22-scale_24) / ((scale_22+scale_24)/2.0) * 100.0

print("\n========== CALIBRATION (empirical from labelled samples) ==========")
print(f"22 mm median: {median_22_px:.2f} pixels")
print(f"24 mm median: {median_24_px:.2f} pixels")
print(f"Scale from 22 mm parts: {scale_22:.4f} px/mm")
print(f"Scale from 24 mm parts: {scale_24:.4f} px/mm")
print(f"Common calibration: {pixels_per_mm:.4f} px/mm")
print(f"Scale disagreement: {scale_disagreement:.2f}%")
if scale_disagreement > 5:
    print("WARNING: Scale estimates differ by >5%; results should be treated as provisional.")

for item in measurements:
    if item["status"] != "DETECTED":
        continue
    item["diameter_mm"] = item["diameter_px"] / pixels_per_mm
    item["classification"] = classify_diameter(item["diameter_mm"])
    # Copy overlay into predicted class folder as well, so all classes are easy to review.
    source_path = PROJECT_DIR / item["image"]
    image = cv2.imread(str(source_path))
    try:
        result = measure_hole(image)
        label = f"{item['diameter_mm']:.2f} mm -> {item['classification']}"
        dest = DIAGNOSTIC_DIR / item["classification"] / f"{source_path.stem}_overlay.jpg"
        cv2.imwrite(str(dest), draw_diagnostic(image, result, label))
    except Exception:
        pass

csv_path = OUTPUT_DIR / "measurement_results.csv"
try:
    csv_file = csv_path.open("w", newline="", encoding="utf-8-sig")
except PermissionError:
    csv_path = OUTPUT_DIR / "measurement_results_new.csv"
    csv_file = csv_path.open("w", newline="", encoding="utf-8-sig")
with csv_file as f:
    fields = ["image", "source_folder", "known_diameter_mm", "diameter_px", "diameter_mm", "classification", "status", "error"]
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for item in measurements:
        row = item.copy()
        for key in ("diameter_px", "diameter_mm"):
            if row[key] is not None:
                row[key] = round(row[key], 3)
        writer.writerow(row)

successful = [r for r in measurements if r["status"] == "DETECTED"]
failed = [r for r in measurements if r["status"] == "FAILED"]
print("\n========== SUMMARY ==========")
print(f"Total images: {len(measurements)}")
print(f"Successful measurements: {len(successful)}")
print(f"Detection failures: {len(failed)}")
print(f"Classified as 22mm: {sum(r['classification']=='22mm' for r in successful)}")
print(f"Classified as 24mm: {sum(r['classification']=='24mm' for r in successful)}")
print(f"Unclassified: {sum(r['classification']=='unclassified' for r in successful)}")
print(f"CSV saved to: {csv_path}")
print(f"Diagnostic images saved under: {DIAGNOSTIC_DIR}")
