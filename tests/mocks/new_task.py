def new_task(message: str, mode: str, todos: str = None) -> dict:
    """Mock new_task tool."""
    return {"status": "success", "message": message, "mode": mode, "todos": todos}