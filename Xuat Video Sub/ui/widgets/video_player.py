import os
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QVBoxLayout, QWidget, QSlider, QHBoxLayout, QPushButton, QLabel, QSizePolicy, QApplication, QLineEdit, QSpinBox, QDoubleSpinBox
from PyQt6.QtCore import Qt, QUrl, QSizeF, pyqtSignal, QRectF, QEvent
from PyQt6.QtCore import Qt, QUrl, QSizeF, pyqtSignal, QRectF
from PyQt6.QtGui import QPen, QColor, QBrush, QPainter
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtWidgets import QGraphicsRectItem

class VideoPlayerWidget(QWidget):
    position_changed = pyqtSignal(int)
    duration_changed = pyqtSignal(int)
    state_changed = pyqtSignal(QMediaPlayer.PlaybackState)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_player()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Scene & View
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setStyleSheet("background-color: #0d1117; border: none;")
        self.view.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        
        # Video Item
        self.video_item = QGraphicsVideoItem()
        self.scene.addItem(self.video_item)
        self.video_item.setZValue(0)
        
        layout.addWidget(self.view)

        # Controls
        controls_layout = QHBoxLayout()
        
        self.btn_back10 = QPushButton("⏮ 10s")
        self.btn_back10.clicked.connect(lambda: self.seek_relative(-10000))
        controls_layout.addWidget(self.btn_back10)
        
        self.btn_play = QPushButton("▶ Phát")
        self.btn_play.clicked.connect(self.toggle_play)
        controls_layout.addWidget(self.btn_play)
        
        self.btn_fwd10 = QPushButton("10s ⏭")
        self.btn_fwd10.clicked.connect(lambda: self.seek_relative(10000))
        controls_layout.addWidget(self.btn_fwd10)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)
        controls_layout.addWidget(self.slider)

        self.time_label = QLabel("00:00 / 00:00")
        controls_layout.addWidget(self.time_label)

        layout.addLayout(controls_layout)

    def setup_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_item)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.video_item.nativeSizeChanged.connect(self.adjust_video_size)
        
        # Connect video sink for frame extraction
        sink = self.video_item.videoSink()
        if sink:
            sink.videoFrameChanged.connect(self._on_frame_changed)

    def _on_frame_changed(self, frame):
        if frame.isValid():
            image = frame.toImage()
            if not image.isNull():
                # We can scale the image to the video_item's current size in the scene 
                # so that crops map perfectly
                vs = self.video_item.size()
                if vs.width() > 0:
                    scaled_image = image.scaled(int(vs.width()), int(vs.height()), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
                    # Notify parent/main window that a new frame is available for blur manager
                    if hasattr(self, 'frame_ready_callback') and self.frame_ready_callback:
                        self.frame_ready_callback(scaled_image)

    def load_video(self, file_path):
        if file_path and os.path.exists(file_path):
            self.player.setSource(QUrl.fromLocalFile(file_path))
        else:
            self.player.setSource(QUrl())
            self.slider.setRange(0, 0)
            self.time_label.setText("00:00 / 00:00")
            
    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            if self.player.source().isValid():
                self.player.play()

    def set_position(self, pos):
        self.player.setPosition(pos)
        
    def seek_relative(self, ms):
        if self.player.duration() > 0:
            new_pos = max(0, min(self.player.position() + ms, self.player.duration()))
            self.player.setPosition(new_pos)
            
    def keyPressEvent(self, event):
        # Ignore keys if focus is on an input field
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, (QLineEdit, QSpinBox, QDoubleSpinBox)):
            super().keyPressEvent(event)
            return
            
        if event.key() == Qt.Key.Key_Space:
            self.toggle_play()
            event.accept()
        elif event.key() == Qt.Key.Key_Left:
            self.seek_relative(-10000)
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            self.seek_relative(10000)
            event.accept()
        else:
            super().keyPressEvent(event)

    def format_time(self, ms):
        s = ms // 1000
        m = s // 60
        s = s % 60
        return f"{m:02d}:{s:02d}"

    def _on_position_changed(self, pos):
        if not self.slider.isSliderDown():
            self.slider.setValue(pos)
        dur = self.player.duration()
        self.time_label.setText(f"{self.format_time(pos)} / {self.format_time(dur)}")
        self.position_changed.emit(pos)

    def _on_duration_changed(self, dur):
        self.slider.setRange(0, dur)
        self.duration_changed.emit(dur)

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setText("⏸ Tạm dừng")
        else:
            self.btn_play.setText("▶ Phát")
        self.state_changed.emit(state)

    def adjust_video_size(self):
        ns = self.video_item.nativeSize()
        if ns.width() > 0:
            self.video_item.setSize(ns)
            self.scene.setSceneRect(0, 0, ns.width(), ns.height())
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            if hasattr(self, 'on_video_resize'):
                self.on_video_resize()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_video_size()
