def search_files(path: str, regex: str, file_pattern: str = None) -> dict:
    """Mock search_files tool."""
    return {"status": "success", "path": path, "regex": regex, "file_pattern": file_pattern, "matches": []}