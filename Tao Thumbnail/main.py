import sys
import os
import io
import urllib.request
import json
import traceback

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QFileDialog, QMessageBox, QColorDialog, QSpinBox,
                             QGroupBox, QFormLayout, QScrollArea, QComboBox, QTextEdit, QProgressBar)
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QColor

from PIL import Image, ImageDraw, ImageFont, ImageFilter

class AIGeneratorWorker(QThread):
    finished = pyqtSignal(bool, str, object) # success, message, image_path_or_data
    progress = pyqtSignal(int)

    def __init__(self, api_key, payload):
        super().__init__()
        self.api_key = api_key
        self.payload = payload

    def run(self):
        url = "https://api.shopaikey.com/images/google/generations"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = json.dumps(self.payload).encode('utf-8')
        
        try:
            self.progress.emit(20)
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                self.progress.emit(60)
                
                if "data" in result and len(result["data"]) > 0:
                    img_url = result["data"][0].get("url")
                    if img_url:
                        # Tải ảnh về
                        self.progress.emit(80)
                        import tempfile
                        import uuid
                        tmp_path = os.path.join(tempfile.gettempdir(), f"nano_banana_{uuid.uuid4().hex}.png")
                        urllib.request.urlretrieve(img_url, tmp_path)
                        self.progress.emit(100)
                        self.finished.emit(True, "Tạo ảnh thành công!", tmp_path)
                    else:
                        self.finished.emit(False, "Không tìm thấy URL ảnh trong kết quả trả về", None)
                else:
                    self.finished.emit(False, "Kết quả trả về không hợp lệ", None)
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8')
            try:
                err_json = json.loads(err_msg)
                err_text = err_json.get("error", {}).get("message", err_msg)
            except:
                err_text = err_msg
            self.finished.emit(False, f"Lỗi API ({e.code}): {err_text}", None)
        except Exception as e:
            self.finished.emit(False, f"Lỗi hệ thống: {str(e)}", None)


class ThumbnailGeneratorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tạo Thumbnail Sub (AI & Custom Text)")
        self.resize(1200, 800)
        
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
        left_panel = QWidget()
        left_panel.setFixedWidth(450)
        control_layout = QVBoxLayout(left_panel)
        
        # Tabs for Control Panel (AI vs Text)
        from PyQt6.QtWidgets import QTabWidget
        self.tabs = QTabWidget()
        
        # TAB 1: AI GENERATION
        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)
        
        ai_form = QFormLayout()
        self.txt_api_key = QLineEdit()
        self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key.setText(self.settings.value("nano_api_key", ""))
        
        self.combo_model = QComboBox()
        self.combo_model.addItems(["nano-banana", "nano-banana-2", "nano-banana-pro"])
        self.combo_model.setCurrentText(self.settings.value("nano_model", "nano-banana-2"))
        self.combo_model.currentTextChanged.connect(self.on_model_changed)
        
        self.txt_prompt = QTextEdit()
        self.txt_prompt.setFixedHeight(80)
        
        self.combo_size = QComboBox()
        self.combo_size.addItems(["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"])
        self.combo_size.setCurrentText("16:9")
        
        self.combo_image_size = QComboBox()
        self.combo_image_size.addItems(["0.5K", "1K", "2K", "4K"])
        self.combo_image_size.setCurrentText("2K")
        
        self.txt_ref_urls = QTextEdit()
        self.txt_ref_urls.setFixedHeight(60)
        self.txt_ref_urls.setPlaceholderText("Nhập URL ảnh tham chiếu (mỗi dòng 1 URL, tối đa 3-5 ảnh)")
        
        ai_form.addRow("API Key:", self.txt_api_key)
        ai_form.addRow("Model:", self.combo_model)
        ai_form.addRow("Prompt:", self.txt_prompt)
        ai_form.addRow("Khung hình:", self.combo_size)
        ai_form.addRow("Độ phân giải:", self.combo_image_size)
        ai_form.addRow("Ảnh tham chiếu:", self.txt_ref_urls)
        
        self.btn_generate_ai = QPushButton("🚀 TẠO ẢNH BẰNG AI")
        self.btn_generate_ai.setStyleSheet("background-color: #3b82f6; color: white; font-weight: bold; padding: 12px; font-size: 14px;")
        self.btn_generate_ai.clicked.connect(self.start_ai_generation)
        
        self.progress_ai = QProgressBar()
        self.progress_ai.hide()
        
        # Manual image select
        manual_bg_layout = QHBoxLayout()
        self.btn_load_bg = QPushButton("Hoặc: Chọn Ảnh Nền Có Sẵn...")
        self.btn_load_bg.clicked.connect(self.load_background)
        self.lbl_bg_name = QLabel("Chưa có ảnh nền")
        self.lbl_bg_name.setWordWrap(True)
        manual_bg_layout.addWidget(self.btn_load_bg)
        manual_bg_layout.addWidget(self.lbl_bg_name)
        
        ai_layout.addLayout(ai_form)
        ai_layout.addWidget(self.btn_generate_ai)
        ai_layout.addWidget(self.progress_ai)
        ai_layout.addSpacing(15)
        ai_layout.addWidget(QLabel("<b>Ảnh nền cục bộ:</b>"))
        ai_layout.addLayout(manual_bg_layout)
        ai_layout.addStretch()
        
        self.tabs.addTab(ai_tab, "Tạo Ảnh Nền AI")
        
        # TAB 2: TEXT OVERLAY
        text_tab = QWidget()
        text_layout = QVBoxLayout(text_tab)
        
        # Put text config in a scroll area just in case
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
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
            
            scroll_layout.addWidget(group)
            
            self.texts_config[pos_name] = {
                'text': txt_input,
                'size': size_spin,
                'color': btn_color,
                'glow': btn_glow,
                'glow_radius': glow_radius
            }
            
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        text_layout.addWidget(scroll)
        
        self.tabs.addTab(text_tab, "Chèn Chữ (Text Overlay)")
        
        control_layout.addWidget(self.tabs)
        
        # Export
        self.btn_export = QPushButton("Xuất Ảnh Thumbnail")
        self.btn_export.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 12px; font-size: 16px;")
        self.btn_export.clicked.connect(self.export_thumbnail)
        control_layout.addWidget(self.btn_export)
        
        # Right Panel (Preview)
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        
        self.lbl_preview = QLabel("Vui lòng tạo ảnh AI hoặc chọn ảnh nền để bắt đầu...")
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setStyleSheet("background-color: #1e1e1e; color: #666;")
        
        preview_layout.addWidget(self.lbl_preview)
        
        main_layout.addWidget(left_panel)
        main_layout.addWidget(preview_panel, stretch=1)
        
        # Initialize UI states
        self.on_model_changed(self.combo_model.currentText())

    def on_model_changed(self, model_name):
        if model_name == "nano-banana":
            self.combo_image_size.setEnabled(False)
        else:
            self.combo_image_size.setEnabled(True)

    def start_ai_generation(self):
        api_key = self.txt_api_key.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập API Key!")
            return
            
        self.settings.setValue("nano_api_key", api_key)
        
        model = self.combo_model.currentText()
        self.settings.setValue("nano_model", model)
        
        prompt = self.txt_prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập Prompt!")
            return
            
        payload = {
            "model": model,
            "prompt": prompt,
            "size": self.combo_size.currentText(),
            "format": "png",
            "response_format": "url"
        }
        
        if model != "nano-banana":
            payload["imageSize"] = self.combo_image_size.currentText()
            
        ref_urls = [url.strip() for url in self.txt_ref_urls.toPlainText().split('\n') if url.strip()]
        if ref_urls:
            max_refs = 3 if model == "nano-banana" else 5
            if len(ref_urls) > max_refs:
                QMessageBox.warning(self, "Lỗi", f"Model {model} chỉ hỗ trợ tối đa {max_refs} ảnh tham chiếu.")
                return
            payload["image_urls"] = ref_urls
            
        self.btn_generate_ai.setEnabled(False)
        self.progress_ai.show()
        self.progress_ai.setValue(0)
        
        self.worker = AIGeneratorWorker(api_key, payload)
        self.worker.progress.connect(self.progress_ai.setValue)
        self.worker.finished.connect(self.on_ai_finished)
        self.worker.start()

    def on_ai_finished(self, success, msg, img_path):
        self.btn_generate_ai.setEnabled(True)
        self.progress_ai.hide()
        
        if success and img_path:
            self.bg_image_path = img_path
            self.lbl_bg_name.setText("AI Generated Image")
            self.update_preview()
            self.tabs.setCurrentIndex(1) # Chuyển sang tab chèn chữ
        else:
            QMessageBox.critical(self, "Lỗi Tạo Ảnh", msg)

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
        self.update_preview()
        
    def get_qcolor_from_btn(self, btn):
        style = btn.styleSheet()
        try:
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
                
            txt_layer = Image.new('RGBA', (width, height), (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt_layer)
            
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            
            x = (width - tw) / 2
            
            if pos_name == "top":
                y = height * 0.1
            elif pos_name == "middle":
                y = (height - th) / 2
            else: 
                y = height * 0.9 - th
                
            if glow_radius > 0:
                glow_layer = Image.new('RGBA', (width, height), (255, 255, 255, 0))
                glow_draw = ImageDraw.Draw(glow_layer)
                
                stroke_w = int(glow_radius / 2) + 2
                glow_draw.text((x, y), text, font=font, fill=glow_color, stroke_width=stroke_w, stroke_fill=glow_color)
                
                glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(glow_radius))
                img = Image.alpha_composite(img, glow_layer)
                
            draw.text((x, y), text, font=font, fill=color)
            img = Image.alpha_composite(img, txt_layer)
            
        return img.convert('RGB')
        
    def update_preview(self):
        try:
            img = self.generate_image()
            
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=85)
            
            qimg = QImage()
            qimg.loadFromData(buf.getvalue())
            
            pixmap = QPixmap.fromImage(qimg)
            
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
