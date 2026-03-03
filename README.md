# Pro Photo & Video Gallery

A high-performance, Windows-native media viewer built with Python and PySide6. Designed for speed, aesthetics, and reliability.

## ✨ Key Features
- **Smooth Virtualized Grid**: Handles 10,000+ items with ease using Qt's Model/View architecture.
- **Bento View**: Toggle a dynamic, variable-sized grid layout for a more modern, masonry-style look.
- **Background Scanning**: Indexing and thumbnail generation run in background threads to keep the UI responsive.
- **Date-First Navigation**: Grouped by date with a "Jump to Date" calendar and quick filters for year/month.
- **Local-Only**: Albums are read-only. Metadata and thumbnails are stored locally in `LocalAppData`.
- **Smart Sorting**: Uses EXIF `DateTimeOriginal` with fallback to file creation date.
- **Rich Viewer**: Full-resolution image viewer with LRU caching and integrated video player.
- **HEIC Support**: Native support for modern iPhone photo formats.

## 🛠 Prerequisites
1. **Python 3.11+**
2. **FFmpeg**: Required for video thumbnail extraction. Ensure `ffmpeg` and `ffprobe` are in your system PATH (or in `C:\ffmpeg\bin\` for the build script).

## 🚀 Setup & Running
1. **Clone or download** this project.
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install pillow-heif  # Required for HEIC support
   ```
3. **Run the App**:
   ```bash
   python run.py
   ```

## ⌨️ Controls & Shortcuts
### Gallery view
- **Double Click**: Open image/video in full viewer.
- **Bento View Checkbox**: Toggle between standard grid and masonry layout.
- **Jump to Date**: Use the calendar or year/month dropdowns to skip to specific dates.

### Media Viewer
- **Left / Right Arrow**: Navigate to previous/next item.
- **Space**: Play/Pause video.
- **Esc**: Close viewer and return to gallery.
- **Close Button**: Exit viewer mode.

## 🏗 Building the Executable
To bundle the application into a standalone Windows `.exe`:
1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Run the build command using the provided spec file:
   ```bash
   pyinstaller --noconfirm ProPhotoGallery.spec
   ```
3. The executable will be generated in the `dist/` directory. 
   *Note: The spec file is configured to bundle `ffmpeg.exe` and `ffprobe.exe` if found in `C:\ffmpeg\bin\`.*

## 📁 Project Structure
- `run.py`: Entry point for the application.
- `app/main.py`: Core application logic.
- `app/ui/`: UI components (Main Window, Media Viewer, Delegates).
- `app/models/`: Qt Media Model for efficient data handling.
- `app/services/`: Background scanner and thumbnail generation service.
- `app/database.py`: SQLite management and filesystem indexing.
- `app/utils/`: EXIF extraction and hashing helpers.

## ⚙️ Technical Decisions
- **Thumbnails**: 300px width JPEGs stored in a SHA1-hashed cache in LocalAppData.
- **Database**: SQLite with indexing on `date_taken` for fast retrieval and sorting.
- **Memory Management**: Full-resolution images are released when the viewer closes, with a 10-item LRU cache for adjacent preloading.
