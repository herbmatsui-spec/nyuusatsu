def execute_command(command: str, cwd: str = None, timeout: int = None) -> dict:
    """Mock execute_command tool."""
    return {"status": "success", "command": command, "cwd": cwd, "timeout": timeout}