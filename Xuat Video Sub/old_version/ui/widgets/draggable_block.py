from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush

class DraggableBlock(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DraggableBlock")
        # Không dùng CSS background để tránh xung đột với theme.qss
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setMouseTracking(True)
        
        # Mặc định là Không che
        self.bg_color = QColor(0, 0, 0, 50) 
        
        self.subtitle_label = QLabel("Vị trí Subtitle", self)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setStyleSheet("color: white; font-weight: bold; background-color: transparent; border: none;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.subtitle_label)
        
        effect = QGraphicsDropShadowEffect(self.subtitle_label)
        effect.setOffset(2, 2)
        effect.setBlurRadius(5)
        effect.setColor(QColor(0, 0, 0, 200))
        self.subtitle_label.setGraphicsEffect(effect)

        self.dragging = False
        self.resizing_top = False
        self.resizing_bottom = False
        self.drag_start_y = 0
        self.rect_start = QRect()
        self.min_height = 40
        self.margin = 10
        self.parent_height = 1000

        self.resize(100, 80)

    def set_blur_mode(self, mode):
        if mode == "Làm mờ (Blur)":
            # Dùng màu tối có độ trong suốt (opacity) để biểu diễn mờ thay vì cục màu trắng
            self.bg_color = QColor(20, 20, 20, 160)
        elif mode == "Hộp đen (Black Box)":
            self.bg_color = QColor(0, 0, 0, 220)
        else:
            self.bg_color = QColor(0, 0, 0, 50)
        self.update()

    def paintEvent(self, event):
        # Tự vẽ background thủ công để không bị đè bởi QSS
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Vẽ nền
        painter.setBrush(QBrush(self.bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 8, 8)
        
        # Viền đứt đoạn
        pen = QPen(QColor(255, 255, 255, 180))
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRoundedRect(1, 1, self.width()-2, self.height()-2, 8, 8)
        
        # Tay cầm (handles)
        painter.setBrush(QColor(255, 255, 255, 200))
        painter.setPen(Qt.PenStyle.NoPen)
        
        handle_len = 30
        handle_thick = 4
        
        painter.drawRoundedRect((self.width() - handle_len) // 2, 2, handle_len, handle_thick, 2, 2)
        painter.drawRoundedRect((self.width() - handle_len) // 2, self.height() - handle_thick - 2, handle_len, handle_thick, 2, 2)
        
        painter.drawRoundedRect(2, (self.height() - handle_len) // 2, handle_thick, handle_len, 2, 2)
        painter.drawRoundedRect(self.width() - handle_thick - 2, (self.height() - handle_len) // 2, handle_thick, handle_len, 2, 2)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_y = event.pos().y()
            self.rect_start = self.geometry()
            
            if self.drag_start_y <= self.margin:
                self.resizing_top = True
            elif self.drag_start_y >= self.height() - self.margin:
                self.resizing_bottom = True
            else:
                self.dragging = True

    def mouseMoveEvent(self, event):
        y = event.pos().y()
        
        if y <= self.margin or y >= self.height() - self.margin:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)

        if self.dragging:
            delta = y - self.drag_start_y
            new_y = self.y() + delta
            if new_y < 0: new_y = 0
            if new_y + self.height() > self.parent_height:
                new_y = self.parent_height - self.height()
            self.move(self.x(), new_y)
            
        elif self.resizing_top:
            delta = y - self.drag_start_y
            new_y = self.geometry().y() + delta
            new_h = self.geometry().height() - delta
            if new_h >= self.min_height and new_y >= 0:
                self.setGeometry(self.x(), new_y, self.width(), new_h)
                
        elif self.resizing_bottom:
            delta = y - self.drag_start_y
            new_h = self.rect_start.height() + delta
            if new_h >= self.min_height and self.y() + new_h <= self.parent_height:
                self.resize(self.width(), new_h)

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.resizing_top = False
        self.resizing_bottom = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
