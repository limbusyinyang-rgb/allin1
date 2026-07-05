import os
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QFileDialog, QTabWidget, QLineEdit, QProgressBar, QMessageBox, QDialog
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtMultimedia import QMediaPlayer

from models.subtitle_style import SubtitleStyle
from core.subtitle_renderer import SubtitleRenderer
from core.ffmpeg_engine import FFmpegExportEngine
from ui.widgets.video_player import VideoPlayerWidget
from ui.widgets.subtitle_overlay import SubtitleOverlayWidget
from ui.widgets.watermark_manager import WatermarkManager
from ui.widgets.blur_manager import BlurManager
from ui.widgets.audio_mixer import AudioMixerWidget
from ui.dialogs.export_settings import ExportSettingsDialog

class MainCapCutWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Exporter (CapCut Clone)")
        self.resize(1280, 800)
        
        # Data Models
        self.sub_style = SubtitleStyle.load()
        self.watermarks = []
        self.blurs = []
        self.sub_renderer = SubtitleRenderer()
        
        self.setup_ui()
        
        # Real-time subtitle sync timer
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.sync_subtitles)
        self.sync_timer.start(50)  # 20 FPS subtitle update
        
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        # Top Bar
        top_bar = QHBoxLayout()
        
        self.video_input = QLineEdit()
        self.video_input.setPlaceholderText("Video File...")
        self.btn_vid = QPushButton("Video")
        self.btn_vid.clicked.connect(self.browse_video)
        
        self.srt_input = QLineEdit()
        self.srt_input.setPlaceholderText("SRT File...")
        self.btn_srt = QPushButton("SRT")
        self.btn_srt.clicked.connect(self.browse_srt)
        
        self.btn_export = QPushButton("Export Video")
        self.btn_export.setStyleSheet("background-color: #10b981; color: white; font-weight: bold;")
        self.btn_export.clicked.connect(self.show_export_dialog)
        
        top_bar.addWidget(self.video_input)
        top_bar.addWidget(self.btn_vid)
        top_bar.addWidget(self.srt_input)
        top_bar.addWidget(self.btn_srt)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_export)
        main_layout.addLayout(top_bar)
        
        # Main Layout (Video on left, Tabs on right)
        work_layout = QHBoxLayout()
        
        # Video Player
        self.video_player = VideoPlayerWidget()
        work_layout.addWidget(self.video_player, stretch=6)
        
        # Tabs for editing
        self.tabs = QTabWidget()
        
        self.sub_overlay = SubtitleOverlayWidget(self.video_player.scene, self.sub_style)
        self.tabs.addTab(self.sub_overlay, "Subtitles")
        
        self.wm_manager = WatermarkManager(self.video_player.scene, self.watermarks)
        self.tabs.addTab(self.wm_manager, "Watermarks")
        
        self.blur_manager = BlurManager(self.video_player.scene, self.blurs)
        self.tabs.addTab(self.blur_manager, "Blurs")
        
        self.audio_mixer = AudioMixerWidget(self.video_player)
        self.tabs.addTab(self.audio_mixer, "Audio")
        
        work_layout.addWidget(self.tabs, stretch=4)
        
        main_layout.addLayout(work_layout)
        
        # Bottom Export Status
        status_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.status_lbl = QLabel("Ready")
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_export)
        
        status_layout.addWidget(self.progress_bar)
        status_layout.addWidget(self.status_lbl)
        status_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(status_layout)
        
        # Link video player resize to update items
        self.video_player.video_item.nativeSizeChanged.connect(self.on_video_resize)
        
        # Link frame updates to blur manager and sub overlay
        def on_frame_ready(qimage):
            self.blur_manager.process_frame(qimage)
            self.sub_overlay.process_frame(qimage)
            self.wm_manager.process_frame(qimage)
            
        self.video_player.frame_ready_callback = on_frame_ready
        
        def pause_video():
            if self.video_player.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.video_player.player.pause()
                
        self.blur_manager.pause_callback = pause_video
        self.sub_overlay.pause_callback = pause_video
    def browse_video(self):
        settings = QSettings("MyCapCut", "SubExporter")
        last_dir = settings.value("last_video_dir", "")
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Video", last_dir, "Video Files (*.mp4 *.mkv)")
        if path:
            import os
            settings.setValue("last_video_dir", os.path.dirname(path))
            self.video_input.setText(path)
            self.video_player.load_video(path)
            
    def browse_srt(self):
        settings = QSettings("MyCapCut", "SubExporter")
        last_dir = settings.value("last_srt_dir", "")
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Phụ Đề", last_dir, "Subtitle Files (*.srt)")
        if path:
            import os
            settings.setValue("last_srt_dir", os.path.dirname(path))
            self.srt_input.setText(path)
            self.sub_renderer.load_srt(path)
            
    def on_video_resize(self):
        # Update relative coordinates for subtitle box, etc.
        vs = self.video_player.video_item.size()
        if vs.width() > 0:
            self.sub_overlay.update_from_video_size(vs.width(), vs.height())
            
    def sync_subtitles(self):
        if hasattr(self, 'video_player') and self.video_player.player:
            pos = self.video_player.player.position()
            text = self.sub_renderer.get_subtitle_at_time(pos)
            self.sub_overlay.update_text(text)

    def show_export_dialog(self):
        duration_sec = 0
        if hasattr(self, 'video_player') and self.video_player.player:
            duration_sec = self.video_player.player.duration() / 1000.0
            
        dialog = ExportSettingsDialog(self, video_duration=duration_sec)
        
        # Check if output is empty and auto suggest
        if not dialog.output_path.text() and self.video_input.text():
            import json
            import os
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "workspace_config.json")
            out_dir = os.path.dirname(self.video_input.text())
            try:
                if os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        if "workspace" in cfg:
                            ws = cfg["workspace"]
                            out_dir = os.path.join(ws, "Video đã xuất")
                            os.makedirs(out_dir, exist_ok=True)
            except Exception: pass
            
            base_name = os.path.basename(self.video_input.text())
            name_without_ext, _ = os.path.splitext(base_name)
            out = os.path.join(out_dir, name_without_ext + "_export.mp4")
            
            dialog.output_path.setText(out)
            
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_settings()
            config["output_input"] = dialog.output_path.text() # Keep backwards compatibility
            self.start_export(config)
            
    def start_export(self, export_config):
        # Gather all configs
        vs = self.video_player.video_item.size()
        if vs.width() > 0:
            self.sub_overlay.save_position_to_model(vs.height())
            self.wm_manager.sync_to_models(vs.width(), vs.height())
            self.blur_manager.sync_to_models(vs.width(), vs.height())
            
        audio_cfg = self.audio_mixer.get_config()
        
        full_config = {
            "video_input": self.video_input.text(),
            "srt_input": self.srt_input.text(),
            "sub_style": self.sub_style,
            "watermarks": self.watermarks,
            "blurs": self.blurs,
        }
        full_config.update(export_config)
        full_config.update(audio_cfg)
        
        self.btn_export.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_lbl.setText("Đang xuất video...")
        
        self.engine = FFmpegExportEngine(full_config)
        self.engine.progress_updated.connect(self.progress_bar.setValue)
        self.engine.log_updated.connect(lambda txt: self.status_lbl.setText(txt[-100:])) # Show last part of log
        self.engine.finished.connect(self.on_export_finished)
        self.engine.start()
        
    def cancel_export(self):
        if hasattr(self, 'engine') and self.engine.is_running:
            self.engine.stop()
            
    def on_export_finished(self, out_path, success):
        self.btn_export.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        if success:
            QMessageBox.information(self, "Thành công", f"Đã xuất video:\n{out_path}")
        else:
            QMessageBox.warning(self, "Lỗi", "Xuất video thất bại hoặc đã bị hủy!")

# Import QDialog manually
from PyQt6.QtWidgets import QDialog
