# publishing_utils.py
import requests
import jinja2
import base64
import os
import logging
from html2image import Html2Image

# Configure logging for this module
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Jinja2 Environment Setup ---
# Calculate absolute path to the directory containing this script
script_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the absolute path to the 'templates' directory
templates_dir_abs_path = os.path.join(script_dir, "templates")
logger.info(f"Looking for templates in: {templates_dir_abs_path}") # Log the path being used

# Use the absolute path for the loader
template_loader = jinja2.FileSystemLoader(searchpath=templates_dir_abs_path)
template_env = jinja2.Environment(loader=template_loader, autoescape=True)

# --- Initialize Html2Image ---
# ... (hti initialization and browser path code remains the same) ...
hti = Html2Image()
hti.output_path = os.path.abspath("generated_images")
logger.info(f"Set html2image output path to: {hti.output_path}")

# --- Set Custom Browser Flags for New Headless Mode --- ADD THIS ---
# This explicitly tells Chrome to use the newer headless implementation
# Also hide scrollbars which is usually desirable for screenshots
hti.browser.flags = ['--headless=new', '--hide-scrollbars']
# If running in Docker or some CI environments, you might also need:
# hti.browser.flags.append('--no-sandbox')
logger.info(f"Set custom browser flags: {hti.browser.flags}")
# --- End of added section ---

try:
    chrome_paths = [
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary',
        '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
    ]
    for path in chrome_paths:
        if os.path.exists(path):
            hti.browser_path = path
            logger.info(f"Found browser at: {path}")
            break
    else:
        logger.warning("No compatible browser found in common locations. Using default browser path.")
except Exception as e:
    logger.warning(f"Could not set browser path: {e}")


# --- encode_image_base64 function remains the same ---
def encode_image_base64(image_path: str) -> str | None:
    # ... (no changes needed here) ...
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return encoded_string
    except FileNotFoundError:
        logger.error(f"Background image file not found at: {image_path}")
        return None
    except Exception as e:
        logger.error(f"Error encoding image {image_path}: {e}")
        return None

# --- render_html_template function --- ADD DEBUG CHECK ---
def render_html_template(template_filename: str, data: dict, background_base64: str | None) -> str | None:
    """Renders the HTML template with provided data and logs the output."""
    try:
        # --- ADD EXPLICIT FILE CHECK ---
        # Construct the full path Jinja2 *should* be finding
        full_template_path = os.path.join(templates_dir_abs_path, template_filename)
        logger.info(f"Explicitly checking for template file at: {full_template_path}")
        if not os.path.exists(full_template_path):
            logger.error(f"!!! File check FAILED. Template not found at calculated path: {full_template_path}")
            # Optionally list directory contents for debugging:
            try:
                logger.error(f"Contents of '{templates_dir_abs_path}': {os.listdir(templates_dir_abs_path)}")
            except Exception as list_e:
                logger.error(f"Could not list directory contents: {list_e}")
            return None # Exit early if file check fails
        else:
            logger.info(">>> File check PASSED. Template exists at calculated path.")
        # --- END EXPLICIT FILE CHECK ---

        # Now try to get the template using the filename (Jinja searches the configured path)
        template = template_env.get_template(template_filename)
        render_data = {'post': data, 'background_image_base64': background_base64}
        html_content = template.render(render_data)
        logger.info(f"Successfully rendered HTML template: {template_filename}")
        log_html_snippet = html_content[:500] + "..." + html_content[-100:] if len(html_content) > 600 else html_content
        logger.info(f"Rendered HTML (snippet):\n{log_html_snippet}")
        return html_content
    except jinja2.TemplateNotFound:
        # This error should ideally not happen now if the file check passed, but keep it as a fallback
        logger.error(f"Jinja2 TemplateNotFound Error for '{template_filename}' (even after file check).")
        return None
    except jinja2.TemplateError as e:
        logger.error(f"Failed to render HTML template '{template_filename}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during HTML rendering: {e}")
        return None


# --- generate_image_local function remains the same ---
def generate_image_local(html_content: str, css_content: str | None = None, output_filename: str = "temp_post_image.png", size: tuple = (540, 540)) -> str | None:
    # ... (no changes needed here) ...
    full_output_path = os.path.join(hti.output_path, output_filename)
    logger.info(f"Attempting to generate image locally, saving filename '{output_filename}' to directory '{hti.output_path}'")
    try:
        if not os.path.exists(hti.output_path):
            os.makedirs(hti.output_path)
            logger.info(f"Created output directory: {hti.output_path}")
        hti.screenshot(
            html_str=html_content,
            css_str=css_content if css_content else '',
            save_as=output_filename,
            size=size
        )
        if os.path.exists(full_output_path):
            logger.info(f"Successfully generated image locally: {full_output_path}")
            return full_output_path
        else:
             logger.error(f"Image generation command executed but output file not found at {full_output_path}")
             return None
    except Exception as e:
        logger.error(f"Failed to generate image using html2image: {e}")
        logger.error("Ensure Chrome or Edge is installed and accessible by html2image.")
        return None

# --- post_image_to_telegram function remains the same ---
def post_image_to_telegram(bot_token: str, chat_id: str, image_path: str, caption: str, parse_mode: str = "HTML") -> bool:
    # ... (no changes needed here) ...
    if not all([bot_token, chat_id, image_path, caption]):
         logger.error("Missing Telegram Bot Token, Chat ID, Image Path, or Caption. Cannot post.")
         return False
    if not os.path.exists(image_path):
        logger.error(f"Image file not found at path: {image_path}. Cannot post to Telegram.")
        return False
    telegram_api_url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    telegram_payload = {
        'chat_id': chat_id,
        'caption': caption,
        'parse_mode': parse_mode
    }
    success = False
    logger.info(f"Uploading local image {image_path} to Telegram channel {chat_id}...")
    try:
        with open(image_path, 'rb') as image_file:
            files = {'photo': (os.path.basename(image_path), image_file)}
            tg_response = requests.post(
                telegram_api_url,
                data=telegram_payload,
                files=files,
                timeout=45
            )
        tg_response.raise_for_status()
        response_data = tg_response.json()
        if response_data.get('ok'):
             logger.info(f"Successfully posted image to Telegram.")
             success = True
        else:
             logger.error(f"Telegram API error: {response_data.get('description')}")
    except FileNotFoundError:
        logger.error(f"Failed to open image file for upload: {image_path}")
    except requests.exceptions.Timeout:
        logger.error("Telegram API request timed out during image upload.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Telegram API request failed: {e}")
        if e.response is not None:
            logger.error(f"Telegram Status Code: {e.response.status_code}, Response: {e.response.text[:500]}...")
    except Exception as e:
        logger.error(f"An unexpected error occurred during Telegram posting: {e}")
    return success

