def read_file(path: str, mode: str = 'slice', indentation: dict = None, limit: int = 2000, offset: int = 1) -> dict:
    """Mock read_file tool."""
    return {"status": "success", "path": path, "mode": mode, "content": "# mock content"}