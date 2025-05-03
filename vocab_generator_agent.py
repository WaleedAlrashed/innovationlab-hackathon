# vocab_generator_agent.py
import os
import requests
import json
import re
from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents.setup import fund_agent_if_low
from models import WordRequest
import time # For unique filenames

# Import utility functions
from publishing_utils import (
    render_html_template,
    # generate_image_url, # No longer needed
    generate_image_local, # New function
    # post_to_telegram, # No longer needed
    post_image_to_telegram, # New function
    encode_image_base64,
    logger as utils_logger
)

# --- Load Environment Variables ---
load_dotenv()

# --- Configuration ---
VOCAB_AGENT_SEED = os.environ.get("VOCAB_AGENT_SEED", "my_very_secret_vocab_agent_seed_789")
ASI_API_KEY = os.environ.get("ASI_API_KEY")
ASI_API_ENDPOINT = os.environ.get("ASI_API_ENDPOINT", "https://api.asi1.ai/v1/chat/completions")
# Load secrets needed by utility functions (HCTI keys no longer needed for generation)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
BACKGROUND_IMAGE_PATH = "assets/images/post_background.png"
HTML_TEMPLATE_FILE = "post_template.html"
# Define where to save temporary images
IMAGE_OUTPUT_DIR = "generated_images" # Create this directory

# --- Pre-encode background image ---
background_image_base64 = encode_image_base64(BACKGROUND_IMAGE_PATH)

# --- Check if essential secrets are loaded ---
essential_secrets_loaded = all([ASI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID])

# --- Create output directory if it doesn't exist ---
if not os.path.exists(IMAGE_OUTPUT_DIR):
    try:
        os.makedirs(IMAGE_OUTPUT_DIR)
    except OSError as e:
        print(f"Error creating directory {IMAGE_OUTPUT_DIR}: {e}")
        # Handle error appropriately, maybe exit or disable image generation

# --- Agent Setup ---
agent = Agent(
    name="vocab_generator",
    port=8002,
    seed=VOCAB_AGENT_SEED,
    endpoint=["http://127.0.0.1:8002/submit"],
)
fund_agent_if_low(agent.wallet.address())
vocab_proto = Protocol("VocabularyGeneration")

@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Vocabulary Generator Agent started!")
    ctx.logger.info(f"My address is: {agent.address}")
    if not background_image_base64:
         ctx.logger.warning(f"Could not load or encode background image from {BACKGROUND_IMAGE_PATH}. Images will lack background.")
    if not essential_secrets_loaded:
         ctx.logger.warning("Missing ASI key or Telegram info in .env. Full publishing may fail.")

def clean_json_response(text: str) -> str:
    text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()
    return text

