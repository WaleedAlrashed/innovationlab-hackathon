# trigger.py
import asyncio # <-- Import asyncio
from uagents import Agent, Context
from uagents.setup import fund_agent_if_low
from models import CommissionRequest

CREATOR_AGENT_ADDRESS = "agent1qveeesvz20h9029s2rpwt7n7tfuh7090v9wps6vh6d5ek97yetywgh85yu2" # Make sure this is correct!

if CREATOR_AGENT_ADDRESS == "FILL_IN_CREATOR_AGENT_ADDRESS_HERE":
    print("Please fill in the CREATOR_AGENT_ADDRESS in trigger.py")
    exit()

# No need to specify port, as we won't keep the server running long
trigger_agent = Agent(name="trigger", seed="trigger_seed_phrase")
fund_agent_if_low(trigger_agent.wallet.address())

@trigger_agent.on_event("startup")
async def send_commission(ctx: Context):
    ctx.logger.info(f"Sending commission request to {CREATOR_AGENT_ADDRESS}")
    try:
        await ctx.send(
            CREATOR_AGENT_ADDRESS,
            CommissionRequest(
                client_name="Test Client Inc.",
                task_description="Design a company logo",
                budget=500.00,
                deadline="2025-05-10",
            ),
        )
        ctx.logger.info("Commission request sent.")
    except Exception as e:
        ctx.logger.error(f"Failed to send commission request: {e}")

    # --- Add these lines ---
    ctx.logger.info("Task complete, trigger agent shutting down.")
    # Give a very short delay to ensure the message is dispatched
    await asyncio.sleep(1.0)
    # Stop the agent's execution loop
    ctx.agent.stop()
    # --- End of added lines ---


if __name__ == "__main__":
    trigger_agent.run()
    # The script will exit shortly after agent.stop() is called
