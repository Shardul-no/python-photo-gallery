from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QStackedWidget, QPushButton, 
    QHBoxLayout, QSlider, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QUrl, QTime, QTimer, QEvent
from PySide6.QtGui import QPixmap, QKeyEvent, QImage
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
import collections
from PIL import Image, ImageOps
import pillow_heif

pillow_heif.register_heif_opener()

class ImageCache:
    def __init__(self, max_size=10):
        self.cache = collections.OrderedDict()
        self.max_size = max_size

    def get(self, path):
        if path in self.cache:
            self.cache.move_to_end(path)
            return self.cache[path]
        return None

    def put(self, path, pixmap):
        self.cache[path] = pixmap
        self.cache.move_to_end(path)
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def clear(self):
        self.cache.clear()

class MediaViewer(QWidget):
    closed = Signal()
    next_requested = Signal()
    prev_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        
        # Simple & Premium Dark Theme
        self.setStyleSheet("""
            QWidget#viewerMain {
                background-color: #0c0c0c;
            }
            QWidget#actionPanel {
                background-color: #1a1a1a;
                border-top: 1px solid #333;
            }
            QPushButton {
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 6px;
                color: white;
                font-family: 'Segoe UI', sans-serif;
                font-size: 16px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton#navBtn {
                font-size: 24px;
                border-radius: 30px;
                min-width: 60px;
                min-height: 60px;
            }
            QPushButton#closeBtn {
                background-color: #c42b1c;
                border: none;
                font-size: 18px;
            }
            QPushButton#closeBtn:hover {
                background-color: #e81123;
            }
            QPushButton#playBtn {
                background-color: transparent;
                border: none;
                font-size: 28px;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 14px;
            }
            QSlider::groove:horizontal {
                height: 8px;
                background: #333;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: #0078d4;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: white;
                border: 2px solid #0078d4;
                width: 18px;
                height: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
        """)

        self.setObjectName("viewerMain")
        
        # Main Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Top Bar
        self.top_bar = QWidget()
        self.top_bar.setFixedHeight(50)
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(15, 0, 15, 0)
        top_layout.addStretch()
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setFixedSize(45, 35)
        self.close_btn.clicked.connect(self.close_viewer)
        top_layout.addWidget(self.close_btn)
        self.main_layout.addWidget(self.top_bar)

        # 2. Content Area (Mid)
        self.mid_area = QWidget()
        mid_layout = QHBoxLayout(self.mid_area)
        mid_layout.setContentsMargins(10, 0, 10, 0)
        mid_layout.setSpacing(20)

        self.prev_btn = QPushButton("<")
        self.prev_btn.setObjectName("navBtn")
        self.prev_btn.clicked.connect(self.prev_requested.emit)
        mid_layout.addWidget(self.prev_btn)

        self.stack = QStackedWidget()
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.stack.addWidget(self.image_label)
        
        from PySide6.QtMultimediaWidgets import QVideoWidget
        self.video_widget = QVideoWidget()
        self.stack.addWidget(self.video_widget)
        mid_layout.addWidget(self.stack)

        self.next_btn = QPushButton(">")
        self.next_btn.setObjectName("navBtn")
        self.next_btn.clicked.connect(self.next_requested.emit)
        mid_layout.addWidget(self.next_btn)

        self.main_layout.addWidget(self.mid_area, 1)

        # 3. Dedicated Video Control Panel (Footer)
        self.action_panel = QWidget()
        self.action_panel.setObjectName("actionPanel")
        self.action_panel.setFixedHeight(120)
        action_layout = QVBoxLayout(self.action_panel)
        action_layout.setContentsMargins(20, 10, 20, 10)
        action_layout.setSpacing(10)

        # Progress Slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.sliderMoved.connect(self.set_position)
        action_layout.addWidget(self.slider)

        # Playback Controls
        play_layout = QHBoxLayout()
        self.time_label = QLabel("00:00")
        self.play_pause_btn = QPushButton("▶")
        self.play_pause_btn.setObjectName("playBtn")
        self.play_pause_btn.setFixedSize(60, 60)
        self.play_pause_btn.clicked.connect(self.toggle_play)
        self.duration_label = QLabel("00:00")
        
        play_layout.addWidget(self.time_label)
        play_layout.addStretch()
        play_layout.addWidget(self.play_pause_btn)
        play_layout.addStretch()
        play_layout.addWidget(self.duration_label)
        action_layout.addLayout(play_layout)

        self.main_layout.addWidget(self.action_panel)

        # Multimedia
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        self.player.playbackStateChanged.connect(self.update_playback_state)
        
        self.image_cache = ImageCache()
        self.current_path = ""
        self.setFocusPolicy(Qt.StrongFocus)

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def update_playback_state(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_pause_btn.setText("⏸")
        else:
            self.play_pause_btn.setText("▶")

    def set_position(self, position):
        self.player.setPosition(position)

    def update_position(self, position):
        if not self.slider.isSliderDown():
            self.slider.setValue(position)
        self.time_label.setText(self.format_time(position))

    def update_duration(self, duration):
        self.slider.setRange(0, duration)
        self.duration_label.setText(self.format_time(duration))

    def format_time(self, ms):
        s = ms // 1000
        m, s = divmod(s, 60)
        return f"{m:02d}:{s:02d}"

    def show_content(self, file_path, media_type):
        self.current_path = file_path
        self.stop_video()
        
        if media_type == "image":
            self.stack.setCurrentIndex(0)
            self.action_panel.hide()
            pixmap = self.image_cache.get(file_path)
            if not pixmap:
                try:
                    with Image.open(file_path) as img:
                        img = ImageOps.exif_transpose(img)
                        if img.mode != "RGB": img = img.convert("RGB")
                        data = img.tobytes("raw", "RGB")
                        qimage = QImage(data, img.size[0], img.size[1], QImage.Format_RGB888)
                        pixmap = QPixmap.fromImage(qimage)
                        self.image_cache.put(file_path, pixmap)
                except Exception:
                    pixmap = QPixmap(file_path)
            
            if pixmap:
                scaled_pix = pixmap.scaled(self.stack.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_label.setPixmap(scaled_pix)
            
        elif media_type == "video":
            self.stack.setCurrentIndex(1)
            self.action_panel.show()
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self.player.play()

        self.showFullScreen()
        self.setFocus() 

    def stop_video(self):
        if self.player.playbackState() != QMediaPlayer.StoppedState:
            self.player.stop()

    def close_viewer(self):
        self.stop_video()
        self.image_label.clear()
        self.hide()
        self.closed.emit()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape: self.close_viewer()
        elif event.key() == Qt.Key_Left: self.prev_requested.emit()
        elif event.key() == Qt.Key_Right: self.next_requested.emit()
        elif event.key() == Qt.Key_Space:
            if self.stack.currentIndex() == 1: self.toggle_play()
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        if self.stack.currentIndex() == 0 and self.current_path:
            pixmap = self.image_cache.get(self.current_path)
            if pixmap:
                scaled_pix = pixmap.scaled(self.stack.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_label.setPixmap(scaled_pix)
        super().resizeEvent(event)



