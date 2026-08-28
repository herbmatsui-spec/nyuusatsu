def list_files(path: str, recursive: bool) -> dict:
    """Mock list_files tool."""
    return {"status": "success", "path": path, "recursive": recursive, "files": []}