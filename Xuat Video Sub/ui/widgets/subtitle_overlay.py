from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem, QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QSpinBox, QComboBox, QDoubleSpinBox, QColorDialog, QPushButton, QFontComboBox, QGraphicsDropShadowEffect, QCheckBox, QLabel, QSlider, QGraphicsPixmapItem
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPen, QBrush, QPixmap, QImage
import cv2
import numpy as np

from ui.widgets.common import ResizableGraphicsRectItem

class SubtitleGraphicsItem(ResizableGraphicsRectItem):
    def __init__(self, style, parent=None):
        super().__init__(QRectF(0, 0, 100, 50), parent)
        self.style = style
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        
        self.setPen(QPen(QColor(255, 255, 255, 100), 2, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        
        # Background blur pixmap
        self.bg_blur_pixmap = QGraphicsPixmapItem(self)
        self.bg_blur_pixmap.setZValue(-1)
        self.bg_blur_pixmap.setVisible(False)
        self.setFlag(self.GraphicsItemFlag.ItemClipsChildrenToShape, True)
        
        self.text_item = QGraphicsTextItem(self)
        self.text_item.setPlainText("Văn bản phụ đề mẫu")
        
        self.glow_effect = QGraphicsDropShadowEffect()
        self.text_item.setGraphicsEffect(self.glow_effect)
        
        self.update_font()

    def update_font(self):
        font = QFont(self.style.font_family, int(self.style.font_size))
        
        self.text_item.setFont(font)
        
        # Color
        if self.style.use_color:
            self.text_item.setDefaultTextColor(QColor(self.style.color))
        else:
            self.text_item.setDefaultTextColor(QColor(255, 255, 255))
            
        from PyQt6.QtGui import QTextCursor, QTextCharFormat
        cursor = QTextCursor(self.text_item.document())
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextCharFormat()
        
        # Outline via TextCharFormat
        if self.style.use_outline:
            pen = QPen(QColor(self.style.outline_color), self.style.outline_width)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            fmt.setTextOutline(pen)
        else:
            fmt.setTextOutline(QPen(Qt.PenStyle.NoPen))
            
        cursor.mergeCharFormat(fmt)
        
        # Glow via DropShadowEffect
        if self.style.use_glow:
            self.glow_effect.setEnabled(True)
            self.glow_effect.setColor(QColor(self.style.glow_color))
            self.glow_effect.setBlurRadius(self.style.glow_radius)
            self.glow_effect.setOffset(0, 0)
        else:
            self.glow_effect.setEnabled(False)
        
        br = self.text_item.boundingRect()
        rr = self.rect()
        self.text_item.setPos((rr.width() - br.width())/2, (rr.height() - br.height())/2)

    def set_text(self, text):
        self.text_item.setPlainText(text)
        self.update_font()

    def set_frame(self, qimage: QImage):
        if not getattr(self.style, 'use_background_blur', False) or getattr(self.style, 'blur_intensity', 0) <= 0:
            self.bg_blur_pixmap.setVisible(False)
            return
            
        self.bg_blur_pixmap.setVisible(True)
        
        scene_rect = self.sceneBoundingRect()
        crop_rect = scene_rect.toRect().intersected(qimage.rect())
        
        if crop_rect.isEmpty():
            return
            
        cropped = qimage.copy(crop_rect)
        cropped = cropped.convertToFormat(QImage.Format.Format_RGB32)
        
        scale_factor = 4
        small_width = max(1, cropped.width() // scale_factor)
        small_height = max(1, cropped.height() // scale_factor)
        cropped_small = cropped.scaled(small_width, small_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        
        ptr = cropped_small.bits()
        ptr.setsize(small_height * small_width * 4)
        arr = np.array(ptr).reshape(small_height, small_width, 4)
        
        kernel = 1 + int(self.style.blur_intensity * 2)
        kernel = max(3, kernel // scale_factor)
        if kernel % 2 == 0: kernel += 1
        
        sigma = kernel / 3.0
        blurred_arr = cv2.GaussianBlur(arr, (kernel, kernel), sigmaX=sigma)
        
        qimg_blur_small = QImage(blurred_arr.data, small_width, small_height, 4 * small_width, QImage.Format.Format_RGB32).copy()
        qimg_blur = qimg_blur_small.scaled(cropped.width(), cropped.height(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        
        self.bg_blur_pixmap.setPixmap(QPixmap.fromImage(qimg_blur))
        self.bg_blur_pixmap.setPos(self.mapFromScene(float(crop_rect.x()), float(crop_rect.y())))

class SubtitleOverlayWidget(QWidget):
    def __init__(self, scene, style_model, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.style = style_model
        
        self.graphics_item = SubtitleGraphicsItem(self.style)
        self.scene.addItem(self.graphics_item)
        self.graphics_item.setZValue(200)
        
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Real-time update and pause hooks
        self.graphics_item.on_geometry_changed = lambda: self.graphics_item.set_frame(self.last_image) if hasattr(self, 'last_image') and self.last_image else None
        self.graphics_item.on_interaction = self.request_pause
        
        form = QFormLayout()
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(self.style.font_family))
        self.font_combo.currentFontChanged.connect(self.on_font_changed)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(10, 200)
        self.font_size_spin.setValue(int(self.style.font_size))
        self.font_size_spin.valueChanged.connect(self.on_style_changed)
        
        # Color row
        color_layout = QHBoxLayout()
        self.chk_color = QCheckBox("Màu chữ")
        self.chk_color.setChecked(self.style.use_color)
        self.btn_color = QPushButton("Chọn màu")
        self.btn_color.setEnabled(self.style.use_color)
        
        self.chk_color.toggled.connect(self.on_chk_color_toggled)
        self.btn_color.clicked.connect(self.choose_color)
        
        color_layout.addWidget(self.chk_color)
        color_layout.addWidget(self.btn_color)
        
        # Outline row
        outline_layout = QHBoxLayout()
        self.chk_outline = QCheckBox("Tô viền")
        self.chk_outline.setChecked(self.style.use_outline)
        self.btn_outline = QPushButton("Màu viền")
        self.btn_outline.setEnabled(self.style.use_outline)
        self.spin_outline = QSpinBox()
        self.spin_outline.setRange(0, 20)
        self.spin_outline.setValue(int(self.style.outline_width))
        self.spin_outline.setEnabled(self.style.use_outline)
        
        self.chk_outline.toggled.connect(self.on_chk_outline_toggled)
        self.btn_outline.clicked.connect(self.choose_outline_color)
        self.spin_outline.valueChanged.connect(self.on_style_changed)
        
        outline_layout.addWidget(self.chk_outline)
        outline_layout.addWidget(self.btn_outline)
        outline_layout.addWidget(QLabel("Dày:"))
        outline_layout.addWidget(self.spin_outline)
        
        # Glow row
        glow_layout = QHBoxLayout()
        self.chk_glow = QCheckBox("Rực sáng")
        self.chk_glow.setChecked(self.style.use_glow)
        self.btn_glow = QPushButton("Màu sáng")
        self.btn_glow.setEnabled(self.style.use_glow)
        self.spin_glow = QSpinBox()
        self.spin_glow.setRange(0, 50)
        self.spin_glow.setValue(int(self.style.glow_radius))
        self.spin_glow.setEnabled(self.style.use_glow)
        glow_layout.addWidget(self.chk_glow)
        glow_layout.addWidget(self.btn_glow)
        glow_layout.addWidget(QLabel("Toả:"))
        glow_layout.addWidget(self.spin_glow)
        
        self.chk_glow.toggled.connect(self.on_chk_glow_toggled)
        self.btn_glow.clicked.connect(self.choose_glow_color)
        self.spin_glow.valueChanged.connect(self.on_style_changed)
        
        # Blur row
        blur_layout = QHBoxLayout()
        self.chk_blur = QCheckBox("Kèm Làm Mờ")
        self.chk_blur.setChecked(self.style.use_background_blur)
        self.spin_blur_intensity = QSpinBox()
        self.spin_blur_intensity.setRange(1, 100)
        self.spin_blur_intensity.setValue(self.style.blur_intensity)
        self.spin_blur_intensity.setEnabled(self.style.use_background_blur)
        blur_layout.addWidget(self.chk_blur)
        blur_layout.addWidget(QLabel("Mức độ:"))
        blur_layout.addWidget(self.spin_blur_intensity)
        
        self.chk_blur.toggled.connect(self.on_chk_blur_toggled)
        self.spin_blur_intensity.valueChanged.connect(self.on_style_changed)
        
        form.addRow("Font:", self.font_combo)
        form.addRow("Cỡ chữ:", self.font_size_spin)
        form.addRow(color_layout)
        form.addRow(outline_layout)
        form.addRow(glow_layout)
        form.addRow(blur_layout)
        layout.addLayout(form)
        
    def on_font_changed(self, font):
        self.style.font_family = font.family()
        self.graphics_item.update_font()
        

    def on_chk_color_toggled(self, checked):
        self.style.use_color = checked
        self.btn_color.setEnabled(checked)
        self.graphics_item.update_font()
        
    def on_chk_outline_toggled(self, checked):
        self.style.use_outline = checked
        self.btn_outline.setEnabled(checked)
        self.spin_outline.setEnabled(checked)
        self.graphics_item.update_font()
        
    def on_chk_glow_toggled(self, checked):
        self.style.use_glow = checked
        self.btn_glow.setEnabled(checked)
        self.spin_glow.setEnabled(checked)
        self.graphics_item.update_font()
        
    def on_chk_blur_toggled(self, checked):
        self.style.use_background_blur = checked
        self.spin_blur_intensity.setEnabled(checked)
        self.graphics_item.set_frame(self.last_image) if hasattr(self, 'last_image') and self.last_image else None
        
    def on_style_changed(self):
        self.request_pause()
        self.style.font_size = float(self.font_size_spin.value())
        self.style.outline_width = self.spin_outline.value()
        self.style.glow_radius = self.spin_glow.value()
        self.style.blur_intensity = self.spin_blur_intensity.value()
        
        self.graphics_item.update_font()
        self.graphics_item.set_frame(self.last_image) if hasattr(self, 'last_image') and self.last_image else None
        self.style.save()
        
    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.style.color), self)
        if color.isValid():
            self.style.color = color.name()
            self.graphics_item.update_font()
            
    def choose_outline_color(self):
        color = QColorDialog.getColor(QColor(self.style.outline_color), self)
        if color.isValid():
            self.style.outline_color = color.name()
            self.graphics_item.update_font()
            
    def choose_glow_color(self):
        color = QColorDialog.getColor(QColor(self.style.glow_color), self)
        if color.isValid():
            self.style.glow_color = color.name()
            self.graphics_item.update_font()

    def update_from_video_size(self, width, height):
        x = width * self.style.box_x_pct
        y = height * self.style.box_y_pct
        w = width * self.style.box_w_pct
        h = height * self.style.box_h_pct
        self.graphics_item.setPos(x, y)
        self.graphics_item.setRect(0, 0, w, h)
        
    def sync_to_model(self, total_width, total_height):
        pos = self.graphics_item.scenePos()
        rect = self.graphics_item.rect()
        self.style.box_x_pct = pos.x() / total_width
        self.style.box_y_pct = pos.y() / total_height
        self.style.box_w_pct = rect.width() / total_width
        self.style.box_h_pct = rect.height() / total_height
        self.style.save()
        
    def update_text(self, text):
        self.graphics_item.set_text(text)
        
    def process_frame(self, qimage):
        self.last_image = qimage
        self.graphics_item.set_frame(qimage)
        
    def save_position_to_model(self, total_height):
        # We need total_width as well
        scene = self.graphics_item.scene()
        total_width = scene.width() if scene else 1920
        
        pos = self.graphics_item.scenePos()
        rect = self.graphics_item.rect()
        
        self.style.box_x_pct = max(0.0, min(1.0, pos.x() / total_width))
        self.style.box_y_pct = max(0.0, min(1.0, pos.y() / total_height))
        self.style.box_w_pct = max(0.0, min(1.0, rect.width() / total_width))
        self.style.box_h_pct = max(0.0, min(1.0, rect.height() / total_height))

    def request_pause(self):
        if hasattr(self, 'pause_callback') and self.pause_callback:
            self.pause_callback()
