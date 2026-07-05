import sys
import os

# Ensure the parent directory is in sys.path if needed
# We assume this is run from within "d:\Tooo\Xuat Video Sub"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainCapCutWindow

def main():
    app = QApplication(sys.argv)
    
    try:
        import qdarkstyle
        app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt6'))
    except ImportError:
        pass
    
    # Load custom fonts if any, etc.
    
    window = MainCapCutWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
