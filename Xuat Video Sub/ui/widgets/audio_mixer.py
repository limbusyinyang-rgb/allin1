import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QSlider, QLabel, QPushButton, QFileDialog, QDoubleSpinBox
from PyQt6.QtCore import Qt, QUrl, QSettings
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

class AudioMixerWidget(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window # Reference to get players
        self.added_audio_path = ""
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        # Original Audio Volume
        self.orig_vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.orig_vol_slider.setRange(0, 200)
        self.orig_vol_slider.setValue(100)
        self.orig_vol_slider.valueChanged.connect(self.update_orig_volume)
        form.addRow("Original Vol (%):", self.orig_vol_slider)
        
        # Added Audio
        row_audio = QHBoxLayout()
        self.btn_audio = QPushButton("Chọn Audio Thêm")
        self.btn_audio.clicked.connect(self.browse_audio)
        self.lbl_audio = QLabel("None")
        row_audio.addWidget(self.btn_audio)
        row_audio.addWidget(self.lbl_audio)
        form.addRow("Added Audio:", row_audio)
        
        # Added Audio Volume
        self.add_vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.add_vol_slider.setRange(0, 200)
        self.add_vol_slider.setValue(100)
        self.add_vol_slider.valueChanged.connect(self.update_add_volume)
        form.addRow("Added Vol (%):", self.add_vol_slider)
        
        # Trim Video to Audio
        self.chk_trim_video = QCheckBox("Cắt video vừa bằng thời lượng Audio thêm")
        self.chk_trim_video.setChecked(True)
        form.addRow("", self.chk_trim_video)
        
        layout.addLayout(form)
        layout.addStretch()

    def browse_audio(self):
        settings = QSettings("MyCapCut", "SubExporter")
        last_dir = settings.value("last_audio_dir", "")
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Audio", last_dir, "Audio Files (*.mp3 *.wav *.aac)")
        if path:
            settings.setValue("last_audio_dir", os.path.dirname(path))
            self.added_audio_path = path
            self.lbl_audio.setText(os.path.basename(path))
            
            # Load to player for preview
            player = getattr(self.main_window, "audio_player", None)
            if player:
                player.setSource(QUrl.fromLocalFile(path))

    def update_orig_volume(self, val):
        player = getattr(self.main_window, "player", None)
        if player and player.audioOutput():
            player.audioOutput().setVolume(val / 100.0)

    def update_add_volume(self, val):
        player = getattr(self.main_window, "audio_player", None)
        if player and player.audioOutput():
            player.audioOutput().setVolume(val / 100.0)
            
    def get_config(self):
        return {
            "orig_audio_vol": self.orig_vol_slider.value() / 100.0,
            "added_audio": self.added_audio_path,
            "added_audio_vol": self.add_vol_slider.value() / 100.0,
            "trim_video": self.chk_trim_video.isChecked()
        }
