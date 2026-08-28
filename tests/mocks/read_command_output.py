def read_command_output(artifact_id: str, search: str = None, offset: int = None, limit: int = None) -> dict:
    """Mock read_command_output tool."""
    return {"status": "success", "artifact_id": artifact_id, "search": search, "offset": offset, "limit": limit}