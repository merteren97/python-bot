import cv2
import numpy as np
from typing import Optional, Tuple
from core.template_matcher import TemplateMatcher

HSVRange = Tuple[Tuple[int, int, int], Tuple[int, int, int]]

class BaseBarChecker:
    """
    Menü ROI’si içinde kendi template'ini arayıp, ROI’yi HSV ile açık/koyu maskeleyerek doluluk yüzdesi hesaplar.
    Doluluk = light_pixels / (light_pixels + dark_pixels) * 100
    """
    def __init__(self,
                 name: str,
                 bar_template: TemplateMatcher,
                 light_hsv: HSVRange,
                 dark_hsv: HSVRange,
                 low_threshold: float = 30.0,  # %
                 key_on_low: Optional[str] = None,
                 input_controller=None,
                 active: bool = True,
                 bar_match_threshold: float = 0.85):
        self.name = name
        self.bar_template = bar_template
        self.light_hsv = light_hsv
        self.dark_hsv = dark_hsv
        self.low_threshold = low_threshold
        self.key_on_low = key_on_low
        self.input_controller = input_controller
        self.active = active
        self.bar_match_threshold = bar_match_threshold

    def set_light_hsv(self, lower, upper):
        self.light_hsv = (tuple(lower), tuple(upper))

    def set_dark_hsv(self, lower, upper):
        self.dark_hsv = (tuple(lower), tuple(upper))

    def process_in_menu(self, frame_bgr, menu_rect) -> Optional[float]:
        """
        frame_bgr: tam ekran BGR
        menu_rect: (x,y,w,h) — önce menu bulunmuş olmalı
        Dönüş: doluluk yüzdesi veya None
        """
        if not self.active:
            return None

        # Menü içinde bar'ı ara
        hit = self.bar_template.find_in_roi(frame_bgr, menu_rect)
        if hit is None:
            return None
        x, y, w, h, score = hit
        roi = frame_bgr[y:y+h, x:x+w]

        # HSV’ye çevir ve maskeleri uygula
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        l1, u1 = self.light_hsv
        l2, u2 = self.dark_hsv
        mask_light = cv2.inRange(hsv, np.array(l1, dtype=np.uint8), np.array(u1, dtype=np.uint8))
        mask_dark  = cv2.inRange(hsv, np.array(l2, dtype=np.uint8), np.array(u2, dtype=np.uint8))

        light_pixels = cv2.countNonZero(mask_light)
        dark_pixels  = cv2.countNonZero(mask_dark)
        total = light_pixels + dark_pixels
        if total == 0:
            return None

        percent = (light_pixels / total) * 100.0

        # Eşik altı aksiyon (opsiyonel)
        if self.key_on_low and percent < self.low_threshold and self.input_controller:
            self.input_controller.press_key(self.key_on_low)

        return float(percent)