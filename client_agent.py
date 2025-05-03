# client_agent.py
from uagents import Agent, Context, Protocol
from uagents.setup import fund_agent_if_low

# Import shared models
from models import AgreementDraft, Approval, PaymentNotification # Hypothetical TransactAI model

# --- Configuration ---
# !! REPLACE THESE PLACEHOLDERS !!
CLIENT_SEED = "my_very_secret_client_seed_phrase_456" # Make this unique and secret
# This will be filled in after running creator_agent.py once
CREATOR_AGENT_ADDRESS = "agent1qveeesvz20h9029s2rpwt7n7tfuh7090v9wps6vh6d5ek97yetywgh85yu2"

if CREATOR_AGENT_ADDRESS == "agent1qveeesvz20h9029s2rpwt7n7tfuh7090v9wps6vh6d5ek97yetywgh85yu2":
    print("WARNING: CREATOR_AGENT_ADDRESS not set. Run creator_agent.py first and fill this in.")

# --- Agent Setup ---
agent = Agent(
    name="client_agent",
    port=8001, # Use a different port than the creator agent
    seed=CLIENT_SEED,
    endpoint=["http://127.0.0.1:8001/submit"],
)

# Fund the agent if needed
fund_agent_if_low(agent.wallet.address())

# Create a protocol
client_proto = Protocol("ClientCommission")

@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Client Agent started!")
    ctx.logger.info(f"My address is: {agent.address}")

# --- Message Handlers ---

@client_proto.on_message(model=AgreementDraft)
async def handle_agreement_draft(ctx: Context, sender: str, msg: AgreementDraft):
    ctx.logger.info(f"Received agreement draft for commission {msg.commission_id} from {sender}.")
    ctx.logger.info(f"Draft Text: {msg.draft_text}")

    # --- Simulate Approval ---
    # For the hackathon demo, automatically approve.
    # In a real scenario, you might have user interaction here.
    ctx.logger.info(f"Automatically approving commission {msg.commission_id}.")
    await ctx.send(
        CREATOR_AGENT_ADDRESS,
        Approval(commission_id=msg.commission_id, approved=True),
    )

# --- TransactAI Handling ---
# This handler depends on the ACTUAL model TransactAI sends to recipients.
# Replace `PaymentNotification` with the correct model from TransactAI docs.
@client_proto.on_message(model=PaymentNotification)
async def handle_payment_notification(ctx: Context, sender: str, msg: PaymentNotification):
    # This message comes FROM the TransactAI agent (sender)
    ctx.logger.info(f"Received payment notification from TransactAI ({sender}):")
    ctx.logger.info(f"  Amount: {msg.amount} {msg.denomination}")
    ctx.logger.info(f"  Status: {msg.status}")
    ctx.logger.info(f"  Sender: {msg.sender_address}") # Address of the original payer (Creator Agent)
    ctx.logger.info(f"  Notes: {msg.notes}")
    # You could add logic here based on the payment status

# Include the protocol
agent.include(client_proto)

# Run the agent
if __name__ == "__main__":
    agent.run()
