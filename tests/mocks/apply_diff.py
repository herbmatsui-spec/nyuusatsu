def apply_diff(path: str, diff: str) -> dict:
    """Mock apply_diff tool."""
    return {"status": "success", "path": path, "diff_applied": diff}