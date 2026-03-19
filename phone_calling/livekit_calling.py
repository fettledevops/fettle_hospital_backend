import asyncio
from dotenv import load_dotenv
from livekit import api
import json
import os

load_dotenv()

AGENT_NAME = "amor-inb-final"


async def _dispatch_call(phone_number: str, id_key: str):
    print("Initiating SIP Outbound call to", phone_number, "via room", id_key)
    async with api.LiveKitAPI() as livekit_api:
        # 1. Dispatch the Agent to the room
        await livekit_api.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME,
                room=id_key,
                metadata=json.dumps(
                    {"phone_number": phone_number, "id_key": id_key, "type": "outbound"}
                ),
            )
        )

        # 2. Invite the Patient via SIP (CloudConnect Trunk)
        # Assuming Asterisk/CloudConnect configuration is handled via SIP Trunks in LiveKit
        # or direct SIP participant creation.
        try:
            await livekit_api.sip.create_sip_participant(
                api.CreateSipParticipantRequest(
                    sip_trunk_id=os.getenv(
                        "LIVEKIT_SIP_TRUNK_ID"
                    ),  # Needs to be set in .env
                    sip_call_to=phone_number,
                    room_name=id_key,
                    participant_name="Patient",
                    participant_identity=f"sip_{phone_number}",
                )
            )
            print(f"SIP Participant created for {phone_number}")
        except Exception as e:
            print(f"Error creating SIP participant: {str(e)}")


def dispatch_call(phone_number: str, id_key: str):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_dispatch_call(phone_number, id_key))
    finally:
        loop.close()


# dispatch_call("+918360039458", "1234567")
