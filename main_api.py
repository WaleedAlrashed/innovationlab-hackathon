# main_api.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field # Use Field for default values
from typing import Optional
from dotenv import load_dotenv
import uvicorn # Server to run FastAPI

# Import the core generation function
from publishing_utils import generate_vocab_data, logger

# Load environment variables (needed for the generation function)
load_dotenv()

# --- Define Request and Response Models ---

class WordInput(BaseModel):
    word: str

# Define the output structure EXACTLY as Laravel expects
class VocabOutput(BaseModel):
    word: str
    word_arabic: str
    phonetics: str # Matches Laravel form key
    meaning: str
    synonyms: str
    antonyms: str
    example: str # Matches Laravel form key
    example_arabic: str # Matches Laravel form key
    icon: str = "" # Default empty string
    description: str
    # Add other fields if your Laravel code uses them from the response
    url: Optional[str] = None
    question: Optional[str] = None


# --- Create FastAPI App ---
app = FastAPI(
    title="Vocabulary Generation API",
    description="Generates vocabulary data using ASI-1 Mini.",
    version="1.0.0"
)

# --- API Endpoint ---
@app.post("/generate", response_model=VocabOutput)
async def generate_vocabulary_endpoint(request: WordInput):
    """
    Receives a word, generates vocabulary data using ASI-1 Mini,
    and returns the structured JSON response.
    """
    logger.info(f"API endpoint /generate received request for word: {request.word}")

    # Call the core generation logic
    result_data = await generate_vocab_data(request.word) # Use await if generate_vocab_data is async

    if result_data:
        logger.info(f"Successfully generated data for API request: {request.word}")
        # Ensure the response matches the Pydantic model structure
        # FastAPI will automatically validate and convert this dict
        return result_data
    else:
        logger.error(f"Failed to generate data for API request: {request.word}")
        # Raise an HTTP exception if generation fails
        raise HTTPException(status_code=500, detail="Failed to generate vocabulary data from ASI-1 Mini.")

# --- Add a simple root endpoint for testing ---
@app.get("/")
def read_root():
    return {"message": "Vocabulary Generation API is running."}

# --- Run the server (for local testing) ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080)) # Use port 8080 or from env
    uvicorn.run(app, host="0.0.0.0", port=port)

