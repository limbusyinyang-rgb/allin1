import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QProgressBar, QFileDialog, QMessageBox, QComboBox, QFormLayout)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QIcon

from downloader import DownloadWorker

class VideoDownloaderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tải Video Sub (Tiktok, Douyin, Bilibili)")
        self.resize(600, 250)
        
        self.settings = QSettings("MyCapCut", "TaiVideoSub")
        self.worker = None
        
        self.setup_ui()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Tải Video Không Watermark")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #10b981;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # URL Input
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Dán link video (Tiktok, Douyin, Bilibili) vào đây...")
        url_layout.addWidget(QLabel("Link Video:"))
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)
        
        # Output Directory
        out_layout = QHBoxLayout()
        self.out_input = QLineEdit()
        
        # Check workspace config
        import json
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workspace_config.json")
        default_dir = self.settings.value("last_download_dir", os.path.expanduser("~\\Downloads"))
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if "workspace" in cfg:
                        ws = cfg["workspace"]
                        default_dir = os.path.join(ws, "Video đã tải")
                        os.makedirs(default_dir, exist_ok=True)
        except Exception: pass
        
        self.out_input.setText(default_dir)
        self.btn_browse = QPushButton("Chọn Thư Mục")
        self.btn_browse.clicked.connect(self.browse_output)
        
        out_layout.addWidget(QLabel("Lưu tại:"))
        out_layout.addWidget(self.out_input)
        out_layout.addWidget(self.btn_browse)
        layout.addLayout(out_layout)
        
        # Options
        options_layout = QHBoxLayout()
        self.browser_combo = QComboBox()
        self.browser_combo.addItems(["Không dùng Cookie", "Chrome", "Edge", "Firefox", "Brave", "Opera", "Vivaldi", "Safari"])
        last_browser = self.settings.value("last_browser", "Không dùng Cookie")
        self.browser_combo.setCurrentText(last_browser)
        options_layout.addWidget(QLabel("Lấy Cookie từ:"))
        options_layout.addWidget(self.browser_combo)
        options_layout.addStretch()
        layout.addLayout(options_layout)
        
        # Status and Progress
        self.status_lbl = QLabel("Sẵn sàng")
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        
        layout.addWidget(self.status_lbl)
        layout.addWidget(self.progress_bar)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_download = QPushButton("Tải Video")
        self.btn_download.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 8px;")
        self.btn_download.clicked.connect(self.start_download)
        
        self.btn_cancel = QPushButton("Hủy")
        self.btn_cancel.setStyleSheet("padding: 8px;")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_download)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_download)
        layout.addLayout(btn_layout)
        
    def browse_output(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu", self.out_input.text())
        if dir_path:
            self.out_input.setText(dir_path)
            self.settings.setValue("last_download_dir", dir_path)
            
    def start_download(self):
        url = self.url_input.text().strip()
        out_dir = self.out_input.text().strip()
        browser = self.browser_combo.currentText()
        
        self.settings.setValue("last_browser", browser)
        
        if not url:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập link video!")
            return
            
        if not os.path.exists(out_dir):
            try:
                os.makedirs(out_dir)
            except Exception as e:
                QMessageBox.warning(self, "Lỗi", f"Không thể tạo thư mục lưu: {e}")
                return
                
        self.btn_download.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.url_input.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_lbl.setText("Đang lấy thông tin video...")
        
        browser_val = None
        if browser != "Không dùng Cookie":
            browser_val = browser.lower()
            
        self.worker = DownloadWorker(url, out_dir, browser_val)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_download_finished)
        self.worker.start()
        
    def cancel_download(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_lbl.setText("Đang hủy tải xuống...")
            self.btn_cancel.setEnabled(False)
            
    def update_progress(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            
            if total:
                pct = int(downloaded / total * 100)
                self.progress_bar.setValue(pct)
                
            speed_str = d.get('_speed_str', 'N/A')
            eta_str = d.get('_eta_str', 'N/A')
            self.status_lbl.setText(f"Đang tải... {pct}% (Tốc độ: {speed_str} - Còn lại: {eta_str})")
            
        elif d['status'] == 'finished':
            self.progress_bar.setValue(100)
            self.status_lbl.setText("Đang xử lý file...")
            
    def on_download_finished(self, title, success, err_msg):
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.url_input.setEnabled(True)
        
        if success:
            self.status_lbl.setText(f"Tải xong: {title}")
            QMessageBox.information(self, "Thành công", f"Đã tải xong video:\n{title}")
            self.url_input.clear()
        else:
            if "Đã hủy" in err_msg:
                self.status_lbl.setText("Đã hủy quá trình tải.")
                self.progress_bar.setValue(0)
            else:
                self.status_lbl.setText("Lỗi tải video.")
                QMessageBox.critical(self, "Lỗi", f"Tải video thất bại:\n{err_msg}")
                
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoDownloaderWindow()
    window.show()
    sys.exit(app.exec())
