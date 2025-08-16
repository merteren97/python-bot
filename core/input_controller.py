# core/input_controller.py
import time
import ctypes
import ctypes.wintypes
import pyautogui

# ctypes.wintypes.ULONG_PTR eksikse tanımla
if not hasattr(ctypes.wintypes, "ULONG_PTR"):
    ctypes.wintypes.ULONG_PTR = ctypes.c_void_p

# Win32 import
try:
    import win32gui
    import win32con
    WIN32_AVAILABLE = True
except Exception:
    WIN32_AVAILABLE = False

user32 = ctypes.WinDLL('user32', use_last_error=True)

# Constants
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

# Structures
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD),
        ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.wintypes.ULONG_PTR)
    ]

class INPUT_union(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.wintypes.DWORD),
        ("union", INPUT_union)
    ]

# Function prototypes
user32.SendInput.argtypes = (ctypes.wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = ctypes.wintypes.UINT
user32.MapVirtualKeyW.argtypes = (ctypes.wintypes.UINT, ctypes.wintypes.UINT)
user32.MapVirtualKeyW.restype = ctypes.wintypes.UINT

# Virtual-Key Mapping
NAMED_KEYS_VK = {
    # Harfler
    **{chr(i): i for i in range(ord('A'), ord('Z')+1)},
    # Rakamlar
    **{str(i): ord(str(i)) for i in range(0, 10)},
    # Fonksiyon tuşları
    **{f"f{i}": 0x70 + i - 1 for i in range(1, 13)},
    # Diğer
    "space": 0x20,
    "enter": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
}

def _key_to_vk(key: str):
    key = str(key).lower()
    if key in NAMED_KEYS_VK:
        return NAMED_KEYS_VK[key]
    if len(key) == 1:
        return ord(key.upper())
    return None

def _vk_to_scancode(vk: int):
    if not vk:
        return 0
    return user32.MapVirtualKeyW(vk, 0)

def _send_scancode(scancode: int, keyup: bool = False):
    flags = KEYEVENTF_SCANCODE
    if keyup:
        flags |= KEYEVENTF_KEYUP
    ki = KEYBDINPUT(0, ctypes.wintypes.WORD(scancode), ctypes.wintypes.DWORD(flags), 0, ctypes.wintypes.ULONG_PTR(0))
    inp = INPUT(ctypes.wintypes.DWORD(INPUT_KEYBOARD), INPUT_union(ki))
    res = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    return res == 1

class InputController:
    @staticmethod
    def press_key(key: str, hwnd: int = None, ensure_foreground: bool = True):
        """Press a key using raw scancode input (SendInput) for game compatibility."""
        key_str = str(key)
        # 1) Focus window if needed
        if WIN32_AVAILABLE and hwnd and ensure_foreground:
            try:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.05)
            except Exception:
                pass

        # 2) SendInput with scancode
        try:
            vk = _key_to_vk(key_str)
            sc = _vk_to_scancode(vk)
            if sc:
                down = _send_scancode(sc, keyup=False)
                time.sleep(0.01)
                up = _send_scancode(sc, keyup=True)
                if down and up:
                    print(f"[InputController] SendInput success: '{key_str}', vk={vk}, sc={sc}")
                    return True
                else:
                    print(f"[InputController] SendInput partial/fail: '{key_str}', vk={vk}, sc={sc}")
        except Exception as e:
            print("[InputController] SendInput exception:", e)

        # 3) Fallback: pyautogui
        try:
            pyautogui.press(key_str)
            print(f"[InputController] pyautogui.press success: '{key_str}'")
            return True
        except Exception as e:
            print("[InputController] pyautogui.press failed:", e)

        # 4) Fallback: PostMessage
        if WIN32_AVAILABLE and hwnd:
            try:
                vk = _key_to_vk(key_str)
                win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk, 0)
                time.sleep(0.01)
                win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk, 0)
                print(f"[InputController] PostMessage sent: '{key_str}'")
                return True
            except Exception as e:
                print("[InputController] PostMessage failed:", e)

        print(f"[InputController] press_key failed: '{key_str}'")
        return False
 