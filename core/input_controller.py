import interception

class InputController:
    def __init__(self):
        interception.auto_capture_devices()

    def press_key(self, key):
        try:
            interception.press(key)
            print(f"pressed {key}")
        except Exception as e:
            print(f"Error pressing {key}: {e}")