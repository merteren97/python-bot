import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QSlider, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtCore import Qt, QTimer
from core.screen import ScreenCapture
from core.template_matcher import TemplateMatcher
import config

def estimate_bar_fill(bar_img, bar_template_full, bar_template_empty):
    bar_img_resized = cv2.resize(bar_img, (bar_template_full.shape[1], bar_template_full.shape[0]))
    score_full = cv2.matchTemplate(bar_img_resized, bar_template_full, cv2.TM_CCOEFF_NORMED).max()
    score_empty = cv2.matchTemplate(bar_img_resized, bar_template_empty, cv2.TM_CCOEFF_NORMED).max()
    percent = 100 * (score_full / (score_full + score_empty + 1e-6))
    return percent

class LivePreviewUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Preview - Health/Mana/Stamina")
        self.screen = ScreenCapture()
        self.menu_template = TemplateMatcher(config.MENU_TEMPLATE)
        self.health_template = TemplateMatcher(config.HEALTH_TEMPLATE)
        self.health_bar_roi = None  # Bar konumu burada tutulacak

        self.lower_h, self.lower_s, self.lower_v = 0, 100, 100
        self.upper_h, self.upper_s, self.upper_v = 10, 255, 255

        self.bar_template_full = cv2.imread("assets/canbar_full.png")
        self.bar_template_empty = cv2.imread("assets/canbar_empty.png")

        self.init_ui()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(100)  # 10 fps

    def init_ui(self):
        layout = QVBoxLayout()

        # HSV Sliders
        self.sliders = {}
        for name, val, max_val in [("Lower H", self.lower_h, 179), ("Lower S", self.lower_s, 255),
                                   ("Lower V", self.lower_v, 255), ("Upper H", self.upper_h, 179),
                                   ("Upper S", self.upper_s, 255), ("Upper V", self.upper_v, 255)]:
            label = QLabel(f"{name}: {val}")
            slider = QSlider(Qt.Horizontal)
            slider.setMaximum(max_val)
            slider.setValue(val)
            slider.valueChanged.connect(lambda value, l=label, n=name: self.slider_changed(l, n, value))
            layout.addWidget(label)
            layout.addWidget(slider)
            self.sliders[name] = slider

        # Doluluk oranı label'ı
        self.percent_label = QLabel("Health: %")
        layout.addWidget(self.percent_label)

        self.setLayout(layout)

    def slider_changed(self, label, name, value):
        label.setText(f"{name}: {value}")
        if name == "Lower H": self.lower_h = value
        elif name == "Lower S": self.lower_s = value
        elif name == "Lower V": self.lower_v = value
        elif name == "Upper H": self.upper_h = value
        elif name == "Upper S": self.upper_s = value
        elif name == "Upper V": self.upper_v = value

    def update_frame(self):
        frame = self.screen.capture_full()
        if self.health_bar_roi is None:
            # İlk seferde barın konumunu bul
            menu_coords = self.menu_template.find_best(frame)
            if menu_coords is None:
                return
            x, y, w, h = menu_coords[:4]
            menu_region = frame[y:y+h, x:x+w]
            bar_coords = self.health_template.find_best(menu_region)
            if bar_coords:
                bx, by, bw, bh = bar_coords[:4]
                # Barın global koordinatlarını kaydet
                self.health_bar_roi = (x+bx, y+by, bw, bh)
        if self.health_bar_roi:
            x, y, w, h = self.health_bar_roi
            bar_img = frame[y:y+h, x:x+w]
            percent = estimate_bar_fill(bar_img, self.bar_template_full, self.bar_template_empty)
            # PyQt penceresinde göster
            self.percent_label.setText(f"Health: {percent:.1f}%")
            # İstersen OpenCV penceresinde de gösterilmeye devam edebilir
            cv2.putText(bar_img, f"Health: {percent:.1f}%", (5,20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
            cv2.imshow("Health Preview", bar_img)

    def run(self):
        self.show()
        sys.exit(app.exec_())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = LivePreviewUI()
    ui.run()
