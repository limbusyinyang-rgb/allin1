import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QFileDialog, QMessageBox, QColorDialog, QSpinBox,
                             QGroupBox, QFormLayout, QScrollArea)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QPixmap, QImage, QColor

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io

class ThumbnailGeneratorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tạo Thumbnail Sub (Custom Text)")
        self.resize(1100, 750)
        
        self.settings = QSettings("MyCapCut", "ThumbnailGen")
        self.bg_image_path = None
        self.current_preview = None
        
        # Default font paths on Windows
        self.font_path = "C:\\Windows\\Fonts\\arialbd.ttf"
        if not os.path.exists(self.font_path):
            self.font_path = "C:\\Windows\\Fonts\\arial.ttf"
            
        self.setup_ui()
        self.update_preview()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        
        # Left Panel (Controls)
        control_panel = QWidget()
        control_panel.setFixedWidth(400)
        control_layout = QVBoxLayout(control_panel)
        
        # BG Image Section
        bg_group = QGroupBox("Ảnh Nền (Background)")
        bg_layout = QHBoxLayout(bg_group)
        self.btn_load_bg = QPushButton("Chọn Ảnh Nền...")
        self.btn_load_bg.clicked.connect(self.load_background)
        self.lbl_bg_name = QLabel("Chưa chọn ảnh")
        bg_layout.addWidget(self.btn_load_bg)
        bg_layout.addWidget(self.lbl_bg_name)
        control_layout.addWidget(bg_group)
        
        # Text Configurations
        self.texts_config = {}
        
        for pos_name, pos_label in [("top", "Tiêu đề TRÊN"), ("middle", "Tiêu đề GIỮA"), ("bottom", "Tiêu đề DƯỚI")]:
            group = QGroupBox(pos_label)
            form = QFormLayout(group)
            
            txt_input = QLineEdit()
            txt_input.textChanged.connect(self.schedule_update)
            
            size_spin = QSpinBox()
            size_spin.setRange(10, 500)
            size_spin.setValue(100)
            size_spin.valueChanged.connect(self.schedule_update)
            
            btn_color = QPushButton("Chọn màu")
            btn_color.setStyleSheet("background-color: #ffffff; color: #000000; font-weight: bold;")
            btn_color.clicked.connect(lambda checked, b=btn_color: self.choose_color(b))
            
            btn_glow = QPushButton("Chọn màu")
            btn_glow.setStyleSheet("background-color: #ff0000; color: #ffffff; font-weight: bold;")
            btn_glow.clicked.connect(lambda checked, b=btn_glow: self.choose_color(b))
            
            glow_radius = QSpinBox()
            glow_radius.setRange(0, 100)
            glow_radius.setValue(15)
            glow_radius.valueChanged.connect(self.schedule_update)
            
            form.addRow("Nội dung:", txt_input)
            form.addRow("Kích thước (px):", size_spin)
            form.addRow("Màu chữ:", btn_color)
            form.addRow("Màu rực sáng (Glow):", btn_glow)
            form.addRow("Độ toả sáng:", glow_radius)
            
            control_layout.addWidget(group)
            
            self.texts_config[pos_name] = {
                'text': txt_input,
                'size': size_spin,
                'color': btn_color,
                'glow': btn_glow,
                'glow_radius': glow_radius
            }
            
        # Export
        self.btn_export = QPushButton("Xuất Ảnh Thumbnail")
        self.btn_export.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 10px; font-size: 16px;")
        self.btn_export.clicked.connect(self.export_thumbnail)
        control_layout.addStretch()
        control_layout.addWidget(self.btn_export)
        
        # Right Panel (Preview)
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        
        self.lbl_preview = QLabel("Vui lòng chọn ảnh nền để bắt đầu...")
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setStyleSheet("background-color: #1e1e1e; color: #666;")
        
        # Put in scroll area in case of huge images, though we will scale to fit
        preview_layout.addWidget(self.lbl_preview)
        
        main_layout.addWidget(control_panel)
        main_layout.addWidget(preview_panel, stretch=1)
        
    def choose_color(self, btn):
        color = QColorDialog.getColor()
        if color.isValid():
            bg_hex = color.name()
            # Determine text color based on brightness
            r, g, b, _ = color.getRgb()
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            fg_hex = "#000000" if brightness > 125 else "#ffffff"
            
            btn.setStyleSheet(f"background-color: {bg_hex}; color: {fg_hex}; font-weight: bold;")
            self.schedule_update()
            
    def load_background(self):
        last_dir = self.settings.value("last_img_dir", "")
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Ảnh Nền", last_dir, "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.settings.setValue("last_img_dir", os.path.dirname(path))
            self.bg_image_path = path
            self.lbl_bg_name.setText(os.path.basename(path))
            self.update_preview()
            
    def schedule_update(self):
        # Could use a QTimer to debounce if it's too slow, but PIL is fast enough for UI
        self.update_preview()
        
    def get_qcolor_from_btn(self, btn):
        style = btn.styleSheet()
        try:
            # extract background-color: #XXXXXX
            color_str = style.split("background-color: ")[1].split(";")[0].strip()
            return color_str
        except:
            return "#ffffff"
            
    def _hex_to_rgb(self, hex_str):
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 6:
            return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
        return (255, 255, 255)

    def generate_image(self):
        if not self.bg_image_path or not os.path.exists(self.bg_image_path):
            # Create a dummy blank image if no bg is selected
            img = Image.new('RGB', (1280, 720), color=(40, 40, 40))
        else:
            img = Image.open(self.bg_image_path).convert('RGBA')
            
        width, height = img.size
        
        # Draw each text
        for pos_name, cfg in self.texts_config.items():
            text = cfg['text'].text().strip()
            if not text:
                continue
                
            size = cfg['size'].value()
            color = self._hex_to_rgb(self.get_qcolor_from_btn(cfg['color']))
            glow_color = self._hex_to_rgb(self.get_qcolor_from_btn(cfg['glow']))
            glow_radius = cfg['glow_radius'].value()
            
            try:
                font = ImageFont.truetype(self.font_path, size)
            except:
                font = ImageFont.load_default()
                
            # Create a separate layer for drawing this text's glow and fill
            txt_layer = Image.new('RGBA', (width, height), (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt_layer)
            
            # Calculate text size and position
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            
            x = (width - tw) / 2
            
            if pos_name == "top":
                y = height * 0.1
            elif pos_name == "middle":
                y = (height - th) / 2
            else: # bottom
                y = height * 0.9 - th
                
            # Draw glow (by drawing thick stroke and blurring)
            if glow_radius > 0:
                glow_layer = Image.new('RGBA', (width, height), (255, 255, 255, 0))
                glow_draw = ImageDraw.Draw(glow_layer)
                
                # Draw with stroke for initial thickness
                stroke_w = int(glow_radius / 2) + 2
                glow_draw.text((x, y), text, font=font, fill=glow_color, stroke_width=stroke_w, stroke_fill=glow_color)
                
                # Apply blur
                glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(glow_radius))
                
                # Composite glow
                img = Image.alpha_composite(img, glow_layer)
                
            # Draw main text
            draw.text((x, y), text, font=font, fill=color)
            img = Image.alpha_composite(img, txt_layer)
            
        return img.convert('RGB')
        
    def update_preview(self):
        try:
            img = self.generate_image()
            
            # Convert PIL to QPixmap
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=85)
            
            qimg = QImage()
            qimg.loadFromData(buf.getvalue())
            
            pixmap = QPixmap.fromImage(qimg)
            
            # Scale to fit label
            lbl_size = self.lbl_preview.size()
            if lbl_size.width() > 0 and lbl_size.height() > 0:
                scaled_pix = pixmap.scaled(lbl_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.lbl_preview.setPixmap(scaled_pix)
            
            self.current_preview = img
        except Exception as e:
            self.lbl_preview.setText(f"Lỗi hiển thị: {e}")
            
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preview()
        
    def export_thumbnail(self):
        if not self.current_preview:
            QMessageBox.warning(self, "Lỗi", "Không có ảnh để xuất!")
            return
            
        last_dir = self.settings.value("last_export_dir", "")
        
        # Check workspace config
        import json
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workspace_config.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if "workspace" in cfg:
                        ws = cfg["workspace"]
                        last_dir = os.path.join(ws, "Thumbnail đã tạo")
                        os.makedirs(last_dir, exist_ok=True)
        except Exception: pass
        
        if not last_dir and self.bg_image_path:
            last_dir = os.path.dirname(self.bg_image_path)
            
        path, _ = QFileDialog.getSaveFileName(self, "Lưu Thumbnail", os.path.join(last_dir, "thumbnail_export.jpg"), "JPEG (*.jpg);;PNG (*.png)")
        if path:
            try:
                self.settings.setValue("last_export_dir", os.path.dirname(path))
                self.current_preview.save(path, quality=95)
                QMessageBox.information(self, "Thành công", f"Đã lưu thumbnail tại:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Lỗi khi lưu ảnh: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ThumbnailGeneratorWindow()
    window.show()
    sys.exit(app.exec())
