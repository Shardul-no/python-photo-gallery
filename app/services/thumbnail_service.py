import os
import subprocess
from PIL import Image
import pillow_heif
from ..database import get_thumbnail_dir
from ..utils.hash_utils import get_file_hash

# Ensure registration happens early
pillow_heif.register_heif_opener()

class ThumbnailService:
    @staticmethod
    def generate_thumbnail(file_path: str, media_type: str, duration: float = None) -> str:
        """
        Generates a thumbnail and returns the path to it.
        If it exists, just returns the path.
        """
        if not file_path or not os.path.exists(file_path):
            return ""
            
        thumb_name = f"{get_file_hash(file_path)}.jpg"
        thumb_path = os.path.join(get_thumbnail_dir(), thumb_name)
        
        if os.path.exists(thumb_path):
            return thumb_path
        
        ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if media_type == "image" or ext in ['.heic', '.heif']:
                ThumbnailService._generate_image_thumbnail(file_path, thumb_path)
            elif media_type == "video":
                ThumbnailService._generate_video_thumbnail(file_path, thumb_path, duration)
            
            if os.path.exists(thumb_path):
                return thumb_path
        except Exception as e:
            print(f"Error generating thumbnail for {file_path}: {e}")
            # HEIC Fallback using ffmpeg if PIL fails
            if ext in ['.heic', '.heif']:
                try:
                    ThumbnailService._generate_heic_fallback(file_path, thumb_path)
                    if os.path.exists(thumb_path):
                        return thumb_path
                except Exception as fe:
                    print(f"HEIC Fallback failed for {file_path}: {fe}")
            
        return ""

    @staticmethod
    def _generate_image_thumbnail(src, dst):
        with Image.open(src) as img:
            # Convert to RGB (Required for JPEG saving and HEIC/PNG transparency)
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            # Maintain aspect ratio, width 300px
            width = 300
            w_percent = (width / float(img.size[0]))
            height = int((float(img.size[1]) * float(w_percent)))
            
            img = img.resize((width, height), Image.Resampling.LANCZOS)
            img.save(dst, "JPEG", quality=75)

    @staticmethod
    def _generate_heic_fallback(src, dst):
        """Uses ffmpeg to convert HEIC to JPEG thumbnail."""
        cmd = [
            'ffmpeg',
            '-y',
            '-i', src,
            '-frames:v', '1',
            '-vf', 'scale=300:-1',
            dst
        ]
        subprocess.run(cmd, capture_output=True, check=False)

    @staticmethod
    def _generate_video_thumbnail(src, dst, duration):
        # Extract frame at 30% duration
        seek_time = (duration * 0.3) if duration else 1.0
        
        cmd = [
            'ffmpeg',
            '-y',
            '-ss', str(seek_time),
            '-i', src,
            '-frames:v', '1',
            '-q:v', '2',
            '-vf', 'scale=300:-1',
            dst
        ]
        subprocess.run(cmd, capture_output=True, check=False)
