import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

MENU_TEMPLATE = os.path.join(ASSETS_DIR, "menu.png")
CANBAR_TEMPLATE = os.path.join(ASSETS_DIR, "canbar.png")
MANABAR_TEMPLATE = os.path.join(ASSETS_DIR, "manabar.png")
STAMINABAR_TEMPLATE = os.path.join(ASSETS_DIR, "staminabar.png")

MENU_MATCH_THRESHOLD = 0.80
BAR_MATCH_THRESHOLD = 0.80

# Default HSVs
HEALTH_LIGHT_HSV = ((0, 120, 120), (10, 255, 255))
HEALTH_DARK_HSV  = ((0, 120, 50),  (10, 255, 120))

MANA_LIGHT_HSV   = ((90, 100, 80), (130, 255, 255))
MANA_DARK_HSV    = ((90, 100, 50), (130, 255, 120))

STAMINA_LIGHT_HSV= ((20, 100, 100), (40, 255, 255))
STAMINA_DARK_HSV = ((20, 100, 50),  (40, 255, 120))

# Keys and thresholds defaults (General settings)
DEFAULT_GENERAL_SETTINGS = {
    "health_enabled": True,
    "health_threshold": 50,      # percent
    "health_key": "h",
    "mana_enabled": False,
    "mana_threshold": 40,
    "mana_key": "m",
    "stamina_enabled": False,
    "pickup_enabled": False,
    "pickup_key": "z",
    "pickup_interval_ms": 1500,
    "loop_delay_ms": 250
}

# Paths for settings
SETTINGS_PATH = os.path.join(BASE_DIR, "hsv_settings.json")       # HSV per-feature (existing)
GENERAL_SETTINGS_PATH = os.path.join(BASE_DIR, "general_settings.json")

# Window title substring to find your game window (change this)
WINDOW_TITLE_SUBSTRING = "METIN2"

# Settings JSON path for HSV values
SETTINGS_PATH = os.path.join(BASE_DIR, "hsv_settings.json")