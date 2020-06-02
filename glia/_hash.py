import hashlib
from pathlib import Path


def hash_update_from_file(filename, hash):
    assert Path(filename).is_file()
    with open(str(filename), "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash.update(chunk)
    return hash


def hash_file(filename):  # pragma: nocover
    return hash_update_from_file(filename, hashlib.md5()).hexdigest()


def hash_update_from_dir(directory, hash):
    assert Path(directory).is_dir()
    for path in sorted(Path(directory).iterdir()):
        hash.update(path.name.encode())
        if path.is_file():
            hash = hash_update_from_file(path, hash)
        elif path.is_dir():  # pragma: nocover
            hash = hash_update_from_dir(path, hash)
    return hash


def get_directory_hash(directory):
    return hash_update_from_dir(directory, hashlib.md5()).hexdigest()

def hash_path(path):
    return hashlib.md5(path.encode()).hexdigest()
