
import threading
import time

import cv2

from MVS_FrameGrab import Camera
from measure import measure_hole


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

# This must match the camera's User Defined Name in MVS.
# We will confirm the correct name when the camera arrives.
CAMERA_NAME = "EngravingLinesB"

# Provisional calibration from your saved-image tests.
PIXELS_PER_MM = 7.9074

TOLERANCE_MM = 0.5

WINDOW_NAME = "Live Hole Diameter Inspection"


# --------------------------------------------------
# CLASSIFICATION
# --------------------------------------------------

def classify_diameter(diameter_mm):
    if 21.5 <= diameter_mm < 22.5:
        return "22mm"

    if 23.5 <= diameter_mm <= 24.5:
        return "24mm"

    return "CHECK PART"


# --------------------------------------------------
# DISPLAY
# --------------------------------------------------

def draw_result(frame, result, label):
    output = frame.copy()

    if result is not None:
        center = (
            round(result["cx"]),
            round(result["cy"]),
        )
        radius = round(result["radius_px"])

        cv2.circle(
            output,
            center,
            radius,
            (0, 255, 0),
            3,
        )

    if label == "22mm":
        text = "Diameter = 22mm"
        color = (0, 220, 0)
    elif label == "24mm":
        text = "Diameter = 24mm"
        color = (0, 220, 0)
    else:
        text = "CHECK PART"
        color = (0, 165, 255)

    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 3

    # Fit the label to the available image width.
    image_height, image_width = output.shape[:2]
    font_scale = 1.3

    (text_width, text_height), baseline = cv2.getTextSize(
        text, font, font_scale, thickness
    )

    if text_width + 40 > image_width:
        font_scale = max(
            0.5,
            (image_width - 40) / max(text_width, 1) * font_scale,
        )
        (text_width, text_height), baseline = cv2.getTextSize(
            text, font, font_scale, thickness
        )

    box_width = min(image_width - 10, text_width + 30)
    box_height = text_height + baseline + 25

    cv2.rectangle(
        output,
        (5, 5),
        (5 + box_width, 5 + box_height),
        (20, 20, 20),
        -1,
    )

    cv2.putText(
        output,
        text,
        (20, 10 + text_height + 10),
        font,
        font_scale,
        color,
        thickness,
        cv2.LINE_AA,
    )

    return output


# --------------------------------------------------
# LIVE CAMERA
# --------------------------------------------------

def main():
    camera = Camera(camStr=CAMERA_NAME)

    # The wrapper's initialize() method runs a continuous reconnect
    # loop, so it must run in the background.
    camera_thread = threading.Thread(
        target=camera.initialize,
        daemon=True,
    )
    camera_thread.start()

    print("Waiting for the Hikrobot camera...")
    print("Press Q in the video window to quit.")

    last_status_time = 0
    last_frame_time = 0

    try:
        while True:
            if not camera.g_bConnect:
                now = time.time()

                if now - last_status_time >= 2:
                    print("Camera not connected yet; waiting...")
                    last_status_time = now

                # Allows the window to remain responsive while waiting.
                blank = __import__("numpy").zeros(
                    (360, 640, 3), dtype="uint8"
                )
                cv2.putText(
                    blank,
                    "Waiting for Hikrobot camera...",
                    (20, 180),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 200, 255),
                    2,
                    cv2.LINE_AA,
                )
                cv2.imshow(WINDOW_NAME, blank)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

                time.sleep(0.05)
                continue

            # This wrapper retrieves one frame from the MVS SDK.
            frame = camera.get_image_mv()

            if frame is None:
                time.sleep(0.01)
                continue

            last_frame_time = time.time()

            try:
                result = measure_hole(frame)
                diameter_px = float(result["diameter_px"])
                diameter_mm = diameter_px / PIXELS_PER_MM

                label = classify_diameter(diameter_mm)
                display = draw_result(frame, result, label)

            except Exception:
                display = draw_result(frame, None, "CHECK PART")

            cv2.imshow(WINDOW_NAME, display)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        print("Stopping live inspection...")

    finally:
        cv2.destroyAllWindows()

        # Best-effort camera cleanup. The existing wrapper has a
        # reconnect loop, so complete shutdown should be verified
        # when tested with the actual camera.
        try:
            camera.g_bConnect = False
            camera.clear()
        except Exception as exc:
            print(f"Camera cleanup message: {exc}")

        print("Live inspection window closed.")


if __name__ == "__main__":
    main()
