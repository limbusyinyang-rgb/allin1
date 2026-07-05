import sys
import os
import json
import time
import re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QFormLayout, QPushButton, QLabel, QLineEdit, QFileDialog, 
    QComboBox, QProgressBar, QTextEdit, QMessageBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QMenu
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QColor, QAction

# Import pysrt
try:
    import pysrt
except ImportError:
    pysrt = None

# Default settings file path
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# Model mappings matching the user's Gemini model image
MODELS = {
    "3.1 Flash-Lite": "gemini-2.0-flash-lite",
    "3.5 Flash": "gemini-2.5-flash",
    "3.1 Pro": "gemini-2.0-pro-exp-02-05"
}

def load_config():
    """Load cached configuration like API Key, Glossary, etc."""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
    return {}

def save_config(config):
    """Cache configuration locally"""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

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

def is_vietnamese(text: str) -> bool:
    """Check if the text already contains Vietnamese accented characters"""
    if not text:
        return False
    # Regex matching common Vietnamese characters with accent marks
    vietnamese_pattern = re.compile(
        r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]',
        re.UNICODE
    )
    return bool(vietnamese_pattern.search(text))

def load_srt(filepath):
    """Load SRT file, testing multiple encodings for robustness"""
    if pysrt is None:
        raise ImportError("Thư viện `pysrt` chưa được cài đặt. Vui lòng chạy lệnh: pip install pysrt")
    
    encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'latin-1', 'cp1252', 'gbk', 'utf-32']
    for enc in encodings:
        try:
            return pysrt.open(filepath, encoding=enc), enc
        except Exception:
            continue
    # Fallback to default loading if all fails
    return pysrt.open(filepath), 'utf-8'


class GlossaryWorker(QThread):
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, api_key, model_name, srt_path):
        super().__init__()
        self.api_key = api_key
        self.model_name = model_name
        self.srt_path = srt_path

    def run(self):
        try:
            from google import genai
            client = genai.Client(
                api_key=self.api_key,
                http_options={'base_url': 'https://api.shopaikey.com'}
            )
            
            # Read first 150 non-empty subtitle lines from SRT for analysis
            subs, enc = load_srt(self.srt_path)
            sample_lines = []
            for sub in subs:
                text = sub.text.strip() if sub.text else ""
                if text and not is_vietnamese(text):
                    sample_lines.append(text)
                if len(sample_lines) >= 150:
                    break
            
            if not sample_lines:
                self.finished.emit("{}")
                return

            sample_text = "\n".join(sample_lines)
            
            prompt = f"""Đọc văn bản phụ đề mẫu sau đây. Trích xuất các danh từ riêng, tên nhân vật, địa danh hoặc các thuật ngữ cốt lõi cần bản dịch nhất quán.
Dịch các từ đó sang tiếng Việt phù hợp.
Trả về duy nhất một đối tượng JSON với các cặp key=value dạng:
{{
  "tên_gốc": "tên_dịch"
}}
Không thêm bất kỳ giải thích nào khác ngoài JSON.

Văn bản phụ đề mẫu:
{sample_text}
"""
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            self.finished.emit(response.text.strip())
        except Exception as e:
            self.error_occurred.emit(str(e))


class StoryMemoryWorker(QThread):
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, api_key, model_name, srt_path):
        super().__init__()
        self.api_key = api_key
        self.model_name = model_name
        self.srt_path = srt_path

    def run(self):
        try:
            from google import genai
            client = genai.Client(
                api_key=self.api_key,
                http_options={'base_url': 'https://api.shopaikey.com'}
            )
            
            subs, enc = load_srt(self.srt_path)
            # Take up to 2000 non-empty lines to fit safely within token context
            sample_lines = []
            for sub in subs:
                text = sub.text.strip() if sub.text else ""
                if text and not is_vietnamese(text):
                    sample_lines.append(text)
                if len(sample_lines) >= 2000:
                    break
            
            if not sample_lines:
                self.finished.emit("{}")
                return

            sample_text = "\n".join(sample_lines)
            
            prompt = f"""Đọc văn bản phụ đề sau và trích xuất cấu trúc câu chuyện.
Trả về duy nhất 1 JSON có định dạng sau:
{{
  "characters": [
    {{"name": "tên_gốc", "gender": "giới_tính", "vn_name": "tên_việt", "pronoun": "cách_xưng_hô"}}
  ],
  "relationships": "tóm tắt quan hệ",
  "genre": "thể loại truyện",
  "rules": "các quy tắc dịch đặc biệt (nếu có)"
}}
Tuyệt đối không giải thích thêm. Bắt buộc kết quả phải là mã JSON hợp lệ.
Văn bản:
{sample_text}
"""
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={"response_mime_type": "application/json", "temperature": 0.2}
            )
            self.finished.emit(response.text.strip())
        except Exception as e:
            self.error_occurred.emit(str(e))


