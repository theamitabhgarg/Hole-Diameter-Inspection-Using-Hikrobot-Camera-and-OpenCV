import os
import sys
import ctypes
import traceback
import csv
from datetime import datetime

import cv2
import numpy as np

# Hikrobot SDK configuration
DLL_DIR = r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64"
SDK_DIR = r"D:\MVS\Development\Samples\Python\MvImport"
CAMERA_IP = "192.168.1.20"

if not os.path.isdir(DLL_DIR):
    raise FileNotFoundError(f"Hikrobot DLL directory not found: {DLL_DIR}")
if not os.path.isdir(SDK_DIR):
    raise FileNotFoundError(f"Hikrobot SDK directory not found: {SDK_DIR}")

os.add_dll_directory(DLL_DIR)
sys.path.insert(0, SDK_DIR)

from MvCameraControl_class import *
from measure import measure_hole

# Pixel-based boundary from the labelled image dataset.
# This is not a physical mm calibration.
PIXEL_CLASSIFICATION_BOUNDARY = (211.87 + 260.74) / 2.0

WINDOW_NAME = "Hikrobot Live Diameter Inspection"
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 1.2
FONT_THICKNESS = 3

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
CSV_PATH = os.path.join(OUTPUT_DIR, "live_inspection_results.csv")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def classify_diameter(diameter_px):
    try:
        diameter_px = float(diameter_px)
    except (TypeError, ValueError):
        return "CHECK PART"

    if not np.isfinite(diameter_px) or diameter_px <= 0:
        return "CHECK PART"

    if diameter_px < PIXEL_CLASSIFICATION_BOUNDARY:
        return "22mm"
    return "24mm"


def inspect_frame(image):
    try:
        result = measure_hole(image)
        if not isinstance(result, dict):
            return None, "CHECK PART"

        diameter_px = result.get("diameter_px")
        if diameter_px is None:
            return None, "CHECK PART"

        diameter_px = float(diameter_px)
        return diameter_px, classify_diameter(diameter_px)
    except Exception:
        return None, "CHECK PART"


def draw_result(image, diameter_px, label, saved_message=False):
    display = image.copy()
    height, width = display.shape[:2]

    if diameter_px is None:
        main_text = "CHECK PART"
    else:
        main_text = f"{label} | Opening: {diameter_px:.1f} px"

    color = (0, 200, 0) if label in ("22mm", "24mm") else (0, 0, 255)
    (text_width, text_height), _ = cv2.getTextSize(
        main_text, FONT, FONT_SCALE, FONT_THICKNESS
    )
    x = max(10, (width - text_width) // 2)
    y = min(max(text_height + 20, 50), height - 10)

    cv2.putText(
        display, main_text, (x, y), FONT, FONT_SCALE,
        (0, 0, 0), FONT_THICKNESS + 2, cv2.LINE_AA
    )
    cv2.putText(
        display, main_text, (x, y), FONT, FONT_SCALE,
        color, FONT_THICKNESS, cv2.LINE_AA
    )

    help_text = "S: save inspection    Q: quit"
    cv2.putText(
        display, help_text, (15, height - 18),
        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA
    )

    if saved_message:
        cv2.putText(
            display, "Inspection saved", (15, 65),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA
        )

    return display


def save_inspection(diameter_px, label):
    file_exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp", "diameter_px", "classification", "boundary_px"
            ],
        )
        if not file_exists or os.path.getsize(CSV_PATH) == 0:
            writer.writeheader()

        writer.writerow({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "diameter_px": "" if diameter_px is None else round(diameter_px, 2),
            "classification": label,
            "boundary_px": round(PIXEL_CLASSIFICATION_BOUNDARY, 3),
        })


def find_camera():
    device_list = MV_CC_DEVICE_INFO_LIST()
    device_types = MV_GIGE_DEVICE | MV_USB_DEVICE

    ret = MvCamera.MV_CC_EnumDevices(device_types, device_list)
    if ret != 0:
        raise RuntimeError(
            f"Camera enumeration failed: 0x{ret & 0xFFFFFFFF:08X}"
        )
    if device_list.nDeviceNum == 0:
        raise RuntimeError("No Hikrobot cameras found.")

    print(f"Found {device_list.nDeviceNum} camera(s).")

    for index in range(device_list.nDeviceNum):
        info = ctypes.cast(
            device_list.pDeviceInfo[index],
            ctypes.POINTER(MV_CC_DEVICE_INFO)
        ).contents

        if info.nTLayerType != MV_GIGE_DEVICE:
            continue

        ip_value = info.SpecialInfo.stGigEInfo.nCurrentIp
        ip_address = ".".join(
            str((ip_value >> shift) & 0xFF)
            for shift in (24, 16, 8, 0)
        )
        name = bytes(
            info.SpecialInfo.stGigEInfo.chUserDefinedName
        ).split(b"\0", 1)[0].decode(errors="replace")

        print(f"Camera {index}: name={name}, IP={ip_address}")
        if ip_address == CAMERA_IP:
            return info

    raise RuntimeError(f"Camera at {CAMERA_IP} was not found.")


