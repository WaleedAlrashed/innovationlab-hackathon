# publishing_utils.py (or rename/move to generation_logic.py)
from typing import Any

import requests
import json
import re
import os
import logging
from dotenv import load_dotenv
from models import OutputData

# Load environment variables at the module level if needed by functions here
load_dotenv()
ASI1_MODEL = "asi1-mini"
ASI_API_KEY = os.environ.get("ASI_API_KEY")
ASI_API_ENDPOINT = os.environ.get("ASI_API_ENDPOINT", "https://api.asi1.ai/v1/chat/completions")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Keep clean_json_response
def clean_json_response(text: str) -> str:
    text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()
    return text


def get_completion(
    context: str,
    prompt: str,
    response_schema: dict[str, Any] | None = None,
    max_tokens: int = 1000,
) -> str:
    # ASI1 API is OpenAI-compatible, but may not support response_schema
    messages = []
    if context:
        messages.append({"role": "system", "content": context})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": ASI1_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if response_schema is not None:
        # If ASI1 supports response_format, add it here. Otherwise, ignore.
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": response_schema.get("title", "output"),
                "strict": False,
                "schema": response_schema,
            },
        }

    HEADERS = {"Authorization": f"bearer {ASI_API_KEY}", "Content-Type": "application/json"}

    try:
        response = requests.post(
            ASI_API_ENDPOINT,
            headers=HEADERS,
            data=json.dumps(payload),
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        # ASI1 returns choices[0].message.content (OpenAI-compatible)
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"An error occurred: {e}"

# --- NEW Core Generation Function ---
async def generate_vocab_data(word: str) -> dict | None:
    """
    Generates vocabulary data for a word using ASI-1 Mini and formats description.
    Returns a dictionary with the data or None on failure.
    """
    word = word.strip().lower()
    logger.info(f"Generating vocab data for word: {word}")

    if not ASI_API_KEY:
        logger.error("ASI_API_KEY not found in environment variables.")
        return None

    # Simplified prompt (no icon needed for API response)
    formatted_prompt = f"""Generate a vocabulary post for '{word}' including the following json keys:
1.  word
2.  word_arabic (no english pronunciation)
3.  phonetic
4.  meaning
5.  synonyms (3 synonyms comma-separated)
6.  antonyms (3 antonyms comma-separated)
7.  example_sentence (underline the word using markdown like _word_)
8.  example_sentence_arabic (Arabic example translation - no english pronunciation)
9.  url (merriam-webster.com link for the word)
10. question (one-line question related to the word)

notes: response should be returned as valid json object only, do not include any text before or after the json object, ensure all keys are present.
"""
    try:
        # --- Make API Call using get_completion ---
        api_response_text = get_completion(
            context="Vocabulary generation context",
            prompt=formatted_prompt,
            response_schema=OutputData.model_json_schema(),
            max_tokens=1000
        )
        # --- Parse JSON Response into OutputData ---
        try:
            inner_data = json.loads(api_response_text)
            logger.info("Successfully parsed JSON response.")

            # Validate and structure the response using OutputData
            description = f"""<b>#{inner_data["word"].capitalize()} Word of the Day: {inner_data["word"]}</b>

            🗣 Your Turn!
            <i>{inner_data["question"]}</i>
            Share it below!

            🔗 <a href="{inner_data["url"]}">Read More</a>
            📌 #Daily{inner_data["word"].capitalize()} | {TELEGRAM_CHAT_ID or '@your_channel'}"""

            inner_data["description"] = description
            output_data = OutputData(**inner_data).model_dump()
            logger.info(f"Final output_data prepared: {output_data}")
            return output_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing response content: {e}")
            return None

    except Exception as e:
        logger.error(f"An unexpected error occurred during API call: {e}")
        return None