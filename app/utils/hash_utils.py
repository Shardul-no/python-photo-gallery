import hashlib

def get_file_hash(file_path: str) -> str:
    """Returns SHA1 hash of the file path string for unique thumbnail naming."""
    return hashlib.sha1(file_path.encode('utf-8')).hexdigest()
