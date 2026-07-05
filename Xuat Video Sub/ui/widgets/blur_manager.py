from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QGraphicsPixmapItem, QMenu, QInputDialog, QMessageBox, QListWidgetItem, QSlider, QLabel, QFormLayout
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPen, QBrush, QPixmap, QImage, QPainterPath
import uuid
import cv2
import numpy as np

from ui.widgets.common import ResizableGraphicsRectItem

class BlurGraphicsItem(ResizableGraphicsRectItem):
    def __init__(self, model, parent=None):
        super().__init__(QRectF(0, 0, 200, 150), parent)
        self.model = model
        
        # Transparent border
        self.setPen(QPen(QColor(255, 215, 0, 200), 2, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        
        self.setFlag(self.GraphicsItemFlag.ItemClipsChildrenToShape, True)
        
        # Child pixmap for the blurred image
        self.pixmap_item = QGraphicsPixmapItem(self)
        self.pixmap_item.setPos(0, 0)
        self.update_effect()

    def update_effect(self):
        # Update shape to apply new corner radius
        self.update()

    def shape(self):
        path = QPainterPath()
        r = self.rect()
        if r.width() > 0 and r.height() > 0:
            radius = min(r.width(), r.height()) / 2.0 * (self.model.corner_radius / 100.0)
            path.addRoundedRect(r, radius, radius)
        return path

    def set_frame(self, qimage: QImage):
        if getattr(self.model, 'intensity', 0) <= 0:
            self.pixmap_item.setVisible(False)
            return
            
        self.pixmap_item.setVisible(True)
        
        scene_rect = self.sceneBoundingRect()
        crop_rect = scene_rect.toRect().intersected(qimage.rect())
        
        if crop_rect.isEmpty():
            return
            
        cropped = qimage.copy(crop_rect)
        cropped = cropped.convertToFormat(QImage.Format.Format_RGB32)
        
        # Scale down for performance
        scale_factor = 4
        small_width = max(1, cropped.width() // scale_factor)
        small_height = max(1, cropped.height() // scale_factor)
        cropped_small = cropped.scaled(small_width, small_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        
        ptr = cropped_small.bits()
        ptr.setsize(small_height * small_width * 4)
        arr = np.array(ptr).reshape(small_height, small_width, 4)
        
        kernel = 1 + int(self.model.intensity * 2)
        # Scale kernel down as well to match visual effect
        kernel = max(3, kernel // scale_factor)
        if kernel % 2 == 0: kernel += 1
        
        sigma = kernel / 3.0
        blurred_arr = cv2.GaussianBlur(arr, (kernel, kernel), sigmaX=sigma)
        
        qimg_blur_small = QImage(blurred_arr.data, small_width, small_height, 4 * small_width, QImage.Format.Format_RGB32).copy()
        qimg_blur = qimg_blur_small.scaled(cropped.width(), cropped.height(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        
        self.pixmap_item.setPixmap(QPixmap.fromImage(qimg_blur))
        self.pixmap_item.setPos(self.mapFromScene(float(crop_rect.x()), float(crop_rect.y())))
        
    def update_model(self, total_width, total_height):
        scene_rect = self.sceneBoundingRect()
        
        self.model.x_pct = scene_rect.center().x() / total_width
        self.model.y_pct = scene_rect.center().y() / total_height
        self.model.w_pct = scene_rect.width() / total_width
        self.model.h_pct = scene_rect.height() / total_height
        self.model.rotation = self.rotation()

class BlurManager(QWidget):
    def __init__(self, scene, blurs_list, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.blurs = blurs_list
        self.items = {}
        self.last_image = None
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        
        # Left side: List and Add button
        left_layout = QVBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.list_widget.currentRowChanged.connect(self.on_item_selected)
        
        btn_add = QPushButton("+ Thêm Vùng Làm Mờ (Blur)")
        btn_add.clicked.connect(self.add_blur)
        
        left_layout.addWidget(btn_add)
        left_layout.addWidget(self.list_widget)
        
        # Right side: Properties panel
        right_layout = QFormLayout()
        
        self.slider_intensity = QSlider(Qt.Orientation.Horizontal)
        self.slider_intensity.setRange(0, 100)
        self.slider_intensity.setEnabled(False)
        self.slider_intensity.valueChanged.connect(self.on_properties_changed)
        
        self.slider_radius = QSlider(Qt.Orientation.Horizontal)
        self.slider_radius.setRange(0, 100)
        self.slider_radius.setEnabled(False)
        self.slider_radius.valueChanged.connect(self.on_properties_changed)
        
        right_layout.addRow(QLabel("Độ mờ (Intensity):"), self.slider_intensity)
        right_layout.addRow(QLabel("Bo góc (Corner):"), self.slider_radius)
        
        prop_widget = QWidget()
        prop_widget.setLayout(right_layout)
        
        layout.addLayout(left_layout, stretch=1)
        layout.addWidget(prop_widget, stretch=1)

    def add_blur(self):
        from models.subtitle_style import BlurModel
        b = BlurModel(id=str(uuid.uuid4()), blur_type="gaussian")
        self.blurs.append(b)
        
        list_item = QListWidgetItem(f"Blur Block")
        list_item.setData(Qt.ItemDataRole.UserRole, b.id)
        self.list_widget.addItem(list_item)
        
        item = BlurGraphicsItem(b)
        self.scene.addItem(item)
        item.setPos(200, 200)
        item.setZValue(50)
        
        # Real-time update hooks
        item.on_geometry_changed = lambda: item.set_frame(self.last_image) if self.last_image else None
        item.on_interaction = self.request_pause
        
        self.items[b.id] = item
        
    def request_pause(self):
        if hasattr(self, 'pause_callback') and self.pause_callback:
            self.pause_callback()
        
    def show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item: return
        
        b_id = item.data(Qt.ItemDataRole.UserRole)
        
        menu = QMenu()
        act_del = menu.addAction("Xóa")
        
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == act_del:
            self.blurs = [b for b in self.blurs if b.id != b_id]
            self.list_widget.takeItem(self.list_widget.row(item))
            if b_id in self.items:
                self.scene.removeItem(self.items[b_id])
                del self.items[b_id]
            self.update_properties_panel()
        
    def on_item_selected(self, row):
        if row < 0: 
            self.update_properties_panel()
            return
            
        item = self.list_widget.item(row)
        b_id = item.data(Qt.ItemDataRole.UserRole)
        for item_id, g_item in self.items.items():
            g_item.setSelected(item_id == b_id)
            
        self.update_properties_panel(b_id)
            
    def update_properties_panel(self, b_id=None):
        self.slider_intensity.blockSignals(True)
        self.slider_radius.blockSignals(True)
        
        if b_id is None:
            self.slider_intensity.setEnabled(False)
            self.slider_radius.setEnabled(False)
        else:
            model = next((b for b in self.blurs if b.id == b_id), None)
            if model:
                self.slider_intensity.setEnabled(True)
                self.slider_radius.setEnabled(True)
                self.slider_intensity.setValue(model.intensity)
                self.slider_radius.setValue(model.corner_radius)
                
        self.slider_intensity.blockSignals(False)
        self.slider_radius.blockSignals(False)
        
    def on_properties_changed(self):
        row = self.list_widget.currentRow()
        if row < 0: return
        item = self.list_widget.item(row)
        b_id = item.data(Qt.ItemDataRole.UserRole)
        
        model = next((b for b in self.blurs if b.id == b_id), None)
        if model:
            self.request_pause()
            model.intensity = self.slider_intensity.value()
            model.corner_radius = self.slider_radius.value()
            if b_id in self.items:
                self.items[b_id].update_effect()
                if self.last_image:
                    self.items[b_id].set_frame(self.last_image)
            
    def sync_to_models(self, total_width, total_height):
        for b_id, item in self.items.items():
            item.update_model(total_width, total_height)
            
    def process_frame(self, image: QImage):
        self.last_image = image
        for b_id, item in self.items.items():
            item.set_frame(image)
