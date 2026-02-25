# Pro Photo & Video Gallery

A high-performance, Windows-native media viewer built with Python and PySide6.

## Features
- **Smooth Virtualized Grid**: Handles 10,000+ items with ease using Qt's Model/View architecture.
- **Local-Only**: Albums are read-only. Metadata and thumbnails are stored in `LocalAppData`.
- **Background Scanning**: Indexing and thumbnail generation run in background threads to keep the UI responsive.
- **Smart Sorting**: Uses EXIF `DateTimeOriginal` with fallback to file creation date.
- **Rich Viewer**: Full-resolution image viewer with LRU caching and integrated video player.
- **Modern Dark UI**: Sleek, minimal design with smooth animations.

## Prerequisites
1. **Python 3.11+**
2. **FFmpeg**: Required for video thumbnail extraction. Ensure `ffmpeg` and `ffprobe` are in your system PATH.

## Setup
1. Clone or download this project.
2. Install dependencies:
   ```bash
   pip install PySide6 Pillow
   ```
   *Note: For HEIC support, you may also need `pip install pillow-heif`.*

## Running the App
Run the following command from the project root:
```bash
python -m app.main
```

## Project Structure
- `app/main.py`: Entry point.
- `app/database.py`: SQLite and filesystem management.
- `app/services/`: Background scanner and thumbnail generation.
- `app/ui/`: Main window, grid delegate, and media viewer.
- `app/models/`: Qt Media Model.
- `app/utils/`: EXIF extraction and hashing helpers.

## Technical Decisions
- **Thumbnails**: 300px width JPEGs stored in a SHA1-hashed cache.
- **Database**: SQLite with indexing on `date_taken` for fast retrieval and sorting.
- **Memory Management**: Full-resolution images are released when the viewer closes, with a 10-item LRU cache for adjacent preloading/navigation.
