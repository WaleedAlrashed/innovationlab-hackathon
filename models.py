# models.py
from uagents import Model
from typing import Dict, Any

class WordRequest(Model):
    """Model to request vocabulary generation for a specific word."""
    word: str

class VocabResponse(Model):
    """Model to send back the generated vocabulary data or an error."""
    word: str
    data: Dict[str, Any] | None = None # Holds the generated JSON data
    error: str | None = None # Holds an error message if generation failed
