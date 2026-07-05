import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFileDialog, QProgressBar, 
                             QMessageBox, QComboBox, QSpinBox, QGroupBox, QSlider)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from core.config import load_config, save_config
from core.srt_utils import parse_srt
from core.exporter import ExportWorker
from ui.widgets.preview_widget import PreviewWidget

class ExportApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Trình Xuất Video - Subtitle Utilities Suite")
        self.resize(1100, 650)
        self.worker = None
        self.config = load_config()
        self.subs = []
        self._user_is_seeking = False

        self.setup_ui()
        self.load_last_state()
        self.update_preview_source()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout_h = QHBoxLayout(central_widget)
        main_layout_h.setContentsMargins(20, 20, 20, 20)
        main_layout_h.setSpacing(20)

        left_panel_widget = QWidget()
        left_panel = QVBoxLayout(left_panel_widget)
        left_panel.setContentsMargins(0, 0, 0, 0)
        left_panel.setSpacing(15)

        title_lbl = QLabel("🎥 Xuất Video Phụ Đề")
        title_lbl.setObjectName("titleLabel")
        left_panel.addWidget(title_lbl)

        gbox_inputs = QGroupBox("Tệp đầu vào")
        lay_inputs = QVBoxLayout(gbox_inputs)
        lay_inputs.setSpacing(10)

        # Video Input
        row_video = QHBoxLayout()
        self.video_input = QLineEdit()
        self.video_input.setPlaceholderText("Chọn video gốc (.mp4)...")
        self.video_input.textChanged.connect(self.update_preview_source)
        btn_browse_video = QPushButton("Duyệt...")
        btn_browse_video.setObjectName("btnBrowse")
        btn_browse_video.clicked.connect(self.browse_video)
        row_video.addWidget(self.video_input)
        row_video.addWidget(btn_browse_video)
        lay_inputs.addWidget(QLabel("Video gốc:"))
        lay_inputs.addLayout(row_video)

        # SRT Input
        row_srt = QHBoxLayout()
        self.srt_input = QLineEdit()
        self.srt_input.setPlaceholderText("Chọn phụ đề (.srt)...")
        self.srt_input.textChanged.connect(self.update_preview_source)
        btn_browse_srt = QPushButton("Duyệt...")
        btn_browse_srt.setObjectName("btnBrowse")
        btn_browse_srt.clicked.connect(self.browse_srt)
        row_srt.addWidget(self.srt_input)
        row_srt.addWidget(btn_browse_srt)
        lay_inputs.addWidget(QLabel("Phụ đề:"))
        lay_inputs.addLayout(row_srt)

        # Audio Input
        row_audio = QHBoxLayout()
        self.audio_input = QLineEdit()
        self.audio_input.setPlaceholderText("Chọn âm thanh lồng tiếng (Tùy chọn)...")
        self.audio_input.textChanged.connect(self.update_preview_source)
        btn_browse_audio = QPushButton("Duyệt...")
        btn_browse_audio.setObjectName("btnBrowse")
        btn_browse_audio.clicked.connect(self.browse_audio)
        row_audio.addWidget(self.audio_input)
        row_audio.addWidget(btn_browse_audio)
        lay_inputs.addWidget(QLabel("Âm thanh Lồng tiếng (Tùy chọn):"))
        lay_inputs.addLayout(row_audio)
        
        left_panel.addWidget(gbox_inputs)

        # Settings Group
        gbox_settings = QGroupBox("Cài đặt xuất")
        lay_settings = QVBoxLayout(gbox_settings)
        lay_settings.setSpacing(10)
        
        row_opts = QHBoxLayout()
        
        col_audio_mode = QVBoxLayout()
        col_audio_mode.addWidget(QLabel("Chế độ âm thanh:"))
        self.audio_combo = QComboBox()
        self.audio_combo.addItems([
            "Giữ nguyên âm thanh gốc",
            "Thay thế bằng lồng tiếng",
            "Mix (Gốc 10% + Lồng tiếng 100%)"
        ])
        self.audio_combo.currentTextChanged.connect(self.update_preview_source)
        col_audio_mode.addWidget(self.audio_combo)
        row_opts.addLayout(col_audio_mode)
        
        col_font = QVBoxLayout()
        col_font.addWidget(QLabel("Cỡ chữ (Sub):"))
        self.font_spin = QSpinBox()
        self.font_spin.setRange(10, 100)
        self.font_spin.setValue(24)
        self.font_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.font_spin.valueChanged.connect(self.update_subtitle_display)
        col_font.addWidget(self.font_spin)
        row_opts.addLayout(col_font)
        
        lay_settings.addLayout(row_opts)

        # Blur Mode
        row_opts2 = QHBoxLayout()
        col_blur_mode = QVBoxLayout()
        col_blur_mode.addWidget(QLabel("Che Sub gốc:"))
        self.blur_combo = QComboBox()
        self.blur_combo.addItems([
            "Không che",
            "Làm mờ (Blur)",
            "Hộp đen (Black Box)"
        ])
        self.blur_combo.currentTextChanged.connect(self.update_blur_mode)
        col_blur_mode.addWidget(self.blur_combo)
        row_opts2.addLayout(col_blur_mode)
        lay_settings.addLayout(row_opts2)
        
        # Output
        lay_settings.addWidget(QLabel("Nơi lưu Video kết quả:"))
        row_out = QHBoxLayout()
        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("Đường dẫn lưu video (.mp4)...")
        btn_browse_out = QPushButton("Lưu vào...")
        btn_browse_out.setObjectName("btnBrowse")
        btn_browse_out.clicked.connect(self.browse_output)
        row_out.addWidget(self.output_input)
        row_out.addWidget(btn_browse_out)
        lay_settings.addLayout(row_out)
        
        left_panel.addWidget(gbox_settings)

        left_panel.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        left_panel.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Sẵn sàng")
        left_panel.addWidget(self.status_label)

        row_actions = QHBoxLayout()
        self.btn_start = QPushButton("▶ Bắt đầu Xuất Video")
        self.btn_start.setObjectName("btnStart")
        self.btn_start.clicked.connect(self.start_export)
        
        self.btn_stop = QPushButton("⏹ Dừng")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_export)
        
        row_actions.addWidget(self.btn_start)
        row_actions.addWidget(self.btn_stop)
        
        left_panel.addLayout(row_actions)
        main_layout_h.addWidget(left_panel_widget, stretch=4)
        
        # Right Panel: Live Preview Player
        right_panel_widget = QWidget()
        right_panel = QVBoxLayout(right_panel_widget)
        right_panel.setContentsMargins(0, 0, 0, 0)
        right_panel.setSpacing(10)
        
        preview_title = QLabel("📺 Live Preview (Kéo để chỉnh vị trí Sub)")
        preview_title.setObjectName("previewTitle")
        right_panel.addWidget(preview_title)
        
        self.preview_widget = PreviewWidget()
        self.preview_widget.setMinimumSize(450, 300)
        right_panel.addWidget(self.preview_widget, stretch=1)
        
        player_controls = QHBoxLayout()
        
        self.btn_play = QPushButton("▶ Phát")
        self.btn_play.clicked.connect(self.toggle_play)
        player_controls.addWidget(self.btn_play)
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderPressed.connect(self.on_slider_pressed)
        self.slider.sliderReleased.connect(self.on_slider_released)
        self.slider.sliderMoved.connect(self.set_position)
        player_controls.addWidget(self.slider)
        
        self.time_label = QLabel("00:00 / 00:00")
        player_controls.addWidget(self.time_label)
        
        right_panel.addLayout(player_controls)
        main_layout_h.addWidget(right_panel_widget, stretch=5)

        self.video_player = QMediaPlayer()
        self.video_audio_output = QAudioOutput()
        self.video_player.setAudioOutput(self.video_audio_output)
        self.video_player.setVideoOutput(self.preview_widget.video_widget)
        
        self.audio_player = QMediaPlayer()
        self.dubbing_audio_output = QAudioOutput()
        self.audio_player.setAudioOutput(self.dubbing_audio_output)
        
        self.video_player.positionChanged.connect(self.position_changed)
        self.video_player.durationChanged.connect(self.duration_changed)
        self.video_player.playbackStateChanged.connect(self.state_changed)

    def load_last_state(self):
        if "video_input" in self.config: self.video_input.setText(self.config["video_input"])
        if "srt_input" in self.config: self.srt_input.setText(self.config["srt_input"])
        if "audio_input" in self.config: self.audio_input.setText(self.config["audio_input"])
        if "output_input" in self.config: self.output_input.setText(self.config["output_input"])
        if "font_size" in self.config: self.font_spin.setValue(self.config["font_size"])
        if "audio_mode" in self.config:
            idx = self.audio_combo.findText(self.config["audio_mode"])
            if idx >= 0: self.audio_combo.setCurrentIndex(idx)
        if "blur_mode" in self.config:
            idx = self.blur_combo.findText(self.config["blur_mode"])
            if idx >= 0: self.blur_combo.setCurrentIndex(idx)
            
        if "block_y_pct" in self.config and "block_h_pct" in self.config:
            self.loaded_block_y_pct = self.config["block_y_pct"]
            self.loaded_block_h_pct = self.config["block_h_pct"]
        else:
            self.loaded_block_y_pct = None

    def browse_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Video Gốc", "", "Video Files (*.mp4 *.mkv *.avi *.mov)")
        if path:
            self.video_input.setText(path)
            self.config["video_input"] = path
            if not self.output_input.text():
                out_path = os.path.splitext(path)[0] + "_subbed.mp4"
                self.output_input.setText(out_path)
                self.config["output_input"] = out_path
            save_config(self.config)
            self.update_preview_source()

    def browse_srt(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Phụ Đề", "", "Subtitle Files (*.srt)")
        if path:
            self.srt_input.setText(path)
            self.config["srt_input"] = path
            save_config(self.config)
            self.update_preview_source()

    def browse_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Âm Thanh Lồng Tiếng", "", "Audio Files (*.wav *.mp3 *.aac *.m4a)")
        if path:
            self.audio_input.setText(path)
            self.config["audio_input"] = path
            self.audio_combo.setCurrentIndex(1)
            save_config(self.config)
            self.update_preview_source()

    def browse_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Lưu Video", "", "MP4 Video (*.mp4)")
        if path:
            self.output_input.setText(path)
            self.config["output_input"] = path
            save_config(self.config)

    def update_blur_mode(self):
        self.preview_widget.block.set_blur_mode(self.blur_combo.currentText())

    def update_preview_source(self):
        video = self.video_input.text().strip()
        audio = self.audio_input.text().strip()
        srt = self.srt_input.text().strip()
        
        if video and os.path.exists(video):
            self.video_player.setSource(QUrl.fromLocalFile(video))
        else:
            self.video_player.setSource(QUrl())
            self.video_player.stop()
            self.slider.setRange(0, 0)
            self.time_label.setText("00:00 / 00:00")
            
        if audio and os.path.exists(audio):
            self.audio_player.setSource(QUrl.fromLocalFile(audio))
        else:
            self.audio_player.setSource(QUrl())
            
        self.subs = parse_srt(srt)
        
        mode = self.audio_combo.currentText()
        if "Thay thế" in mode:
            self.video_audio_output.setVolume(0.0)
            self.dubbing_audio_output.setVolume(1.0)
        elif "Mix" in mode:
            self.video_audio_output.setVolume(0.1)
            self.dubbing_audio_output.setVolume(1.0)
        else:
            self.video_audio_output.setVolume(1.0)
            self.dubbing_audio_output.setVolume(0.0)
            
        self.update_subtitle_display()
        self.update_blur_mode()

    def toggle_play(self):
        if self.video_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.video_player.pause()
            self.audio_player.pause()
        else:
            if not self.video_player.source().isValid():
                QMessageBox.warning(self, "Lỗi", "Vui lòng chọn video đầu vào hợp lệ để phát!")
                return
            self.video_player.play()
            if self.audio_player.source().isValid():
                self.audio_player.setPosition(self.video_player.position())
                self.audio_player.play()

    def on_slider_pressed(self):
        self._user_is_seeking = True

    def on_slider_released(self):
        self._user_is_seeking = False
        self.set_position(self.slider.value())

    def set_position(self, position):
        self.video_player.setPosition(position)
        if self.audio_player.source().isValid():
            self.audio_player.setPosition(position)
        self.update_subtitle_display()
            
    def duration_changed(self, duration):
        self.slider.setRange(0, duration)
        self.position_changed(self.video_player.position())
        
        if getattr(self, "loaded_block_y_pct", None) is not None:
            ph = self.preview_widget.height()
            y = int(self.loaded_block_y_pct * ph)
            h = int(self.loaded_block_h_pct * ph)
            self.preview_widget.block.setGeometry(0, y, self.preview_widget.width(), h)
        
    def position_changed(self, position):
        if not self._user_is_seeking:
            self.slider.setValue(position)
        
        def format_time(ms):
            s = ms // 1000
            m = s // 60
            s = s % 60
            return f"{m:02d}:{s:02d}"
            
        dur = self.video_player.duration()
        self.time_label.setText(f"{format_time(position)} / {format_time(dur)}")
        self.update_subtitle_display()
        
    def state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setText("⏸ Tạm dừng")
        else:
            self.btn_play.setText("▶ Phát")

    def update_subtitle_display(self):
        position = self.video_player.position()
        current_text = ""
        for sub in self.subs:
            if sub['start'] <= position <= sub['end']:
                current_text = sub['text']
                break
        
        if not current_text:
            current_text = "Đây là dòng Subtitle mẫu\n(Sample Subtitle)"
                
        self.preview_widget.block.subtitle_label.setText(current_text)
        
        font = self.preview_widget.block.subtitle_label.font()
        font.setPointSize(self.font_spin.value())
        font.setBold(True)
        self.preview_widget.block.subtitle_label.setFont(font)

    def start_export(self):
        self.video_player.pause()
        self.audio_player.pause()
        
        video_path = self.video_input.text().strip()
        srt_path = self.srt_input.text().strip()
        audio_path = self.audio_input.text().strip()
        out_path = self.output_input.text().strip()
        audio_mode = self.audio_combo.currentText()
        blur_mode = self.blur_combo.currentText()
        font_size = self.font_spin.value()

        if not video_path or not os.path.exists(video_path):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn video đầu vào hợp lệ!")
            return
        if not srt_path or not os.path.exists(srt_path):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file SRT hợp lệ!")
            return
        if audio_mode != "Giữ nguyên âm thanh gốc" and (not audio_path or not os.path.exists(audio_path)):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file âm thanh hoặc chuyển về chế độ 'Giữ nguyên âm thanh gốc'.")
            return
        if not out_path:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn đường dẫn lưu tệp!")
            return

        ph = self.preview_widget.height()
        if ph <= 0: ph = 1
        y_pct = self.preview_widget.block.y() / ph
        h_pct = self.preview_widget.block.height() / ph

        self.config["video_input"] = video_path
        self.config["srt_input"] = srt_path
        self.config["audio_input"] = audio_path
        self.config["output_input"] = out_path
        self.config["audio_mode"] = audio_mode
        self.config["blur_mode"] = blur_mode
        self.config["font_size"] = font_size
        self.config["block_y_pct"] = y_pct
        self.config["block_h_pct"] = h_pct
        save_config(self.config)

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        
        self.worker = ExportWorker(
            video_path, srt_path, audio_path, out_path, audio_mode, blur_mode, y_pct, h_pct, font_size
        )
        self.worker.progress_updated.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def stop_export(self):
        if self.worker:
            self.worker.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_label.setText("Đã hủy quá trình xuất video.")

    def on_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.status_label.setText(message)

    def on_finished(self, out_path):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        QMessageBox.information(self, "Thành công", f"Đã xuất video thành công!\n{out_path}")

    def on_error(self, err):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        QMessageBox.critical(self, "Lỗi", f"Đã xảy ra lỗi:\n{err}")
