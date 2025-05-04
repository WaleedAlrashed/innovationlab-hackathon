# models.py
from uagents import Model
from typing import Dict, Any
from pydantic import BaseModel
from typing import Optional

class WordRequest(Model):
    """Model to request vocabulary generation for a specific word."""
    word: str

class VocabResponse(Model):
    """Model to send back the generated vocabulary data or an error."""
    word: str
    data: Dict[str, Any] | None = None # Holds the generated JSON data
    error: str | None = None # Holds an error message if generation failed

class OutputData(BaseModel):
    word: str
    word_arabic: str
    phonetic: str
    meaning: str
    synonyms: str
    antonyms: str
    example_sentence: str
    example_sentence_arabic: str
    url: Optional[str]
    question: Optional[str] = "What do you think about this word?"
    icon: Optional[str] = ""
    description: str