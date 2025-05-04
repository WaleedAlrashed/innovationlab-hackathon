# vocab_generator_agent.py
import os
import requests
import json
import re
from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents.setup import fund_agent_if_low
from models import WordRequest
import time  # For unique filenames

# Import utility functions
from publishing_utils import (
    generate_vocab_data
)

# --- Load Environment Variables ---
load_dotenv()

# --- Configuration ---
VOCAB_AGENT_SEED = os.environ.get("VOCAB_AGENT_SEED", "my_very_secret_vocab_agent_seed_789")
ASI_API_KEY = os.environ.get("ASI_API_KEY")
ASI_API_ENDPOINT = os.environ.get("ASI_API_ENDPOINT", "https://api.asi1.ai/v1/chat/completions")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
BACKGROUND_IMAGE_PATH = "assets/images/post_background.png"
HTML_TEMPLATE_FILE = "post_template.html"
IMAGE_OUTPUT_DIR = "generated_images"


# --- Check if essential secrets are loaded ---
essential_secrets_loaded = all([ASI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID])

# --- Create output directory if it doesn't exist ---
if not os.path.exists(IMAGE_OUTPUT_DIR):
    try:
        os.makedirs(IMAGE_OUTPUT_DIR)
    except OSError as e:
        print(f"Error creating directory {IMAGE_OUTPUT_DIR}: {e}")

# --- Agent Setup ---
agent = Agent(
    name="vocab_generator",
    port=8002,
    seed=VOCAB_AGENT_SEED,
    endpoint=["http://127.0.0.1:8002/submit"],
    mailbox=True
)
fund_agent_if_low(agent.wallet.address())
vocab_proto = Protocol("VocabularyGeneration")


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Vocabulary Generator Agent started!")
    ctx.logger.info(f"My address is: {agent.address}")
    if not essential_secrets_loaded:
        ctx.logger.warning("Missing ASI key or Telegram info in .env. Full publishing may fail.")


def clean_json_response(text: str) -> str:
    text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()
    return text


def crete_image_api_call(payload: dict) -> str:
    """
    Call the ASI-1 Mini API to generate an image.
    """

    url = "https://tools.waleedalrashed.com/api/posts/image"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/113.0.0.0 Safari/537.36"

    }
    try:
        response = requests.post(url,headers=headers, json=payload)
        if response.status_code in [200, 201]:
            image_path = response.json().get("image_url")
            return image_path
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error calling image API: {e}")
        return None

# --- Message Handler ---
@vocab_proto.on_message(model=WordRequest)
async def handle_word_request(ctx: Context, sender: str, msg: WordRequest):
    ctx.logger.info(f"Received word request from {sender}: {msg.word}")
    image_path = ""  # TODO
    word = msg.word.strip().lower()

    image_path = ctx.storage.get(word)

    if image_path:
        ctx.logger.info(f"Word '{word}' already exists in storage. Returning existing data.")
        await ctx.send(
            destination=sender,
            message=WordRequest(word=image_path),
            timeout=60,
        )
        return
    ctx.logger.info(f"Calling ASI-1 Mini for word: {word}")


    try:
        json_payload = await generate_vocab_data(word)

        image_path = crete_image_api_call(json_payload)
        ctx.logger.info(f"Image path: {image_path}")
        ctx.storage.set(word, image_path)

        api_response_text = await ctx.send(
            destination=sender,
            message=WordRequest(word=image_path),
            timeout=60,
        )
        if api_response_text.status == api_response_text.status.FAILED:
            raise ValueError(f"Agent SDK returned no data. {api_response_text}")
        ctx.logger.info(f"Successfully received response from Agent SDK. {api_response_text.detail}")
    except Exception as e:
        ctx.logger.error(f"Failed to generate vocabulary data for word: {word}: {e}")
# Include the protocol
agent.include(vocab_proto)

# Run the agent
if __name__ == "__main__":
    agent.run()