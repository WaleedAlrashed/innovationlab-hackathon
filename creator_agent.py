# creator_agent.py
import os
import uuid
import requests # For making HTTP requests to ASI-1
from uagents import Agent, Context, Protocol
from uagents.setup import fund_agent_if_low

# Import shared models
from models import (
    CommissionRequest,
    AgreementDraft,
    Approval,
    PaymentRequest, # Hypothetical TransactAI model
)

# --- Configuration ---
# !! REPLACE THESE PLACEHOLDERS !!
CREATOR_SEED = "my_very_secret_creator_seed_phrase_123" # Make this unique and secret
# Get API Key from asi1.ai platform
ASI_API_KEY = os.environ.get("ASI_API_KEY", "sk_d811ec74abde421eb3afa6c0fce1d3a4cac9b9ff111b4d3eb1f8a15fd0ce69b5")
# Get API Endpoint from asi1.ai platform documentation
ASI_API_ENDPOINT = os.environ.get(
    "ASI_API_ENDPOINT", "https://asi1.ai/v1/chat/completions"
) # Check ASI-1 docs!
# Get TransactAI agent address from hackathon resources
TRANSACTAI_AGENT_ADDRESS = (
    "agent1qtdvskm3g5ngmvfuqek6shrpjz6ed8jc84s6phmark05z5a8naxawu5jsrq" # From Ishaan's resources
)
# This will be filled in after running client_agent.py once
CLIENT_AGENT_ADDRESS = "hagent1qwqlsjqn0qgct6fnlsjj55u5a8034y728x7a36hkd36gue9y9dg7snp53nm"

if ASI_API_KEY == "sk_d811ec74abde421eb3afa6c0fce1d3a4cac9b9ff111b4d3eb1f8a15fd0ce69b5":
    print("WARNING: ASI_API_KEY not set. Please set environment variable or replace placeholder.")
if CLIENT_AGENT_ADDRESS == "FILL_IN_CLIENT_AGENT_ADDRESS_HERE":
    print("WARNING: CLIENT_AGENT_ADDRESS not set. Run client_agent.py first and fill this in.")

# --- Agent Setup ---
agent = Agent(
    name="creator_agent",
    port=8000,
    seed=CREATOR_SEED,
    endpoint=["http://127.0.0.1:8000/submit"],
)

# Fund the agent if needed (for interacting with Fetch.ai network if required by TransactAI)
fund_agent_if_low(agent.wallet.address())

# Create a protocol for easier handling
creator_proto = Protocol("CreatorCommission")

@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Creator Agent started!")
    ctx.logger.info(f"My address is: {agent.address}")
    # Ensure storage is initialized for budget tracking
    if ctx.storage.get("commissions") is None:
        ctx.storage.set("commissions", {})

# --- Message Handlers ---

@creator_proto.on_message(model=CommissionRequest)
async def handle_commission_request(ctx: Context, sender: str, msg: CommissionRequest):
    ctx.logger.info(f"Received commission request from {sender}: {msg.task_description}")

    commission_id = str(uuid.uuid4()) # Generate unique ID

    # --- ASI-1 Mini Integration ---
    ctx.logger.info("Calling ASI-1 Mini to draft agreement...")
    prompt = (
        f"You are an AI assistant helping a creator. Based on the following commission request, "
        f"draft a very simple 2-sentence agreement summary. Include client name, task description, "
        f"budget (${msg.budget}), and deadline ({msg.deadline}).\n\n"
        f"Client: {msg.client_name}\nTask: {msg.task_description}\nBudget: ${msg.budget}\nDeadline: {msg.deadline}"
    )

    headers = {
        "Authorization": f"Bearer {ASI_API_KEY}",
        "Content-Type": "application/json",
    }
    # NOTE: The payload structure depends HEAVILY on the ASI-1 API documentation.
    # This is a common structure for OpenAI-compatible APIs. CHECK THE DOCS!
    payload = {
        "model": "asi-1-mini", # Or whatever the correct model name is
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 150, # Adjust as needed
        # Add other parameters like temperature if desired
    }

    draft_text = "Error generating draft." # Default error text
    try:
        response = requests.post(ASI_API_ENDPOINT, headers=headers, json=payload, timeout=30)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        api_response = response.json()

        # --- Extract Response ---
        # Again, this depends ENTIRELY on the actual API response structure. Check ASI-1 docs!
        # This assumes an OpenAI-like structure.
        if api_response.get("choices") and len(api_response["choices"]) > 0:
            message = api_response["choices"][0].get("message")
            if message and message.get("content"):
                draft_text = message["content"].strip()
                ctx.logger.info("ASI-1 Mini draft generated successfully.")
            else:
                ctx.logger.error(f"ASI-1 response format unexpected (message/content missing): {api_response}")
        else:
            ctx.logger.error(f"ASI-1 response format unexpected (choices missing): {api_response}")

    except requests.exceptions.RequestException as e:
        ctx.logger.error(f"ASI-1 API request failed: {e}")
    except Exception as e:
        ctx.logger.error(f"Error processing ASI-1 response: {e}")
        ctx.logger.error(f"ASI-1 Raw Response: {response.text if 'response' in locals() else 'No response object'}")


    # --- Store and Send Draft ---
    # Store commission details (budget needed for payment later)
    commissions = ctx.storage.get("commissions")
    commissions[commission_id] = {"budget": msg.budget, "draft": draft_text}
    ctx.storage.set("commissions", commissions)

    ctx.logger.info(f"Sending draft for commission {commission_id} to client.")
    await ctx.send(
        CLIENT_AGENT_ADDRESS,
        AgreementDraft(commission_id=commission_id, draft_text=draft_text),
    )

@creator_proto.on_message(model=Approval)
async def handle_approval(ctx: Context, sender: str, msg: Approval):
    ctx.logger.info(f"Received approval status for commission {msg.commission_id}: {msg.approved}")

    if msg.approved:
        commissions = ctx.storage.get("commissions")
        commission_data = commissions.get(msg.commission_id)

        if commission_data and commission_data.get("budget"):
            budget = commission_data["budget"]
            ctx.logger.info(f"Commission approved. Requesting payment of ${budget} via TransactAI.")

            # --- TransactAI Integration ---
            # Use the ACTUAL model defined by TransactAI
            payment_msg = PaymentRequest(
                recipient_address=CLIENT_AGENT_ADDRESS, # Pay the client agent
                amount=float(budget),
                denomination="USD", # CHECK TransactAI DOCS for correct denomination
                notes=f"Payment for approved commission {msg.commission_id}"
            )
            try:
                await ctx.send(TRANSACTAI_AGENT_ADDRESS, payment_msg)
                ctx.logger.info("Payment request sent to TransactAI.")
            except Exception as e:
                ctx.logger.error(f"Failed to send payment request to TransactAI: {e}")
        else:
            ctx.logger.warning(f"Could not find budget for approved commission {msg.commission_id}. Cannot request payment.")
    else:
        ctx.logger.info(f"Commission {msg.commission_id} was not approved.")
        # Optionally, clean up stored data here
        # commissions = ctx.storage.get("commissions")
        # if msg.commission_id in commissions:
        #     del commissions[msg.commission_id]
        #     ctx.storage.set("commissions", commissions)

# Include the protocol in the agent
agent.include(creator_proto)

# Run the agent
if __name__ == "__main__":
    agent.run()