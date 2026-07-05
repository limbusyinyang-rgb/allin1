import sys
import os

# Import torch first to prevent WinError 127 when paddleocr/albumentations load it later
try:
    import torch
except ImportError:
    pass

# Add Nvidia CUDA/cuDNN package DLL directories to DLL search path and PATH on Windows
_dll_handles = []
if sys.platform == "win32":
    for p in sys.path:
        if "site-packages" in p.lower():
            nvidia_path = os.path.join(p, "nvidia")
            if os.path.exists(nvidia_path):
                for sub in ["cublas", "cudnn", "cuda_nvrtc", "cuda_runtime"]:
                    bin_path = os.path.join(nvidia_path, sub, "bin")
                    if os.path.exists(bin_path):
                        try:
                            _dll_handles.append(os.add_dll_directory(bin_path))
                            # Add to PATH as double-insurance for legacy DLL loaders
                            os.environ["PATH"] = bin_path + os.path.pathsep + os.environ["PATH"]
                        except Exception as e:
                            print(f"Error adding DLL path {bin_path}: {e}")

import time
import json
import cv2
import numpy as np
from difflib import SequenceMatcher
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QFormLayout, QPushButton, QLabel, QLineEdit, QFileDialog, 
    QComboBox, QProgressBar, QTextEdit, QMessageBox, QGroupBox,
    QSlider, QDoubleSpinBox, QSpinBox, QGridLayout, QCheckBox, QSizePolicy
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QIcon, QImage, QPixmap, QPainter, QPen, QColor

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

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


# Import PaddleOCR
try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

# List of OCR Languages
OCR_LANGUAGES = {
    "Tiếng Trung (Giản Thể)": "ch",
    "Tiếng Trung (Phồn Thể)": "chinese_cht",
    "Tiếng Anh": "en"
}

def format_srt_timestamp(seconds: float) -> str:
    """Format seconds into SRT timestamp format: HH:MM:SS,mmm"""
    ms = int(round(seconds * 1000))
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    secs = ms // 1000
    ms %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"

def extract_video_chunk(chunk_id, video_path, start_sec, end_sec, ocr_langs, device, scan_interval, min_confidence, crop_region, filter_keywords):
    try:
        # Import inside the function to support multiprocessing
        from paddleocr import PaddleOCR
        import cv2
        import numpy as np

        gpu_enabled = (device == "cuda")
        reader = PaddleOCR(use_angle_cls=False, lang=ocr_langs, use_gpu=gpu_enabled, show_log=False)
        
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_step = max(1, int(fps * scan_interval))
        
        cap.set(cv2.CAP_PROP_POS_MSEC, start_sec * 1000)
        
        ocr_raw_results = []
        prev_edges = None
        prev_valid_texts = []
        prev_conf_sum = 0.0
        prev_conf_count = 0
        
        frame_idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        end_frame = int(end_sec * fps)
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame_idx > end_frame:
                break
            
            timestamp = frame_idx / fps
            
            h, w, _ = frame.shape
            x1, x2 = int(crop_region[0]/100.0 * w), int(crop_region[1]/100.0 * w)
            y1, y2 = int(crop_region[2]/100.0 * h), int(crop_region[3]/100.0 * h)
            x1, x2 = max(0, min(x1, w - 1)), max(0, min(x2, w))
            y1, y2 = max(0, min(y1, h - 1)), max(0, min(y2, h))
            
            if x2 > x1 and y2 > y1:
                cropped = frame[y1:y2, x1:x2]
                crop_h, crop_w, _ = cropped.shape
                if crop_h < 64:
                    scale = 64.0 / crop_h
                    cropped = cv2.resize(cropped, (int(crop_w * scale), 64), interpolation=cv2.INTER_CUBIC)
                
                gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, 100, 200)
                
                edge_changed = False
                if prev_edges is not None and prev_edges.shape == edges.shape:
                    diff = cv2.absdiff(edges, prev_edges)
                    change_ratio = np.count_nonzero(diff) / edges.size
                    if change_ratio >= 0.005: 
                        edge_changed = True
                else:
                    edge_changed = True
                    
                force_scan = (frame_idx % frame_step == 0)
                
                if edge_changed or force_scan:
                    results = reader.ocr(cropped, cls=False)
                    valid_texts = []
                    conf_sum, conf_count = 0.0, 0
                    if results and results[0]:
                        for line in results[0]:
                            bbox, (text, confidence) = line
                            text = text.strip()
                            for kw in filter_keywords:
                                if kw in text: text = text.replace(kw, "")
                            text = text.strip()
                            if text and confidence >= min_confidence:
                                valid_texts.append(text)
                                conf_sum += confidence
                                conf_count += 1
                                
                    prev_edges = edges.copy()
                    prev_valid_texts = list(valid_texts)
                    prev_conf_sum = conf_sum
                    prev_conf_count = conf_count
                else:
                    valid_texts = list(prev_valid_texts)
                    conf_sum = prev_conf_sum
                    conf_count = prev_conf_count
                
                if valid_texts:
                    avg_conf = conf_sum / conf_count
                    joined_text = "\n".join(valid_texts).strip()
                    ocr_raw_results.append((timestamp, joined_text, avg_conf))
                else:
                    ocr_raw_results.append((timestamp, "", 0.0))
            
            frame_idx += 1
            
        cap.release()
        return chunk_id, ocr_raw_results
    except Exception as e:
        return chunk_id, e

