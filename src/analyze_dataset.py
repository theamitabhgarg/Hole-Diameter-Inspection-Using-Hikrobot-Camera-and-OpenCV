"""Analyze the existing images/22mm and images/24mm dataset.

Run from project root:
    python src/analyze_dataset.py

Primary output is a diameter in pixels. Optional provisional scale fitting uses the
folder labels (22 and 24 mm) as assumed nominal values. This is NOT an independent
calibration and must not be presented as validated metrology.
"""
import csv
import json
import statistics
from pathlib import Path
import cv2

from config import IMAGES_DIR, OUTPUT_DIR, SETTINGS_FILE, LABEL_FOLDERS, SUPPORTED_EXTENSIONS, PIXELS_PER_MM
from measure import measure_hole, draw_diagnostic


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "diagnostics").mkdir(parents=True, exist_ok=True)
    records = []
    for folder, nominal_mm in LABEL_FOLDERS.items():
        folder_path = IMAGES_DIR / folder
        if not folder_path.exists():
            print(f"WARNING: Missing folder: {folder_path}")
            continue
        for path in sorted(folder_path.iterdir()):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            img = cv2.imread(str(path))
            try:
                if img is None:
                    raise ValueError("OpenCV could not read file")
                m = measure_hole(img)
                dpx = 2 * m["radius_px"]
                records.append({
                    "filename": path.name, "source_folder": folder,
                    "folder_nominal_mm": nominal_mm, "status": "measured",
                    "diameter_px": dpx, "center_x_px": m["cx"], "center_y_px": m["cy"],
                    "radius_px": m["radius_px"], "circularity": m["circularity"],
                    "fit_std_px": m["fit_std_px"], "error": ""
                })
                cv2.imwrite(str(OUTPUT_DIR / "diagnostics" / f"{folder}_{path.stem}_overlay.png"),
                            draw_diagnostic(img, m, folder))
                print(f"{folder}/{path.name}: {dpx:.2f} px")
            except Exception as e:
                records.append({
                    "filename": path.name, "source_folder": folder,
                    "folder_nominal_mm": nominal_mm, "status": "failed",
                    "diameter_px": "", "center_x_px": "", "center_y_px": "",
                    "radius_px": "", "circularity": "", "fit_std_px": "", "error": str(e)
                })
                cv2.imwrite(str(OUTPUT_DIR / "diagnostics" / f"{folder}_{path.stem}_FAILED.png"), img) if img is not None else None
                print(f"{folder}/{path.name}: FAILED - {e}")

    csv_path = OUTPUT_DIR / "measurements.csv"
    fields = ["filename","source_folder","folder_nominal_mm","status","diameter_px",
              "center_x_px","center_y_px","radius_px","circularity","fit_std_px","error"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

    success = [r for r in records if r["status"] == "measured"]
    summary = {}
    for folder in LABEL_FOLDERS:
        vals = [r["diameter_px"] for r in success if r["source_folder"] == folder]
        summary[folder] = {
            "count_measured": len(vals),
            "mean_diameter_px": statistics.mean(vals) if vals else None,
            "std_diameter_px_sample": statistics.stdev(vals) if len(vals) > 1 else None,
            "min_diameter_px": min(vals) if vals else None,
            "max_diameter_px": max(vals) if vals else None,
        }
    result = {"counts": {"images_found": len(records), "measured": len(success),
                         "failed": len(records)-len(success)}, "summary": summary}
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("\nSummary:")
    print(json.dumps(result, indent=2))
    print(f"\nSaved measurements: {csv_path}")
    print(f"Saved overlays: {OUTPUT_DIR / 'diagnostics'}")
    if PIXELS_PER_MM:
        print(f"Configured scale: {PIXELS_PER_MM} px/mm; conversion can be added once independently established.")
    else:
        print("No physical calibration provided: measurements are in pixels, not mm.")
        print("Folder names are class labels, not a physical calibration reference.")


if __name__ == "__main__":
    main()
