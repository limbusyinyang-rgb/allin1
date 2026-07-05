import sys
import os

# Tự động kích hoạt môi trường ảo (.venv) nếu có
venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "Scripts", "python.exe")
if os.path.exists(venv_python) and os.path.normcase(sys.executable) != os.path.normcase(venv_python):
    import subprocess
    sys.exit(subprocess.call([venv_python] + sys.argv))

import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QGridLayout, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor

import urllib.request
import json
import socket

class NetworkWorker(QThread):
    network_error = pyqtSignal()
    update_available = pyqtSignal()

    def run(self):
        # 1. Check internet using raw socket to avoid SSL/DNS issues
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
        except Exception as e:
            self.network_error.emit()
            return
            
        # 2. Check update
        GITHUB_VERSION_URL = "https://raw.githubusercontent.com/limbusyinyang-rgb/Version/main/version.json"
        LOCAL_VERSION_FILE_NAME = "local_version.json"
        try:
            req = urllib.request.Request(GITHUB_VERSION_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                github_data = json.loads(response.read().decode('utf-8'))
                remote_version = github_data.get("version", "0.0.0")
                
            local_version = "0.0.0"
            install_path = os.path.dirname(os.path.abspath(__file__))
            local_version_file = os.path.join(install_path, LOCAL_VERSION_FILE_NAME)
            if os.path.exists(local_version_file):
                with open(local_version_file, "r", encoding="utf-8") as f:
                    local_version = json.load(f).get("version", "0.0.0")
                    
            if remote_version != local_version:
                self.update_available.emit()
        except:
            pass

class FeatureCard(QFrame):
    """Custom styling card representing a feature tool in the suite"""
    def __init__(self, title, description, badge_text="", button_text="Khởi Chạy", parent=None):
        super().__init__(parent)
        self.setObjectName("FeatureCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)
        
        # Inner layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # Header banner row
        header_row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        header_row.addWidget(title_label)
        
        if badge_text:
            badge = QLabel(badge_text)
            badge.setObjectName("BadgeLabel")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_row.addWidget(badge)
        header_row.addStretch()
        layout.addLayout(header_row)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setObjectName("CardDesc")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Spacing
        layout.addStretch()
        
        # Action button
        self.action_btn = QPushButton(button_text)
        self.action_btn.setObjectName("CardBtn")
        layout.addWidget(self.action_btn)

    def set_disabled_state(self, message="Chức năng sắp ra mắt"):
        self.action_btn.setText(message)
        self.action_btn.setEnabled(False)
        self.action_btn.setObjectName("CardBtnDisabled")
        self.setObjectName("FeatureCardDisabled")


class MainSuiteDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Subtitle Processing Suite - Bảng Điều Khiển")
        self.resize(900, 550)
        self.setup_ui()
        self.apply_styles()
        
        self.network_worker = NetworkWorker()
        self.network_worker.network_error.connect(self.on_network_error)
        self.network_worker.update_available.connect(self.on_update_available)
        
        self.net_timer = QTimer(self)
        self.net_timer.timeout.connect(self.network_worker.start)
        self.net_timer.start(3600000) # 1 hour
        self.network_worker.start() # initial check

    def on_network_error(self):
        QMessageBox.critical(self, "Lỗi Mạng", "Phần mềm bắt buộc phải có kết nối mạng liên tục để hoạt động. Vui lòng kiểm tra lại kết nối internet!")
        
    def on_update_available(self):
        self.btn_update.show()
        
    def prompt_update(self):
        QMessageBox.information(self, "Có Bản Cập Nhật Mới", "Có bản cập nhật mới trên máy chủ!\n\nVui lòng tắt phần mềm và mở lại bằng Launcher (Trình khởi chạy) để hệ thống tự động tải về bản mới nhất.")

    def setup_ui(self):
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # Header Title
        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(5)

        main_title = QLabel("SUBTITLE UTILITIES SUITE")
        main_title.setObjectName("MainTitle")
        
        sub_title = QLabel("Hệ thống công cụ xử lý phụ đề và lồng tiếng tự động sử dụng AI & TTS")
        sub_title.setObjectName("SubTitle")
        
        text_layout.addWidget(main_title)
        text_layout.addWidget(sub_title)
        
        title_layout.addLayout(text_layout)
        title_layout.addStretch()
        
        self.btn_update = QPushButton("🔴 Cập nhật")
        self.btn_update.setObjectName("BtnUpdate")
        self.btn_update.hide()
        self.btn_update.clicked.connect(self.prompt_update)
        title_layout.addWidget(self.btn_update)
        
        self.btn_settings = QPushButton("⚙️ Cài đặt Thư Mục")
        self.btn_settings.setObjectName("BtnSettings")
        self.btn_settings.clicked.connect(self.open_workspace_settings)
        title_layout.addWidget(self.btn_settings)
        
        main_layout.addWidget(title_container)

        # Grid of Cards
        grid = QGridLayout()
        grid.setSpacing(20)
        
        # Card 1: Subtitle Extraction
        self.card_extract = FeatureCard(
            title="Trích Xuất Phụ Đề",
            description="Tự động nhận dạng chữ viết (OCR) trên khung hình video để trích xuất phụ đề cứng (tiếng Trung, Anh, Việt) thành tệp SRT.",
            button_text="Trích Xuất Sub",
            badge_text="Thử Nghiệm"
        )
        self.card_extract.action_btn.clicked.connect(self.launch_extract_tool)
        # Card 2: Subtitle Translation
        self.card_translate = FeatureCard(
            title="Dịch Phụ Đề AI",
            description="Dịch phụ đề từ các ngôn ngữ khác sang Tiếng Việt chuẩn văn phong, giữ nguyên định dạng thời gian bằng Gemini AI.",
            button_text="Dịch Phụ Đề",
            badge_text="Thử Nghiệm"
        )
        self.card_translate.action_btn.clicked.connect(self.launch_translate_tool)

        # Card 3: Subtitle Dubbing
        self.card_dubbing = FeatureCard(
            title="Lồng Tiếng Phụ Đề",
            description="Chuyển đổi văn bản phụ đề SRT thành tệp âm thanh lồng tiếng hoàn chỉnh khớp nối chính xác thời gian bằng CapCut TTS.",
            button_text="Lồng Tiếng Sub",
            badge_text="Thử Nghiệm"
        )
        self.card_dubbing.action_btn.clicked.connect(self.launch_dubbing_tool)

        # Card 4: Subtitle Video Exporter
        self.card_export_video = FeatureCard(
            title="Xuất Video Sub",
            description="Ghép cứng phụ đề đã dịch và lồng tiếng vào video gốc để kết xuất ra tệp video hoàn thành.",
            button_text="Xuất Video",
            badge_text="Thử Nghiệm"
        )
        self.card_export_video.action_btn.clicked.connect(self.launch_export_tool)
        
        # Card 5: Video Downloader
        self.card_download = FeatureCard(
            title="Tải Video Sub",
            description="Tự động bắt link và tải video từ TikTok, Douyin, Bilibili với chất lượng cao nhất, không dính logo (watermark).",
            button_text="Tải Video",
            badge_text="Thử Nghiệm"
        )
        self.card_download.action_btn.clicked.connect(self.launch_download_tool)

        # Row 0
        grid.addWidget(self.card_download, 0, 0)
        
        # Card 6: Thumbnail Creator
        self.card_thumbnail = FeatureCard(
            title="Tạo Thumbnail",
            description="Tự động tạo ảnh bìa (thumbnail) hoặc viết câu lệnh (prompt) AI cho video của bạn.",
            button_text="Tạo Thumbnail",
            badge_text="Thử Nghiệm"
        )
        self.card_thumbnail.action_btn.clicked.connect(self.launch_thumbnail_tool)
        
        grid.addWidget(self.card_thumbnail, 0, 1)

        # Row 1
        grid.addWidget(self.card_extract, 1, 0)
        grid.addWidget(self.card_translate, 1, 1)

        # Row 2
        grid.addWidget(self.card_dubbing, 2, 0)
        grid.addWidget(self.card_export_video, 2, 1)

        main_layout.addLayout(grid)

        # Bottom footer bar info
        footer_label = QLabel("Phiên bản Suite 1.0 • Phát triển dựa trên Python & PyQt6")
        footer_label.setObjectName("FooterLabel")
        footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(footer_label)

    def apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #0f0f11;
                color: #e2e8f0;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif;
            }
            
            #MainTitle {
                font-size: 24px;
                font-weight: 800;
                color: #f7fafc;
                letter-spacing: 1.5px;
            }
            
            #SubTitle {
                font-size: 13px;
                color: #a0aec0;
            }
            
            #FeatureCard {
                background-color: #161619;
                border: 1px solid #2d3748;
                border-radius: 12px;
                min-height: 180px;
            }
            
            #FeatureCard:hover {
                border-color: #a855f7; /* Suite theme hover glow: Violet */
                background-color: #1a1a20;
            }
            
            #FeatureCardDisabled {
                background-color: #111113;
                border: 1px solid #1f2937;
                border-radius: 12px;
                min-height: 180px;
            }
            
            #CardTitle {
                font-size: 16px;
                font-weight: bold;
                color: #f8fafc;
            }
            
            #BadgeLabel {
                background-color: #c084fc;
                color: #1e1b4b;
                font-size: 10px;
                font-weight: bold;
                border-radius: 4px;
                padding: 2px 6px;
                margin-left: 10px;
            }
            
            #CardDesc {
                font-size: 13px;
                color: #94a3b8;
                line-height: 1.4;
                margin-top: 5px;
            }
            
            QPushButton#CardBtn {
                background-color: #3b82f6; /* Accent color: Blue */
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
                font-size: 13px;
            }
            
            QPushButton#CardBtn:hover {
                background-color: #2563eb;
            }
            
            QPushButton#CardBtn:pressed {
                background-color: #1d4ed8;
            }
            
            QPushButton#CardBtnDisabled {
                background-color: #1e293b;
                color: #64748b;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
                font-size: 13px;
            }
            
            #FooterLabel {
                color: #475569;
                font-size: 11px;
                margin-top: 10px;
            }
            
            QPushButton#BtnSettings {
                background-color: #3f3f46;
                color: white;
                border: 1px solid #52525b;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton#BtnSettings:hover {
                background-color: #52525b;
            }
            
            QPushButton#BtnUpdate {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton#BtnUpdate:hover {
                background-color: #dc2626;
            }
        """)

    def open_workspace_settings(self):
        from PyQt6.QtWidgets import QFileDialog
        import json
        
        folder = QFileDialog.getExistingDirectory(self, "Chọn Thư Mục Dự Án Tổng")
        if folder:
            # Create subfolders
            subfolders = ["Video đã tải", "Thumbnail đã tạo", "Sub đã trích xuất", "Video lồng tiếng", "Video đã xuất"]
            for sub in subfolders:
                path = os.path.join(folder, sub)
                os.makedirs(path, exist_ok=True)
                
            # Save to config
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace_config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"workspace": folder}, f, ensure_ascii=False, indent=4)
                
            QMessageBox.information(self, "Thành công", f"Đã thiết lập thư mục dự án:\n{folder}\nĐã tự động tạo các thư mục con thành công!")

    def launch_tool(self, relative_path):
        """Helper to run a sub-tool in a separate process"""
        python_exe = sys.executable
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)
        
        if not os.path.exists(script_path):
            QMessageBox.critical(
                self, 
                "Không tìm thấy tệp", 
                f"Không tìm thấy tệp mã nguồn của ứng dụng:\n{script_path}"
            )
            return

        try:
            # Launch in separate operating system process with corresponding cwd
            p = subprocess.Popen([python_exe, os.path.basename(script_path)], cwd=os.path.dirname(script_path))
            if not hasattr(self, 'running_processes'):
                self.running_processes = []
            self.running_processes.append(p)
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Lỗi khởi chạy", 
                f"Không thể mở ứng dụng:\n{e}"
            )

    def closeEvent(self, event):
        if hasattr(self, 'running_processes'):
            for p in self.running_processes:
                try:
                    p.kill()
                except:
                    pass
        import os
        os._exit(0)

    def launch_extract_tool(self):
        self.launch_tool("Trich Xuat Sub/app.py")

    def launch_translate_tool(self):
        self.launch_tool("Dich Sub/app.py")

    def launch_dubbing_tool(self):
        self.launch_tool("Long Tieng Sub/app.py")

    def launch_export_tool(self):
        self.launch_tool("Xuat Video Sub/main.py")

    def launch_download_tool(self):
        self.launch_tool("Tai Video Sub/main.py")
        
    def launch_thumbnail_tool(self):
        self.launch_tool("Tao Thumbnail/main.py")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    import license_dialog
    is_valid, msg, exp_date = license_dialog.require_license()
    if not is_valid:
        sys.exit(0)
        
    window = MainSuiteDashboard()
    window.setWindowTitle(f"Công cụ xử lý Video Tooo - Bản quyền: {msg}")
    window.show()
    sys.exit(app.exec())
