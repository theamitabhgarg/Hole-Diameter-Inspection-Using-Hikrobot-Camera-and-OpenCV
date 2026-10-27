
import cv2
import numpy as np

MIN_CORE_AREA = 3000
MAX_CORE_AREA = 100000
MIN_CORE_SIZE = 60
MAX_CORE_SIZE = 300
MAX_AXIS_DIFFERENCE_RATIO = 0.15


def _gray(image):
    if image is None:
        raise ValueError("Could not read image")

    if image.ndim == 2:
        return image.copy()

    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def measure_hole(image):
    gray = _gray(image)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0.8)

    # Normalize local contrast to reduce sensitivity to lighting.
    normalized = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    ).apply(blurred)

    # Adaptive threshold instead of a fixed darkness threshold.
    mask = cv2.adaptiveThreshold(
        normalized,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        51,
        5
    )

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (3, 3)
    )
    mask = cv2.morphologyEx(
        mask, cv2.MORPH_CLOSE, kernel
    )

    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask, 8
    )

    candidates = []

    for i in range(1, count):
        x, y, w, h, area = map(int, stats[i])

        if not MIN_CORE_AREA <= area <= MAX_CORE_AREA:
            continue

        if not (
            MIN_CORE_SIZE <= w <= MAX_CORE_SIZE
            and MIN_CORE_SIZE <= h <= MAX_CORE_SIZE
        ):
            continue

        if x <= 0 or y <= 0:
            continue

        if x + w >= gray.shape[1] or y + h >= gray.shape[0]:
            continue

        component = np.uint8(labels == i) * 255
        contours, _ = cv2.findContours(
            component,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_NONE
        )

        if not contours:
            continue

        contour = max(contours, key=cv2.contourArea)

        if len(contour) < 5:
            continue

        (cx, cy), (a, b), angle = cv2.fitEllipse(contour)

        major = max(a, b)
        minor = min(a, b)

        if minor <= 0:
            continue

        axis_difference = (major - minor) / major

        # Keep candidates reasonably circular, but avoid the
        # overly strict circularity rejection from the previous version.
        if axis_difference > MAX_AXIS_DIFFERENCE_RATIO:
            continue

        contour_area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)

        circularity = (
            4 * np.pi * contour_area / perimeter**2
            if perimeter > 0 else 0
        )

        # Prefer round, compact components.
        score = contour_area * (minor / major) * circularity

        candidates.append({
            "score": score,
            "cx": cx,
            "cy": cy,
            "major": major,
            "minor": minor,
            "angle": angle,
            "contour": contour,
            "area": contour_area,
            "circularity": circularity,
        })

    if not candidates:
        raise ValueError(
            "Hole not detected reliably. Keep part flat and in focus."
        )

    best = max(candidates, key=lambda c: c["score"])

    diameter = (best["major"] + best["minor"]) / 2.0

    return {
        "cx": float(best["cx"]),
        "cy": float(best["cy"]),
        "radius_px": float(diameter / 2),
        "diameter_px": float(diameter),
        "axis_a_px": float(best["major"]),
        "axis_b_px": float(best["minor"]),
        "fit_std_px": float((best["major"] - best["minor"]) / 2),
        "axis_difference_ratio": float(
            (best["major"] - best["minor"]) / best["major"]
        ),
        "score": float(best["score"]),
        "threshold": -1,
        "area_px": float(best["area"]),
        "circularity": float(best["circularity"]),
        "angle_deg": float(best["angle"]),
        "contour": best["contour"],
    }


def draw_diagnostic(image, result, label=None):
    output = image.copy()

    center = (
        int(round(result["cx"])),
        int(round(result["cy"]))
    )

    axes = (
        max(1, int(round(result["axis_a_px"] / 2))),
        max(1, int(round(result["axis_b_px"] / 2)))
    )

    cv2.ellipse(
        output,
        center,
        axes,
        result.get("angle_deg", 0),
        0,
        360,
        (0, 255, 0),
        3
    )

    text = f"Inner opening: {result['diameter_px']:.1f} px"

    if label:
        text += f" | {label}"

    cv2.putText(
        output, text, (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX, 0.85,
        (0, 0, 0), 4, cv2.LINE_AA
    )

    cv2.putText(
        output, text, (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX, 0.85,
        (0, 255, 0), 2, cv2.LINE_AA
    )

    return output
