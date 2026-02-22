import asyncio
from dotenv import load_dotenv
from livekit import api
import json
load_dotenv()

AGENT_NAME = "assistant2"

async def _dispatch_call(phone_number: str, id_key: str):
    print("dispatching call to", phone_number, "with id_key", id_key)
    async with api.LiveKitAPI() as livekit_api:
        await livekit_api.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME,
                room=id_key,
                metadata=json.dumps({
                    "phone_number": phone_number,
                    "id_key": id_key
                })
            )
        )
def dispatch_call(phone_number: str, id_key: str):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_dispatch_call(phone_number, id_key))
    finally:
        loop.close()

# dispatch_call("+918360039458", "1234567")

