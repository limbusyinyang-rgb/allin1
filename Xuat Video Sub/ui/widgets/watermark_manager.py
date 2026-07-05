from PyQt6.QtWidgets import QGraphicsPixmapItem, QGraphicsTextItem, QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QSpinBox, QDoubleSpinBox, QColorDialog, QPushButton, QFontComboBox, QGraphicsDropShadowEffect, QListWidget, QListWidgetItem, QMenu, QInputDialog, QFileDialog, QCheckBox, QLabel, QLineEdit
from PyQt6.QtCore import Qt, QRectF, QSettings
from PyQt6.QtGui import QColor, QFont, QPen, QBrush, QPixmap
import uuid
import os

from ui.widgets.common import ResizableGraphicsRectItem

class WatermarkGraphicsItem(ResizableGraphicsRectItem):
    def __init__(self, model, parent=None):
        super().__init__(QRectF(0, 0, 200, 100), parent)
        self.model = model
        
        self.setPen(QPen(QColor(0, 255, 0, 200), 2, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        
        # Background blur pixmap
        self.bg_blur_pixmap = QGraphicsPixmapItem(self)
        self.bg_blur_pixmap.setZValue(-1)
        self.bg_blur_pixmap.setVisible(False)
        self.setFlag(self.GraphicsItemFlag.ItemClipsChildrenToShape, True)
        
        if self.model.is_text:
            self.content_item = QGraphicsTextItem("Watermark", self)
            self.glow_effect = QGraphicsDropShadowEffect()
            self.content_item.setGraphicsEffect(self.glow_effect)
            self.update_font()
        else:
            self.content_item = QGraphicsPixmapItem(self)
            self.update_image()

    def update_font(self):
        if not self.model.is_text: return
        
        font = QFont(self.model.font_family or "Arial", int(self.model.font_size))
        self.content_item.setFont(font)
        
        if self.model.use_color:
            self.content_item.setDefaultTextColor(QColor(self.model.color))
        else:
            self.content_item.setDefaultTextColor(QColor(255, 255, 255))
            
        from PyQt6.QtGui import QTextCursor, QTextCharFormat
        cursor = QTextCursor(self.content_item.document())
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextCharFormat()
        
        if self.model.use_outline:
            pen = QPen(QColor(self.model.outline_color), self.model.outline_width)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            fmt.setTextOutline(pen)
        else:
            fmt.setTextOutline(QPen(Qt.PenStyle.NoPen))
            
        cursor.mergeCharFormat(fmt)
            
        if self.model.use_glow:
            self.glow_effect.setEnabled(True)
            self.glow_effect.setColor(QColor(self.model.glow_color))
            self.glow_effect.setBlurRadius(self.model.glow_radius)
            self.glow_effect.setOffset(0, 0)
        else:
            self.glow_effect.setEnabled(False)
            
        self.content_item.setPlainText(self.model.text or "Watermark")
        self.content_item.setTextWidth(self.rect().width())
        self.content_item.setOpacity(self.model.opacity)
        
        # Center horizontally and vertically
        br = self.content_item.boundingRect()
        rr = self.rect()
        self.content_item.setPos((rr.width() - br.width())/2, (rr.height() - br.height())/2)

    def set_frame(self, qimage):
        if not getattr(self.model, 'use_background_blur', False) or getattr(self.model, 'blur_intensity', 0) <= 0:
            self.bg_blur_pixmap.setVisible(False)
            return
            
        self.bg_blur_pixmap.setVisible(True)
        
        scene_rect = self.sceneBoundingRect()
        crop_rect = scene_rect.toRect().intersected(qimage.rect())
        
        if crop_rect.isEmpty():
            return
            
        import cv2
        import numpy as np
        from PyQt6.QtGui import QImage, QPixmap
        
        cropped = qimage.copy(crop_rect)
        cropped = cropped.convertToFormat(QImage.Format.Format_RGB32)
        
        scale_factor = 4
        small_width = max(1, cropped.width() // scale_factor)
        small_height = max(1, cropped.height() // scale_factor)
        cropped_small = cropped.scaled(small_width, small_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        
        ptr = cropped_small.bits()
        ptr.setsize(small_height * small_width * 4)
        arr = np.array(ptr).reshape(small_height, small_width, 4)
        
        kernel = 1 + int(self.model.blur_intensity * 2)
        kernel = max(3, kernel // scale_factor)
        if kernel % 2 == 0: kernel += 1
        
        sigma = kernel / 3.0
        blurred_arr = cv2.GaussianBlur(arr, (kernel, kernel), sigmaX=sigma)
        
        qimg_blur_small = QImage(blurred_arr.data, small_width, small_height, 4 * small_width, QImage.Format.Format_RGB32).copy()
        qimg_blur = qimg_blur_small.scaled(cropped.width(), cropped.height(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        
        self.bg_blur_pixmap.setPixmap(QPixmap.fromImage(qimg_blur))
        self.bg_blur_pixmap.setPos(self.mapFromScene(float(crop_rect.x()), float(crop_rect.y())))

    def update_image(self):
        if self.model.is_text: return
        if self.model.image_path:
            pix = QPixmap(self.model.image_path)
            # Scale pixmap to fit rect approximately
            r = self.rect()
            pix = pix.scaled(int(r.width()), int(r.height()), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.content_item.setPixmap(pix)
            self.content_item.setOpacity(self.model.opacity)
            
            pr = self.content_item.boundingRect()
            self.content_item.setPos((r.width() - pr.width())/2, (r.height() - pr.height())/2)

    def update_model(self, total_width, total_height):
        pos = self.scenePos()
        rect = self.rect()
        self.model.x_pct = (pos.x() + rect.width()/2) / total_width
        self.model.y_pct = (pos.y() + rect.height()/2) / total_height
        self.model.w_pct = rect.width() / total_width
        self.model.h_pct = rect.height() / total_height
        self.model.rotation = self.rotation()
        
    def itemChange(self, change, value):
        if change == QGraphicsPixmapItem.GraphicsItemChange.ItemTransformHasChanged or change == QGraphicsPixmapItem.GraphicsItemChange.ItemPositionHasChanged:
            if self.model.is_text:
                self.content_item.setTextWidth(self.rect().width())
                br = self.content_item.boundingRect()
                rr = self.rect()
                self.content_item.setPos((rr.width() - br.width())/2, (rr.height() - br.height())/2)
            else:
                self.update_image()
        return super().itemChange(change, value)

class WatermarkManager(QWidget):
    def __init__(self, scene, watermarks_list, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.watermarks = watermarks_list
        self.items = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        btns = QHBoxLayout()
        btn_add_txt = QPushButton("+ Text WM")
        btn_add_txt.clicked.connect(lambda: self.add_wm(True))
        btn_add_img = QPushButton("+ Image WM")
        btn_add_img.clicked.connect(lambda: self.add_wm(False))
        btns.addWidget(btn_add_txt)
        btns.addWidget(btn_add_img)
        
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.list_widget.currentRowChanged.connect(self.on_item_selected)
        
        # Properties panel
        self.prop_panel = QWidget()
        prop_layout = QFormLayout(self.prop_panel)
        
        self.text_input = QLineEdit()
        self.text_input.textChanged.connect(self.update_prop)
        
        self.font_combo = QFontComboBox()
        self.font_combo.currentFontChanged.connect(self.update_prop)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(10, 200)
        self.font_size_spin.valueChanged.connect(self.update_prop)
        
        self.opacity_spin = QDoubleSpinBox()
        self.opacity_spin.setRange(0.1, 1.0)
        self.opacity_spin.setSingleStep(0.1)
        self.opacity_spin.valueChanged.connect(self.update_prop)
        
        # Styling rows
        color_layout = QHBoxLayout()
        self.chk_color = QCheckBox("Màu chữ")
        self.btn_color = QPushButton("Chọn màu")
        self.btn_color.clicked.connect(self.choose_color)
        color_layout.addWidget(self.chk_color)
        color_layout.addWidget(self.btn_color)
        
        outline_layout = QHBoxLayout()
        self.chk_outline = QCheckBox("Tô viền")
        self.btn_outline = QPushButton("Màu viền")
        self.btn_outline.clicked.connect(self.choose_outline_color)
        self.spin_outline = QDoubleSpinBox()
        self.spin_outline.setRange(0.0, 20.0)
        outline_layout.addWidget(self.chk_outline)
        outline_layout.addWidget(self.btn_outline)
        outline_layout.addWidget(QLabel("Dày:"))
        outline_layout.addWidget(self.spin_outline)
        
        glow_layout = QHBoxLayout()
        self.chk_glow = QCheckBox("Rực sáng")
        self.btn_glow = QPushButton("Màu sáng")
        self.btn_glow.clicked.connect(self.choose_glow_color)
        self.spin_glow = QDoubleSpinBox()
        self.spin_glow.setRange(0.0, 50.0)
        glow_layout.addWidget(self.chk_glow)
        glow_layout.addWidget(self.btn_glow)
        glow_layout.addWidget(QLabel("Toả:"))
        glow_layout.addWidget(self.spin_glow)
        
        self.chk_color.toggled.connect(self.update_prop)
        self.chk_outline.toggled.connect(self.update_prop)
        self.chk_glow.toggled.connect(self.update_prop)
        self.spin_outline.valueChanged.connect(self.update_prop)
        self.spin_glow.valueChanged.connect(self.update_prop)
        
        blur_layout = QHBoxLayout()
        self.chk_blur = QCheckBox("Kèm Làm Mờ")
        self.spin_blur_intensity = QSpinBox()
        self.spin_blur_intensity.setRange(1, 100)
        blur_layout.addWidget(self.chk_blur)
        blur_layout.addWidget(QLabel("Mức độ:"))
        blur_layout.addWidget(self.spin_blur_intensity)
        
        self.chk_blur.toggled.connect(self.update_prop)
        self.spin_blur_intensity.valueChanged.connect(self.update_prop)
        
        prop_layout.addRow("Nội dung:", self.text_input)
        prop_layout.addRow("Font:", self.font_combo)
        prop_layout.addRow("Cỡ chữ:", self.font_size_spin)
        prop_layout.addRow("Độ mờ (Opacity):", self.opacity_spin)
        prop_layout.addRow(color_layout)
        prop_layout.addRow(outline_layout)
        prop_layout.addRow(glow_layout)
        prop_layout.addRow(blur_layout)
        
        self.prop_panel.setEnabled(False)
        
        layout.addLayout(btns)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.prop_panel)
        
        self.current_wm_id = None

    def add_wm(self, is_text):
        from models.subtitle_style import WatermarkModel
        w = WatermarkModel(id=str(uuid.uuid4()), is_text=is_text)
        if not is_text:
            settings = QSettings("MyCapCut", "SubExporter")
            last_dir = settings.value("last_watermark_dir", "")
            path, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh Watermark", last_dir, "Images (*.png *.jpg *.jpeg)")
            if not path: return
            settings.setValue("last_watermark_dir", os.path.dirname(path))
            w.image_path = path
        else:
            w.text = "Watermark"
            w.font_family = "Arial"
            
        self.watermarks.append(w)
        lbl = "Text WM" if is_text else "Image WM"
        list_item = QListWidgetItem(f"{lbl} - {w.text or 'Img'}")
        list_item.setData(Qt.ItemDataRole.UserRole, w.id)
        self.list_widget.addItem(list_item)
        
        item = WatermarkGraphicsItem(w)
        self.scene.addItem(item)
        item.setPos(50, 50)
        item.setZValue(200)
        self.items[w.id] = item

    def show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item: return
        w_id = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu()
        act_del = menu.addAction("Xóa")
        if menu.exec(self.list_widget.mapToGlobal(pos)) == act_del:
            self.watermarks = [w for w in self.watermarks if w.id != w_id]
            self.list_widget.takeItem(self.list_widget.row(item))
            if w_id in self.items:
                self.scene.removeItem(self.items[w_id])
                del self.items[w_id]
            if self.current_wm_id == w_id:
                self.prop_panel.setEnabled(False)
                self.current_wm_id = None

    def on_item_selected(self, row):
        if row < 0: return
        item = self.list_widget.item(row)
        w_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_wm_id = w_id
        
        # Select in scene
        for item_id, g_item in self.items.items():
            g_item.setSelected(item_id == w_id)
        
        w = next((x for x in self.watermarks if x.id == w_id), None)
        if not w: return
        
        self.prop_panel.setEnabled(True)
        self.text_input.blockSignals(True)
        self.font_size_spin.blockSignals(True)
        self.opacity_spin.blockSignals(True)
        self.chk_color.blockSignals(True)
        self.chk_outline.blockSignals(True)
        self.chk_glow.blockSignals(True)
        self.spin_outline.blockSignals(True)
        self.spin_glow.blockSignals(True)
        
        self.text_input.setText(w.text)
        self.font_size_spin.setValue(int(w.font_size))
        self.opacity_spin.setValue(w.opacity)
        self.chk_color.setChecked(w.use_color)
        self.chk_outline.setChecked(w.use_outline)
        self.chk_glow.setChecked(w.use_glow)
        self.spin_outline.setValue(int(w.outline_width))
        self.spin_glow.setValue(int(w.glow_radius))
        
        self.chk_blur.blockSignals(True)
        self.spin_blur_intensity.blockSignals(True)
        self.chk_blur.setChecked(getattr(w, 'use_background_blur', False))
        self.spin_blur_intensity.setValue(getattr(w, 'blur_intensity', 30))
        self.spin_blur_intensity.setEnabled(getattr(w, 'use_background_blur', False))
        
        self.btn_color.setEnabled(w.use_color)
        self.btn_outline.setEnabled(w.use_outline)
        self.spin_outline.setEnabled(w.use_outline)
        self.btn_glow.setEnabled(w.use_glow)
        self.spin_glow.setEnabled(w.use_glow)
        
        self.text_input.setEnabled(w.is_text)
        self.font_combo.setEnabled(w.is_text)
        self.font_size_spin.setEnabled(w.is_text)
        self.chk_color.setEnabled(w.is_text)
        self.chk_outline.setEnabled(w.is_text)
        self.chk_glow.setEnabled(w.is_text)
        
        self.text_input.blockSignals(False)
        self.font_size_spin.blockSignals(False)
        self.opacity_spin.blockSignals(False)
        self.chk_color.blockSignals(False)
        self.chk_outline.blockSignals(False)
        self.chk_glow.blockSignals(False)
        self.spin_outline.blockSignals(False)
        self.spin_glow.blockSignals(False)
        self.chk_blur.blockSignals(False)
        self.spin_blur_intensity.blockSignals(False)

    def update_prop(self):
        if not self.current_wm_id: return
        w = next((x for x in self.watermarks if x.id == self.current_wm_id), None)
        if not w: return
        
        w.text = self.text_input.text()
        w.font_family = self.font_combo.currentFont().family()
        w.font_size = self.font_size_spin.value()
        w.opacity = self.opacity_spin.value()
        
        w.use_color = self.chk_color.isChecked()
        self.btn_color.setEnabled(w.use_color)
        w.use_outline = self.chk_outline.isChecked()
        self.btn_outline.setEnabled(w.use_outline)
        self.spin_outline.setEnabled(w.use_outline)
        w.use_glow = self.chk_glow.isChecked()
        self.btn_glow.setEnabled(w.use_glow)
        self.spin_glow.setEnabled(w.use_glow)
        
        w.outline_width = self.spin_outline.value()
        w.glow_radius = self.spin_glow.value()
        w.use_background_blur = self.chk_blur.isChecked()
        w.blur_intensity = self.spin_blur_intensity.value()
        self.spin_blur_intensity.setEnabled(w.use_background_blur)
        
        if self.current_wm_id in self.items:
            item = self.items[self.current_wm_id]
            if w.is_text: item.update_font()
            else: item.update_image()
            
        cur_item = self.list_widget.currentItem()
        if cur_item:
            lbl = "Text WM" if w.is_text else "Image WM"
            cur_item.setText(f"{lbl} - {w.text or 'Img'}")
            
    def choose_color(self):
        if not self.current_wm_id: return
        w = next((x for x in self.watermarks if x.id == self.current_wm_id), None)
        c = QColorDialog.getColor(QColor(w.color), self)
        if c.isValid():
            w.color = c.name()
            self.update_prop()
            
    def choose_outline_color(self):
        if not self.current_wm_id: return
        w = next((x for x in self.watermarks if x.id == self.current_wm_id), None)
        c = QColorDialog.getColor(QColor(w.outline_color), self)
        if c.isValid():
            w.outline_color = c.name()
            self.update_prop()
            
    def choose_glow_color(self):
        if not self.current_wm_id: return
        w = next((x for x in self.watermarks if x.id == self.current_wm_id), None)
        c = QColorDialog.getColor(QColor(w.glow_color), self)
        if c.isValid():
            w.glow_color = c.name()
            self.update_prop()

    def sync_to_models(self, total_width, total_height):
        for w_id, item in self.items.items():
            item.update_model(total_width, total_height)

    def process_frame(self, qimage):
        self.last_image = qimage
        for item in self.items.values():
            item.set_frame(qimage)
