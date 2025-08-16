import sys
import os
import time
import json
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QSlider, QGroupBox, QGridLayout, QComboBox, QMessageBox, QTabWidget,
    QCheckBox, QSpinBox, QLineEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap

# ensure project root importable
current_dir = os.path.dirname(os.path.abspath(__file__))
proj_root = os.path.abspath(os.path.join(current_dir, ".."))
if proj_root not in sys.path:
    sys.path.append(proj_root)

import config
from core.window_finder import find_window_by_title
from core.screen import ScreenCapture
from core.template_matcher import TemplateMatcher
from core.input_controller import InputController
from features.health_checker import HealthChecker

# load/save helpers
def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_json(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# default general settings loader -> ensure file exists
def load_or_create_general_settings():
    data = load_json(config.GENERAL_SETTINGS_PATH)
    if data is None:
        data = config.DEFAULT_GENERAL_SETTINGS.copy()
        save_json(config.GENERAL_SETTINGS_PATH, data)
    # ensure all keys exist
    for k, v in config.DEFAULT_GENERAL_SETTINGS.items():
        if k not in data:
            data[k] = v
    return data

# Bot thread
class BotThread(QThread):
    percent_signal = pyqtSignal(str, float)  # name, percent
    preview_signal = pyqtSignal(str, object)  # name, roi_bgr

    def __init__(self, win_info, bar_positions, loop_delay_ms, checkers, general_settings):
        super().__init__()
        self.win_info = win_info
        self.bar_positions = bar_positions  # dict of abs positions
        self.loop_delay = max(10, int(loop_delay_ms)) / 1000.0
        self.checkers = checkers  # dict of Feature->Checker
        self.general_settings = general_settings
        self._running = False
        self.sc = ScreenCapture(region=self.win_info)
        self.input_ctrl = InputController()
        self._last_pickup = 0.0
        self._last_heal = 0.0
        self._heal_cooldown = 0.5  # seconds between auto-heal keypresses
        self._mana_cooldown = 0.5

    def run(self):
        self._running = True
        while self._running:
            try:
                frame = self.sc.capture()
            except Exception as e:
                print("[BotThread] capture hata:", e)
                time.sleep(0.2)
                continue

            tnow = time.time()

            # process bars
            for key, pos in self.bar_positions.items():
                # pos has absolute screen coords; convert to window-local region coords
                lx = int(pos["left"] - self.win_info["left"])
                ly = int(pos["top"] - self.win_info["top"])
                w = int(pos["width"]); h = int(pos["height"])
                ih, iw = frame.shape[:2]
                x0 = max(0, min(iw-1, lx)); y0 = max(0, min(ih-1, ly))
                x1 = max(0, min(iw, x0 + w)); y1 = max(0, min(ih, y0 + h))
                if x1 <= x0 or y1 <= y0:
                    continue
                roi = frame[y0:y1, x0:x1]

                # map bar key naming: can -> Health, mana -> Mana, stamina -> Stamina
                feature = "Health" if key == "can" else ("Mana" if key == "mana" else "Stamina")

                checker = self.checkers.get(feature)
                if checker:
                    percent = checker.analyze_roi(roi)
                else:
                    percent = None

                if percent is not None:
                    # emit percent for UI only for Health and Mana
                    self.percent_signal.emit(feature, percent)

                    # if Health auto enabled & below threshold -> press heal key (respect cooldown)
                    gs = self.general_settings
                    if feature == "Health" and gs.get("health_enabled", False):
                        thr = float(gs.get("health_threshold", 50))
                        if percent < thr and (tnow - self._last_heal) > self._heal_cooldown:
                            key = gs.get("health_key", "h")
                            try:
                                self.input_ctrl.press_key(key)
                                self._last_heal = tnow
                                print(f"[AutoHeal] pressed '{key}' because {percent:.1f}% < {thr}")
                            except Exception as e:
                                print("[AutoHeal] hata:", e)
                    # Mana similar
                    if feature == "Mana" and gs.get("mana_enabled", False):
                        thr = float(gs.get("mana_threshold", 40))
                        if percent < thr and (tnow - self._last_mana) > self._mana_cooldown:
                            key = gs.get("mana_key", "m")
                            try:
                                self.input_ctrl.press_key(key)
                                self._last_mana = tnow
                                print(f"[AutoMana] pressed '{key}' because {percent:.1f}% < {thr}")
                            except Exception as e:
                                print("[AutoMana] hata:", e)

                # send preview to UI (so mask preview etc. can be rendered)
                self.preview_signal.emit(feature, roi.copy())

            # pickup job (z key) if enabled
            gs = self.general_settings
            if gs.get("pickup_enabled", False):
                interval = max(10, int(gs.get("pickup_interval_ms", 1000))) / 1000.0
                if (tnow - self._last_pickup) >= interval:
                    key = gs.get("pickup_key", "z")
                    try:
                        self.input_ctrl.press_key(key)
                        self._last_pickup = tnow
                        print(f"[Pickup] pressed '{key}'")
                    except Exception as e:
                        print("[Pickup] hata:", e)

            time.sleep(self.loop_delay)

    def stop(self):
        self._running = False
        self.wait()

class MainUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Game Bot - Yeni Kontrol Paneli")
        self.resize(1000, 640)

        # state
        self.win_info = None
        self.menu_hit = None
        self.bar_positions = {}
        self.bot_thread = None

        # input controller
        self.input_ctrl = InputController()

        # checkers for Health/Mana/Stamina
        self.checkers = {
            "Health": HealthChecker(config.HEALTH_LIGHT_HSV, config.HEALTH_DARK_HSV, method="projection"),
            "Mana": HealthChecker(config.MANA_LIGHT_HSV, config.MANA_DARK_HSV, method="projection"),
            "Stamina": HealthChecker(config.STAMINA_LIGHT_HSV, config.STAMINA_DARK_HSV, method="projection")
        }

        # load general settings (or create defaults)
        self.general_settings = load_or_create_general_settings()

        # build UI (tabs)
        self._build_ui()

        # load HSV settings (hsv_settings.json) into Bot Settings tab controls (if any)
        self.hsv_settings = load_json(config.SETTINGS_PATH) or {}

        # apply general settings into UI controls
        self._apply_general_settings_to_ui()

    def _build_ui(self):
        root = QVBoxLayout()

        self.tabs = QTabWidget()
        self.tab_general = QWidget()
        self.tab_botsettings = QWidget()
        self.tabs.addTab(self.tab_general, "Genel")
        self.tabs.addTab(self.tab_botsettings, "Bot Ayarları")
        root.addWidget(self.tabs)

        # --- General tab ---
        g_layout = QVBoxLayout()
        # scan / start/stop row
        row1 = QHBoxLayout()
        self.btn_scan = QPushButton("Pencereyi Tara")
        self.btn_scan.clicked.connect(self.on_scan)
        row1.addWidget(self.btn_scan)
        self.btn_start = QPushButton("Botu Başlat")
        self.btn_start.clicked.connect(self.on_start)
        row1.addWidget(self.btn_start)
        self.btn_stop = QPushButton("Botu Durdur")
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_stop.setEnabled(False)
        row1.addWidget(self.btn_stop)
        g_layout.addLayout(row1)

        self.info_label = QLabel("Durum: Henüz taranmadı.")
        g_layout.addWidget(self.info_label)

        # Health / Mana / Stamina boxes
        boxes = QHBoxLayout()

        # helper to create small panel per feature
        def feature_panel(name, key):
            box = QGroupBox(name)
            bl = QVBoxLayout()
            enable = QCheckBox("Aktif")
            enable.setChecked(self.general_settings.get(f"{key}_enabled", False))
            threshold_row = QHBoxLayout()
            threshold_row.addWidget(QLabel("Eşik (%)"))
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setValue(int(self.general_settings.get(f"{key}_threshold", 50)))
            threshold_row.addWidget(spin)
            key_row = QHBoxLayout()
            key_row.addWidget(QLabel("Tuş"))
            key_edit = QLineEdit(self.general_settings.get(f"{key}_key", "h"))
            key_edit.setMaxLength(1)
            key_row.addWidget(key_edit)
            # preview label
            preview = QLabel()
            preview.setFixedSize(220, 36)
            preview.setStyleSheet("background:#111; border:1px solid #444")

            bl.addWidget(enable)
            bl.addLayout(threshold_row)
            bl.addLayout(key_row)
            bl.addWidget(preview)
            box.setLayout(bl)
            return {"group": box, "enable": enable, "threshold": spin, "key_edit": key_edit, "preview": preview}

        self.feature_panels = {
            "Health": feature_panel("Health (Can)", "health"),
            "Mana": feature_panel("Mana", "mana"),
            "Stamina": feature_panel("Stamina", "stamina")
        }
        # set health default enabled true (if general settings default says so)
        # add to boxes
        boxes.addWidget(self.feature_panels["Health"]["group"])
        boxes.addWidget(self.feature_panels["Mana"]["group"])
        boxes.addWidget(self.feature_panels["Stamina"]["group"])
        g_layout.addLayout(boxes)

        # pickup section
        pickup_box = QGroupBox("Eşya Toplama (Pickup)")
        p_layout = QHBoxLayout()
        self.chk_pickup = QCheckBox("Pickup Aktif")
        self.chk_pickup.setChecked(self.general_settings.get("pickup_enabled", False))
        p_layout.addWidget(self.chk_pickup)
        p_layout.addWidget(QLabel("Tuş:"))
        self.le_pickup_key = QLineEdit(self.general_settings.get("pickup_key", "z"))
        self.le_pickup_key.setMaxLength(1)
        p_layout.addWidget(self.le_pickup_key)
        p_layout.addWidget(QLabel("Interval (ms):"))
        self.sld_pickup = QSlider(Qt.Horizontal)
        self.sld_pickup.setRange(50, 5000)
        self.sld_pickup.setValue(int(self.general_settings.get("pickup_interval_ms", 1500)))
        p_layout.addWidget(self.sld_pickup)
        self.lbl_pickup_val = QLabel(str(self.sld_pickup.value()) + " ms")
        p_layout.addWidget(self.lbl_pickup_val)
        self.sld_pickup.valueChanged.connect(lambda v: self.lbl_pickup_val.setText(str(v) + " ms"))
        pickup_box.setLayout(p_layout)
        g_layout.addWidget(pickup_box)

        # loop delay and save general
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(QLabel("Frame Delay (ms):"))
        self.sld_loop = QSlider(Qt.Horizontal)
        self.sld_loop.setRange(10, 2000)
        self.sld_loop.setValue(int(self.general_settings.get("loop_delay_ms", 250)))
        bottom_row.addWidget(self.sld_loop)
        self.lbl_loop_val = QLabel(str(self.sld_loop.value()) + " ms")
        self.sld_loop.valueChanged.connect(lambda v: self.lbl_loop_val.setText(str(v) + " ms"))
        bottom_row.addWidget(self.lbl_loop_val)
        self.btn_save_general = QPushButton("Genel Ayarları Kaydet")
        self.btn_save_general.clicked.connect(self.on_save_general)
        bottom_row.addWidget(self.btn_save_general)
        g_layout.addLayout(bottom_row)

        self.tab_general.setLayout(g_layout)

        # --- Bot Ayarları tab (HSV + suggest + save) ---
        b_layout = QVBoxLayout()
        # reuse earlier design: combobox select feature + sliders + suggest + save
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Feature:"))
        self.cmb_feature = QComboBox()
        self.cmb_feature.addItems(["Health", "Mana", "Stamina"])
        self.cmb_feature.currentIndexChanged.connect(self._on_bot_feature_changed)
        top_row.addWidget(self.cmb_feature)
        self.btn_suggest = QPushButton("Öneri Al (ROI'den)")
        self.btn_suggest.clicked.connect(self.on_suggest)
        top_row.addWidget(self.btn_suggest)
        self.btn_save_hsv = QPushButton("HSV Kaydet")
        self.btn_save_hsv.clicked.connect(self.on_save_hsv)
        top_row.addWidget(self.btn_save_hsv)
        b_layout.addLayout(top_row)

        # preview and mask
        pm_row = QHBoxLayout()
        self.lbl_bot_preview = QLabel()
        self.lbl_bot_preview.setFixedSize(420, 80)
        self.lbl_bot_preview.setStyleSheet("background:#111; border:1px solid #444")
        pm_row.addWidget(self.lbl_bot_preview)
        self.lbl_bot_mask = QLabel()
        self.lbl_bot_mask.setFixedSize(420, 80)
        self.lbl_bot_mask.setStyleSheet("background:#111; border:1px solid #444")
        pm_row.addWidget(self.lbl_bot_mask)
        b_layout.addLayout(pm_row)

        # hsv sliders grid (same as before)
        hsv_group = QGroupBox("HSV Ayarları (Seçili feature)")
        grid = QGridLayout()
        labels = ["L_H","L_S","L_V","LU_H","LU_S","LU_V","D_H","D_S","D_V","DU_H","DU_S","DU_V"]
        self.hsv_sliders = {}
        r = 0
        for i, lab in enumerate(labels):
            row = i // 3
            col = (i % 3) * 2
            lbl = QLabel(lab)
            s = QSlider(Qt.Horizontal)
            if "H" in lab:
                s.setRange(0,180)
            else:
                s.setRange(0,255)
            s.valueChanged.connect(self._on_hsv_slider_changed)
            grid.addWidget(lbl, row, col)
            grid.addWidget(s, row, col+1)
            self.hsv_sliders[lab] = s
        hsv_group.setLayout(grid)
        b_layout.addWidget(hsv_group)

        self.tab_botsettings.setLayout(b_layout)

        self.setLayout(root)

        # connect features preview updates via existing preview slot
        # (BotThread will emit preview_signal, handled by _on_preview)
        # initialize sliders from defaults or saved hsv_settings
        self._on_bot_feature_changed(0)

    # ---------------- General tab handlers ----------------
    def _apply_general_settings_to_ui(self):
        gs = self.general_settings
        # map keys
        self.feature_panels["Health"]["enable"].setChecked(gs.get("health_enabled", False))
        self.feature_panels["Health"]["threshold"].setValue(int(gs.get("health_threshold", 50)))
        self.feature_panels["Health"]["key_edit"].setText(str(gs.get("health_key", "h")))

        self.feature_panels["Mana"]["enable"].setChecked(gs.get("mana_enabled", False))
        self.feature_panels["Mana"]["threshold"].setValue(int(gs.get("mana_threshold", 40)))
        self.feature_panels["Mana"]["key_edit"].setText(str(gs.get("mana_key", "m")))

        self.feature_panels["Stamina"]["enable"].setChecked(gs.get("stamina_enabled", False))
        self.feature_panels["Stamina"]["threshold"].setValue(int(gs.get("stamina_threshold", 0)))
        self.feature_panels["Stamina"]["key_edit"].setText(str(gs.get("stamina_key", "")))

        self.chk_pickup.setChecked(gs.get("pickup_enabled", False))
        self.le_pickup_key.setText(str(gs.get("pickup_key", "z")))
        self.sld_pickup.setValue(int(gs.get("pickup_interval_ms", 1500)))
        self.sld_loop.setValue(int(gs.get("loop_delay_ms", 250)))

    def on_scan(self):
        found = find_window_by_title(config.WINDOW_TITLE_SUBSTRING)
        if not found:
            QMessageBox.warning(self, "Hata", "Pencere bulunamadı. config.py içindeki WINDOW_TITLE_SUBSTRING ayarını kontrol et.")
            self.info_label.setText("Pencere bulunamadı.")
            return
        self.win_info = found
        self.info_label.setText(f"Pencere bulundu: left={found['left']} top={found['top']} w={found['width']} h={found['height']}")
        # capture once and find menu & bars
        sc = ScreenCapture(region=self.win_info)
        frame = sc.capture()
        menu_matcher = TemplateMatcher(config.MENU_TEMPLATE, threshold=config.MENU_MATCH_THRESHOLD, auto_scale=True)
        hit = menu_matcher.find_best(frame)
        if not hit:
            # try bottom region
            h = frame.shape[0]; w = frame.shape[1]
            bottom_region = frame[int(h*0.6):h, 0:w]
            hitb = menu_matcher.find_best(bottom_region)
            if hitb:
                bx, by, bw, bh, score = hitb
                hit = (bx, int(by + int(h*0.6)), bw, bh, score)
        if not hit:
            QMessageBox.warning(self, "Hata", "Menü bulunamadı. menu.png doğru kırpılmış mı kontrol et.")
            self.info_label.setText("Menü bulunamadı.")
            return
        mx, my, mw, mh, scv = hit
        self.menu_hit = {"x":mx, "y":my, "w":mw, "h":mh, "score":scv}
        menu_img = frame[my:my+mh, mx:mx+mw]

        # find bars inside menu_img
        bars = {"can": config.CANBAR_TEMPLATE, "mana": config.MANABAR_TEMPLATE, "stamina": config.STAMINABAR_TEMPLATE}
        found_bars = {}
        for name, tpl in bars.items():
            matcher = TemplateMatcher(tpl, threshold=config.BAR_MATCH_THRESHOLD, auto_scale=True)
            bhit = matcher.find_best(menu_img)
            if bhit:
                bx, by, bw, bh, score = bhit
                # absolute in full screen coordinates: win left/top + menu offset + bx/by
                abs_left = self.win_info["left"] + mx + bx
                abs_top  = self.win_info["top"] + my + by
                found_bars[name] = {"left": abs_left, "top": abs_top, "width": bw, "height": bh, "score": score}
        self.bar_positions = found_bars
        self.lbl_positions = getattr(self, "lbl_positions", QLabel())  # if exists
        # update previews for each feature if present
        for feat_name, panel in [("Health", self.feature_panels["Health"]), ("Mana", self.feature_panels["Mana"]), ("Stamina", self.feature_panels["Stamina"])]:
            bar_key = "can" if feat_name=="Health" else ("mana" if feat_name=="Mana" else "stamina")
            if bar_key in self.bar_positions:
                # grab a local ROI for showing preview
                sc_local = ScreenCapture(region=self.win_info)
                frame2 = sc_local.capture()
                pos = self.bar_positions[bar_key]
                lx = int(pos["left"] - self.win_info["left"]); ly = int(pos["top"] - self.win_info["top"])
                w = int(pos["width"]); h = int(pos["height"])
                ih, iw = frame2.shape[:2]
                x0 = max(0, min(iw-1, lx)); y0 = max(0, min(ih-1, ly))
                x1 = max(0, min(iw, x0 + w)); y1 = max(0, min(ih, y0 + h))
                if x1>x0 and y1>y0:
                    roi = frame2[y0:y1, x0:x1]
                    try:
                        rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
                        h0, w0 = rgb.shape[:2]
                        qimg = QImage(rgb.data, w0, h0, 3*w0, QImage.Format_RGB888)
                        pix = QPixmap.fromImage(qimg).scaled(panel["preview"].width(), panel["preview"].height(), Qt.KeepAspectRatio)
                        panel["preview"].setPixmap(pix)
                    except Exception:
                        pass

        self.info_label.setText(self.info_label.text() + f" | Bars: {list(self.bar_positions.keys())}")

    def on_start(self):
        if not self.win_info or not self.bar_positions:
            QMessageBox.warning(self, "Hata", "Önce 'Pencereyi Tara' and bar positions bulunmalı.")
            return
        if self.bot_thread and self.bot_thread.isRunning():
            return

        # prepare checkers with current HSV settings
        # ensure checkers use latest sliders/settings
        # (we already update checkers when sliders change in Bot Settings)
        loop_ms = max(10, self.sld_loop.value())
        # assemble general settings from UI
        gs = {
            "health_enabled": bool(self.feature_panels["Health"]["enable"].isChecked()),
            "health_threshold": int(self.feature_panels["Health"]["threshold"].value()),
            "health_key": str(self.feature_panels["Health"]["key_edit"].text() or "h"),
            "mana_enabled": bool(self.feature_panels["Mana"]["enable"].isChecked()),
            "mana_threshold": int(self.feature_panels["Mana"]["threshold"].value()),
            "mana_key": str(self.feature_panels["Mana"]["key_edit"].text() or "m"),
            "stamina_enabled": bool(self.feature_panels["Stamina"]["enable"].isChecked()),
            "pickup_enabled": bool(self.chk_pickup.isChecked()),
            "pickup_key": str(self.le_pickup_key.text() or "z"),
            "pickup_interval_ms": int(self.sld_pickup.value()),
            "loop_delay_ms": int(self.sld_loop.value())
        }
        # save current general settings in memory
        self.general_settings = gs

        self.bot_thread = BotThread(self.win_info, self.bar_positions, loop_ms, self.checkers, gs)
        self.bot_thread.percent_signal.connect(self._on_percent)
        self.bot_thread.preview_signal.connect(self._on_preview)
        self.bot_thread.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.info_label.setText("Bot çalışıyor...")

    def on_stop(self):
        if self.bot_thread:
            self.bot_thread.stop()
            self.bot_thread = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.info_label.setText("Bot durduruldu.")

    def on_save_general(self):
        # collect UI values and save to config.GENERAL_SETTINGS_PATH
        data = {
            "health_enabled": bool(self.feature_panels["Health"]["enable"].isChecked()),
            "health_threshold": int(self.feature_panels["Health"]["threshold"].value()),
            "health_key": str(self.feature_panels["Health"]["key_edit"].text() or "h"),
            "mana_enabled": bool(self.feature_panels["Mana"]["enable"].isChecked()),
            "mana_threshold": int(self.feature_panels["Mana"]["threshold"].value()),
            "mana_key": str(self.feature_panels["Mana"]["key_edit"].text() or "m"),
            "stamina_enabled": bool(self.feature_panels["Stamina"]["enable"].isChecked()),
            "pickup_enabled": bool(self.chk_pickup.isChecked()),
            "pickup_key": str(self.le_pickup_key.text() or "z"),
            "pickup_interval_ms": int(self.sld_pickup.value()),
            "loop_delay_ms": int(self.sld_loop.value())
        }
        save_json(config.GENERAL_SETTINGS_PATH, data)
        QMessageBox.information(self, "Kaydedildi", "Genel ayarlar kaydedildi.")
        self.general_settings = data

    # ---------------- Bot Settings (HSV) handlers ----------------
    def _on_bot_feature_changed(self, idx):
        feat = self.cmb_feature.currentText()
        # load from hsv_settings if present
        hdata = load_json(config.SETTINGS_PATH) or {}
        item = hdata.get(feat, None)
        if item:
            # set sliders
            L = tuple(item.get("light", (0,0,0)))
            LU = tuple(item.get("light_up", (0,0,0)))
            D = tuple(item.get("dark", (0,0,0)))
            DU = tuple(item.get("dark_up", (0,0,0)))
        else:
            # defaults
            if feat == "Health":
                L, LU = config.HEALTH_LIGHT_HSV
                D, DU = config.HEALTH_DARK_HSV
            elif feat == "Mana":
                L, LU = config.MANA_LIGHT_HSV
                D, DU = config.MANA_DARK_HSV
            else:
                L, LU = config.STAMINA_LIGHT_HSV
                D, DU = config.STAMINA_DARK_HSV
        self._set_hsv_sliders(L, LU, D, DU)
        # apply to checker immediately
        self._apply_current_hsv_to_checker()

    def _set_hsv_sliders(self, L, LU, D, DU):
        # L, LU, D, DU are tuples
        self.hsv_sliders["L_H"].setValue(int(L[0])); self.hsv_sliders["L_S"].setValue(int(L[1])); self.hsv_sliders["L_V"].setValue(int(L[2]))
        self.hsv_sliders["LU_H"].setValue(int(LU[0])); self.hsv_sliders["LU_S"].setValue(int(LU[1])); self.hsv_sliders["LU_V"].setValue(int(LU[2]))
        self.hsv_sliders["D_H"].setValue(int(D[0])); self.hsv_sliders["D_S"].setValue(int(D[1])); self.hsv_sliders["D_V"].setValue(int(D[2]))
        self.hsv_sliders["DU_H"].setValue(int(DU[0])); self.hsv_sliders["DU_S"].setValue(int(DU[1])); self.hsv_sliders["DU_V"].setValue(int(DU[2]))

    def _on_hsv_slider_changed(self, *_):
        # when sliders change, apply to current feature's checker
        self._apply_current_hsv_to_checker()

    def _apply_current_hsv_to_checker(self):
        feat = self.cmb_feature.currentText()
        L = (self.hsv_sliders["L_H"].value(), self.hsv_sliders["L_S"].value(), self.hsv_sliders["L_V"].value())
        LU= (self.hsv_sliders["LU_H"].value(), self.hsv_sliders["LU_S"].value(), self.hsv_sliders["LU_V"].value())
        D = (self.hsv_sliders["D_H"].value(), self.hsv_sliders["D_S"].value(), self.hsv_sliders["D_V"].value())
        DU= (self.hsv_sliders["DU_H"].value(), self.hsv_sliders["DU_S"].value(), self.hsv_sliders["DU_V"].value())
        checker = self.checkers.get(feat)
        if checker:
            checker.set_light_hsv(L, LU)
            checker.set_dark_hsv(D, DU)

    def on_save_hsv(self):
        feat = self.cmb_feature.currentText()
        data = load_json(config.SETTINGS_PATH) or {}
        data.setdefault(feat, {})
        data[feat]["light"] = [self.hsv_sliders["L_H"].value(), self.hsv_sliders["L_S"].value(), self.hsv_sliders["L_V"].value()]
        data[feat]["light_up"] = [self.hsv_sliders["LU_H"].value(), self.hsv_sliders["LU_S"].value(), self.hsv_sliders["LU_V"].value()]
        data[feat]["dark"] = [self.hsv_sliders["D_H"].value(), self.hsv_sliders["D_S"].value(), self.hsv_sliders["D_V"].value()]
        data[feat]["dark_up"] = [self.hsv_sliders["DU_H"].value(), self.hsv_sliders["DU_S"].value(), self.hsv_sliders["DU_V"].value()]
        save_json(config.SETTINGS_PATH, data)
        QMessageBox.information(self, "Kaydedildi", f"{feat} HSV ayarları kaydedildi.")

    # ---------------- Suggest (ROI'den) ----------------
    def _feature_to_bar_key(self, feature_name):
        mapping = {"health": "can", "mana": "mana", "stamina": "stamina"}
        return mapping.get(feature_name.lower(), feature_name.lower())

    def on_suggest(self):
        feat = self.cmb_feature.currentText()
        bar_key = self._feature_to_bar_key(feat)
        if bar_key not in self.bar_positions:
            QMessageBox.warning(self, "Hata", "Önce scan yap ve ilgili bar bulunmalı.")
            return
        roi = self.bar_positions[bar_key]
        sc = ScreenCapture(region=self.win_info)
        stats = sample_hsv_stats_from_rois(sc, self.win_info, roi, n=10, delay=0.06)
        if not stats:
            QMessageBox.warning(self, "Hata", "ROI'den örnek alınamadı.")
            return
        low, up = suggest_range_from_stats(stats)
        # apply to sliders
        self._set_hsv_sliders(low, up, (low[0]+8, max(low[1],40), max(low[2],40)), (up[0]+8, up[1], up[2]))
        # better: set light and dark systematically
        L = low; LU = up
        D = (max(0, low[0]-15), max(0, low[1]//2), max(0, low[2]//2))
        DU= (min(180, up[0]+15), up[1], min(255, up[2]//2 + 60))
        self._set_hsv_sliders(L, LU, D, DU)
        self._apply_current_hsv_to_checker()
        QMessageBox.information(self, "Öneri Uygulandı", f"{feat} için öneri uygulandı.")

    # ---------------- preview / percent callbacks ----------------
    def _on_percent(self, name, p):
        if name == "Health":
            self.feature_panels["Health"]["preview"]  # preview updated elsewhere
            self.feature_panels["Health"]["threshold"]  # nothing
            # update percent label on Bot Settings side
            self.lbl_percent = getattr(self, "lbl_percent", None)
            # display in main UI percent label
            self.info_label.setText(f"Health: {p:.1f} %")
        # for Mana and Stamina you can add separate displays if desired

    def _on_preview(self, name, img):
        # show preview only for the currently selected feature in both tabs
        # convert BGR->RGB and show in both relevant preview labels
        try:
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            qimg = QImage(rgb.data, w, h, 3*w, QImage.Format_RGB888)
            # If selected feature in Bot Settings matches this preview, show in bot preview
            if self.cmb_feature.currentText().lower() == ("health" if name=="Health" else name.lower()):
                pix = QPixmap.fromImage(qimg).scaled(self.lbl_bot_preview.width(), self.lbl_bot_preview.height(), Qt.KeepAspectRatio)
                self.lbl_bot_preview.setPixmap(pix)
                # also compute mask and show
                low, up = self._get_current_slider_light()
                hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv, np.array(low, dtype=np.uint8), np.array(up, dtype=np.uint8))
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                mask_rgb = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
                qimg2 = QImage(mask_rgb.data, mask_rgb.shape[1], mask_rgb.shape[0], 3*mask_rgb.shape[1], QImage.Format_RGB888)
                pix2 = QPixmap.fromImage(qimg2).scaled(self.lbl_bot_mask.width(), self.lbl_bot_mask.height(), Qt.KeepAspectRatio)
                self.lbl_bot_mask.setPixmap(pix2)
            # update small preview in General tab panels if matches
            if (name=="Health" and "Health" in self.feature_panels) or (name=="Mana" and "Mana" in self.feature_panels) or (name=="Stamina" and "Stamina" in self.feature_panels):
                panel = self.feature_panels["Health"] if name=="Health" else (self.feature_panels["Mana"] if name=="Mana" else self.feature_panels["Stamina"])
                pix_small = QPixmap.fromImage(qimg).scaled(panel["preview"].width(), panel["preview"].height(), Qt.KeepAspectRatio)
                panel["preview"].setPixmap(pix_small)
        except Exception as e:
            pass

    def _get_current_slider_light(self):
        L = (self.hsv_sliders["L_H"].value(), self.hsv_sliders["L_S"].value(), self.hsv_sliders["L_V"].value())
        LU= (self.hsv_sliders["LU_H"].value(), self.hsv_sliders["LU_S"].value(), self.hsv_sliders["LU_V"].value())
        return L, LU

# helper functions used (sampling and suggestion) - same as earlier implementation
def sample_hsv_stats_from_rois(scapture, win_info, roi_abs, n=8, delay=0.06):
    import numpy as np
    all_pixels = []
    for i in range(n):
        try:
            frame = scapture.capture()
        except Exception as e:
            time.sleep(delay)
            continue
        lx = int(roi_abs["left"] - win_info["left"])
        ly = int(roi_abs["top"] - win_info["top"])
        w = int(roi_abs["width"]); h = int(roi_abs["height"])
        ih, iw = frame.shape[:2]
        x0 = max(0, min(iw-1, lx)); y0 = max(0, min(ih-1, ly))
        x1 = max(0, min(iw, x0 + w)); y1 = max(0, min(ih, y0 + h))
        if x1 <= x0 or y1 <= y0:
            time.sleep(delay)
            continue
        roi = frame[y0:y1, x0:x1]
        if roi.size == 0:
            time.sleep(delay)
            continue
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        pixels = hsv.reshape(-1,3)
        all_pixels.append(pixels)
        time.sleep(delay)
    if not all_pixels:
        return None
    all_pixels = np.vstack(all_pixels)
    med = np.median(all_pixels, axis=0).astype(int)
    std = np.std(all_pixels, axis=0).astype(int)
    return {"median": tuple(med.tolist()), "std": tuple(std.tolist()), "count": int(all_pixels.shape[0])}

def suggest_range_from_stats(stats, h_margin=12, s_margin=40, v_margin=40):
    mh, ms, mv = stats["median"]
    sh, ss, sv = stats["std"]
    h_m = max(h_margin, int(1.2*sh))
    s_m = max(s_margin, int(1.2*ss))
    v_m = max(v_margin, int(1.2*sv))
    low = (max(0, mh - h_m), max(0, ms - s_m), max(0, mv - v_m))
    up  = (min(180, mh + h_m), min(255, ms + s_m), min(255, mv + v_m))
    return low, up

# ---------- RUN ----------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainUI()
    w.show()
    sys.exit(app.exec_())
