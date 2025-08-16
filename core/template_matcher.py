import cv2
import os

class TemplateMatcher:
    def __init__(self, template_path, threshold=0.85, auto_scale=True):
        if not os.path.isfile(template_path):
            raise FileNotFoundError(f"Template not found: {template_path}")
        tpl = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if tpl is None:
            raise IOError(f"Template can't be read: {template_path}")
        self.template = tpl
        self.t_h, self.t_w = tpl.shape[:2]
        self.threshold = float(threshold)
        self.auto_scale = bool(auto_scale)

    def _prepare_template_for(self, image):
        ih, iw = image.shape[:2]
        th, tw = self.t_h, self.t_w
        if ih >= th and iw >= tw:
            return self.template, tw, th
        if not self.auto_scale:
            return None, None, None
        scale = min(max( (ih / th) if th else 0, 0.01), max( (iw / tw) if tw else 0, 0.01))
        new_w = max(1, int(tw * scale))
        new_h = max(1, int(th * scale))
        tpl_resized = cv2.resize(self.template, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return tpl_resized, new_w, new_h

    def find_best(self, image):
        if image is None:
            return None
        tpl, tw, th = self._prepare_template_for(image)
        if tpl is None:
            return None
        res = cv2.matchTemplate(image, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val >= self.threshold:
            x, y = max_loc
            return (int(x), int(y), int(tw), int(th), float(max_val))
        return None

    def find_in_roi(self, parent_image, roi_rect):
        px, py, pw, ph = roi_rect
        ih, iw = parent_image.shape[:2]
        px = max(0, int(px)); py = max(0, int(py))
        pw = max(0, int(min(pw, iw - px))); ph = max(0, int(min(ph, ih - py)))
        if pw <= 0 or ph <= 0:
            return None
        roi = parent_image[py:py+ph, px:px+pw]
        hit = self.find_best(roi)
        if hit is None:
            return None
        x, y, w, h, score = hit
        return (px + x, py + y, w, h, score)
