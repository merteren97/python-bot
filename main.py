import sys
import os
this_dir = os.path.dirname(os.path.abspath(__file__))
if this_dir not in sys.path:
    sys.path.append(this_dir)

from PyQt5.QtWidgets import QApplication
from ui.main_ui import MainUI

def main():
    app = QApplication(sys.argv)
    w = MainUI()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
