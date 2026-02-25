import os
from PySide6.QtCore import QRunnable, Signal, QObject
from ..database import get_connection
from ..utils.exif_utils import get_media_metadata
from .thumbnail_service import ThumbnailService

class ScannerSignals(QObject):
    progress = Signal(int, int)  # current, total
    finished = Signal()
    error = Signal(str)
    item_added = Signal(dict)

class MediaScanner(QRunnable):
    def __init__(self, album_id, root_path):
        super().__init__()
        self.album_id = album_id
        self.root_path = root_path
        self.signals = ScannerSignals()
        self.supported_extensions = {
            '.jpg', '.jpeg', '.png', '.heic',  # Images
            '.mp4', '.mov', '.m4v'             # Videos
        }

    def run(self):
        try:
            files_to_scan = []
            for root, _, files in os.walk(self.root_path):
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in self.supported_extensions:
                        files_to_scan.append(os.path.join(root, file))

            total = len(files_to_scan)
            if total == 0:
                self.signals.finished.emit()
                return

            conn = get_connection()
            cursor = conn.cursor()
            
            batch = []
            for i, file_path in enumerate(files_to_scan):
                # Check if already indexed (optional but good for performance)
                cursor.execute("SELECT id FROM media WHERE file_path = ?", (file_path,))
                if cursor.fetchone():
                    self.signals.progress.emit(i + 1, total)
                    continue

                meta = get_media_metadata(file_path)
                thumb_path = ThumbnailService.generate_thumbnail(
                    file_path, meta["type"], meta["duration"]
                )
                
                item = {
                    "album_id": self.album_id,
                    "file_path": file_path,
                    "date_taken": meta["date_taken"],
                    "type": meta["type"],
                    "duration": meta["duration"],
                    "thumbnail_path": thumb_path
                }
                
                batch.append((
                    item["album_id"], item["file_path"], item["date_taken"],
                    item["type"], item["duration"], item["thumbnail_path"]
                ))
                
                self.signals.item_added.emit(item)
                
                if len(batch) >= 200:
                    cursor.executemany('''
                        INSERT OR IGNORE INTO media 
                        (album_id, file_path, date_taken, type, duration, thumbnail_path)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', batch)
                    conn.commit()
                    batch = []
                
                self.signals.progress.emit(i + 1, total)

            if batch:
                cursor.executemany('''
                    INSERT OR IGNORE INTO media 
                    (album_id, file_path, date_taken, type, duration, thumbnail_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', batch)
                conn.commit()

            conn.close()
            self.signals.finished.emit()

        except Exception as e:
            self.signals.error.emit(str(e))
