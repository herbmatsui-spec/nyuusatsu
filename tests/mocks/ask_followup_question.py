def ask_followup_question(question: str, follow_up: list) -> dict:
    """Mock ask_followup_question tool."""
    return {"status": "success", "question": question, "follow_up": follow_up}