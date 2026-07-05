import os
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QHBoxLayout, QLineEdit, QComboBox, QSpinBox, QPushButton, QLabel, QFileDialog
from PyQt6.QtCore import Qt, QSettings

class ExportSettingsDialog(QDialog):
    def __init__(self, parent=None, video_duration=0):
        super().__init__(parent)
        self.setWindowTitle("Cấu hình Xuất Video")
        self.resize(400, 350)
        self.video_duration = video_duration
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["H264 (CPU)", "H264 (NVENC)", "H264 (QuickSync)"])
        form.addRow("Bộ mã hóa (Codec):", self.codec_combo)
        
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Tùy chỉnh", "Tiêu chuẩn (4000 kbps, 30fps)", "High (8000 kbps, 60fps)", "Ultra (15000 kbps, 60fps)"])
        self.quality_combo.currentIndexChanged.connect(self.on_quality_changed)
        form.addRow("Chất lượng:", self.quality_combo)
        
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(500, 50000)
        self.bitrate_spin.setSingleStep(500)
        self.bitrate_spin.setValue(4000)
        self.bitrate_spin.valueChanged.connect(self.update_estimated_size)
        form.addRow("Video Bitrate (kbps):", self.bitrate_spin)
        
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(10, 120)
        self.fps_spin.setValue(30)
        form.addRow("FPS:", self.fps_spin)
        
        self.audio_bitrate_spin = QSpinBox()
        self.audio_bitrate_spin.setRange(64, 320)
        self.audio_bitrate_spin.setValue(128)
        self.audio_bitrate_spin.valueChanged.connect(self.update_estimated_size)
        form.addRow("Audio Bitrate (kbps):", self.audio_bitrate_spin)
        
        self.lbl_size = QLabel("Dung lượng ước tính: ~ 0 MB")
        self.lbl_size.setStyleSheet("color: #AAAAAA; font-style: italic;")
        form.addRow("", self.lbl_size)
        
        self.output_path = QLineEdit()
        btn_out = QPushButton("Chọn Thư mục...")
        btn_out.clicked.connect(self.browse_out)
        row_out = QHBoxLayout()
        row_out.addWidget(self.output_path)
        row_out.addWidget(btn_out)
        form.addRow("Save To:", row_out)
        
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        btn_export = QPushButton("Xuất Video")
        btn_export.setStyleSheet("background-color: #3b82f6; color: white; font-weight: bold; padding: 8px;")
        btn_export.clicked.connect(self.accept)
        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_export)
        layout.addLayout(btn_layout)
        
    def browse_out(self):
        settings = QSettings("MyCapCut", "SubExporter")
        last_dir = settings.value("last_export_dir", "")
        path, _ = QFileDialog.getSaveFileName(self, "Lưu Video", last_dir or "export_video.mp4", "Video Files (*.mp4)")
        if path:
            settings.setValue("last_export_dir", os.path.dirname(path))
            self.output_path.setText(path)

    def on_quality_changed(self, index):
        if index == 1:
            self.bitrate_spin.setValue(4000)
            self.fps_spin.setValue(30)
        elif index == 2:
            self.bitrate_spin.setValue(8000)
            self.fps_spin.setValue(60)
        elif index == 3:
            self.bitrate_spin.setValue(15000)
            self.fps_spin.setValue(60)
            
    def update_estimated_size(self):
        total_kbps = self.bitrate_spin.value() + self.audio_bitrate_spin.value()
        # total_kbps / 8192 = MB per second
        mb = (total_kbps / 8192) * self.video_duration
        self.lbl_size.setText(f"Dung lượng ước tính: ~ {mb:.1f} MB")

    def get_settings(self):
        return {
            "codec": self.codec_combo.currentText(),
            "video_bitrate": self.bitrate_spin.value(),
            "fps": self.fps_spin.value(),
            "audio_bitrate": self.audio_bitrate_spin.value()
        }
