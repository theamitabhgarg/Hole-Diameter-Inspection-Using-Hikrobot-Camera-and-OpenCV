
from pathlib import Path

import cv2
from measure import measure_hole, draw_diagnostic

# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
IMAGE_DIR = PROJECT_DIR / "images"
OUTPUT_DIR = PROJECT_DIR / "live_demo_output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Existing empirical calibration from calibrate.py.
# We will validate this before relying on live classifications.
PIXELS_PER_MM = 7.9074

TOLERANCE_MM = 0.5

CLASSES = {
    "22mm": 22.0,
    "24mm": 24.0,
}

EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"
}


def classify_diameter(diameter_mm):
    """Return a nominal class only when inside its tolerance."""

    if 21.5 <= diameter_mm < 22.5:
        return "22 mm"

    if 23.5 <= diameter_mm <= 24.5:
        return "24 mm"

    return "CHECK PART"


def add_result_text(image, label):
    """Display the diameter classification in large text."""

    output = image.copy()

    if label == "22 mm":
        text = "Diameter = 22mm"
        color = (0, 200, 0)
    elif label == "24 mm":
        text = "Diameter = 24mm"
        color = (0, 200, 0)
    else:
        text = "CHECK PART"
        color = (0, 140, 255)

    # Scale the banner to fit the image width.
    height, width = output.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.3
    thickness = 3

    (text_width, text_height), baseline = cv2.getTextSize(
        text, font, font_scale, thickness
    )

    banner_width = min(width, text_width + 40)
    banner_height = text_height + baseline + 30

    cv2.rectangle(
        output, (10, 10),
        (10 + banner_width, 10 + banner_height),
        (20, 20, 20), -1
    )

    cv2.putText(
        output, text,
        (25, 10 + text_height + 15),
        font, font_scale, color, thickness, cv2.LINE_AA
    )

    return output



def process_image(image_path, source_class):
    image = cv2.imread(str(image_path))

    if image is None:
        print(f"Could not read: {image_path.name}")
        return

    try:
        result = measure_hole(image)

        diameter_px = float(result["diameter_px"])
        diameter_mm = diameter_px / PIXELS_PER_MM

        label = classify_diameter(diameter_mm)

        # Draw the detected hole boundary.
        diagnostic = draw_diagnostic(image, result)

        # Display only the nominal class in the large label.
        diagnostic = add_result_text(diagnostic, label)

        output_folder = OUTPUT_DIR / source_class
        output_folder.mkdir(parents=True, exist_ok=True)

        output_path = output_folder / f"{image_path.stem}_result.jpg"

        if not cv2.imwrite(str(output_path), diagnostic):
            raise OSError(f"Could not save image: {output_path}")

        print(
            f"{image_path.name}: "
            f"{diameter_px:.1f} px -> {label}"
        )

    except Exception as exc:
        print(f"FAILED: {image_path.name}: {exc}")


def main():
    total = 0

    for source_class in CLASSES:
        folder = IMAGE_DIR / source_class

        if not folder.is_dir():
            print(f"Missing folder: {folder}")
            continue

        images = sorted(
            path for path in folder.iterdir()
            if path.is_file()
            and path.suffix.lower() in EXTENSIONS
        )

        print(f"\nProcessing {source_class}: {len(images)} images")

        for image_path in images:
            process_image(image_path, source_class)
            total += 1

    print("\nImage test completed.")
    print(f"Images processed: {total}")
    print(f"Results saved in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
