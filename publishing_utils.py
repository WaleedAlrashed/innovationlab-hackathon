# publishing_utils.py (or rename/move to generation_logic.py)

import requests
import json
import re
import os
import logging
from dotenv import load_dotenv

# Load environment variables at the module level if needed by functions here
load_dotenv()
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

    headers = {"Authorization": f"bearer {ASI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "asi1-mini", "messages": [{"role": "user", "content": formatted_prompt}],
        "max_tokens": 1000, "temperature": 0.7, "stream": False,
        "response_format": {"type": "json_object"}
    }

    try:
        # --- Make API Call ---
        response = requests.post(ASI_API_ENDPOINT, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        api_response_text = response.text
        # Clean potential markdown fences (though less likely with json_object mode)
        cleaned_text = clean_json_response(api_response_text)

        # --- Parse OUTER JSON Response ---
        try:
            result_json = json.loads(cleaned_text)
            logger.info("Successfully parsed OUTER JSON response from ASI-1.")
            # logger.debug(f"Outer JSON: {result_json}") # Optional debug log

            # --- Safely Access and Parse INNER JSON Content ---
            try:
                inner_content_str = result_json['choices'][0]['message']['content']
                # Sometimes the inner content might have escaped quotes, try cleaning again
                inner_content_str_cleaned = clean_json_response(inner_content_str)

                try:
                    inner_data = json.loads(inner_content_str_cleaned)
                    logger.info("Successfully parsed INNER JSON content.")
                    # logger.debug(f"Inner Data: {inner_data}") # Optional debug log

                    # --- Populate output_data using INNER_DATA ---
                    output_data = {
                        'word': inner_data.get('word', word), # Use original word as fallback
                        'word_arabic': inner_data.get('word_arabic', ''),
                        # Use 'phonetic' from inner_data for the 'phonetics' key Laravel expects
                        'phonetic': inner_data.get('phonetic', ''),
                        'meaning': inner_data.get('meaning', ''),
                        'synonyms': inner_data.get('synonyms', ''),
                        'antonyms': inner_data.get('antonyms', ''),
                        # Use 'example_sentence' from inner_data for the 'example' key Laravel expects
                        'example_sentence': inner_data.get('example_sentence', ''),
                        # Use 'example_sentence_arabic' from inner_data for the 'example_arabic' key
                        'example_sentence_arabic': inner_data.get('example_sentence_arabic', ''),
                        'url': inner_data.get('url', ''),
                        'question': inner_data.get('question', ''),
                        'icon': '', # Add empty icon field as Laravel expects it
                        'description': '' # Will be filled below
                    }
                    logger.info("Populated output_data from inner JSON.")
                    # logger.debug(f"Initial output_data: {output_data}") # Optional debug log

                    # --- Format Description ---
                    url = output_data['url']
                    question = output_data['question'] or 'What do you think about this word?'
                    response_word = output_data['word']
                    word_capitalized = response_word.capitalize()
                    description = f"""<b>#{response_word.capitalize()} Word of the Day: {response_word}</b>

🗣 Your Turn!
<i>{question}</i>
Share it below!

🔗 <a href="{url}">Read More</a>
📌 #Daily{word_capitalized} | {TELEGRAM_CHAT_ID or '@your_channel'}"""
                    output_data['description'] = description.strip()

                    logger.info(f"Final output_data prepared: {output_data}")
                    return output_data # Return the structured dictionary

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode INNER JSON content string: {e}")
                    logger.error(f"Inner content string was: {inner_content_str_cleaned}")
                    return None

            except (KeyError, IndexError, TypeError) as e:
                logger.error(f"Failed to access nested content in ASI-1 response structure: {e}")
                logger.error(f"Outer JSON structure was: {result_json}")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode OUTER JSON response: {e}")
            logger.error(f"Cleaned response text was: {cleaned_text}")
            return None
        except Exception as e:
             logger.error(f"Error processing ASI-1 response content: {e}")
             return None

    except requests.exceptions.RequestException as e:
        logger.error(f"ASI-1 API request failed: {e}")
        if e.response is not None:
             logger.error(f"Status Code: {e.response.status_code}, Response: {e.response.text[:200]}...")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during ASI-1 call: {e}")
        return None