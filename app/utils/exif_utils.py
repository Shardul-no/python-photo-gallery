import os
import datetime
from PIL import Image
from PIL.ExifTags import TAGS
import subprocess
import json
import pillow_heif

pillow_heif.register_heif_opener()

def get_media_metadata(file_path: str) -> dict:
    """Extracts date taken and duration (for videos)."""
    ext = os.path.splitext(file_path)[1].lower()
    metadata = {
        "date_taken": None,
        "duration": None,
        "type": "image" if ext in ['.jpg', '.jpeg', '.png', '.heic'] else "video"
    }
    # Using type hint for clarity
    metadata: dict[str, any] = metadata
    
    # Try EXIF for images
    if metadata["type"] == "image":
        try:
            with Image.open(file_path) as img:
                exif_data = img.getexif()
                if exif_data:
                    # Look in the Exif IFD (0x8769) for DateTimeOriginal
                    exif_ifd = exif_data.get_ifd(0x8769)
                    date_str = exif_ifd.get(0x9003) or exif_data.get(0x0132) # 0x9003 is DateTimeOriginal, 0x0132 is DateTime
                    if date_str:
                        try:
                            # EXIF date format is usually YYYY:MM:DD HH:MM:SS
                            dt = datetime.datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                            metadata["date_taken"] = dt.isoformat()
                        except ValueError:
                            pass
        except Exception:
            pass
            
    # Try ffprobe for videos
    elif metadata["type"] == "video":
        try:
            cmd = [
                'ffprobe', 
                '-v', 'quiet', 
                '-print_format', 'json', 
                '-show_format', 
                '-show_streams', 
                file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                # Duration
                duration = data.get('format', {}).get('duration')
                if duration:
                    metadata["duration"] = float(duration)
                
                # Date taken (creation_time)
                tags = data.get('format', {}).get('tags', {})
                creation_time = tags.get('creation_time')
                if creation_time:
                    # Often in ISO format already
                    metadata["date_taken"] = creation_time
        except Exception:
            pass

    # Fallback to file creation time
    if not metadata["date_taken"]:
        try:
            mtime = os.path.getmtime(file_path)
            dt = datetime.datetime.fromtimestamp(mtime)
            metadata["date_taken"] = dt.isoformat()
        except Exception:
            metadata["date_taken"] = datetime.datetime.now().isoformat()
            
    return metadata
