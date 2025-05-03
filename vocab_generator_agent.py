# vocab_generator_agent.py
import os
import requests # For making HTTP requests to ASI-1
import json
import re # For cleaning the response
from uagents import Agent, Context, Protocol
from uagents.setup import fund_agent_if_low

# Import shared models
from models import WordRequest # We no longer need VocabResponse here

# --- Configuration ---
# !! REPLACE THESE PLACEHOLDERS !!
VOCAB_AGENT_SEED = "my_very_secret_vocab_agent_seed_789" # Make unique and secret
# Get API Key from asi1.ai platform
ASI_API_KEY = os.environ.get("ASI_API_KEY", "sk_d811ec74abde421eb3afa6c0fce1d3a4cac9b9ff111b4d3eb1f8a15fd0ce69b5")
# Get API Endpoint from asi1.ai platform documentation - CORRECTED URL
ASI_API_ENDPOINT = os.environ.get(
    "ASI_API_ENDPOINT", "https://api.asi1.ai/v1/chat/completions" # <-- CORRECTED
)

if ASI_API_KEY == "YOUR_ASI1_API_KEY_HERE":
    print("WARNING: ASI_API_KEY not set. Please set environment variable or replace placeholder.")

# --- Agent Setup ---
agent = Agent(
    name="vocab_generator",
    port=8002, # Use a different port
    seed=VOCAB_AGENT_SEED,
    endpoint=["http://127.0.0.1:8002/submit"],
)

# Fund the agent if needed (might not be necessary if only calling external APIs)
fund_agent_if_low(agent.wallet.address())

# Create a protocol
vocab_proto = Protocol("VocabularyGeneration")

@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Vocabulary Generator Agent started!")
    ctx.logger.info(f"My address is: {agent.address}")

def clean_json_response(text: str) -> str:
    """Cleans the LLM response to extract JSON."""
    # Remove Markdown code block fences (```json ... ```)
    text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    # Remove potential leading/trailing whitespace and newlines that might remain
    text = text.strip()
    return text

# --- Message Handler ---
# Removed replies=VocabResponse as we now log instead of replying
@vocab_proto.on_message(model=WordRequest)
async def handle_word_request(ctx: Context, sender: str, msg: WordRequest):
    ctx.logger.info(f"Received word request from {sender}: {msg.word}")
    word = msg.word.strip().lower() # Normalize the word

    # --- Format Prompt for ASI-1 Mini (adapted from your PHP) ---
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
10. question (one-line question related to the word, e.g., for 'reverie': What’s your favorite reverie or daydream?)
11. icon (a simple, single-color SVG code string for an icon that resembles the english word, the SVG MUST have a transparent background, use viewBox='0 0 100 100')

notes: response should be returned as valid json object only, do not include any text before or after the json object, ensure all keys are present.
"""

    # --- ASI-1 Mini API Call ---
    ctx.logger.info(f"Calling ASI-1 Mini for word: {word}")
    headers = {
        # Use lowercase 'bearer' as per ASI-1 docs example
        "Authorization": f"bearer {ASI_API_KEY}",
        "Content-Type": "application/json",
    }
    # Adapt payload structure based on ASI-1 documentation
    payload = {
        "model": "asi1-mini", # Verify model name
        "messages": [{"role": "user", "content": formatted_prompt}],
        "max_tokens": 1500, # Increased token limit
        "temperature": 0.7, # Adjust creativity/consistency
        "stream": False, # Added stream parameter as per docs example
        "response_format": {"type": "json_object"} # Request JSON mode if supported
    }

    error_message = None
    result_json = None

    try:
        response = requests.post(ASI_API_ENDPOINT, headers=headers, json=payload, timeout=60) # Increased timeout
        response.raise_for_status() # Check for HTTP errors (like 404, 401, etc.)
        api_response_text = response.text # Get raw text first

        # --- Clean and Parse Response ---
        cleaned_text = clean_json_response(api_response_text)
        ctx.logger.info(f"Cleaned ASI-1 Response: {cleaned_text[:200]}...") # Log beginning of cleaned text

        try:
            result_json = json.loads(cleaned_text) # Parse the cleaned JSON
            ctx.logger.info("Successfully parsed JSON response from ASI-1.")

            # --- Format Post Description ---
            url = result_json.get('url', '')
            question = result_json.get('question', 'What do you think about this word?')
            # Use the word from the JSON response if available, otherwise fallback to input
            response_word = result_json.get('word', word)
            word_capitalized = response_word.capitalize()

            post_description = f"""
#DailyLex Word of the Day: {response_word}

🗣 Your Turn!
{question}
Share it below!

🔗 Read More ({url})
📌 #Daily{word_capitalized} | @dailylex_en
"""
            # Add the description to the result
            result_json['description'] = post_description.strip()

        except json.JSONDecodeError as e:
            ctx.logger.error(f"Failed to decode JSON from ASI-1 response: {e}")
            ctx.logger.error(f"Raw Response Text: {api_response_text}")
            error_message = f"Failed to parse JSON response: {e}"
        except Exception as e: # Catch other potential errors during processing
             ctx.logger.error(f"Error processing ASI-1 response content: {e}")
             error_message = f"Error processing response: {e}"

    except requests.exceptions.RequestException as e:
        ctx.logger.error(f"ASI-1 API request failed: {e}")
        # Specifically log the status code if available
        if e.response is not None:
             ctx.logger.error(f"Status Code: {e.response.status_code}, Response: {e.response.text[:200]}...")
        error_message = f"API request failed: {e}"
    except Exception as e: # Catch other unexpected errors
        ctx.logger.error(f"An unexpected error occurred: {e}")
        error_message = f"An unexpected error occurred: {e}"


    # --- Log Result or Error (Instead of Sending Back) ---
    if result_json and not error_message:
        # Log the successful result
        ctx.logger.info(f"Successfully generated vocabulary data for word '{word}':")
        # Log the formatted description
        ctx.logger.info(f"Formatted Description:\n{result_json.get('description', 'N/A')}")
        # Log the generated SVG icon if present and not empty
        generated_icon = result_json.get('icon')
        if generated_icon:
            ctx.logger.info(f"Generated Icon SVG: {generated_icon}")
        else:
            ctx.logger.warning("Generated data did not include an 'icon'.")
        # Optionally log the full data for debugging
        ctx.logger.info(f"Full Generated Data: {json.dumps(result_json, indent=2)}")

    else:
        # Log the error
        ctx.logger.error(f"Failed to generate vocabulary data for word '{word}'. Error: {error_message or 'Unknown error during generation.'}")
    # --- End of logging section ---


# Include the protocol
agent.include(vocab_proto)

# Run the agent
if __name__ == "__main__":
    agent.run()
