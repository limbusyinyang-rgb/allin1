import sys
from PyQt6.QtWidgets import QApplication, QWidget, QStackedLayout, QLabel
from PyQt6.QtCore import Qt

app = QApplication(sys.argv)
w = QWidget()
l = QStackedLayout(w)
l.setStackingMode(QStackedLayout.StackingMode.StackAll)

b1 = QLabel("BOTTOM (Should be visible)")
b1.setStyleSheet("background: red; color: white;")
b1.setAlignment(Qt.AlignmentFlag.AlignCenter)
l.addWidget(b1)

b2 = QLabel("TOP (Should be overlaid)")
b2.setStyleSheet("background: transparent; color: black; font-weight: bold; border: 2px solid blue;")
b2.setAlignment(Qt.AlignmentFlag.AlignTop)
l.addWidget(b2)

l.setCurrentWidget(b2)

w.resize(200, 200)
# Instead of show and loop, we'll just test if it runs without errors
sys.exit(0)
