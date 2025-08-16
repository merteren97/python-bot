import cv2
import numpy as np

class HealthChecker:
    def __init__(self, light_hsv, dark_hsv, low_threshold=30.0, key_on_low=None, input_ctrl=None, method="projection"):
        self.light_hsv = light_hsv
        self.dark_hsv = dark_hsv
        self.low_threshold = low_threshold
        self.key_on_low = key_on_low
        self.input_ctrl = input_ctrl
        self.active = True
        self.method = method  # 'pixel', 'projection', 'contour'

    def set_light_hsv(self, lower, upper):
        self.light_hsv = (tuple(lower), tuple(upper))

    def set_dark_hsv(self, lower, upper):
        self.dark_hsv = (tuple(lower), tuple(upper))

    def _clean_mask(self, mask, ksize=3):
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        return mask

    def analyze_roi(self, roi_bgr):
        """
        roi_bgr: small BGR image of the bar.
        returns percent (0..100) or None
        """
        if roi_bgr is None or roi_bgr.size == 0:
            return None

        hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        l1, u1 = self.light_hsv
        l2, u2 = self.dark_hsv

        mask_light = cv2.inRange(hsv, np.array(l1, dtype=np.uint8), np.array(u1, dtype=np.uint8))
        mask_light = self._clean_mask(mask_light, ksize=3)
        mask_dark = cv2.inRange(hsv, np.array(l2, dtype=np.uint8), np.array(u2, dtype=np.uint8))
        mask_dark = self._clean_mask(mask_dark, ksize=3)

        h, w = mask_light.shape[:2]
        percent = None

        if self.method == "pixel":
            lp = int(cv2.countNonZero(mask_light))
            dp = int(cv2.countNonZero(mask_dark))
            total = lp + dp
            if total == 0:
                gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
                bright = int(cv2.countNonZero(cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)[1]))
                total = h * w
                if total == 0:
                    return None
                percent = (bright / total) * 100.0
            else:
                percent = (lp / total) * 100.0

        elif self.method == "projection":
            col_counts = np.sum(mask_light > 0, axis=0).astype(float)
            col_frac = col_counts / float(h) if h>0 else col_counts
            col_thresh = 0.35
            filled_cols = np.count_nonzero(col_frac > col_thresh)
            percent = (filled_cols / float(w)) * 100.0 if w>0 else 0.0
            if np.sum(col_counts) < 3:
                lp = int(cv2.countNonZero(mask_light))
                total = h * w
                percent = (lp / total) * 100.0 if total>0 else 0.0

        elif self.method == "contour":
            contours, _ = cv2.findContours(mask_light, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                percent = 0.0
            else:
                c = max(contours, key=cv2.contourArea)
                x, y, cw, ch = cv2.boundingRect(c)
                percent = (cw / float(w)) * 100.0 if w>0 else 0.0
                if cv2.contourArea(c) < 4:
                    lp = int(cv2.countNonZero(mask_light))
                    total = h * w
                    percent = (lp / total) * 100.0 if total>0 else 0.0
        else:
            # fallback
            return self.analyze_roi(roi_bgr)

        if percent is None:
            return None
        percent = max(0.0, min(100.0, float(percent)))
        return percent