class TranscriptionWorker(QThread):
    progress_updated = pyqtSignal(int, str)  # percentage, log/text snippet
    finished = pyqtSignal(str)              # status message / output path
    error_occurred = pyqtSignal(str)         # error message

    def __init__(self, video_path, srt_path, device, ocr_langs, scan_interval, min_confidence, similarity_threshold, crop_region, filter_keywords):
        super().__init__()
        self.video_path = video_path
        self.srt_path = srt_path
        self.device = device
        self.ocr_langs = ocr_langs
        self.scan_interval = scan_interval
        self.min_confidence = min_confidence / 100.0
        self.similarity_threshold = similarity_threshold / 100.0
        self.crop_region = crop_region
        self.filter_keywords = filter_keywords
        self.is_running = True

    def run(self):
        try:
            from paddleocr import PaddleOCR
            import cv2
            import numpy as np
            
            if PaddleOCR is None:
                raise ImportError("Thư viện `paddleocr` chưa được cài đặt.")

            self.progress_updated.emit(2, f"Đang khởi tạo mô hình AI (GPU: {self.device})...")

            gpu_enabled = (self.device == "cuda")
            reader = PaddleOCR(use_angle_cls=False, lang=self.ocr_langs, use_gpu=gpu_enabled, show_log=False)

            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                raise ValueError("Không thể mở tệp video. Định dạng không được hỗ trợ hoặc tệp bị hỏng.")

            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps

            if fps <= 0 or frame_count <= 0:
                cap.release()
                raise ValueError("Không thể đọc thông số FPS hoặc tổng số khung hình của video.")

            self.progress_updated.emit(5, f"Thời lượng video: {duration:.2f} giây (FPS: {fps:.2f}, Tổng frames: {frame_count})")
            
            frame_step = max(1, int(fps * self.scan_interval))
            ocr_raw_results = []
            
            prev_edges = None
            prev_valid_texts = []
            prev_conf_sum = 0.0
            prev_conf_count = 0
            
            frame_idx = 0
            
            while cap.isOpened() and self.is_running:
                ret, frame = cap.read()
                if not ret:
                    break
                
                timestamp = frame_idx / fps
                
                h, w, _ = frame.shape
                x1, x2 = int(self.crop_region[0]/100.0 * w), int(self.crop_region[1]/100.0 * w)
                y1, y2 = int(self.crop_region[2]/100.0 * h), int(self.crop_region[3]/100.0 * h)
                x1, x2 = max(0, min(x1, w - 1)), max(0, min(x2, w))
                y1, y2 = max(0, min(y1, h - 1)), max(0, min(y2, h))
                
                if x2 > x1 and y2 > y1:
                    cropped = frame[y1:y2, x1:x2]
                    crop_h, crop_w, _ = cropped.shape
                    if crop_h < 64:
                        scale = 64.0 / crop_h
                        cropped = cv2.resize(cropped, (int(crop_w * scale), 64), interpolation=cv2.INTER_CUBIC)
                    
                    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
                    edges = cv2.Canny(gray, 100, 200)
                    
                    edge_changed = False
                    if prev_edges is not None and prev_edges.shape == edges.shape:
                        diff = cv2.absdiff(edges, prev_edges)
                        change_ratio = np.count_nonzero(diff) / edges.size
                        if change_ratio >= 0.005: 
                            edge_changed = True
                    else:
                        edge_changed = True
                        
                    force_scan = (frame_idx % frame_step == 0)
                    
                    if edge_changed or force_scan:
                        results = reader.ocr(cropped, cls=False)
                        valid_texts = []
                        conf_sum, conf_count = 0.0, 0
                        if results and results[0]:
                            for line in results[0]:
                                bbox, (text, confidence) = line
                                text = text.strip()
                                for kw in self.filter_keywords:
                                    if kw in text: text = text.replace(kw, "")
                                text = text.strip()
                                if text and confidence >= self.min_confidence:
                                    valid_texts.append(text)
                                    conf_sum += confidence
                                    conf_count += 1
                                    
                        prev_edges = edges.copy()
                        prev_valid_texts = list(valid_texts)
                        prev_conf_sum = conf_sum
                        prev_conf_count = conf_count
                    else:
                        valid_texts = list(prev_valid_texts)
                        conf_sum = prev_conf_sum
                        conf_count = prev_conf_count
                    
                    if valid_texts:
                        avg_conf = conf_sum / conf_count
                        joined_text = "\n".join(valid_texts).strip()
                        ocr_raw_results.append((timestamp, joined_text, avg_conf))
                    else:
                        ocr_raw_results.append((timestamp, "", 0.0))
                
                frame_idx += 1
                
                if frame_idx % int(fps * 2) == 0:  # Update progress every 2 seconds of video
                    pct = 7 + int((frame_idx / frame_count) * 85)
                    self.progress_updated.emit(pct, f"Đang quét ({frame_idx}/{frame_count} frames)...")
                    
            cap.release()

            if not self.is_running:
                return

            self.progress_updated.emit(92, "Đang xử lý gộp các phân đoạn phụ đề...")
            
            # Sort by timestamp
            all_raw_results.sort(key=lambda x: x[0])
            
            # Deduplicate by rounding timestamp to avoid overlap duplicates
            unique_raw_results = []
            seen_times = set()
            for ts, txt, conf in all_raw_results:
                ts_key = round(ts, 1)
                if ts_key not in seen_times:
                    seen_times.add(ts_key)
                    unique_raw_results.append((ts, txt, conf))
                    
            ocr_raw_results = unique_raw_results

            # 3. Process raw OCR results into grouped subtitles using hysteresis/debouncing algorithm
            subtitles = []
            current_sub = None
            max_gap = 0.3  # seconds allowed for missing frame OCR detections before finalizing
            
            for timestamp, text, confidence in ocr_raw_results:
                if text:
                    if current_sub is None:
                        current_sub = {
                            'start': timestamp,
                            'end': timestamp,
                            'last_seen': timestamp,
                            'texts': {text: (1, confidence)} # text -> (count, max_confidence)
                        }
                    else:
                        # Find the best text in this segment so far
                        best_text = max(current_sub['texts'].keys(), key=lambda k: current_sub['texts'][k][0])
                        similarity = SequenceMatcher(None, text, best_text).ratio()
                        
                        if similarity >= self.similarity_threshold:
                            current_sub['end'] = timestamp
                            current_sub['last_seen'] = timestamp
                            count, max_conf = current_sub['texts'].get(text, (0, 0.0))
                            current_sub['texts'][text] = (count + 1, max(max_conf, confidence))
                        else:
                            # Finalize previous and start new
                            final_text = max(current_sub['texts'].keys(), key=lambda k: (current_sub['texts'][k][0], current_sub['texts'][k][1]))
                            subtitles.append({
                                'start': current_sub['start'],
                                'end': current_sub['end'],
                                'text': final_text
                            })
                            current_sub = {
                                'start': timestamp,
                                'end': timestamp,
                                'last_seen': timestamp,
                                'texts': {text: (1, confidence)}
                            }
                else:
                    if current_sub is not None:
                        # If the time since last seen text is greater than max_gap, finalize it
                        if timestamp - current_sub['last_seen'] > max_gap:
                            final_text = max(current_sub['texts'].keys(), key=lambda k: (current_sub['texts'][k][0], current_sub['texts'][k][1]))
                            subtitles.append({
                                'start': current_sub['start'],
                                'end': current_sub['end'],
                                'text': final_text
                            })
                            current_sub = None

            if current_sub is not None:
                final_text = max(current_sub['texts'].keys(), key=lambda k: (current_sub['texts'][k][0], current_sub['texts'][k][1]))
                subtitles.append({
                    'start': current_sub['start'],
                    'end': current_sub['end'],
                    'text': final_text
                })

            # Filter out empty or extremely short segments
            subtitles = [s for s in subtitles if s['text'].strip() and (s['end'] - s['start']) >= 0.1]
            
            # 3.5 Wrap text if line exceeds 10 characters
            import textwrap
            for sub in subtitles:
                lines = sub['text'].split('\n')
                wrapped_lines = []
                is_chinese = self.ocr_langs in ["ch", "chinese_cht"]
                for line in lines:
                    if len(line) > 10:
                        if is_chinese:
                            # Balance the split if it's between 11 and 20 characters
                            if len(line) <= 20:
                                mid = (len(line) + 1) // 2
                                wrapped_lines.extend([line[:mid], line[mid:]])
                            else:
                                wrapped_lines.extend([line[i:i+10] for i in range(0, len(line), 10)])
                        else:
                            wrapped_lines.extend(textwrap.wrap(line, 10))
                    else:
                        wrapped_lines.append(line)
                sub['text'] = "\n".join(wrapped_lines)
            if not self.is_running:
                return

            # 4. Save to SRT
            self.progress_updated.emit(96, "Đang ghi phụ đề ra tệp .srt...")
            
            srt_content = []
            for idx, sub in enumerate(subtitles, 1):
                timestamp_str = f"{format_srt_timestamp(sub['start'])} --> {format_srt_timestamp(sub['end'])}"
                line_text = sub['text'].strip()
                srt_segment = f"{idx}\n{timestamp_str}\n{line_text}\n\n"
                srt_content.append(srt_segment)

            with open(self.srt_path, "w", encoding="utf-8") as f:
                f.write("".join(srt_content))

            self.progress_updated.emit(100, f"Hoàn thành trích xuất! Tổng cộng {len(subtitles)} câu phụ đề.")
            self.finished.emit(self.srt_path)

        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        self.is_running = False


class OcrExtractorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OCR Subtitle Extractor - Trích Xuất Sub Từ Video")
        self.worker = None
        self.config = load_config()
        
        self.original_pixmap = None
        self.preview_frame_rgb = None
        self.preview_width = 0
        self.preview_height = 0

        # UI Setup
        self.setup_ui()
        self.apply_styles()
        self.detect_gpu_support()
        self.load_cached_settings()
        
        self.showMaximized()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        top_layout = QHBoxLayout(central_widget)
        top_layout.setContentsMargins(20, 20, 20, 20)
        top_layout.setSpacing(20)
        
        left_panel = QWidget()
        main_layout = QVBoxLayout(left_panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(15)
        
        right_panel = QWidget()
        self.right_layout = QVBoxLayout(right_panel)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(15)
        
        top_layout.addWidget(left_panel, stretch=5)
        top_layout.addWidget(right_panel, stretch=5)

        # Header Title
        header_label = QLabel("OCR SUBTITLE EXTRACTOR")
        header_label.setObjectName("HeaderLabel")
        desc_label = QLabel("Trích xuất phụ đề tự động bằng nhận dạng chữ viết trên video (Bắt sub tiếng Trung)")
        desc_label.setObjectName("DescLabel")
        
        main_layout.addWidget(header_label)
        main_layout.addWidget(desc_label)

        # 1. File Selection Group
        file_group = QGroupBox("Chọn Tệp Tin")
        file_layout = QFormLayout(file_group)
        file_layout.setSpacing(10)

        # Video Input Row
        self.video_input = QLineEdit()
        self.video_input.setPlaceholderText("Đường dẫn đến tệp video cần trích phụ đề...")
        self.video_input.textChanged.connect(self.on_video_path_changed)
        video_btn = QPushButton("Chọn Video")
        video_btn.clicked.connect(self.select_video)
        
        video_row = QHBoxLayout()
        video_row.addWidget(self.video_input)
        video_row.addWidget(video_btn)
        file_layout.addRow("Video Đầu Vào:", video_row)

        # SRT Output Row
        self.srt_input = QLineEdit()
        self.srt_input.setPlaceholderText("Đường dẫn để lưu tệp phụ đề (.srt)...")
        
        from PyQt6.QtWidgets import QStyle
        open_folder_btn = QPushButton()
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        open_folder_btn.setIcon(icon)
        open_folder_btn.setToolTip("Mở thư mục lưu")
        open_folder_btn.setFixedWidth(36)
        open_folder_btn.clicked.connect(self.open_output_folder)

        srt_btn = QPushButton("Chọn Nơi Lưu")
        srt_btn.clicked.connect(self.select_srt_output)

        srt_row = QHBoxLayout()
        srt_row.addWidget(self.srt_input)
        srt_row.addWidget(open_folder_btn)
        srt_row.addWidget(srt_btn)
        file_layout.addRow("Lưu Tệp SRT:", srt_row)

        main_layout.addWidget(file_group)

        # 2. Configurations Group
        config_group = QGroupBox("Cấu Hình Nhận Diện OCR")
        config_main_layout = QVBoxLayout(config_group)
        config_main_layout.setSpacing(10)
        
        config_layout = QHBoxLayout()
        config_layout.setSpacing(20)

        # Left Column Configurations
        left_col = QWidget()
        left_layout = QFormLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.lang_combo = QComboBox()
        for display_name in OCR_LANGUAGES.keys():
            self.lang_combo.addItem(display_name)
        
        self.scans_per_sec_spin = QSpinBox()
        self.scans_per_sec_spin.setRange(10, 100)
        self.scans_per_sec_spin.setSingleStep(10)
        self.scans_per_sec_spin.setValue(10)
        from PyQt6.QtWidgets import QAbstractSpinBox
        self.scans_per_sec_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.scans_per_sec_spin.setFixedWidth(80)
        
        scan_layout = QHBoxLayout()
        scan_layout.setContentsMargins(0, 0, 0, 0)
        scan_layout.addWidget(self.scans_per_sec_spin)
        scan_layout.addWidget(QLabel("lần/giây"))
        
        self.scan_warning_label = QLabel()
        self.scan_warning_label.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 11px;")
        scan_layout.addWidget(self.scan_warning_label)
        scan_layout.addStretch()
        
        self.scans_per_sec_spin.valueChanged.connect(self.on_scan_freq_changed)
        
        left_layout.addRow("Ngôn Ngữ OCR:", self.lang_combo)
        left_layout.addRow("Tần Suất Quét:", scan_layout)

        # Right Column Configurations
        right_col = QWidget()
        right_layout = QFormLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.device_combo = QComboBox()
        self.device_combo.addItems(["cuda", "cpu"])

        right_layout.addRow("Thiết Bị Chạy:", self.device_combo)

        config_layout.addWidget(left_col)
        config_layout.addWidget(right_col)
        config_main_layout.addLayout(config_layout)
        main_layout.addWidget(config_group)

        # Multiprocessing group removed

        # 3. Subtitle Region Selection (Crop) Group
        crop_group = QGroupBox("Căn Chỉnh Vùng Quét Phụ Đề")
        crop_main_layout = QVBoxLayout(crop_group)
        crop_main_layout.setSpacing(10)

        # Right Side Preview
        preview_group = QGroupBox("Xem Trước Video")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #1e1e24; border: 1px dashed #4b5563; border-radius: 6px; color: #a0aec0;")
        self.preview_label.setText("Chưa tải video. Hãy chọn tệp video để xem trước vùng crop phụ đề.")
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.preview_label.setMinimumSize(100, 300)
        preview_layout.addWidget(self.preview_label, stretch=1)
        
        # Video Timeline Slider for scrubbing
        timeline_layout = QHBoxLayout()
        timeline_layout.addWidget(QLabel("Timeline Video:"))
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 100)
        self.timeline_slider.setValue(40)
        self.timeline_slider.setEnabled(False)
        self.timeline_slider.valueChanged.connect(self.on_timeline_changed)
        timeline_layout.addWidget(self.timeline_slider)
        preview_layout.addLayout(timeline_layout)
        
        self.right_layout.addWidget(preview_group)

        # Sliders for crop coordinates
        sliders_layout = QGridLayout()
        sliders_layout.setSpacing(10)

        # Y-Start Slider (Crop Top)
        sliders_layout.addWidget(QLabel("Cắt Trên (Y-Start):"), 0, 0)
        self.y_start_slider = QSlider(Qt.Orientation.Horizontal)
        self.y_start_slider.setRange(0, 100)
        self.y_start_slider.setValue(80)
        self.y_start_slider.valueChanged.connect(self.on_crop_slider_changed)
        self.y_start_label = QLabel("80%")
        self.y_start_label.setFixedWidth(35)
        sliders_layout.addWidget(self.y_start_slider, 0, 1)
        sliders_layout.addWidget(self.y_start_label, 0, 2)

        # Y-End Slider (Crop Bottom)
        sliders_layout.addWidget(QLabel("Cắt Dưới (Y-End):"), 0, 3)
        self.y_end_slider = QSlider(Qt.Orientation.Horizontal)
        self.y_end_slider.setRange(0, 100)
        self.y_end_slider.setValue(95)
        self.y_end_slider.valueChanged.connect(self.on_crop_slider_changed)
        self.y_end_label = QLabel("95%")
        self.y_end_label.setFixedWidth(35)
        sliders_layout.addWidget(self.y_end_slider, 0, 4)
        sliders_layout.addWidget(self.y_end_label, 0, 5)

        # X-Start Slider (Crop Left)
        sliders_layout.addWidget(QLabel("Cắt Trái (X-Start):"), 1, 0)
        self.x_start_slider = QSlider(Qt.Orientation.Horizontal)
        self.x_start_slider.setRange(0, 100)
        self.x_start_slider.setValue(0)
        self.x_start_slider.valueChanged.connect(self.on_crop_slider_changed)
        self.x_start_label = QLabel("0%")
        self.x_start_label.setFixedWidth(35)
        sliders_layout.addWidget(self.x_start_slider, 1, 1)
        sliders_layout.addWidget(self.x_start_label, 1, 2)

        # X-End Slider (Crop Right)
        sliders_layout.addWidget(QLabel("Cắt Phải (X-End):"), 1, 3)
        self.x_end_slider = QSlider(Qt.Orientation.Horizontal)
        self.x_end_slider.setRange(0, 100)
        self.x_end_slider.setValue(100)
        self.x_end_slider.valueChanged.connect(self.on_crop_slider_changed)
        self.x_end_label = QLabel("100%")
        self.x_end_label.setFixedWidth(35)
        sliders_layout.addWidget(self.x_end_slider, 1, 4)
        sliders_layout.addWidget(self.x_end_label, 1, 5)

        crop_main_layout.addLayout(sliders_layout)
        
        # Thêm khung Lọc từ khóa
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Từ khóa loại bỏ (cách nhau bởi dấu phẩy):"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Ví dụ: tiktok, 抖音, watermark...")
        filter_layout.addWidget(self.filter_input)
        
        self.sample_filter_btn = QPushButton("Lấy Mẫu Từ Vùng Cắt")
        self.sample_filter_btn.setToolTip("Chạy nhanh OCR trên vùng đang cắt để lấy ký tự nhiễu")
        self.sample_filter_btn.clicked.connect(self.sample_filter_keywords)
        filter_layout.addWidget(self.sample_filter_btn)
        
        crop_main_layout.addLayout(filter_layout)

        main_layout.addWidget(crop_group)

        # 4. Actions Buttons
        action_layout = QHBoxLayout()
        self.start_btn = QPushButton("Bắt Đầu Trích Xuất")
        self.start_btn.setObjectName("StartBtn")
        self.start_btn.clicked.connect(self.start_extraction)

        self.stop_btn = QPushButton("Hủy Bỏ")
        self.stop_btn.setObjectName("StopBtn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_extraction)

        action_layout.addWidget(self.start_btn)
        action_layout.addWidget(self.stop_btn)
        main_layout.addLayout(action_layout)

        # 5. Progress and Log
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        main_layout.addWidget(self.progress_bar)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Nhật ký nhận dạng phụ đề OCR thời gian thực sẽ hiển thị tại đây...")
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
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: #a855f7;
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
                selection-background-color: #4f46e5;
            }
            
            QLineEdit:focus {
                border: 1px solid #6366f1;
            }
            
            QPushButton {
                background-color: #1f2937;
                color: #f7fafc;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 4px 10px;
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
                background-color: #6366f1;
                color: #ffffff;
                border: none;
                font-size: 13px;
                font-weight: bold;
                padding: 6px;
            }
            
            #StartBtn:hover {
                background-color: #4f46e5;
            }
            
            #StartBtn:pressed {
                background-color: #3730a3;
            }
            
            #StartBtn:disabled {
                background-color: #2d3748;
                color: #718096;
            }
            
            #StopBtn {
                background-color: #ef4444;
                color: #ffffff;
                border: none;
                font-size: 13px;
                font-weight: bold;
                padding: 6px;
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
                min-width: 150px;
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
                selection-background-color: #4f46e5;
                selection-color: #ffffff;
                outline: 0px;
            }
            
            QDoubleSpinBox, QSpinBox {
                background-color: #1a1a1e;
                border: 1px solid #2d3748;
                border-radius: 6px;
                padding: 6px 12px;
                color: #f7fafc;
            }
            
            QSlider::groove:horizontal {
                border: 1px solid #2d3748;
                height: 6px;
                background: #1a1a1e;
                border-radius: 3px;
            }
            
            QSlider::handle:horizontal {
                background: #6366f1;
                border: none;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            
            QSlider::handle:horizontal:hover {
                background: #4f46e5;
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
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #a855f7);
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

    def detect_gpu_support(self):
        """Auto-detect CUDA availability and adjust configuration controls accordingly"""
        import paddle
        cuda_ok = paddle.device.is_compiled_with_cuda()
        
        if cuda_ok:
            self.device_combo.setCurrentText("cuda")
            self.log_output.append("Phát hiện GPU (NVIDIA GeForce/CUDA). Đã tự động chọn thiết bị chạy 'cuda'.\n")
        else:
            self.device_combo.setCurrentText("cpu")
            cuda_idx = self.device_combo.findText("cuda")
            if cuda_idx != -1:
                self.device_combo.removeItem(cuda_idx)
            self.log_output.append("Không phát hiện GPU (CUDA). Đang chạy ở chế độ CPU.\n")

    def load_cached_settings(self):
        self.video_input.setText(self.config.get("video_input", ""))
        self.srt_input.setText(self.config.get("srt_input", ""))
        
        lang_idx = self.lang_combo.findText(self.config.get("ocr_lang_name", "Tiếng Trung Giản Thể + Anh"))
        if lang_idx != -1:
            self.lang_combo.setCurrentIndex(lang_idx)
            
        self.device_combo.setCurrentText(self.config.get("device", "cuda"))
        self.scans_per_sec_spin.setValue(self.config.get("scans_per_sec", 3))
        
        # Crop coordinates
        self.x_start_slider.setValue(self.config.get("crop_x_start", 0))
        self.x_end_slider.setValue(self.config.get("crop_x_end", 100))
        self.y_start_slider.setValue(self.config.get("crop_y_start", 70))
        self.y_end_slider.setValue(self.config.get("crop_y_end", 95))
        self.filter_input.setText(self.config.get("filter_keywords", ""))
        
        self.on_crop_slider_changed()

    def select_video(self):
        initial_dir = self.config.get("last_dir", "")
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Chọn Video Đầu Vào", 
            initial_dir, 
            "Video Files (*.mp4 *.mkv *.avi *.mov *.flv *.webm);;All Files (*)"
        )
        if file_path:
            self.video_input.setText(file_path)
            base_name = os.path.basename(file_path)
            name_without_ext, _ = os.path.splitext(base_name)
            
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
                            out_dir = os.path.join(ws, "Sub đã trích xuất")
                            os.makedirs(out_dir, exist_ok=True)
            except Exception: pass
            
            out_path = os.path.join(out_dir, name_without_ext + ".srt")
            self.srt_input.setText(out_path)
            
            self.config["video_input"] = file_path
            self.config["srt_input"] = out_path
            self.config["last_dir"] = os.path.dirname(file_path)
            save_config(self.config)

    def select_srt_output(self):
        initial_dir = self.config.get("last_dir", "")
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Chọn Nơi Lưu Tệp Phụ Đề SRT", 
            self.srt_input.text() or initial_dir, 
            "Subtitle Files (*.srt);;All Files (*)"
        )
        if file_path:
            self.srt_input.setText(file_path)
            self.config["srt_input"] = file_path
            self.config["last_dir"] = os.path.dirname(file_path)
            save_config(self.config)

    def on_video_path_changed(self, text):
        path = text.strip()
        if path and os.path.exists(path) and os.path.isfile(path):
            self.load_video_preview(path)

    def load_video_preview(self, video_path):
        try:
            if hasattr(self, 'preview_cap') and self.preview_cap is not None:
                self.preview_cap.release()
                
            self.preview_cap = cv2.VideoCapture(video_path)
            if not self.preview_cap.isOpened():
                self.preview_label.setText("Lỗi: Không thể mở tệp video này.")
                return
            
            frame_count = int(self.preview_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = self.preview_cap.get(cv2.CAP_PROP_FPS)
            self.total_frames = frame_count
            self.video_fps = fps if fps > 0 else 25.0
            self.current_video_cap_path = video_path
            
            duration_sec = int(frame_count / self.video_fps)
            
            self.timeline_slider.setEnabled(True)
            self.timeline_slider.blockSignals(True)
            self.timeline_slider.setRange(0, duration_sec)
            self.timeline_slider.setSingleStep(1)
            self.timeline_slider.setPageStep(10)
            
            middle_sec = int(duration_sec * 0.4)
            self.timeline_slider.setValue(middle_sec)
            self.timeline_slider.blockSignals(False)
            
            middle_frame = int(middle_sec * self.video_fps)
            self.preview_cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
            ret, frame = self.preview_cap.read()
            
            if ret:
                # Convert BGR to RGB
                self.preview_frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.preview_height, self.preview_width, _ = self.preview_frame_rgb.shape
                
                # Convert to QImage and QPixmap
                qimage = QImage(
                    self.preview_frame_rgb.data, 
                    self.preview_width, 
                    self.preview_height, 
                    self.preview_width * 3, 
                    QImage.Format.Format_RGB888
                )
                self.original_pixmap = QPixmap.fromImage(qimage)
                self.update_preview_overlay()
            else:
                self.preview_label.setText("Lỗi: Không thể trích xuất khung hình từ video.")
        except Exception as e:
            self.preview_label.setText(f"Lỗi tải ảnh xem trước: {e}")

    def sample_filter_keywords(self):
        if not hasattr(self, 'preview_frame_rgb') or self.preview_frame_rgb is None:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn tệp video trước.")
            return
            
        x_start = self.x_start_slider.value()
        x_end = self.x_end_slider.value()
        y_start = self.y_start_slider.value()
        y_end = self.y_end_slider.value()
        
        h, w, _ = self.preview_frame_rgb.shape
        x1 = int(w * x_start / 100.0)
        x2 = int(w * x_end / 100.0)
        y1 = int(h * y_start / 100.0)
        y2 = int(h * y_end / 100.0)
        
        if x2 <= x1 or y2 <= y1:
            QMessageBox.warning(self, "Lỗi", "Vùng cắt không hợp lệ.")
            return
            
        cropped = self.preview_frame_rgb[y1:y2, x1:x2]
        
        try:
            from paddleocr import PaddleOCR
            self.sample_filter_btn.setEnabled(False)
            self.sample_filter_btn.setText("Đang đọc chữ...")
            QApplication.processEvents()
            
            lang_name = self.lang_combo.currentText()
            
            reader = PaddleOCR(use_angle_cls=False, lang=OCR_LANGUAGES[lang_name], use_gpu=(self.device_combo.currentText()=="cuda"), show_log=False)
            results = reader.ocr(cropped, cls=False)
            
            words = []
            if results and results[0]:
                for line in results[0]:
                    bbox, (text, confidence) = line
                    if text.strip() and confidence >= 0.1:
                        words.append(text.strip())
            
            if words:
                current_text = self.filter_input.text().strip()
                new_text = ", ".join(words)
                if current_text:
                    if not current_text.endswith(","):
                        current_text += ","
                    self.filter_input.setText(current_text + " " + new_text)
                else:
                    self.filter_input.setText(new_text)
            else:
                QMessageBox.information(self, "Thông báo", "Không tìm thấy chữ nào trong vùng cắt này.")
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Lỗi OCR khi lấy mẫu: {e}")
        finally:
            self.sample_filter_btn.setEnabled(True)
            self.sample_filter_btn.setText("Lấy Mẫu Từ Vùng Cắt")
    # MP toggle removed

    def on_scan_freq_changed(self, value):
        if value > 50:
            self.scan_warning_label.setText("( GPU có thể quá tải )")
        else:
            self.scan_warning_label.setText("")

    def on_timeline_changed(self):
        if hasattr(self, 'preview_cap') and self.preview_cap is not None and hasattr(self, 'video_fps'):
            target_sec = self.timeline_slider.value()
            target_frame = int(target_sec * self.video_fps)
            
            try:
                self.preview_cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                ret, frame = self.preview_cap.read()
                
                if ret:
                    self.preview_frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.preview_height, self.preview_width, _ = self.preview_frame_rgb.shape
                    qimage = QImage(
                        self.preview_frame_rgb.data, 
                        self.preview_width, 
                        self.preview_height, 
                        self.preview_width * 3, 
                        QImage.Format.Format_RGB888
                    )
                    self.original_pixmap = QPixmap.fromImage(qimage)
                    self.update_preview_overlay()
            except Exception as e:
                print(f"Lỗi khi đọc frame timeline: {e}")

    def on_crop_slider_changed(self):
        self.x_start_label.setText(f"{self.x_start_slider.value()}%")
        self.x_end_label.setText(f"{self.x_end_slider.value()}%")
        self.y_start_label.setText(f"{self.y_start_slider.value()}%")
        self.y_end_label.setText(f"{self.y_end_slider.value()}%")
        self.update_preview_overlay()

    def update_preview_overlay(self):
        if self.original_pixmap is None:
            return
        
        # Copy original pixmap
        pixmap = self.original_pixmap.copy()
        
        # Get coordinates
        x_start = self.x_start_slider.value()
        x_end = self.x_end_slider.value()
        y_start = self.y_start_slider.value()
        y_end = self.y_end_slider.value()
        
        # Keep inside bounds
        if x_start >= x_end:
            x_end = x_start + 1
        if y_start >= y_end:
            y_end = y_start + 1
            
        # Draw on the pixmap
        painter = QPainter(pixmap)
        
        # Convert percentages to actual pixel values
        px_x1 = int(x_start / 100.0 * self.preview_width)
        px_x2 = int(x_end / 100.0 * self.preview_width)
        px_y1 = int(y_start / 100.0 * self.preview_height)
        px_y2 = int(y_end / 100.0 * self.preview_height)
        
        # Draw dark mask overlay outside selection (top, bottom, left, right)
        mask_color = QColor(0, 0, 0, 160)
        # Top
        painter.fillRect(0, 0, self.preview_width, px_y1, mask_color)
        # Bottom
        painter.fillRect(0, px_y2, self.preview_width, self.preview_height - px_y2, mask_color)
        # Left
        painter.fillRect(0, px_y1, px_x1, px_y2 - px_y1, mask_color)
        # Right
        painter.fillRect(px_x2, px_y1, self.preview_width - px_x2, px_y2 - px_y1, mask_color)
        
        # Draw red border
        painter.setPen(QPen(QColor(239, 68, 68), 3, Qt.PenStyle.SolidLine))
        painter.drawRect(px_x1, px_y1, px_x2 - px_x1, px_y2 - px_y1)
        
        painter.end()
        
        # Scale to fit QLabel
        scaled_pixmap = pixmap.scaled(
            self.preview_label.width(), 
            self.preview_label.height(), 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        self.preview_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preview_overlay()

    def start_extraction(self):
        video_path = self.video_input.text().strip()
        srt_path = self.srt_input.text().strip()

        if not video_path or not os.path.exists(video_path):
            QMessageBox.warning(self, "Lỗi Tệp Tin", "Vui lòng chọn một video đầu vào hợp lệ!")
            return

        if not srt_path:
            QMessageBox.warning(self, "Lỗi Nơi Lưu", "Vui lòng chọn đường dẫn để lưu tệp SRT!")
            return

        # Prepare parameters
        device = self.device_combo.currentText()
        lang_name = self.lang_combo.currentText()
        ocr_langs = OCR_LANGUAGES[lang_name]
        scans_per_sec = self.scans_per_sec_spin.value()
        scan_interval = 1.0 / scans_per_sec
        min_confidence = 30  # Default internal value (30% to catch most texts)
        similarity_threshold = 60 # Allow minor OCR noise (60% similarity) to merge into same timeline
        
        x_start = self.x_start_slider.value()
        x_end = self.x_end_slider.value()
        y_start = self.y_start_slider.value()
        y_end = self.y_end_slider.value()
        
        filter_text = self.filter_input.text().strip()
        filter_keywords = [k.strip() for k in filter_text.split(",") if len(k.strip()) >= 2]
        
        # Save configurations
        self.config["video_input"] = video_path
        self.config["srt_input"] = srt_path
        self.config["ocr_lang_name"] = lang_name
        self.config["device"] = device
        self.config["scans_per_sec"] = scans_per_sec
        self.config["crop_x_start"] = x_start
        self.config["crop_x_end"] = x_end
        self.config["crop_y_start"] = y_start
        self.config["crop_y_end"] = y_end
        self.config["filter_keywords"] = filter_text
        self.config["last_dir"] = os.path.dirname(video_path)
        save_config(self.config)

        # Reset UI
        self.log_output.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("Đang trích xuất OCR...")

        # Disable inputs
        self.toggle_inputs(False)

        # Run worker
        self.worker = TranscriptionWorker(
            video_path=video_path,
            srt_path=srt_path,
            device=device,
            ocr_langs=ocr_langs,
            scan_interval=scan_interval,
            min_confidence=min_confidence,
            similarity_threshold=similarity_threshold,
            crop_region=(x_start, x_end, y_start, y_end),
            filter_keywords=filter_keywords
        )
        self.worker.progress_updated.connect(self.on_progress)
        self.worker.finished.connect(self.on_success)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def stop_extraction(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
            self.log_output.append("\n--- Đã dừng tiến trình bởi người dùng ---")
            self.status_label.setText("Đã hủy")
            self.progress_bar.setValue(0)
            self.toggle_inputs(True)
            self.worker = None

    def on_progress(self, val, message):
        self.progress_bar.setValue(val)
        if message:
            self.log_output.append(message)
            self.log_output.ensureCursorVisible()

    def on_success(self, srt_path):
        self.status_label.setText("Hoàn thành")
        QMessageBox.information(
            self, 
            "Thành Công", 
            f"Trích xuất phụ đề hoàn tất!\nTệp đã được lưu tại:\n{srt_path}"
        )
        self.toggle_inputs(True)
        self.worker = None

    def on_error(self, error_msg):
        self.status_label.setText("Gặp lỗi")
        self.log_output.append(f"\n[LỖI]: {error_msg}")
        QMessageBox.critical(
            self, 
            "Gặp Lỗi", 
            f"Đã xảy ra lỗi trong quá trình trích xuất phụ đề:\n{error_msg}"
        )
        self.toggle_inputs(True)
        self.worker = None

    def toggle_inputs(self, enabled):
        self.start_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(not enabled)
        
        self.video_input.setEnabled(enabled)
        self.srt_input.setEnabled(enabled)
        self.lang_combo.setEnabled(enabled)
        self.device_combo.setEnabled(enabled)
        self.scans_per_sec_spin.setEnabled(enabled)
        self.timeline_slider.setEnabled(enabled)
        self.filter_input.setEnabled(enabled)
        self.sample_filter_btn.setEnabled(enabled)
        
        self.x_start_slider.setEnabled(enabled)
        self.x_end_slider.setEnabled(enabled)
        self.y_start_slider.setEnabled(enabled)
        self.y_end_slider.setEnabled(enabled)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(1000)
        # Force kill python process to release GPU
        os._exit(0)

    def open_output_folder(self):
        path = self.srt_input.text().strip()
        if path:
            folder = os.path.dirname(os.path.abspath(path))
            if os.path.exists(folder):
                os.startfile(folder)
            else:
                QMessageBox.warning(self, "Không tìm thấy", f"Thư mục không tồn tại: {folder}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = OcrExtractorApp()
    window.show()
    sys.exit(app.exec())
