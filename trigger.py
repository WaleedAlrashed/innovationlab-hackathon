# trigger.py (Corrected Again)
import asyncio
from uagents import Agent, Context
from uagents.setup import fund_agent_if_low
from models import WordRequest

# !! REPLACE WITH THE VOCAB GENERATOR AGENT'S ADDRESS !!
VOCAB_AGENT_ADDRESS = "agent1qvmpklewvc668xawcgv6vnfkqmdccghnd26efsm7ps5a5rdc57rfz4ftlt8" # Make sure this is correct!

if VOCAB_AGENT_ADDRESS == "FILL_IN_VOCAB_AGENT_ADDRESS_HERE":
    print("Please fill in the VOCAB_AGENT_ADDRESS in trigger.py")
    exit()

# Define the agent
trigger_agent = Agent(name="trigger", seed="trigger_seed_phrase_abc")
fund_agent_if_low(trigger_agent.wallet.address())

@trigger_agent.on_event("startup")
async def send_word(ctx: Context):
    target_word = "browser" # The word you want to generate content for
    ctx.logger.info(f"Sending word request for '{target_word}' to {VOCAB_AGENT_ADDRESS}")
    try:
        # Send the message
        await ctx.send(
            VOCAB_AGENT_ADDRESS,
            WordRequest(word=target_word),
        )
        ctx.logger.info("Word request sent.")
    except Exception as e:
        ctx.logger.error(f"Failed to send word request: {e}")

    # No explicit stop needed here.
    # The agent should exit after this handler finishes.
    ctx.logger.info("Startup task complete.")


if __name__ == "__main__":
    # Run the agent. It will execute the startup task and then exit.
    trigger_agent.run()
    print("Trigger agent finished execution.") # Added print statement