class TranslationWorker(QThread):
    progress_updated = pyqtSignal(int, str)      # percentage, log_message
    row_translated = pyqtSignal(int, str)        # table_row_index, translated_text
    report_updated = pyqtSignal(int, int, int)   # translated, untranslated, empty
    finished = pyqtSignal(str)                   # output_file_path
    error_occurred = pyqtSignal(str)              # error_message

    def __init__(self, api_key, model_name, records, input_path, output_path, genre, glossary, batch_size, context_lines, temperature):
        super().__init__()
        self.api_key = api_key
        self.model_name = model_name
        self.records = records  # List of subtitle row dictionaries
        self.input_path = input_path
        self.output_path = output_path
        self.genre = genre
        self.glossary = glossary
        self.batch_size = batch_size
        self.context_lines = context_lines
        self.temperature = temperature
        self.is_running = True

    def run(self):
        try:
            # 1. Configure Gemini API
            self.progress_updated.emit(1, "Đang kết nối Google Gemini API...")
            from google import genai
            from google.genai import types
            client = genai.Client(
                api_key=self.api_key,
                http_options={'base_url': 'https://api.shopaikey.com'}
            )

            total_lines = len(self.records)

            # Analyze counts
            empty_count = 0
            untranslated_count = 0
            translated_count = 0

            for r in self.records:
                if r["is_empty"]:
                    empty_count += 1
                elif r["trans"] is not None and r["trans"] != "Chưa dịch..." and r["trans"] != "[LỖI DỊCH]":
                    translated_count += 1
                else:
                    untranslated_count += 1

            # 2. Setup Contexts and Memory
            glossary_str = ""
            if self.glossary:
                glossary_str = "\n".join([f"- '{k}' dịch thành '{v}'" for k, v in self.glossary.items()])
            else:
                glossary_str = "(Không có từ điển)"

            srt_dir = os.path.dirname(self.input_path)
            
            # Load Story Memory
            story_memory = {}
            memory_path = os.path.join(srt_dir, "story_memory.json")
            if os.path.exists(memory_path):
                try:
                    with open(memory_path, "r", encoding="utf-8") as f:
                        story_memory = json.load(f)
                except Exception:
                    pass
                    
            # Load Chapter Summary
            chapter_summary_path = os.path.join(srt_dir, "chapter_summary.json")
            chapter_summary = ""
            if os.path.exists(chapter_summary_path):
                try:
                    with open(chapter_summary_path, "r", encoding="utf-8") as f:
                        chapter_summary = json.load(f).get("summary", "")
                except Exception:
                    pass

            # Filter records that need translation
            to_translate = [r for r in self.records if r["needs_translation"]]
            
            # 3. Process in batches
            total_batches = (len(to_translate) + self.batch_size - 1) // self.batch_size
            batch_idx = 0
            
            lines_translated_since_summary = 0
            recent_translated_texts = []

            while batch_idx < total_batches and self.is_running:
                start_offset = batch_idx * self.batch_size
                end_offset = min(start_offset + self.batch_size, len(to_translate))
                batch_records = to_translate[start_offset:end_offset]
                
                # Context sliding window
                first_record_idx = batch_records[0]["index"]
                context_idx_start = max(0, first_record_idx - self.context_lines)
                context_records = []
                for i in range(context_idx_start, first_record_idx):
                    r = self.records[i]
                    if r["is_empty"]:
                        continue
                    txt = r["trans"] if r["trans"] and r["trans"] not in ["Chưa dịch...", "[LỖI DỊCH]"] else r["orig"]
                    context_records.append({"id": r["id"], "text": txt})

                context_json_str = json.dumps(context_records, ensure_ascii=False) if context_records else "[]"

                # Format input JSON
                translate_json = [{"id": r["id"], "src": r["orig"]} for r in batch_records]
                translate_json_str = json.dumps(translate_json, ensure_ascii=False)
                
                # Token optimization: Inject only active characters
                active_chars = []
                batch_text_concat = " ".join([r["orig"] for r in batch_records])
                if "characters" in story_memory:
                    for char in story_memory["characters"]:
                        # check if original name appears in batch string
                        if char.get("name") in batch_text_concat:
                            active_chars.append(char)
                
                story_context_str = ""
                if active_chars:
                    story_context_str += "Nhân vật xuất hiện trong đoạn này:\n" + json.dumps(active_chars, ensure_ascii=False) + "\n"
                if "relationships" in story_memory:
                    story_context_str += f"Quan hệ: {story_memory['relationships']}\n"
                if "rules" in story_memory:
                    story_context_str += f"Quy tắc dịch: {story_memory['rules']}\n"

                self.progress_updated.emit(
                    int(3 + (batch_idx / total_batches) * 92),
                    f"Đang dịch nhóm {batch_idx + 1}/{total_batches} (Dòng {batch_records[0]['id']} đến {batch_records[-1]['id']})..."
                )

                prompt = f"""Bạn là dịch giả chuyên nghiệp chuyên dịch tiểu thuyết và hoạt hình Trung Quốc.

QUY TẮC:
- Không thêm nội dung.
- Không bỏ dòng.
- Giữ nguyên số lượng dòng.
- Không xuất timeline.
- Không đánh số.
- Không thêm giải thích.
- Không thay đổi tên nhân vật trong story_memory.
- Nếu thiếu thông tin, ưu tiên cách dịch trước đó.
- Không tự suy diễn.
- Chỉ xuất lời thoại.
- Toàn bộ kết quả phải nằm trong một code block duy nhất là JSON list dạng: [{{"id": int, "tgt": "str"}}]

Genre: {self.genre}
{story_context_str}

Chapter Summary (Bối cảnh truyện gần đây):
{chapter_summary if chapter_summary else "N/A"}

Glossary:
{glossary_str}

Context (Tham khảo bối cảnh các câu trước đó, KHÔNG DỊCH PHẦN NÀY):
{context_json_str}

Translate (BẮT BUỘC dịch phần này, trả về JSON list):
{translate_json_str}
"""
                # Request with retries
                retries = 3
                success = False
                translated_batch = {}

                while retries > 0 and not success and self.is_running:
                    try:
                        response = client.models.generate_content(
                            model=self.model_name,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                temperature=self.temperature
                            )
                        )
                        response_text = response.text.strip()
                        
                        # Parse JSON
                        data = json.loads(response_text)
                        
                        if isinstance(data, list):
                            is_hallucinated = False
                            for item in data:
                                if "id" in item and "tgt" in item:
                                    tgt = item["tgt"]
                                    translated_batch[int(item["id"])] = tgt
                                    # Anti-hallucination check
                                    if re.search(r'\d{2}:\d{2}:\d{2}', tgt) or tgt.startswith("Chú thích") or tgt.startswith("Giải thích"):
                                        is_hallucinated = True
                            
                            missing_ids = [r["id"] for r in batch_records if r["id"] not in translated_batch]
                            
                            if not missing_ids and len(data) == len(batch_records) and not is_hallucinated:
                                success = True
                            else:
                                msg = f"Lỗi Ảo Giác hoặc Sai số lượng (Thiếu: {len(missing_ids)}, Thừa: {len(data) - len(batch_records)})."
                                self.progress_updated.emit(
                                    int(3 + (batch_idx / total_batches) * 92),
                                    f"[CẢNH BÁO]: {msg}. Đang thử lại (còn {retries-1} lần)..."
                                )
                                retries -= 1
                                time.sleep(2)
                        else:
                            retries -= 1
                            time.sleep(2)

                    except Exception as e:
                        retries -= 1
                        self.progress_updated.emit(
                            int(3 + (batch_idx / total_batches) * 92),
                            f"Lỗi API hoặc JSON: {e}. Thử lại (Còn {retries} lượt)..."
                        )
                        time.sleep(2)

                if not self.is_running:
                    return

                if not success:
                    # Fallback if all retries fail
                    self.progress_updated.emit(
                        int(3 + (batch_idx / total_batches) * 92),
                        f"LỖI: Không thể dịch nhóm dòng từ {batch_records[0]['id']} đến {batch_records[-1]['id']}."
                    )
                    for r in batch_records:
                        r["trans"] = "[LỖI DỊCH]"
                        self.row_translated.emit(r["index"], "[LỖI DỊCH]")
                else:
                    # Update local records and UI table rows
                    for r in batch_records:
                        val = translated_batch.get(r["id"], "[LỖI DỊCH]")
                        r["trans"] = val
                        self.row_translated.emit(r["index"], val)
                        translated_count += 1
                        untranslated_count -= 1
                        
                        recent_translated_texts.append(val)
                        lines_translated_since_summary += 1

                # Update count reports
                self.report_updated.emit(translated_count, untranslated_count, empty_count)
                
                # Auto-save translation state to disk after each batch to prevent data loss on cancel
                self.save_temp_srt()
                
                # Auto chapter summary generation (every 500 lines)
                if lines_translated_since_summary >= 500:
                    try:
                        self.progress_updated.emit(
                            int(3 + (batch_idx / total_batches) * 92),
                            "Đang cập nhật tóm tắt cốt truyện (Chapter Summary)..."
                        )
                        sum_prompt = f"Tóm tắt cũ:\n{chapter_summary}\n\nNội dung mới dịch:\n{' '.join(recent_translated_texts)}\n\nHãy hợp nhất và viết một tóm tắt ngắn gọn nhất về diễn biến hiện tại. Trả về JSON: {{\"summary\": \"...\"}}"
                        sum_response = client.models.generate_content(
                            model=self.model_name,
                            contents=sum_prompt,
                            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2)
                        )
                        sum_data = json.loads(sum_response.text.strip())
                        chapter_summary = sum_data.get("summary", "")
                        with open(chapter_summary_path, "w", encoding="utf-8") as f:
                            json.dump({"summary": chapter_summary}, f, ensure_ascii=False)
                    except Exception as e:
                        print("Lỗi tạo summary:", e)
                    
                    lines_translated_since_summary = 0
                    recent_translated_texts = []
                
                batch_idx += 1
                # Anti rate-limiting delay
                time.sleep(0.5)

            if not self.is_running:
                return

            self.progress_updated.emit(98, "Đang hoàn tất tệp phụ đề mới...")
            self.save_temp_srt()
            
            self.progress_updated.emit(100, f"Đã hoàn thành! Tệp lưu tại: {self.output_path}")
            self.finished.emit(self.output_path)

        except Exception as e:
            self.error_occurred.emit(str(e))

    def save_temp_srt(self):
        """Save current translated state to the output file on disk"""
        try:
            subs, encoding = load_srt(self.input_path)
            for r in self.records:
                idx = r["index"]
                trans_val = r["trans"]
                # Save actual translation if it exists, otherwise write original to keep structure
                if trans_val is not None and trans_val != "Chưa dịch..." and trans_val != "[LỖI DỊCH]":
                    subs[idx].text = trans_val
                else:
                    subs[idx].text = r["orig"]
            subs.save(self.output_path, encoding=encoding)
        except Exception as e:
            print(f"Error saving temp progress srt: {e}")

    def stop(self):
        self.is_running = False


class SRTTranslatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gemini SRT Subtitle Translator - Dịch Phụ Đề")
        self.resize(1000, 700)
        self.worker = None
        self.glossary_worker = None
        self.story_memory_worker = None
        
        # Load configs
        self.config = load_config()

        # Build UI
        self.setup_ui()
        self.apply_styles()
        self.load_cached_settings()

    def setup_ui(self):
        # Central widget and horizontal splitter for side-by-side design
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Header Title
        header_label = QLabel("GEMINI SRT TRANSLATOR")
        header_label.setObjectName("HeaderLabel")
        desc_label = QLabel("Dịch phụ đề tự động sang tiếng Việt chất lượng cao bằng AI Gemini (Hỗ trợ Glossary & Ghi chú cốt truyện)")
        desc_label.setObjectName("DescLabel")
        
        main_layout.addWidget(header_label)
        main_layout.addWidget(desc_label)

        # Main splitter (Left: Control Panel, Right: Subtitle Table)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left Panel (Controls)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        # 1. API Credentials Group
        api_group = QGroupBox("Cấu Hình Gemini API")
        api_form = QFormLayout(api_group)
        api_form.setSpacing(8)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Nhập Google Gemini API Key...")
        
        self.model_combo = QComboBox()
        self.model_combo.addItems(["3.1 Flash-Lite", "3.5 Flash", "3.1 Pro"])
        self.model_combo.setCurrentText("3.5 Flash")

        api_form.addRow("API Key:", self.api_key_input)
        api_form.addRow("Mô Hình (Model):", self.model_combo)
        left_layout.addWidget(api_group)

        # 2. File Selection Group
        file_group = QGroupBox("Tệp Tin Phụ Đề")
        file_form = QFormLayout(file_group)
        file_form.setSpacing(8)

        # Input File
        self.srt_input = QLineEdit()
        self.srt_input.setPlaceholderText("Chọn tệp SRT gốc cần dịch...")
        self.srt_input.textChanged.connect(self.load_srt_to_table)
        srt_in_btn = QPushButton("Chọn Tệp")
        srt_in_btn.clicked.connect(self.select_input_srt)

        srt_in_row = QHBoxLayout()
        srt_in_row.addWidget(self.srt_input)
        srt_in_row.addWidget(srt_in_btn)

        # Output File
        self.srt_output = QLineEdit()
        self.srt_output.setPlaceholderText("Đường dẫn để lưu tệp phụ đề đã dịch...")
        
        from PyQt6.QtWidgets import QStyle
        open_folder_btn = QPushButton()
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        open_folder_btn.setIcon(icon)
        open_folder_btn.setToolTip("Mở thư mục lưu")
        open_folder_btn.setFixedWidth(36)
        open_folder_btn.clicked.connect(self.open_output_folder)

        srt_out_btn = QPushButton("Nơi Lưu")
        srt_out_btn.clicked.connect(self.select_output_srt)

        srt_out_row = QHBoxLayout()
        srt_out_row.addWidget(self.srt_output)
        srt_out_row.addWidget(open_folder_btn)
        srt_out_row.addWidget(srt_out_btn)

        file_form.addRow("SRT Gốc:", srt_in_row)
        file_form.addRow("SRT Dịch:", srt_out_row)
        left_layout.addWidget(file_group)

        # 3. Translation Settings Group
        trans_group = QGroupBox("Tham Số Dịch")
        trans_form = QFormLayout(trans_group)
        trans_form.setSpacing(8)

        # Genre field - Comma-separated user input
        self.genre_combo = QLineEdit()
        self.genre_combo.setPlaceholderText("Thể loại, cách nhau bằng dấu phẩy (Ví dụ: Anime, Học đường, Hài hước)")

        from PyQt6.QtWidgets import QSpinBox, QDoubleSpinBox
        
        # Context and Batch Selection
        batch_layout = QHBoxLayout()
        batch_layout.setContentsMargins(0, 0, 0, 0)
        
        self.context_lines_spin = QSpinBox()
        self.context_lines_spin.setRange(0, 100)
        self.context_lines_spin.setValue(20)
        
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(5, 200)
        self.batch_size_spin.setValue(20)
        
        batch_layout.addWidget(QLabel("Ngữ cảnh:"))
        batch_layout.addWidget(self.context_lines_spin)
        batch_layout.addWidget(QLabel("Dịch:"))
        batch_layout.addWidget(self.batch_size_spin)
        batch_layout.addStretch()

        # Temperature
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.temp_spin.setRange(0.0, 1.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(0.1)

        # Glossary with Analysis button
        glossary_container = QWidget()
        glossary_vbox = QVBoxLayout(glossary_container)
        glossary_vbox.setContentsMargins(0, 0, 0, 0)
        glossary_vbox.setSpacing(5)

        self.glossary_input = QTextEdit()
        self.glossary_input.setPlaceholderText("Từ điển thuật ngữ (Gốc=Dịch), ví dụ:\nIron Man=Người Sắt\nCap=Đại úy")
        self.glossary_input.setMaximumHeight(80)

        glossary_btn_row = QHBoxLayout()
        self.glossary_btn = QPushButton("Phân tích Glossary")
        self.glossary_btn.clicked.connect(self.analyze_glossary)
        self.story_memory_btn = QPushButton("Phân tích Truyện")
        self.story_memory_btn.clicked.connect(self.analyze_story_memory)
        
        glossary_btn_row.addWidget(self.glossary_btn)
        glossary_btn_row.addWidget(self.story_memory_btn)
        glossary_btn_row.addStretch()

        glossary_vbox.addWidget(self.glossary_input)
        glossary_vbox.addLayout(glossary_btn_row)

        # Update Glossary button
        self.update_config_btn = QPushButton("Cập nhật Glossary")
        self.update_config_btn.setObjectName("UpdateConfigBtn")
        self.update_config_btn.clicked.connect(self.update_glossary_and_notes)

        trans_form.addRow("Thể Loại Phim:", self.genre_combo)
        trans_form.addRow("Cấu Hình (Dòng):", batch_layout)
        trans_form.addRow("Temperature:", self.temp_spin)
        trans_form.addRow("Glossary (Từ Điển):", glossary_container)
        trans_form.addRow("", self.update_config_btn)
        
        left_layout.addWidget(trans_group)

        # Control Buttons
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Bắt Đầu Dịch")
        self.start_btn.setObjectName("StartBtn")
        self.start_btn.clicked.connect(lambda: self.start_translation())

        self.stop_btn = QPushButton("Hủy Dịch")
        self.stop_btn.setObjectName("StopBtn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_translation)

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        left_layout.addLayout(btn_layout)
        left_layout.addStretch()

        # Right Panel (Subtitle Table)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # Subtitle Table View (3 Columns: Removed index column)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Thời Gian", "Bản Gốc", "Bản Dịch"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        # Support ExtendedSelection (Ctrl, Shift, Ctrl + A)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Custom Context Menu Policy
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        # Connect Item edit changes to save to output SRT
        self.table.itemChanged.connect(self.on_item_changed)

        right_layout.addWidget(self.table)

        # Splitter attachments
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([380, 620])
        main_layout.addWidget(splitter)

        # 4. Status Bar and Counters Reports
        reports_layout = QHBoxLayout()
        reports_layout.setSpacing(20)

        self.total_label = QLabel("0")
        self.empty_label = QLabel("0")
        self.untrans_label = QLabel("0")
        self.trans_label = QLabel("0")

        self.total_label.setObjectName("CounterText")
        self.empty_label.setObjectName("CounterText")
        self.untrans_label.setObjectName("CounterText")
        self.trans_label.setObjectName("CounterTextGreen")

        reports_layout.addWidget(QLabel("Tổng số dòng: "))
        reports_layout.addWidget(self.total_label)
        reports_layout.addWidget(QLabel(" | Dòng trống: "))
        reports_layout.addWidget(self.empty_label)
        reports_layout.addWidget(QLabel(" | Chưa dịch: "))
        reports_layout.addWidget(self.untrans_label)
        reports_layout.addWidget(QLabel(" | Đã dịch: "))
        reports_layout.addWidget(self.trans_label)
        reports_layout.addStretch()

        main_layout.addLayout(reports_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        # Progress log
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Nhật ký chi tiết các cuộc gọi API và phân đoạn dịch...")
        self.log_output.setMaximumHeight(120)
        main_layout.addWidget(self.log_output)

        # Footer Status Label
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
                margin-top: 5px;
                padding-top: 10px;
                font-weight: bold;
                color: #3b82f6; /* Accent color: Blue */
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
                padding: 6px 10px;
                color: #f7fafc;
                selection-background-color: #3b82f6;
            }
            
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
            
            QPushButton {
                background-color: #1f2937;
                color: #f7fafc;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 500;
            }
            
            QPushButton:hover {
                background-color: #374151;
                border-color: #4b5563;
            }
            
            #StartBtn {
                background-color: #10b981; /* Emerald accent */
                color: #ffffff;
                border: none;
                font-size: 13px;
                font-weight: bold;
                padding: 10px;
            }
            
            #StartBtn:hover {
                background-color: #059669;
            }
            
            #StartBtn:pressed {
                background-color: #047857;
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
                padding: 10px;
            }
            
            #StopBtn:hover {
                background-color: #dc2626;
            }
            
            #StopBtn:disabled {
                background-color: #2d3748;
                color: #718096;
            }
            
            #UpdateConfigBtn {
                background-color: #4b5563;
                border: none;
                font-weight: bold;
                padding: 6px;
                color: #ffffff;
            }
            #UpdateConfigBtn:hover {
                background-color: #374151;
            }
            
            QComboBox {
                background-color: #1a1a1e;
                border: 1px solid #2d3748;
                border-radius: 6px;
                padding: 5px 10px;
                color: #f7fafc;
            }
            
            QComboBox QAbstractItemView {
                background-color: #1a1a1e;
                border: 1px solid #2d3748;
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
                outline: 0px;
            }
            
            QTableWidget {
                background-color: #1a1a1e;
                border: 1px solid #2d3748;
                gridline-color: #2d3748;
                border-radius: 6px;
                color: #e2e8f0;
            }
            
            QHeaderView::section {
                background-color: #2d3748;
                color: #e2e8f0;
                padding: 6px;
                border: 1px solid #1a1a1e;
                font-weight: bold;
            }
            
            QProgressBar {
                border: 1px solid #2d3748;
                border-radius: 6px;
                text-align: center;
                background-color: #1a1a1e;
                color: #ffffff;
                font-weight: bold;
                height: 18px;
            }
            
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #10b981);
                border-radius: 5px;
            }
            
            QTextEdit {
                background-color: #1a1a1e;
                border: 1px solid #2d3748;
                border-radius: 6px;
                padding: 8px;
                color: #e2e8f0;
            }
            
            #CounterText {
                font-weight: bold;
                color: #f7fafc;
            }
            
            #CounterTextGreen {
                font-weight: bold;
                color: #10b981;
            }
            
            #StatusLabel {
                color: #718096;
                font-size: 11px;
            }
            
            QMenu {
                background-color: #1a1a1e;
                border: 1px solid #2d3748;
                color: #e2e8f0;
            }
            QMenu::item {
                padding: 6px 20px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #3b82f6;
                color: #ffffff;
            }
        """)

    def load_cached_settings(self):
        """Pre-populate configurations from the config cache"""
        self.api_key_input.setText(self.config.get("api_key", ""))
        self.model_combo.setCurrentText(self.config.get("model", "3.5 Flash"))
        self.genre_combo.setText(self.config.get("genre", ""))
        self.context_lines_spin.setValue(int(self.config.get("context_lines", 20)))
        self.batch_size_spin.setValue(int(self.config.get("batch_size", 20)))
        self.temp_spin.setValue(float(self.config.get("temperature", 0.1)))
        self.glossary_input.setText(self.config.get("glossary_text", ""))
        
        # Load remembered SRT files
        cached_srt = self.config.get("srt_input", "")
        if cached_srt and os.path.exists(cached_srt):
            self.srt_input.setText(cached_srt)
            self.srt_output.setText(self.config.get("srt_output", ""))

    def select_input_srt(self):
        initial_dir = self.config.get("last_dir", "")
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Chọn Tệp Phụ Đề SRT Cần Dịch", 
            initial_dir, 
            "Subtitle Files (*.srt);;All Files (*)"
        )
        if file_path:
            self.srt_input.setText(file_path)
            # Suggest output name
            base, ext = os.path.splitext(file_path)
            self.srt_output.setText(base + "_VI" + ext)
            self.config["srt_input"] = file_path
            self.config["srt_output"] = base + "_VI" + ext
            self.config["last_dir"] = os.path.dirname(file_path)
            save_config(self.config)

    def select_output_srt(self):
        initial_dir = self.config.get("last_dir", "")
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Chọn Nơi Lưu SRT Đã Dịch", 
            self.srt_output.text() or initial_dir, 
            "Subtitle Files (*.srt);;All Files (*)"
        )
        if file_path:
            self.srt_output.setText(file_path)
            self.config["srt_output"] = file_path
            self.config["last_dir"] = os.path.dirname(file_path)
            save_config(self.config)

    def load_srt_to_table(self, file_path):
        """Immediately parse selected SRT file and populate the visual QTableWidget. Load existing translated files for state recovery."""
        if not file_path or not os.path.exists(file_path):
            self.table.setRowCount(0)
            self.total_label.setText("0")
            self.empty_label.setText("0")
            self.untrans_label.setText("0")
            self.trans_label.setText("0")
            return

        try:
            subs, enc = load_srt(file_path)
            
            # Check if output file already exists (to continue previous progress)
            output_path = self.srt_output.text().strip()
            out_subs = None
            if output_path and os.path.exists(output_path):
                try:
                    out_subs, _ = load_srt(output_path)
                except Exception:
                    pass

            self.table.setRowCount(0)
            self.table.setRowCount(len(subs))
            
            empty_count = 0
            untranslated_count = 0
            translated_count = 0

            # Block signals so loading items does not trigger itemChanged auto-save
            self.table.blockSignals(True)

            for i, sub in enumerate(subs):
                # Column 0: Timestamps
                time_str = ""
                if sub.start and sub.end:
                    time_str = f"{format_srt_timestamp(sub.start.ordinal/1000.0)}\n--> {format_srt_timestamp(sub.end.ordinal/1000.0)}"
                item_time = QTableWidgetItem(time_str)
                item_time.setFlags(item_time.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, 0, item_time)

                # Column 1: Original Text
                item_orig = QTableWidgetItem(sub.text)
                item_orig.setFlags(item_orig.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i, 1, item_orig)

                # Column 2: Translation Status (Editable)
                text_clean = sub.text.strip() if sub.text else ""
                if not text_clean:
                    item_trans = QTableWidgetItem("")
                    item_trans.setFlags(item_trans.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    empty_count += 1
                else:
                    existing_trans = ""
                    if out_subs and i < len(out_subs):
                        existing_trans = out_subs[i].text.strip() if out_subs[i].text else ""

                    if existing_trans and existing_trans != "Chưa dịch..." and existing_trans != "[LỖI DỊCH]":
                        item_trans = QTableWidgetItem(existing_trans)
                        item_trans.setForeground(QColor("#10b981"))
                        translated_count += 1
                    elif is_vietnamese(text_clean):
                        # Detect Vietnamese language and skip it to save API costs
                        item_trans = QTableWidgetItem(sub.text)
                        item_trans.setForeground(QColor("#10b981"))
                        translated_count += 1
                    else:
                        item_trans = QTableWidgetItem("Chưa dịch...")
                        item_trans.setForeground(QColor("#718096"))
                        untranslated_count += 1
                
                self.table.setItem(i, 2, item_trans)

            self.table.blockSignals(False)

            self.total_label.setText(str(len(subs)))
            self.empty_label.setText(str(empty_count))
            self.untrans_label.setText(str(untranslated_count))
            self.trans_label.setText(str(translated_count))

        except Exception as e:
            QMessageBox.critical(self, "Lỗi Đọc SRT", f"Không thể phân tích tệp SRT:\n{str(e)}")

    def update_glossary_and_notes(self):
        """Cache user dictionary overrides"""
        self.config["api_key"] = self.api_key_input.text().strip()
        self.config["model"] = self.model_combo.currentText().strip()
        self.config["genre"] = self.genre_combo.text().strip()
        self.config["context_lines"] = self.context_lines_spin.value()
        self.config["batch_size"] = self.batch_size_spin.value()
        self.config["temperature"] = self.temp_spin.value()
        self.config["glossary_text"] = self.glossary_input.toPlainText()
        save_config(self.config)
        self.log_output.append("Đã cập nhật Glossary và cấu hình.")
        QMessageBox.information(self, "Thành Công", "Đã cập nhật cấu hình Glossary!")

    def parse_glossary(self):
        """Parse key=value mappings from the Glossary text area"""
        glossary = {}
        text = self.glossary_input.toPlainText()
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                glossary[k.strip()] = v.strip()
        return glossary

    def update_glossary_and_notes(self):
        """Instantly save Glossary and options to config cache"""
        self.config["api_key"] = self.api_key_input.text().strip()
        self.config["model"] = self.model_combo.currentText().strip()
        self.config["genre"] = self.genre_combo.text().strip()
        self.config["batch_size"] = self.batch_combo.currentText()
        self.config["glossary_text"] = self.glossary_input.toPlainText()
        save_config(self.config)
        self.log_output.append("Đã cập nhật Glossary và cấu hình.")
        QMessageBox.information(self, "Thành Công", "Đã cập nhật cấu hình Glossary!")

    def analyze_glossary(self):
        """Trigger background analysis of input SRT to extract glossary terms using Gemini"""
        api_key = self.api_key_input.text().strip()
        srt_path = self.srt_input.text().strip()

        if not api_key:
            QMessageBox.warning(self, "Gặp Lỗi", "Vui lòng cung cấp Gemini API Key!")
            return
        if not srt_path or not os.path.exists(srt_path):
            QMessageBox.warning(self, "Gặp Lỗi", "Vui lòng chọn tệp tin SRT đầu vào!")
            return

        model_display = self.model_combo.currentText().strip()
        model_name = MODELS.get(model_display, "gemini-2.5-flash")

        self.glossary_btn.setText("Đang phân tích...")
        self.glossary_btn.setEnabled(False)
        self.log_output.append("Đang phân tích các nhân vật và thuật ngữ chính trong tệp SRT...")

        self.glossary_worker = GlossaryWorker(api_key, model_name, srt_path)
        self.glossary_worker.finished.connect(self.on_glossary_success)
        self.glossary_worker.error_occurred.connect(self.on_glossary_error)
        self.glossary_worker.start()

    def on_glossary_success(self, json_str):
        try:
            data = json.loads(json_str)
            existing_text = self.glossary_input.toPlainText().strip()
            
            new_lines = []
            for k, v in data.items():
                new_lines.append(f"{k}={v}")
            
            if existing_text:
                merged = existing_text + "\n" + "\n".join(new_lines)
            else:
                merged = "\n".join(new_lines)
            
            self.glossary_input.setText(merged)
            self.log_output.append("Phân tích Glossary hoàn tất và đã thêm thuật ngữ mới.")
        except Exception as e:
            self.log_output.append(f"Không thể giải mã kết quả Glossary: {e}")
        finally:
            self.glossary_btn.setText("Phân tích Glossary")
            self.glossary_btn.setEnabled(True)
            self.glossary_worker = None

    def on_glossary_error(self, err):
        self.log_output.append(f"Lỗi phân tích Glossary: {err}")
        QMessageBox.critical(self, "Gặp Lỗi", f"Không thể tự động phân tích Glossary:\n{err}")
        self.glossary_btn.setText("Phân tích Glossary")
        self.glossary_btn.setEnabled(True)
        self.glossary_worker = None

    def analyze_story_memory(self):
        api_key = self.api_key_input.text().strip()
        srt_path = self.srt_input.text().strip()
        
        if not api_key:
            QMessageBox.warning(self, "Thiếu API Key", "Vui lòng nhập Google Gemini API Key!")
            return
        if not srt_path or not os.path.exists(srt_path):
            QMessageBox.warning(self, "Thiếu Tệp", "Vui lòng chọn tệp SRT gốc trước khi phân tích truyện!")
            return
            
        model_display = self.model_combo.currentText().strip()
        model_name = MODELS.get(model_display, "gemini-2.5-flash")

        self.story_memory_btn.setEnabled(False)
        self.story_memory_btn.setText("Đang phân tích...")
        self.status_label.setText("Đang đọc file SRT để tạo Story Memory...")
        self.log_output.append("Bắt đầu phân tích cốt truyện và nhân vật...")
        
        self.story_memory_worker = StoryMemoryWorker(api_key, model_name, srt_path)
        self.story_memory_worker.finished.connect(self.on_story_memory_finished)
        self.story_memory_worker.error_occurred.connect(self.on_glossary_error)
        self.story_memory_worker.start()

    def on_story_memory_finished(self, result_text):
        self.story_memory_btn.setEnabled(True)
        self.story_memory_btn.setText("Phân tích Truyện")
        self.story_memory_worker = None
        
        if result_text:
            try:
                # Format to remove markdown if API returned markdown block
                if result_text.startswith("```json"):
                    result_text = result_text[7:]
                    if result_text.endswith("```"):
                        result_text = result_text[:-3]
                result_text = result_text.strip()
                
                # Validate JSON
                json.loads(result_text)
                
                # Save to story_memory.json in the same directory as the SRT
                srt_dir = os.path.dirname(self.srt_input.text().strip())
                memory_path = os.path.join(srt_dir, "story_memory.json")
                with open(memory_path, "w", encoding="utf-8") as f:
                    f.write(result_text)
                
                QMessageBox.information(
                    self, 
                    "Thành công", 
                    f"Phân tích cốt truyện thành công!\nĐã lưu tại: {memory_path}"
                )
                self.log_output.append("Đã tạo story_memory.json thành công.")
                self.status_label.setText("Phân tích truyện hoàn tất.")
            except Exception as e:
                QMessageBox.warning(self, "Lỗi phân tích", f"Dữ liệu trả về không phải JSON hợp lệ.\nLỗi: {e}\n\nNội dung:\n{result_text}")
                self.log_output.append("Lỗi tạo story_memory: " + str(e))
        else:
            QMessageBox.information(self, "Không có kết quả", "Không tìm thấy nội dung phù hợp.")
            self.status_label.setText("Phân tích truyện không có kết quả.")

    def show_context_menu(self, pos):
        """Present a context menu on table right-click with action selectors"""
        menu = QMenu(self)
        translate_action = QAction("Dịch lại các dòng đã chọn", self)
        clear_action = QAction("Xóa bản dịch các dòng đã chọn", self)
        
        menu.addAction(translate_action)
        menu.addAction(clear_action)
        
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        
        # Get selected unique rows
        selected_ranges = self.table.selectedRanges()
        selected_rows = []
        for r in selected_ranges:
            for row in range(r.topRow(), r.bottomRow() + 1):
                selected_rows.append(row)
        selected_rows = list(set(selected_rows))
        selected_rows.sort()

        if not selected_rows:
            return

        if action == translate_action:
            self.start_translation(selected_rows=selected_rows)
        elif action == clear_action:
            self.clear_selected_rows(selected_rows)

    def clear_selected_rows(self, rows):
        """Reset translation column values to untranslated for selected indices"""
        self.table.blockSignals(True)
        for r in rows:
            item_orig = self.table.item(r, 1)
            orig_text = item_orig.text() if item_orig else ""
            item_trans = self.table.item(r, 2)
            if item_trans:
                if not orig_text.strip():
                    item_trans.setText("")
                else:
                    item_trans.setText("Chưa dịch...")
                    item_trans.setForeground(QColor("#718096"))
        self.table.blockSignals(False)
        
        # Sync changes on disk and update status counters
        self.save_current_table_to_srt()
        self.update_counters()
        self.log_output.append(f"Đã xóa bản dịch của các hàng: {[r+1 for r in rows]}")

    def on_item_changed(self, item):
        """Auto-save changes to output SRT file when user manually edits translated cells"""
        if item.column() == 2:  # Column index 2 is "Bản Dịch"
            # Prevent circular highlights
            self.save_current_table_to_srt()
            self.update_counters()

    def save_current_table_to_srt(self):
        """Save current table data state straight to output SRT file"""
        input_path = self.srt_input.text().strip()
        output_path = self.srt_output.text().strip()
        if not input_path or not output_path or not os.path.exists(input_path):
            return
            
        try:
            subs, encoding = load_srt(input_path)
            if len(subs) != self.table.rowCount():
                return
                
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 2)
                val = ""
                if item:
                    txt = item.text().strip()
                    if txt != "Chưa dịch..." and txt != "[LỖI DỊCH]":
                        val = txt
                subs[row].text = val
                
            subs.save(output_path, encoding=encoding)
        except Exception as e:
            print(f"Error auto-saving manually edited table: {e}")

    def update_counters(self):
        """Recalculate and display status reports based on table state"""
        total = self.table.rowCount()
        empty = 0
        untranslated = 0
        translated = 0
        
        for row in range(total):
            item_orig = self.table.item(row, 1)
            item_trans = self.table.item(row, 2)
            
            orig_txt = item_orig.text().strip() if item_orig else ""
            trans_txt = item_trans.text().strip() if item_trans else ""
            
            if not orig_txt:
                empty += 1
            elif trans_txt == "Chưa dịch..." or trans_txt == "[LỖI DỊCH]" or not trans_txt:
                untranslated += 1
            else:
                translated += 1
                
        self.total_label.setText(str(total))
        self.empty_label.setText(str(empty))
        self.untrans_label.setText(str(untranslated))
        self.trans_label.setText(str(translated))

    def start_translation(self, selected_rows=None):
        api_key = self.api_key_input.text().strip()
        input_path = self.srt_input.text().strip()
        output_path = self.srt_output.text().strip()

        if not api_key:
            QMessageBox.warning(self, "Thiếu Thông Tin", "Vui lòng cung cấp Google Gemini API Key!")
            return
        if not input_path or not os.path.exists(input_path):
            QMessageBox.warning(self, "Thiếu Thông Tin", "Vui lòng chọn tệp SRT đầu vào!")
            return
        if not output_path:
            QMessageBox.warning(self, "Thiếu Thông Tin", "Vui lòng chọn nơi lưu SRT đầu ra!")
            return

        model_display = self.model_combo.currentText().strip()
        model_name = MODELS.get(model_display, "gemini-2.5-flash")
        genre = self.genre_combo.text().strip()
        batch_size = self.batch_size_spin.value()
        context_lines = self.context_lines_spin.value()
        temperature = self.temp_spin.value()
        glossary = self.parse_glossary()

        # Cache inputs
        self.config["api_key"] = api_key
        self.config["model"] = model_display
        self.config["genre"] = genre
        self.config["batch_size"] = batch_size
        self.config["context_lines"] = context_lines
        self.config["temperature"] = temperature
        self.config["glossary_text"] = self.glossary_input.toPlainText()
        self.config["srt_input"] = input_path
        self.config["srt_output"] = output_path
        save_config(self.config)

        # Build list of line items from the table view
        records = []
        for row in range(self.table.rowCount()):
            item_orig = self.table.item(row, 1)
            item_trans = self.table.item(row, 2)
            
            orig_text = item_orig.text() if item_orig else ""
            trans_text = item_trans.text() if item_trans else ""
            
            text_clean = orig_text.strip()
            is_empty = not text_clean
            
            # Determine if this specific index should be translated
            needs_translation = False
            if not is_empty:
                if selected_rows is not None:
                    needs_translation = (row in selected_rows)
                else:
                    needs_translation = (trans_text == "Chưa dịch..." or trans_text == "[LỖI DỊCH]" or not trans_text)
            
            records.append({
                "index": row,
                "id": row + 1,
                "orig": orig_text,
                "trans": trans_text if not needs_translation else None,
                "is_empty": is_empty,
                "needs_translation": needs_translation
            })

        # Clear logs & reset progress bar
        self.log_output.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("Đang dịch...")
        
        # Toggle buttons
        self.set_ui_enabled(False)

        # Fire worker thread
        self.worker = TranslationWorker(
            api_key=api_key,
            model_name=model_name,
            records=records,
            input_path=input_path,
            output_path=output_path,
            genre=genre,
            glossary=glossary,
            batch_size=batch_size,
            context_lines=context_lines,
            temperature=temperature
        )
        self.worker.progress_updated.connect(self.on_log_update)
        self.worker.row_translated.connect(self.on_row_translated)
        self.worker.report_updated.connect(self.on_report_update)
        self.worker.finished.connect(self.on_success)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def stop_translation(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
            self.log_output.append("\n--- Đã dừng tiến trình bởi người dùng (Tiến trình đã được lưu) ---")
            self.status_label.setText("Đã dừng")
            self.progress_bar.setValue(0)
            self.set_ui_enabled(True)

    def on_log_update(self, percent, message):
        self.progress_bar.setValue(percent)
        self.log_output.append(message)
        self.log_output.ensureCursorVisible()

    def on_row_translated(self, row_idx, translated_text):
        """Update translation cell of the row in real-time"""
        self.table.blockSignals(True)
        item = self.table.item(row_idx, 2)
        if item:
            item.setText(translated_text)
            if translated_text == "[LỖI DỊCH]":
                item.setForeground(QColor("#ef4444"))
            else:
                item.setForeground(QColor("#10b981"))
            self.table.scrollToItem(item)
        self.table.blockSignals(False)

    def on_report_update(self, trans, untrans, empty):
        self.trans_label.setText(str(trans))
        self.untrans_label.setText(str(untrans))
        self.empty_label.setText(str(empty))

    def report_untranslated_lines(self):
        """Scan table and list all row indices that are still untranslated"""
        untranslated = []
        for row in range(self.table.rowCount()):
            item_orig = self.table.item(row, 1)
            item_trans = self.table.item(row, 2)
            
            orig_txt = item_orig.text().strip() if item_orig else ""
            trans_txt = item_trans.text().strip() if item_trans else ""
            
            if orig_txt and (trans_txt == "Chưa dịch..." or trans_txt == "[LỖI DỊCH]" or not trans_txt):
                untranslated.append(row + 1)
        
        if untranslated:
            self.log_output.append(f"\n--- BÁO CÁO DÒNG CHƯA DỊCH ---")
            self.log_output.append(f"Danh sách các dòng chưa dịch (tổng cộng {len(untranslated)} dòng):")
            self.log_output.append(", ".join(map(str, untranslated)))
        else:
            self.log_output.append(f"\n--- BÁO CÁO DÒNG CHƯA DỊCH: Tất cả các dòng đã được dịch hoàn tất! ---")

    def on_success(self, srt_path):
        self.status_label.setText("Hoàn thành")
        self.report_untranslated_lines()
        QMessageBox.information(
            self, 
            "Dịch Thành Công", 
            f"Quá trình dịch phụ đề hoàn tất!\nTệp tin đã được lưu tại:\n{srt_path}"
        )
        self.set_ui_enabled(True)

    def on_error(self, err_msg):
        self.status_label.setText("Bị lỗi")
        self.report_untranslated_lines()
        QMessageBox.critical(
            self, 
            "Gặp Lỗi", 
            f"Có lỗi nghiêm trọng xảy ra trong lúc dịch phụ đề:\n{err_msg}"
        )
        self.set_ui_enabled(True)

    def set_ui_enabled(self, enabled):
        self.start_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(not enabled)
        
        self.api_key_input.setEnabled(enabled)
        self.model_combo.setEnabled(enabled)
        self.srt_input.setEnabled(enabled)
        self.srt_output.setEnabled(enabled)
        self.genre_combo.setEnabled(enabled)
        self.batch_combo.setEnabled(enabled)
        self.glossary_input.setEnabled(enabled)
        self.glossary_btn.setEnabled(enabled)
        self.update_config_btn.setEnabled(enabled)
        if enabled:
            self.worker = None

    def open_output_folder(self):
        path = self.srt_output.text().strip()
        if path:
            folder = os.path.dirname(os.path.abspath(path))
            if os.path.exists(folder):
                os.startfile(folder)
            else:
                QMessageBox.warning(self, "Không tìm thấy", f"Thư mục không tồn tại: {folder}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Custom font configuration
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = SRTTranslatorApp()
    window.show()
    sys.exit(app.exec())
