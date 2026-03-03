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
                # Simple check to see if scanner was cancelled or source deleted
                if not self.signals: break

                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in self.supported_extensions:
                        files_to_scan.append(os.path.join(root, file))

            total = len(files_to_scan)
            if total == 0:
                try: self.signals.finished.emit()
                except RuntimeError: pass
                return

            conn = get_connection()
            cursor = conn.cursor()
            
            batch = []
            for i, file_path in enumerate(files_to_scan):
                # Safety check
                try: 
                    self.signals.progress.emit(i, total)
                except RuntimeError:
                    break

                # Check if already indexed
                cursor.execute("SELECT id FROM media WHERE file_path = ?", (file_path,))
                if cursor.fetchone():
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
                    "thumbnail_path": thumb_path,
                    "width": meta["width"],
                    "height": meta["height"],
                    "orientation": meta["orientation"]
                }
                
                batch.append((
                    item["album_id"], item["file_path"], item["date_taken"],
                    item["type"], item["duration"], item["thumbnail_path"],
                    item["width"], item["height"], item["orientation"]
                ))
                
                try: self.signals.item_added.emit(item)
                except RuntimeError: break
                
                if len(batch) >= 200:
                    cursor.executemany('''
                        INSERT OR IGNORE INTO media 
                        (album_id, file_path, date_taken, type, duration, thumbnail_path, width, height, orientation)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', batch)
                    conn.commit()
                    batch = []
                
            if batch:
                cursor.executemany('''
                    INSERT OR IGNORE INTO media 
                    (album_id, file_path, date_taken, type, duration, thumbnail_path, width, height, orientation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', batch)
                conn.commit()

            conn.close()
            try: self.signals.finished.emit()
            except RuntimeError: pass

        except Exception as e:
            try: self.signals.error.emit(str(e))
            except RuntimeError: pass
