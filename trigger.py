# trigger.py
from uagents import Agent, Context
from uagents.setup import fund_agent_if_low
from models import CommissionRequest

# !! REPLACE WITH THE CREATOR AGENT'S ADDRESS !!
CREATOR_AGENT_ADDRESS = "agent1qveeesvz20h9029s2rpwt7n7tfuh7090v9wps6vh6d5ek97yetywgh85yu2"

if CREATOR_AGENT_ADDRESS == "FILL_IN_CREATOR_AGENT_ADDRESS_HERE":
    print("Please fill in the CREATOR_AGENT_ADDRESS in trigger.py")
    exit()

trigger_agent = Agent(name="trigger", seed="trigger_seed_phrase")
fund_agent_if_low(trigger_agent.wallet.address())

@trigger_agent.on_event("startup")
async def send_commission(ctx: Context):
    ctx.logger.info(f"Sending commission request to {CREATOR_AGENT_ADDRESS}")
    try:
        await ctx.send(
            CREATOR_AGENT_ADDRESS,
            CommissionRequest(
                client_name="Walter Dark Inc.",
                task_description="Design a company logo",
                budget=500.00,
                deadline="2025-05-10",
            ),
        )
        ctx.logger.info("Commission request sent.")
    except Exception as e:
        ctx.logger.error(f"Failed to send commission request: {e}")
    # Optional: Shut down after sending
    # await asyncio.sleep(2.0) # Allow time for message to send
    # ctx.logger.info("Trigger agent shutting down.")
    # ctx.agent.stop()


if __name__ == "__main__":
    trigger_agent.run()