def main():
    camera = MvCamera()
    created = False
    opened = False
    grabbing = False
    saved_message = False
    last_diameter_px = None
    last_label = "CHECK PART"

    try:
        device_info = find_camera()

        ret = camera.MV_CC_CreateHandle(device_info)
        if ret != 0:
            raise RuntimeError(
                f"CreateHandle failed: 0x{ret & 0xFFFFFFFF:08X}"
            )
        created = True

        ret = camera.MV_CC_OpenDevice()
        if ret != 0:
            raise RuntimeError(
                f"OpenDevice failed: 0x{ret & 0xFFFFFFFF:08X}"
            )
        opened = True
        print("Camera opened successfully.")

        ret = camera.MV_CC_SetEnumValue("TriggerMode", 0)
        if ret != 0:
            print(
                "Warning: could not disable trigger mode: "
                f"0x{ret & 0xFFFFFFFF:08X}"
            )

        ret = camera.MV_CC_StartGrabbing()
        if ret != 0:
            raise RuntimeError(
                f"StartGrabbing failed: 0x{ret & 0xFFFFFFFF:08X}"
            )
        grabbing = True

        payload_size = MVCC_INTVALUE()
        ret = camera.MV_CC_GetIntValue("PayloadSize", payload_size)
        if ret != 0:
            raise RuntimeError(
                f"PayloadSize query failed: 0x{ret & 0xFFFFFFFF:08X}"
            )

        buffer_size = payload_size.nCurValue
        if buffer_size <= 0:
            raise RuntimeError(f"Invalid camera payload size: {buffer_size}")

        source_buffer = (ctypes.c_ubyte * buffer_size)()
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

        print("Live feed started. Press S to save, Q to quit.")
        print(f"Pixel classification boundary: {PIXEL_CLASSIFICATION_BOUNDARY:.3f} px")
        print(f"CSV output: {CSV_PATH}")

        while True:
            frame_info = MV_FRAME_OUT_INFO_EX()
            ret = camera.MV_CC_GetOneFrameTimeout(
                source_buffer, buffer_size, frame_info, 1000
            )

            if ret != 0:
                print(f"Frame retrieval failed: 0x{ret & 0xFFFFFFFF:08X}")
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    break
                continue

            width = frame_info.nWidth
            height = frame_info.nHeight
            frame_length = frame_info.nFrameLen
            if width <= 0 or height <= 0 or frame_length <= 0:
                print("Invalid frame received; skipping.")
                continue

            convert_param = MV_CC_PIXEL_CONVERT_PARAM()
            ctypes.memset(
                ctypes.byref(convert_param), 0, ctypes.sizeof(convert_param)
            )
            convert_param.nWidth = width
            convert_param.nHeight = height
            convert_param.pSrcData = ctypes.cast(
                source_buffer, ctypes.POINTER(ctypes.c_ubyte)
            )
            convert_param.nSrcDataLen = frame_length
            convert_param.enSrcPixelType = frame_info.enPixelType
            convert_param.enDstPixelType = PixelType_Gvsp_BGR8_Packed

            destination_size = width * height * 3
            destination_buffer = (ctypes.c_ubyte * destination_size)()
            convert_param.pDstBuffer = ctypes.cast(
                destination_buffer, ctypes.POINTER(ctypes.c_ubyte)
            )
            convert_param.nDstBufferSize = destination_size

            ret = camera.MV_CC_ConvertPixelType(convert_param)
            if ret != 0:
                print(f"Pixel conversion failed: 0x{ret & 0xFFFFFFFF:08X}")
                continue

            image = np.frombuffer(
                destination_buffer, dtype=np.uint8
            ).reshape((height, width, 3)).copy()

            last_diameter_px, last_label = inspect_frame(image)
            display = draw_result(
                image, last_diameter_px, last_label, saved_message
            )
            cv2.imshow(WINDOW_NAME, display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("s"):
                save_inspection(last_diameter_px, last_label)
                saved_message = True
                print(
                    f"Saved: diameter_px={last_diameter_px}, "
                    f"classification={last_label}"
                )
            else:
                saved_message = False

    except Exception as exc:
        print(f"\nERROR: {exc}")
        traceback.print_exc()

    finally:
        cv2.destroyAllWindows()

        if grabbing:
            try:
                camera.MV_CC_StopGrabbing()
                print("Stopped image acquisition.")
            except Exception as exc:
                print(f"Warning while stopping acquisition: {exc}")

        if opened:
            try:
                camera.MV_CC_CloseDevice()
                print("Camera closed.")
            except Exception as exc:
                print(f"Warning while closing camera: {exc}")

        if created:
            try:
                camera.MV_CC_DestroyHandle()
            except Exception as exc:
                print(f"Warning while destroying camera handle: {exc}")

        print("Camera resources released.")


if __name__ == "__main__":
    main()
