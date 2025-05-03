# models.py
from uagents import Model
from typing import Dict, Any # Import Dict and Any for typing

# Keep existing models if you still need them for other agents
# class CommissionRequest(Model): ...
# class AgreementDraft(Model): ...
# class Approval(Model): ...
# class PaymentRequest(Model): ...
# class PaymentNotification(Model): ...

# --- New Models for Vocab Generator ---

class WordRequest(Model):
    """Model to request vocabulary generation for a specific word."""
    word: str

class VocabResponse(Model):
    """Model to send back the generated vocabulary data or an error."""
    word: str
    data: Dict[str, Any] | None = None # Holds the generated JSON data
    error: str | None = None # Holds an error message if generation failed
