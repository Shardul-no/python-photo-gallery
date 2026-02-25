import sqlite3
import os
from pathlib import Path

def get_app_data_dir():
    """Returns the LocalAppData path for the application."""
    app_data = os.getenv('LOCALAPPDATA')
    if not app_data:
        app_data = os.path.expanduser("~")
    path = Path(app_data) / "PhotoGalleryApp"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_db_path():
    return get_app_data_dir() / "gallery.db"

def get_thumbnail_dir():
    path = get_app_data_dir() / "cache" / "thumbnails"
    path.mkdir(parents=True, exist_ok=True)
    return path

def init_db():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY,
            name TEXT,
            root_path TEXT UNIQUE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY,
            album_id INTEGER,
            file_path TEXT UNIQUE,
            date_taken TEXT,
            type TEXT,
            duration REAL,
            thumbnail_path TEXT,
            FOREIGN KEY(album_id) REFERENCES albums(id)
        )
    ''')
    
    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON media(date_taken DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_album ON media(album_id)')
    
    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(get_db_path())
