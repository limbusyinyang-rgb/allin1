import sys
import os
import json
import time
from copy import deepcopy
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QFormLayout, QPushButton, QLabel, QLineEdit, QFileDialog, 
    QComboBox, QProgressBar, QTextEdit, QMessageBox, QGroupBox
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QColor

# Add current folder to sys.path to allow imports from TTS subfolder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Try importing CapCut signature and helpers
try:
    from TTS.capcut_common_task_client import (
        DEFAULT_DEVICE, BASE, compact_json, tts_new_body, query_body,
        base_headers, make_sign_header, requests, escape_xml
    )
except ImportError:
    DEFAULT_DEVICE = {}
    BASE = ""
    requests = None
    print("Warning: Could not import TTS.capcut_common_task_client")

# Import pysrt
try:
    import pysrt
except ImportError:
    pysrt = None

# Default settings file path
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
VOICE_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TTS", "Voice.json")

def load_config():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
    return {}

def save_config(config):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

def load_capcut_voices():
    """Load CapCut voices dynamically from TTS/Voice.json"""
    if os.path.exists(VOICE_JSON_PATH):
        try:
            with open(VOICE_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                voices = []
                for item in data:
                    display = f"{item['display_name']} ({item['voice_type'].split('_')[0]} - {item['lan'].upper()})"
                    voices.append({
                        "display_name": display,
                        "voice_type": item["voice_type"],
                        "resource_id": item["resource_id"]
                    })
                return voices
        except Exception as e:
            print(f"Error reading Voice.json: {e}")
    return []

def load_srt(filepath):
    if pysrt is None:
        raise ImportError("Thư viện `pysrt` chưa được cài đặt. Vui lòng cài đặt bằng: pip install pysrt")
    
    encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'latin-1', 'cp1252', 'gbk']
    for enc in encodings:
        try:
            return pysrt.open(filepath, encoding=enc), enc
        except Exception:
            continue
    return pysrt.open(filepath), 'utf-8'


