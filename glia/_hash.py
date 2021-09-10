import hashlib
from pathlib import Path


def hash_update_from_file(filename, hash):
    msg = f"Trying to file-hash non file path '{filename}'"
    assert Path(filename).is_file(), msg
    with open(str(filename), "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash.update(chunk)
    return hash


def hash_file(filename):  # pragma: nocover
    return hash_update_from_file(filename, hashlib.md5()).hexdigest()


def hash_update_from_dir(directory, hash):
    msg = f"Trying to directory-hash non directory path '{directory}'"
    assert Path(directory).is_dir(), msg
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
