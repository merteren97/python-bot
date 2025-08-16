import mss
import numpy as np
import cv2
import pyautogui
import time

class ScreenCapture:
    def __init__(self, region=None):
        self.region = None
        self.set_region(region)
        try:
            self.sct = mss.mss()
        except Exception:
            self.sct = None

    def set_region(self, region):
        if region is None:
            self.region = None
            return
        if isinstance(region, dict):
            self.region = {
                "left": int(region["left"]),
                "top": int(region["top"]),
                "width": int(region["width"]),
                "height": int(region["height"])
            }
        else:
            left, top, width, height = region
            self.region = {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}

    def capture(self):
        if self.region is None:
            raise ValueError("Region not set for ScreenCapture.")
        # try mss
        if self.sct:
            try:
                s = self.sct.grab(self.region)
                arr = np.array(s)  # BGRA usually
                if arr.shape[2] == 4:
                    bgr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
                else:
                    bgr = arr[..., :3]
                return bgr
            except Exception as e:
                # fallback to pyautogui
                print("[ScreenCapture] mss error -> fallback pyautogui:", e)
                time.sleep(0.01)
        # fallback
        left = self.region["left"]; top = self.region["top"]
        w = self.region["width"]; h = self.region["height"]
        img = pyautogui.screenshot(region=(left, top, w, h))
        arr = np.array(img)  # RGB
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        return bgr
