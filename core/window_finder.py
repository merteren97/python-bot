import win32gui

def find_window_by_title(substring):
    """
    Finds first visible window whose title contains the substring (case-insensitive).
    Returns dict: {"hwnd": hwnd, "left": left, "top": top, "width": w, "height": h} or None.
    """
    substring = substring.lower()
    found = {"hwnd": None}

    def _enum(h, _):
        try:
            title = win32gui.GetWindowText(h)
            if title and substring in title.lower() and win32gui.IsWindowVisible(h):
                found["hwnd"] = h
        except Exception:
            pass

    win32gui.EnumWindows(_enum, None)
    hwnd = found.get("hwnd")
    if not hwnd:
        return None
    rect = win32gui.GetWindowRect(hwnd)
    left, top, right, bottom = rect
    return {"hwnd": hwnd, "left": left, "top": top, "width": right - left, "height": bottom - top}