class DubbingWorker(QThread):
    progress_updated = pyqtSignal(int, str)  # percentage, log message
    finished = pyqtSignal(str)              # master audio path
    error_occurred = pyqtSignal(str)         # error message

    def __init__(self, srt_path, output_audio_path, voice, resource_id):
        super().__init__()
        self.srt_path = srt_path
        self.output_audio_path = output_audio_path
        self.voice = voice
        self.resource_id = resource_id
        self.is_running = True

    def run(self):
        temp_dir = os.path.join(os.path.dirname(self.output_audio_path), "temp_dubbing")
        try:
            # Create temp dir
            os.makedirs(temp_dir, exist_ok=True)

            # Read SRT file
            self.progress_updated.emit(2, "Đang đọc tệp phụ đề...")
            subs, enc = load_srt(self.srt_path)
            total_lines = len(subs)
            
            if total_lines == 0:
                raise ValueError("Tệp phụ đề trống!")

            self.progress_updated.emit(5, f"Đã tải {total_lines} dòng phụ đề. Bắt đầu lồng tiếng bằng CapCut TTS...")
            segment_files = {}

            # Generate audio per line at constant speed "1.0"
            for i, sub in enumerate(subs):
                if not self.is_running:
                    return

                text = sub.text.strip() if sub.text else ""
                percent = int(5 + (i / total_lines) * 80)
                
                if not text:
                    self.progress_updated.emit(percent, f"Dòng {i+1}: Bỏ qua dòng trống.")
                    continue

                output_seg_path = os.path.join(temp_dir, f"segment_{i:04d}.mp3")

                self.progress_updated.emit(percent, f"Đang lồng tiếng dòng {i+1}/{total_lines}: \"{text[:30]}...\"")
                
                retries = 3
                success = False
                err_log = ""

                while retries > 0 and not success and self.is_running:
                    try:
                        self.run_capcut_tts(text, self.voice, self.resource_id, output_seg_path)
                        success = True
                    except Exception as e:
                        retries -= 1
                        err_log = str(e)
                        self.progress_updated.emit(percent, f"Cảnh báo dòng {i+1}: Gặp lỗi {e}. Thử lại (Còn {retries} lượt)...")
                        time.sleep(1.5)

                if not self.is_running:
                    return

                if success and os.path.exists(output_seg_path):
                    segment_files[i] = output_seg_path
                else:
                    self.progress_updated.emit(percent, f"LỖI: Không thể tạo giọng nói cho dòng {i+1}. Lỗi: {err_log}")

            if not self.is_running:
                return

            # Merge segments using timeline shift logic
            self.progress_updated.emit(90, "Hoàn tất tạo giọng nói. Đang tiến hành hòa âm ghép nối...")
            
            final_audio_path = self.merge_timeline(subs, segment_files, self.output_audio_path)
            self.progress_updated.emit(100, f"Đã lưu tệp lồng tiếng hoàn tất tại: {final_audio_path}")
            self.finished.emit(final_audio_path)

        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            # Clean up segments files safely
            try:
                for f in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, f))
                os.rmdir(temp_dir)
            except Exception:
                pass

    def run_capcut_tts(self, text, voice, resource_id, output_path):
        """Invoke CapCut TTS API client using default speech speed 1.0"""
        if requests is None:
            raise ImportError("Thư viện `requests` chưa được cài đặt!")
        
        from urllib.parse import urlencode
        from TTS.capcut_common_task_client import common_query
        
        device = deepcopy(DEFAULT_DEVICE)
        
        # Dynamically load active CapCut PC device ID to bypass ByteDance server blocks
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            local_config_path = os.path.join(local_appdata, "CapCut", "User Data", "TTNet", "tt_net_config.config")
            if os.path.exists(local_config_path):
                try:
                    import re
                    with open(local_config_path, "rb") as f:
                        config_content = f.read()
                    match = re.search(rb'device_id&#\*(\d+)', config_content)
                    if match:
                        dev_id = match.group(1).decode("utf-8")
                        device["device_id"] = dev_id
                        device["tdid"] = dev_id
                        device["iid"] = dev_id
                except Exception as e:
                    print(f"Error extracting local device_id: {e}")
        
        # Build SSML structure with rate="1.0"
        babi, body = tts_new_body([text], voice, resource_id, "1.0", device)
        path = "/lv/v1/common_task/new"
        query = common_query(device, babi, include_region=True)
        url = BASE + path + "?" + urlencode(query)
        body_text = compact_json(body)
        
        headers = base_headers(device, body_text, appid=True)
        lower_headers = {k.lower(): v for k, v in headers.items()}
        if "sign" not in lower_headers:
            headers["sign"] = make_sign_header(url, device["appvr"], lower_headers["device-time"], device["tdid"])
        
        # Post request to submit task
        resp = requests.post(url, headers=headers, data=body_text.encode("utf-8"), timeout=30)
        resp_data = resp.json()
        
        if resp.status_code != 200 or resp_data.get("ret") != "0":
            err_msg = resp_data.get("errmsg") or f"HTTP {resp.status_code}"
            if "shark" in err_msg.lower():
                err_msg += " (ByteDance chặn request / bảo mật WAF. Vui lòng cập nhật cấu hình Device/Cookies mới)"
            raise RuntimeError(f"CapCut API: {err_msg}")
        
        task = resp_data["data"]["tasks"][0]
        task_id = task["id"]
        token = task["token"]
        
        # Poll query
        retries = 15
        audio_url = None
        query_path = "/lv/v1/common_task/query"
        query_url = BASE + query_path + "?" + urlencode(common_query(device, None, include_region=False))
        
        while retries > 0 and self.is_running:
            q_body_dict = query_body(task_id, token, "sami_text_to_speech")
            q_body_text = compact_json(q_body_dict)
            q_headers = base_headers(device, q_body_text, appid=True)
            q_lower_headers = {k.lower(): v for k, v in q_headers.items()}
            if "sign" not in q_lower_headers:
                q_headers["sign"] = make_sign_header(query_url, device["appvr"], q_lower_headers["device-time"], device["tdid"])
            
            q_resp = requests.post(query_url, headers=q_headers, data=q_body_text.encode("utf-8"), timeout=30)
            q_data = q_resp.json()
            task_info = q_data["data"]["tasks"][0]
            status = task_info["status"]
            
            if status in ("succeed", "success"):
                payload = json.loads(task_info["payload"])
                if "audio_url" in payload:
                    audio_url = payload["audio_url"]
                elif "audio_subtitles" in payload and payload["audio_subtitles"]:
                    audio_url = payload["audio_subtitles"][0]["speech_url"]
                else:
                    audio_url = None
                
                if audio_url:
                    break
                else:
                    raise RuntimeError("Không tìm thấy đường dẫn âm thanh (audio URL) trong phản hồi của CapCut.")
            elif status == "failed":
                err_msg = task_info.get("err_msg", "")
                raise RuntimeError(f"Yêu cầu TTS bị lỗi trên máy chủ CapCut: {err_msg}")
            
            retries -= 1
            time.sleep(2.0)
            
        if not audio_url:
            raise RuntimeError("Hết thời gian chờ phản hồi từ CapCut TTS.")
            
        # Download final mp3 file
        dl_resp = requests.get(audio_url, timeout=30)
        if dl_resp.status_code != 200:
            raise RuntimeError(f"Không thể tải âm thanh: HTTP {dl_resp.status_code}")
            
        with open(output_path, "wb") as f:
            f.write(dl_resp.content)

    def merge_timeline(self, subs, segment_files, output_path):
        """Align and merge individual audio segments into a full silent timeline using pydub.
        Ensures a minimum 0.1s (100ms) gap between consecutive subtitle segments by shifting them forward if they overlap."""
        import pydub
        from pydub import AudioSegment
        import imageio_ffmpeg
        
        # Configure pydub to use imageio-ffmpeg's bundled executable
        pydub.AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Pre-load all segment audios to analyze durations
        loaded_segments = []
        import subprocess
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        
        for i, sub in enumerate(subs):
            seg_path = segment_files.get(i)
            audio = None
            duration_ms = 0
            if seg_path and os.path.exists(seg_path):
                try:
                    # Convert MP3 to WAV using ffmpeg directly (bypasses ffprobe requirement in pydub)
                    wav_path = seg_path.replace(".mp3", ".wav")
                    subprocess.run(
                        [ffmpeg_exe, "-y", "-i", seg_path, wav_path], 
                        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    
                    audio = AudioSegment.from_wav(wav_path)
                    duration_ms = len(audio)
                except Exception as e:
                    self.progress_updated.emit(90, f"Dòng {i+1}: Không thể đọc file âm thanh segment: {e}")
            loaded_segments.append((audio, duration_ms))

        # Calculate non-overlapping timestamps maintaining a 0.1s (100ms) gap
        adjusted_starts = {}
        current_time_ms = 0
        
        for i, sub in enumerate(subs):
            audio, duration_ms = loaded_segments[i]
            if audio is None:
                continue
            
            target_start_ms = int(sub.start.ordinal)
            
            # Start time must be at least original start time, and at least previous_end + 100ms
            start_ms = max(target_start_ms, current_time_ms)
            adjusted_starts[i] = start_ms
            
            # Next segment must start at least 100ms (0.1s) after this one ends
            current_time_ms = start_ms + duration_ms + 100

        # Create silent track matching total adjusted length
        total_duration_ms = current_time_ms + 1000
        master = AudioSegment.silent(duration=total_duration_ms)
        
        # Overlay each segment at its adjusted timestamp
        for i, sub in enumerate(subs):
            audio, _ = loaded_segments[i]
            if audio is not None and i in adjusted_starts:
                start_ms = adjusted_starts[i]
                master = master.overlay(audio, position=start_ms)
                    
        # Export master audio using ffmpeg directly to MP3
        try:
            master.export(output_path, format="mp3")
            return output_path
        except Exception as e:
            raise RuntimeError(f"Lỗi khi xuất file MP3: {e}")

    def stop(self):
        self.is_running = False


class SRTDubbingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CapCut SRT Subtitle Dubbing - Lồng Tiếng Sub")
        self.resize(800, 600)
        self.worker = None
        
        # Cache loads
        self.config = load_config()
        self.capcut_voices = load_capcut_voices()

        self.setup_ui()
        self.apply_styles()
        self.load_cached_settings()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header Title
        header_label = QLabel("SRT SUBTITLE DUBBING - LỒNG TIẾNG SUB")
        header_label.setObjectName("HeaderLabel")
        desc_label = QLabel("Chuyển đổi tệp phụ đề SRT thành băng lồng tiếng ghép nối chuẩn timeline (Chỉ sử dụng CapCut)")
        desc_label.setObjectName("DescLabel")
        
        main_layout.addWidget(header_label)
        main_layout.addWidget(desc_label)

        # 1. File Selection Group
        file_group = QGroupBox("Chọn Tệp Tin")
        file_layout = QFormLayout(file_group)
        file_layout.setSpacing(10)

        # Input SRT Row
        self.srt_input = QLineEdit()
        self.srt_input.setPlaceholderText("Đường dẫn đến tệp phụ đề (.srt) cần lồng tiếng...")
        srt_in_btn = QPushButton("Chọn SRT")
        srt_in_btn.clicked.connect(self.select_srt_input)
        
        srt_in_row = QHBoxLayout()
        srt_in_row.addWidget(self.srt_input)
        srt_in_row.addWidget(srt_in_btn)
        file_layout.addRow("Tệp Phụ Đề:", srt_in_row)

        # Output Audio Row
        self.audio_output = QLineEdit()
        self.audio_output.setPlaceholderText("Đường dẫn để lưu tệp âm thanh hoàn thành...")
        
        from PyQt6.QtWidgets import QStyle
        open_folder_btn = QPushButton()
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        open_folder_btn.setIcon(icon)
        open_folder_btn.setToolTip("Mở thư mục lưu")
        open_folder_btn.setFixedWidth(36)
        open_folder_btn.clicked.connect(self.open_output_folder)

        audio_out_btn = QPushButton("Nơi Lưu")
        audio_out_btn.clicked.connect(self.select_audio_output)

        audio_out_row = QHBoxLayout()
        audio_out_row.addWidget(self.audio_output)
        audio_out_row.addWidget(open_folder_btn)
        audio_out_row.addWidget(audio_out_btn)
        file_layout.addRow("Lưu Âm Thanh:", audio_out_row)

        main_layout.addWidget(file_group)

        # 2. Configurations Group
        config_group = QGroupBox("Cấu Hình Giọng Đọc (CapCut)")
        config_layout = QHBoxLayout(config_group)
        config_layout.setSpacing(20)

        left_col = QWidget()
        left_layout = QFormLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.voice_combo = QComboBox()
        
        left_layout.addRow("Giọng Đọc (Voice):", self.voice_combo)
        config_layout.addWidget(left_col)

        # Populate combo box with CapCut voices directly
        if not self.capcut_voices:
            self.voice_combo.addItem("Không tìm thấy Voice.json", None)
        else:
            for item in self.capcut_voices:
                self.voice_combo.addItem(item["display_name"], item)

        main_layout.addWidget(config_group)

        # 3. Actions Button
        action_layout = QHBoxLayout()
        self.start_btn = QPushButton("Bắt Đầu Lồng Tiếng")
        self.start_btn.setObjectName("StartBtn")
        self.start_btn.clicked.connect(self.start_dubbing)

        self.stop_btn = QPushButton("Hủy Lồng Tiếng")
        self.stop_btn.setObjectName("StopBtn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_dubbing)

        action_layout.addWidget(self.start_btn)
        action_layout.addWidget(self.stop_btn)
        main_layout.addLayout(action_layout)

        # 4. Progress and Log
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Nhật ký tạo giọng nói và tiến trình lồng tiếng sẽ hiển thị tại đây...")
        main_layout.addWidget(self.log_output)

        # Status Bar Info
        self.status_label = QLabel("Sẵn sàng")
        self.status_label.setObjectName("StatusLabel")
        main_layout.addWidget(self.status_label)

    def apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #121214;
                color: #e2e8f0;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif;
                font-size: 13px;
            }
            
            #HeaderLabel {
                font-size: 20px;
                font-weight: bold;
                color: #f7fafc;
                background: transparent;
                letter-spacing: 1px;
            }
            
            #DescLabel {
                color: #a0aec0;
                font-size: 13px;
                margin-bottom: 5px;
            }
            
            QGroupBox {
                border: 1px solid #2d3748;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                font-weight: bold;
                color: #ec4899; /* Dubbing color theme: Pink */
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 5px;
                background-color: #121214;
            }
            
            QLineEdit {
                background-color: #1a1a1e;
                border: 1px solid #2d3748;
                border-radius: 6px;
                padding: 8px 12px;
                color: #f7fafc;
                selection-background-color: #ec4899;
            }
            
            QLineEdit:focus {
                border: 1px solid #ec4899;
            }
            
            QPushButton {
                background-color: #1f2937;
                color: #f7fafc;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            
            QPushButton:hover {
                background-color: #374151;
                border-color: #4b5563;
            }
            
            QPushButton:pressed {
                background-color: #111827;
            }
            
            #StartBtn {
                background-color: #ec4899;
                color: #ffffff;
                border: none;
                font-size: 14px;
                font-weight: bold;
                padding: 12px;
            }
            
            #StartBtn:hover {
                background-color: #db2777;
            }
            
            #StartBtn:pressed {
                background-color: #be185d;
            }
            
            #StartBtn:disabled {
                background-color: #2d3748;
                color: #718096;
            }
            
            #StopBtn {
                background-color: #ef4444;
                color: #ffffff;
                border: none;
                font-size: 14px;
                font-weight: bold;
                padding: 12px;
            }
            
            #StopBtn:hover {
                background-color: #dc2626;
            }
            
            #StopBtn:pressed {
                background-color: #991b1b;
            }
            
            #StopBtn:disabled {
                background-color: #2d3748;
                color: #718096;
            }
            
            QComboBox {
                background-color: #1a1a1e;
                border: 1px solid #2d3748;
                border-radius: 6px;
                padding: 6px 12px;
                color: #f7fafc;
                min-width: 300px;
            }
            
            QComboBox:hover {
                border-color: #4b5563;
            }
            
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left-width: 0px;
            }
            
            QComboBox QAbstractItemView {
                background-color: #1a1a1e;
                border: 1px solid #2d3748;
                selection-background-color: #ec4899;
                selection-color: #ffffff;
                outline: 0px;
            }
            
            QProgressBar {
                border: 1px solid #2d3748;
                border-radius: 6px;
                text-align: center;
                background-color: #1a1a1e;
                color: #ffffff;
                font-weight: bold;
                height: 20px;
            }
            
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ec4899, stop:1 #a855f7);
                border-radius: 5px;
            }
            
            QTextEdit {
                background-color: #1a1a1e;
                border: 1px solid #2d3748;
                border-radius: 8px;
                padding: 12px;
                color: #e2e8f0;
                font-family: 'Courier New', Courier, monospace;
                font-size: 12px;
            }
            
            #StatusLabel {
                color: #718096;
                font-size: 11px;
            }
        """)

    def load_cached_settings(self):
        # Load remembered SRT files and directory
        cached_srt = self.config.get("srt_input", "")
        if cached_srt and os.path.exists(cached_srt):
            self.srt_input.setText(cached_srt)
            self.audio_output.setText(self.config.get("audio_output", ""))
        self.voice_combo.setCurrentText(self.config.get("voice_display", ""))

    def select_srt_input(self):
        initial_dir = self.config.get("last_dir", "")
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Chọn Tệp Phụ Đề SRT", 
            initial_dir, 
            "Subtitle Files (*.srt);;All Files (*)"
        )
        if file_path:
            self.srt_input.setText(file_path)
            # Auto suggest output file name
            base = os.path.splitext(file_path)[0]
            
            # Check workspace config
            import json
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workspace_config.json")
            out_dir = os.path.dirname(file_path)
            try:
                if os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        if "workspace" in cfg:
                            ws = cfg["workspace"]
                            out_dir = os.path.join(ws, "Video lồng tiếng")
                            os.makedirs(out_dir, exist_ok=True)
            except Exception: pass
            
            base_name = os.path.basename(file_path)
            name_without_ext, _ = os.path.splitext(base_name)
            out_path = os.path.join(out_dir, name_without_ext + "_dubbing.mp3")
            
            self.audio_output.setText(out_path)
            # Save to config
            self.config["srt_input"] = file_path
            self.config["audio_output"] = out_path
            self.config["last_dir"] = os.path.dirname(file_path)
            save_config(self.config)

    def select_audio_output(self):
        initial_dir = self.config.get("last_dir", "")
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Chọn Nơi Lưu Tệp Lồng Tiếng", 
            self.audio_output.text() or initial_dir, 
            "Audio Files (*.mp3 *.wav);;All Files (*)"
        )
        if file_path:
            self.audio_output.setText(file_path)
            self.config["audio_output"] = file_path
            self.config["last_dir"] = os.path.dirname(file_path)
            save_config(self.config)

    def start_dubbing(self):
        srt_path = self.srt_input.text().strip()
        audio_output = self.audio_output.text().strip()

        if not srt_path or not os.path.exists(srt_path):
            QMessageBox.warning(self, "Lỗi Tệp Phụ Đề", "Vui lòng chọn tệp phụ đề SRT hợp lệ!")
            return

        if not audio_output:
            QMessageBox.warning(self, "Lỗi Nơi Lưu", "Vui lòng chọn đường dẫn lưu tệp lồng tiếng!")
            return

        # Get voice info
        voice_data = self.voice_combo.currentData()
        if not voice_data:
            QMessageBox.warning(self, "Lỗi Giọng Đọc", "Vui lòng chọn giọng đọc hợp lệ!")
            return

        voice_type = voice_data["voice_type"]
        resource_id = voice_data["resource_id"]

        # Cache inputs
        self.config["srt_input"] = srt_path
        self.config["audio_output"] = audio_output
        self.config["voice_display"] = self.voice_combo.currentText()
        save_config(self.config)

        # Clear components
        self.log_output.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("Đang chạy...")
        
        # Toggle controls
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.srt_input.setEnabled(False)
        self.audio_output.setEnabled(False)
        self.voice_combo.setEnabled(False)

        # Run Worker
        self.worker = DubbingWorker(
            srt_path=srt_path,
            output_audio_path=audio_output,
            voice=voice_type,
            resource_id=resource_id
        )
        self.worker.progress_updated.connect(self.on_progress)
        self.worker.finished.connect(self.on_success)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def stop_dubbing(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
            self.log_output.append("\n--- Đã dừng tiến trình bởi người dùng ---")
            self.status_label.setText("Đã dừng")
            self.progress_bar.setValue(0)
            self.reset_ui_controls()

    def on_progress(self, val, message):
        self.progress_bar.setValue(val)
        self.log_output.append(message)
        self.log_output.ensureCursorVisible()

    def on_success(self, final_path):
        self.status_label.setText("Hoàn thành")
        QMessageBox.information(
            self, 
            "Thành Công", 
            f"Quá trình lồng tiếng phụ đề hoàn tất!\nTệp băng nhạc lồng tiếng được lưu tại:\n{final_path}"
        )
        self.reset_ui_controls()

    def on_error(self, error_msg):
        self.status_label.setText("Gặp lỗi")
        self.log_output.append(f"\n[LỖI]: {error_msg}")
        QMessageBox.critical(
            self, 
            "Gặp Lỗi", 
            f"Đã xảy ra lỗi trong quá trình lồng tiếng phụ đề:\n{error_msg}"
        )
        self.reset_ui_controls()

    def reset_ui_controls(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.srt_input.setEnabled(True)
        self.audio_output.setEnabled(True)
        self.voice_combo.setEnabled(True)
        self.worker = None

    def open_output_folder(self):
        path = self.audio_output.text().strip()
        if path:
            folder = os.path.dirname(os.path.abspath(path))
            if os.path.exists(folder):
                os.startfile(folder)
            else:
                QMessageBox.warning(self, "Không tìm thấy", f"Thư mục không tồn tại: {folder}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Custom font sizing for high DPI screens
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = SRTDubbingApp()
    window.show()
    sys.exit(app.exec())
