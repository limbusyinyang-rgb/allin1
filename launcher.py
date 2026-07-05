import sys
import os
import json
import urllib.request
import urllib.error
import zipfile
import subprocess
import tempfile
import time
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar, QFileDialog, QMessageBox, QPushButton
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# ------------------------------------------------------------------
# THIẾT LẬP CỦA BẠN
# ------------------------------------------------------------------
GITHUB_REPO_OWNER = "limbusyinyang-rgb"
GITHUB_REPO_NAME = "allin1"
GITHUB_API_COMMITS_URL = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/commits/master"
GITHUB_ZIP_URL = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/archive/refs/heads/master.zip"
LOCAL_VERSION_FILE_NAME = "local_version.json"
MAIN_ENTRY_SCRIPT = "main.py"
APP_NAME = "ToooSuite"
# ------------------------------------------------------------------

def get_appdata_dir():
    appdata = os.environ.get("LOCALAPPDATA")
    if not appdata:
        appdata = os.path.expanduser("~")
    app_dir = os.path.join(appdata, APP_NAME)
    os.makedirs(app_dir, exist_ok=True)
    return app_dir

def get_install_path():
    config_file = os.path.join(get_appdata_dir(), "launcher_config.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f).get("install_path")
        except:
            pass
    return None

def save_install_path(path):
    config_file = os.path.join(get_appdata_dir(), "launcher_config.json")
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump({"install_path": path}, f)

class UpdaterThread(QThread):
    progress_msg = pyqtSignal(str)
    progress_pct = pyqtSignal(int)
    finished_update = pyqtSignal(bool, str) # success, message

    def __init__(self, install_path):
        super().__init__()
        self.install_path = install_path

    def run(self):
        try:
            self.progress_msg.emit("Đang kiểm tra kết nối mạng và phiên bản...")
            time.sleep(1)
            
            # 1. Đọc local version
            local_version_file = os.path.join(self.install_path, LOCAL_VERSION_FILE_NAME)
            local_version = "0.0.0"
            if os.path.exists(local_version_file):
                try:
                    with open(local_version_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        local_version = data.get("version", "0.0.0")
                except:
                    pass

            # 2. Lấy version từ GitHub (dùng SHA của commit mới nhất)
            try:
                req = urllib.request.Request(GITHUB_API_COMMITS_URL, headers={
                    'User-Agent': 'Mozilla/5.0',
                    'Accept': 'application/vnd.github.v3+json'
                })
                with urllib.request.urlopen(req, timeout=10) as response:
                    github_data = json.loads(response.read().decode('utf-8'))
                    remote_version = github_data.get("sha", "0.0.0")[:7] # Lấy 7 ký tự đầu
            except Exception as e:
                # Bắt buộc phải có mạng
                self.finished_update.emit(False, f"Lỗi mạng: Không thể kết nối máy chủ.\\n{e}")
                return
                
            self.progress_msg.emit(f"Phiên bản hiện tại: {local_version} | Máy chủ: {remote_version}")
            
            # So sánh phiên bản
            if remote_version == local_version and os.path.exists(os.path.join(self.install_path, MAIN_ENTRY_SCRIPT)):
                self.progress_msg.emit("Bạn đang ở phiên bản mới nhất!")
                time.sleep(1)
                self.finished_update.emit(True, "OK")
                return
                
            # 3. Tải bản cập nhật
            self.progress_msg.emit(f"Đang tải dữ liệu {remote_version} từ GitHub (Có thể mất vài phút)...")
            zip_path = os.path.join(tempfile.gettempdir(), "tooo_update_package.zip")
            
            try:
                req = urllib.request.Request(GITHUB_ZIP_URL, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as response:
                    total_size = int(response.getheader('Content-Length', -1))
                    block_size = 32768
                    read_so_far = 0
                    
                    with open(zip_path, 'wb') as out_file:
                        while True:
                            buffer = response.read(block_size)
                            if not buffer:
                                break
                            read_so_far += len(buffer)
                            out_file.write(buffer)
                            if total_size > 0:
                                self.progress_pct.emit(int((read_so_far * 100) / total_size))
                            else:
                                fake_pct = min(99, int(read_so_far / (1024*1024) * 5))
                                self.progress_pct.emit(fake_pct)
            except Exception as e:
                self.finished_update.emit(False, f"Lỗi khi tải mã nguồn: {e}")
                return
                
            self.progress_pct.emit(100)
            self.progress_msg.emit("Đang giải nén vào thư mục cài đặt...")
            
            # 4. Giải nén vào install_path
            ignore_folders = ['.venv', '.git', '__pycache__', '.idea']
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Tìm thư mục gốc (thường là allin1-master/)
                root_folder = None
                for name in zip_ref.namelist():
                    if "/" in name:
                        root_folder = name.split("/")[0] + "/"
                        break
                        
                total_files = len(zip_ref.namelist())
                for i, member in enumerate(zip_ref.namelist()):
                    # Bỏ qua chính thư mục gốc
                    if member == root_folder:
                        continue
                        
                    # Loại bỏ root_folder khỏi đường dẫn
                    rel_path = member
                    if root_folder and member.startswith(root_folder):
                        rel_path = member[len(root_folder):]
                        
                    if not rel_path:
                        continue
                        
                    if any(rel_path.startswith(folder + "/") or rel_path == folder for folder in ignore_folders):
                        continue
                        
                    # Trích xuất thủ công vào đúng đường dẫn
                    target_path = os.path.join(self.install_path, rel_path)
                    
                    if member.endswith("/"):
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with zip_ref.open(member) as source, open(target_path, "wb") as target:
                            import shutil
                            shutil.copyfileobj(source, target)
                            
                    if i % 50 == 0:
                        self.progress_pct.emit(int((i / total_files) * 100))
                        
            # 5. Cập nhật file local_version
            with open(local_version_file, "w", encoding="utf-8") as f:
                json.dump({"version": remote_version}, f)
                
            try:
                os.remove(zip_path)
            except: pass
            
            # 6. Cài đặt tài nguyên tự động nếu thiếu
            venv_dir = os.path.join(self.install_path, ".venv")
            req_file = os.path.join(self.install_path, "requirements.txt")
            
            if not os.path.exists(venv_dir) and os.path.exists(req_file):
                self.progress_msg.emit("Khởi tạo môi trường (chỉ chạy lần đầu, mất vài phút)...")
                # Tạo venv
                if hasattr(subprocess, 'CREATE_NO_WINDOW'):
                    creationflags = subprocess.CREATE_NO_WINDOW
                else:
                    creationflags = 0
                subprocess.run([sys.executable, "-m", "venv", venv_dir], cwd=self.install_path, creationflags=creationflags)
                
                # Cài requirements
                self.progress_msg.emit("Đang tải các thư viện ngoài (pip install)...")
                pip_exe = os.path.join(venv_dir, "Scripts", "pip.exe") if os.name == 'nt' else os.path.join(venv_dir, "bin", "pip")
                if os.path.exists(pip_exe):
                    subprocess.run([pip_exe, "install", "-r", req_file], cwd=self.install_path, creationflags=creationflags)
                
            self.progress_msg.emit("Cài đặt/Cập nhật hoàn tất! Đang khởi động...")
            time.sleep(1)
            self.finished_update.emit(True, "OK")
            
        except Exception as e:
            self.finished_update.emit(False, f"Lỗi hệ thống: {e}")

class LauncherWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Trình Khởi Chạy - Subtitle Suite")
        self.resize(500, 200)
        self.setStyleSheet("background-color: #1a1a20; color: white; font-family: 'Segoe UI'; font-size: 13px;")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(30, 30, 30, 30)
        self.layout.setSpacing(15)
        
        self.title_lbl = QLabel("SUBTITLE UTILITIES SUITE")
        self.title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #a855f7;")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title_lbl)
        
        self.status_lbl = QLabel()
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_lbl)
        
        # Check install path
        self.install_path = get_install_path()
        if not self.install_path or not os.path.exists(self.install_path):
            self.setup_install_ui()
        else:
            self.setup_update_ui()
            self.start_update()

    def setup_install_ui(self):
        self.status_lbl.setText("Đây là lần đầu khởi chạy. Vui lòng chọn nơi cài đặt phần mềm:")
        
        self.btn_select = QPushButton("Chọn Thư Mục Cài Đặt...")
        self.btn_select.setStyleSheet("background-color: #3b82f6; color: white; padding: 10px; border-radius: 6px; font-weight: bold;")
        self.btn_select.clicked.connect(self.select_directory)
        self.layout.addWidget(self.btn_select)
        
        self.layout.addStretch()

    def select_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn thư mục cài đặt")
        if dir_path:
            # Tạo thư mục con cho gọn
            final_path = os.path.join(dir_path, "Tooo_Subtitle_Suite")
            try:
                os.makedirs(final_path, exist_ok=True)
                save_install_path(final_path)
                self.install_path = final_path
                
                # --- AUTO-CREATE WORKSPACE CONFIG ---
                subfolders = ["Video đã tải", "Thumbnail đã tạo", "Sub đã trích xuất", "Video lồng tiếng", "Video đã xuất"]
                for sub in subfolders:
                    os.makedirs(os.path.join(final_path, sub), exist_ok=True)
                    
                config_path = os.path.join(final_path, "workspace_config.json")
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump({"workspace": final_path}, f, ensure_ascii=False, indent=4)
                # ------------------------------------
                
                # Chuyển UI sang update
                self.btn_select.hide()
                self.setup_update_ui()
                self.start_update()
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể tạo thư mục: {e}")

    def setup_update_ui(self):
        self.status_lbl.setText("Đang khởi tạo...")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 4px;
                text-align: center;
                background-color: #0f0f11;
                height: 18px;
            }
            QProgressBar::chunk {
                background-color: #a855f7;
                border-radius: 3px;
            }
        """)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.layout.addWidget(self.progress_bar)
        
    def start_update(self):
        self.thread = UpdaterThread(self.install_path)
        self.thread.progress_msg.connect(self.status_lbl.setText)
        self.thread.progress_pct.connect(self.progress_bar.setValue)
        self.thread.finished_update.connect(self.on_update_finished)
        self.thread.start()
        
    def on_update_finished(self, success, msg):
        if not success:
            self.status_lbl.setText(msg)
            self.status_lbl.setStyleSheet("color: #ef4444; font-weight: bold;") # Red
            self.progress_bar.hide()
            
            # Thêm nút thử lại
            self.btn_retry = QPushButton("Thử lại")
            self.btn_retry.setStyleSheet("background-color: #ef4444; color: white; padding: 10px; border-radius: 6px;")
            self.btn_retry.clicked.connect(lambda: QApplication.quit())
            self.layout.addWidget(self.btn_retry)
            return
            
        # Khởi chạy main.py
        try:
            python_exe = sys.executable
            venv_python = os.path.join(self.install_path, ".venv", "Scripts", "python.exe")
            if os.path.exists(venv_python):
                python_exe = venv_python
                
            script_path = os.path.join(self.install_path, MAIN_ENTRY_SCRIPT)
            
            if os.path.exists(script_path):
                subprocess.Popen([python_exe, script_path], cwd=self.install_path)
            else:
                QMessageBox.critical(self, "Lỗi", f"Không tìm thấy {MAIN_ENTRY_SCRIPT} trong thư mục cài đặt!")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi khởi chạy: {e}")
            
        QApplication.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LauncherWindow()
    window.show()
    sys.exit(app.exec())
