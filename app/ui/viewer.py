from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QStackedWidget, QPushButton, 
    QHBoxLayout, QSlider, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QUrl, QTime
from PySide6.QtGui import QPixmap, QKeyEvent, QImage
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
import collections
from PIL import Image
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
        
        # Dark Style
        self.setStyleSheet("""
            QWidget {
                background-color: #000000;
                color: white;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 30);
                border: none;
                border-radius: 4px;
                padding: 8px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 60);
            }
            QSlider::handle:horizontal {
                background: #0078d7;
                border: 1px solid #0078d7;
                width: 14px;
                margin: -5px 0;
                border_radius: 7px;
            }
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Content Stack
        self.stack = QStackedWidget()
        
        # Image Page
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.stack.addWidget(self.image_label)
        
        # Video Page
        from PySide6.QtMultimediaWidgets import QVideoWidget
        self.video_widget = QVideoWidget()
        self.video_container = QWidget()
        self.video_layout = QVBoxLayout(self.video_container)
        self.video_layout.setContentsMargins(0, 0, 0, 0)
        self.video_layout.addWidget(self.video_widget)
        
        # Video Controls
        self.video_controls = QWidget()
        self.v_ctrl_layout = QHBoxLayout(self.video_controls)
        
        self.play_pause_btn = QPushButton("Pause")
        self.play_pause_btn.setFixedWidth(60)
        self.play_pause_btn.clicked.connect(self.toggle_play)
        
        self.time_label = QLabel("00:00")
        self.slider = QSlider(Qt.Horizontal)
        self.duration_label = QLabel("00:00")
        
        self.slider.sliderMoved.connect(self.set_position)
        
        self.v_ctrl_layout.addWidget(self.play_pause_btn)
        self.v_ctrl_layout.addWidget(self.time_label)
        self.v_ctrl_layout.addWidget(self.slider)
        self.v_ctrl_layout.addWidget(self.duration_label)
        
        self.video_layout.addWidget(self.video_controls)
        self.stack.addWidget(self.video_container)
        
        self.main_layout.addWidget(self.stack)

        # Navigation Overlay
        self.nav_controls = QWidget(self)
        self.nav_layout = QHBoxLayout(self.nav_controls)
        self.nav_layout.setContentsMargins(20, 20, 20, 20)
        
        self.prev_btn = QPushButton("<")
        self.prev_btn.setFixedSize(50, 50)
        self.prev_btn.clicked.connect(self.prev_requested.emit)
        
        self.next_btn = QPushButton(">")
        self.next_btn.setFixedSize(50, 50)
        self.next_btn.clicked.connect(self.next_requested.emit)
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(50, 50)
        self.close_btn.clicked.connect(self.close_viewer)
        
        self.nav_layout.addWidget(self.prev_btn)
        self.nav_layout.addStretch()
        self.nav_layout.addWidget(self.close_btn)
        self.nav_layout.addStretch()
        self.nav_layout.addWidget(self.next_btn)
        
        # We'll manually position nav_controls to stay on top
        self.nav_controls.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        
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

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def update_playback_state(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_pause_btn.setText("Pause")
        else:
            self.play_pause_btn.setText("Play")

    def set_position(self, position):
        self.player.setPosition(position)

    def update_position(self, position):
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
            self.video_controls.hide()
            pixmap = self.image_cache.get(file_path)
            if not pixmap:
                # Use Pillow to support HEIC properly if needed
                try:
                    with Image.open(file_path) as img:
                        if img.mode != "RGB":
                            img = img.convert("RGB")
                        
                        # Convert PIL Image to QImage then QPixmap
                        data = img.tobytes("raw", "RGB")
                        qimage = QImage(data, img.size[0], img.size[1], QImage.Format_RGB888)
                        pixmap = QPixmap.fromImage(qimage)
                        self.image_cache.put(file_path, pixmap)
                except Exception as e:
                    print(f"Error loading image {file_path}: {e}")
                    pixmap = QPixmap(file_path) # Fallback
            
            if pixmap:
                scaled_pix = pixmap.scaled(
                    self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pix)
            
        elif media_type == "video":
            self.stack.setCurrentIndex(1)
            self.video_controls.show()
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self.player.play()

        self.showFullScreen()

    def stop_video(self):
        if self.player.playbackState() != QMediaPlayer.StoppedState:
            self.player.stop()

    def close_viewer(self):
        self.stop_video()
        self.image_label.clear()
        self.hide()
        self.closed.emit()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.close_viewer()
        elif event.key() == Qt.Key_Left:
            self.prev_requested.emit()
        elif event.key() == Qt.Key_Right:
            self.next_requested.emit()
        elif event.key() == Qt.Key_Space:
            if self.stack.currentIndex() == 1:
                self.toggle_play()
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        if self.stack.currentIndex() == 0 and self.current_path:
            pixmap = self.image_cache.get(self.current_path)
            if pixmap:
                scaled_pix = pixmap.scaled(
                    self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pix)
        
        # Position nav controls
        self.nav_controls.setGeometry(0, 0, self.width(), 100)
        super().resizeEvent(event)
