import os
import datetime
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS
import subprocess
import json
import pillow_heif

pillow_heif.register_heif_opener()

def get_media_metadata(file_path: str) -> dict:
    """Extracts date taken, duration, dimensions, and orientation."""
    ext = os.path.splitext(file_path)[1].lower()
    metadata = {
        "date_taken": None,
        "duration": None,
        "type": "image" if ext in ['.jpg', '.jpeg', '.png', '.heic'] else "video",
        "width": None,
        "height": None,
        "orientation": 1
    }
    
    # Try EXIF/Dimensions for images
    if metadata["type"] == "image":
        try:
            with Image.open(file_path) as img:
                # Get dimensions
                metadata["width"], metadata["height"] = img.size
                
                # Check orientation
                exif_data = img.getexif()
                if exif_data:
                    # Orientation tag is 274
                    metadata["orientation"] = exif_data.get(274, 1)
                    
                    # Look in the Exif IFD (0x8769) for DateTimeOriginal
                    exif_ifd = exif_data.get_ifd(0x8769)
                    date_str = exif_ifd.get(0x9003) or exif_data.get(0x0132)
                    if date_str:
                        try:
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
                
                # Dimensions from first video stream
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        metadata["width"] = stream.get('width')
                        metadata["height"] = stream.get('height')
                        break

                # Duration
                duration = data.get('format', {}).get('duration')
                if duration:
                    metadata["duration"] = float(duration)
                
                # Date taken
                tags = data.get('format', {}).get('tags', {})
                creation_time = tags.get('creation_time')
                if creation_time:
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