# --- Message Handler ---
@vocab_proto.on_message(model=WordRequest)
async def handle_word_request(ctx: Context, sender: str, msg: WordRequest):
    ctx.logger.info(f"Received word request from {sender}: {msg.word}")
    word = msg.word.strip().lower()
    # Simplified prompt
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

    ctx.logger.info(f"Calling ASI-1 Mini for word: {word}")
    headers = {"Authorization": f"bearer {ASI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "asi1-mini", "messages": [{"role": "user", "content": formatted_prompt}],
        "max_tokens": 1000, "temperature": 0.7, "stream": False,
        "response_format": {"type": "json_object"}
    }

    error_message = None
    result_json = None

    try:
        # --- 1. Get Data from ASI-1 ---
        response = requests.post(ASI_API_ENDPOINT, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        api_response_text = response.text
        cleaned_text = clean_json_response(api_response_text)
        # ctx.logger.info(f"Cleaned ASI-1 Response: {cleaned_text[:200]}...") # Already logged in util

        try:
            result_json = json.loads(cleaned_text)
            ctx.logger.info("Successfully parsed JSON response from ASI-1.")

            # Ensure all required fields are present with defaults if missing
            required_fields = {
                'word': word,
                'word_arabic': result_json.get('word_arabic', ''),
                'phonetic': result_json.get('phonetic', ''),
                'meaning': result_json.get('meaning', ''),
                'synonyms': result_json.get('synonyms', ''),
                'antonyms': result_json.get('antonyms', ''),
                'example_sentence': result_json.get('example_sentence', ''),
                'example_sentence_arabic': result_json.get('example_sentence_arabic', '')
            }
            
            # Update result_json with any missing fields
            result_json.update(required_fields)

            # --- Format Description ---
            url = result_json.get('url', '')
            question = result_json.get('question', 'What do you think about this word?')
            response_word = result_json.get('word', word)
            word_capitalized = response_word.capitalize()
            description = f"""<b>#{response_word.capitalize()} Word of the Day: {response_word}</b>

🗣 Your Turn!
<i>{question}</i>
Share it below!

🔗 <a href="{url}">Read More</a>
📌 #Daily{word_capitalized} | {TELEGRAM_CHAT_ID}"""
            result_json['description'] = description.strip()

        except json.JSONDecodeError as e:
            ctx.logger.error(f"Failed to decode JSON from ASI-1 response: {e}")
            error_message = f"Failed to parse JSON response: {e}"
        except Exception as e:
             ctx.logger.error(f"Error processing ASI-1 response content: {e}")
             error_message = f"Error processing response: {e}"

    except requests.exceptions.RequestException as e:
        ctx.logger.error(f"ASI-1 API request failed: {e}")
        if e.response is not None:
             ctx.logger.error(f"Status Code: {e.response.status_code}, Response: {e.response.text[:200]}...")
        error_message = f"API request failed: {e}"
    except Exception as e:
        ctx.logger.error(f"An unexpected error occurred during ASI-1 call: {e}")
        error_message = f"An unexpected error occurred: {e}"

    # --- Proceed with publishing only if ASI-1 call was successful ---
    if result_json and not error_message:
        ctx.logger.info(f"Successfully generated vocabulary data for word '{word}'.")
        # ctx.logger.info(f"Formatted Description:\n{result_json.get('description', 'N/A')}") # Logged by util now
        # ctx.logger.info(f"Full Generated Data: {json.dumps(result_json, indent=2)}") # Logged by util now

        # --- 2. Generate Image Locally ---
        html_content = render_html_template(HTML_TEMPLATE_FILE, result_json, background_image_base64)
        local_image_path = None
        if html_content:
            # Create a unique filename
            timestamp = int(time.time())
            output_filename = f"{word}_{timestamp}.png"
            full_output_path = os.path.join(IMAGE_OUTPUT_DIR, output_filename)

            # Generate the image locally
            local_image_path = generate_image_local(
                html_content=html_content,
                output_filename=output_filename
                # Add css_content= if you have separate CSS string/file
            )

        # --- 3. Post to Telegram ---
        if local_image_path: # Check if image generation was successful
            post_success = post_image_to_telegram(
                bot_token=TELEGRAM_BOT_TOKEN,
                chat_id=TELEGRAM_CHAT_ID,
                image_path=local_image_path, # Pass the local file path
                caption=result_json['description'],
                parse_mode="HTML"
            )
            if post_success:
                ctx.logger.info("Publishing workflow completed successfully.")
                # --- 4. Optional: Clean up generated image ---
                try:
                    os.remove(local_image_path)
                    ctx.logger.info(f"Cleaned up temporary image: {local_image_path}")
                except OSError as e:
                    ctx.logger.warning(f"Could not delete temporary image {local_image_path}: {e}")
            else:
                ctx.logger.error("Publishing workflow failed during Telegram posting.")
        else:
             ctx.logger.error("Publishing workflow failed because image could not be generated locally.")

    else:
        # Log the initial error from ASI-1 call or JSON parsing
        ctx.logger.error(f"Failed to generate vocabulary data for word '{word}'. Error: {error_message or 'Unknown error during generation.'}")


# Include the protocol
agent.include(vocab_proto)

# Run the agent
if __name__ == "__main__":
    agent.run()
