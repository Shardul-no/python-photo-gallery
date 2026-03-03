from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex, Signal
from PySide6.QtGui import QPixmap, QIcon
import os
from datetime import datetime
from ..database import get_connection

class MediaModel(QAbstractListModel):
    # Custom Roles
    FilePathRole = Qt.UserRole + 1
    TypeRole = Qt.UserRole + 2 # "header" or "media"
    MediaTypeRole = Qt.UserRole + 3 # "image" or "video"
    DateRole = Qt.UserRole + 4
    DurationRole = Qt.UserRole + 5
    ThumbnailPathRole = Qt.UserRole + 6
    ExtensionRole = Qt.UserRole + 7
    WidthRole = Qt.UserRole + 8
    HeightRole = Qt.UserRole + 9
    OrientationRole = Qt.UserRole + 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_media_items = []
        self._display_items = []
        self.current_album_id = None
        self.load_data()

    def rowCount(self, parent=QModelIndex()):
        return len(self._display_items)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._display_items)):
            return None

        item = self._display_items[index.row()]

        if role == Qt.DecorationRole:
            if item['type'] == 'header':
                return None
            thumb_path = item['thumbnail_path']
            if thumb_path and os.path.exists(thumb_path):
                return QPixmap(thumb_path)
            return None

        if role == self.TypeRole:
            return item['type']
        
        if item['type'] == 'header':
            if role == Qt.DisplayRole:
                return item['label']
            return None

        if role == self.FilePathRole:
            return item['file_path']
        if role == self.MediaTypeRole:
            return item['media_type']
        if role == self.DateRole:
            return item['date_taken']
        if role == self.DurationRole:
            return item['duration']
        if role == self.ThumbnailPathRole:
            return item['thumbnail_path']
        if role == self.ExtensionRole:
            return os.path.splitext(item['file_path'])[1].lower()
        if role == self.WidthRole:
            return item.get('width')
        if role == self.HeightRole:
            return item.get('height')
        if role == self.OrientationRole:
            return item.get('orientation', 1)

        return None

    def load_data(self, album_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT file_path, date_taken, type, duration, thumbnail_path, width, height, orientation
            FROM media 
        '''
        params = []
        if album_id:
            query += ' WHERE album_id = ?'
            params.append(album_id)
            
        query += ' ORDER BY date_taken DESC'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        self._raw_media_items = []
        for row in rows:
            self._raw_media_items.append({
                'type': 'media',
                'file_path': row[0],
                'date_taken': row[1],
                'media_type': row[2],
                'duration': row[3],
                'thumbnail_path': row[4],
                'width': row[5],
                'height': row[6],
                'orientation': row[7]
            })
        conn.close()
        self._rebuild_display_items()

    def _rebuild_display_items(self):
        self.beginResetModel()
        self._display_items = []
        current_header = None
        
        for item in self._raw_media_items:
            # Parse date
            dt_str = item['date_taken']
            try:
                dt = datetime.fromisoformat(dt_str)
                header_label = dt.strftime("%B %Y")
            except:
                header_label = "Unknown Date"
            
            if header_label != current_header:
                current_header = header_label
                self._display_items.append({
                    'type': 'header',
                    'label': header_label,
                    'date_taken': item['date_taken'] # For sorting if needed
                })
            
            self._display_items.append(item)
        self.endResetModel()

    def add_item_manually(self, item):
        """Used to update UI while scanning. We'll add to raw and rebuild."""
        # Check if item belongs to current filter
        if self.current_album_id is not None:
            if item.get('album_id') != self.current_album_id:
                return

        self._raw_media_items.append({
            'type': 'media',
            'file_path': item['file_path'],
            'date_taken': item['date_taken'],
            'media_type': item['type'],
            'duration': item.get('duration'),
            'thumbnail_path': item.get('thumbnail_path'),
            'width': item.get('width'),
            'height': item.get('height'),
            'orientation': item.get('orientation', 1)
        })
        # Re-sort raw items
        self._raw_media_items.sort(key=lambda x: x['date_taken'], reverse=True)
        self._rebuild_display_items()
        
    def refresh(self, album_id=None):
        self.current_album_id = album_id
        self.load_data(album_id)
