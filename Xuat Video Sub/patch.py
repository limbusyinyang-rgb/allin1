import sys
import os

with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update window size
code = code.replace("self.resize(700, 600)", "self.resize(1100, 600)")

# 2. Add QPixmap import
code = code.replace("from PyQt6.QtGui import QFont, QIcon", "from PyQt6.QtGui import QFont, QIcon, QPixmap")

# 3. Update main_layout to left_panel and add right_panel
old_setup_start = """    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)"""

new_setup_start = """    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout_h = QHBoxLayout(central_widget)
        
        left_panel_widget = QWidget()
        main_layout = QVBoxLayout(left_panel_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(15)"""

code = code.replace(old_setup_start, new_setup_start)

# 4. Right panel append at the end of actions
old_actions_end = """        row_actions.addWidget(self.btn_start)
        row_actions.addWidget(self.btn_stop)
        
        main_layout.addLayout(row_actions)"""

new_actions_end = """        row_actions.addWidget(self.btn_start)
        row_actions.addWidget(self.btn_stop)
        
        main_layout.addLayout(row_actions)
        
        main_layout_h.addWidget(left_panel_widget, stretch=4)
        
        # Right panel for Preview
        right_panel_widget = QWidget()
        right_panel = QVBoxLayout(right_panel_widget)
        right_panel.setContentsMargins(0, 0, 0, 0)
        right_panel.setSpacing(10)
        
        preview_title = QLabel("🖼️ Xem trước Phụ đề")
        preview_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #cbd5e1;")
        right_panel.addWidget(preview_title)
        
        self.preview_label = QLabel("Hãy chọn Video và bấm Xem trước")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #000000; border: 1px solid #2d3748; border-radius: 8px; color: #a0aec0;")
        self.preview_label.setMinimumSize(450, 300)
        right_panel.addWidget(self.preview_label, stretch=1)
        
        main_layout_h.addWidget(right_panel_widget, stretch=5)"""

code = code.replace(old_actions_end, new_actions_end)

# 5. Add preview button next to font size
old_font = """        # Font size
        col_font = QVBoxLayout()
        col_font.addWidget(QLabel("Cỡ chữ (Sub):"))
        self.font_spin = QSpinBox()
        self.font_spin.setRange(10, 100)
        self.font_spin.setValue(24)
        col_font.addWidget(self.font_spin)
        row_opts.addLayout(col_font)"""

new_font = """        # Font size
        col_font = QVBoxLayout()
        col_font.addWidget(QLabel("Cỡ chữ (Sub):"))
        
        font_row = QHBoxLayout()
        self.font_spin = QSpinBox()
        self.font_spin.setRange(10, 100)
        self.font_spin.setValue(24)
        font_row.addWidget(self.font_spin)
        
        self.btn_preview = QPushButton("👀 Xem trước")
        self.btn_preview.setStyleSheet("background-color: #3b82f6; font-weight: bold; padding: 6px 12px;")
        self.btn_preview.clicked.connect(self.generate_preview)
        font_row.addWidget(self.btn_preview)
        
        col_font.addLayout(font_row)
        row_opts.addLayout(col_font)"""

code = code.replace(old_font, new_font)

# 6. Add generate_preview method before start_export
preview_method = """
    def generate_preview(self):
        video_path = self.video_input.text().strip()
        font_size = self.font_spin.value()
        
        if not video_path or not os.path.exists(video_path):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn video đầu vào trước khi xem trước!")
            return
            
        self.btn_preview.setEnabled(False)
        self.btn_preview.setText("Đang tạo...")
        self.preview_label.setText("Đang kết xuất khung hình...")
        QApplication.processEvents()
        
        try:
            temp_srt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview_temp.srt")
            with open(temp_srt, "w", encoding="utf-8") as f:
                f.write("1\\n00:00:00,000 --> 00:01:10,000\\nĐây là phụ đề mẫu\\nSample Subtitle\\n\\n")
            
            preview_img = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview.jpg")
            if os.path.exists(preview_img):
                try:
                    os.remove(preview_img)
                except:
                    pass
            
            ffmpeg_exe = get_ffmpeg_exe()
            escaped_srt = escape_path_for_ffmpeg(temp_srt)
            vf_args = f"subtitles='{escaped_srt}':force_style='FontSize={font_size},Alignment=2,MarginV=15'"
            
            cmd = [
                ffmpeg_exe, "-y", "-ss", "00:00:02", "-i", video_path,
                "-vf", vf_args, "-vframes", "1", "-q:v", "2", preview_img
            ]
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            subprocess.run(cmd, startupinfo=startupinfo, check=False)
            
            if os.path.exists(preview_img):
                pix = QPixmap(preview_img)
                if not pix.isNull():
                    scaled_pix = pix.scaled(
                        self.preview_label.width(), 
                        self.preview_label.height(),
                        Qt.AspectRatioMode.KeepAspectRatio, 
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.preview_label.setPixmap(scaled_pix)
                else:
                    self.preview_label.setText("Đã xuất ảnh nhưng không thể tải lên giao diện.")
            else:
                self.preview_label.setText("Không thể tạo bản xem trước. FFmpeg gặp lỗi.")
                
        except Exception as e:
            self.preview_label.setText(f"Lỗi: {e}")
        finally:
            self.btn_preview.setEnabled(True)
            self.btn_preview.setText("👀 Xem trước")

"""

code = code.replace("    def start_export(self):", preview_method + "    def start_export(self):")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Patch applied successfully.")
