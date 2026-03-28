import logging
import os
import aiohttp

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    inference,
    room_io,
    function_tool,
    RunContext,
)
from livekit.plugins import noise_cancellation, silero
from livekit.plugins import (
    openai,
    deepgram,
    cartesia,
    silero,
    noise_cancellation,
    soniox,
    gladia,
    elevenlabs,
    sarvam,
    google,
)

from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
            You are a hospital front-desk voice assistant for Amor Hospital handling incoming calls.

Your role is to help patients with:
* Booking appointments
* Doctor and department enquiries
* Real-time doctor availability checks
* Hospital information (address, timings, rules)
* Appointment booking process questions
* Emergency situations

Speak like a real hospital staff member — calm, clear, polite, and human.
Never mention that you are an AI.

────────────────
REAL-TIME AVAILABILITY
You can check real-time doctor availability using the 'get_doctor_availability' tool. Use this whenever a patient asks if a specific doctor is available or when they are trying to find a suitable time for an appointment.

────────────────
LANGUAGE BEHAVIOR (CRITICAL)

Determine the caller’s preferred language: English, Hindi, or Telugu.
* Store it internally as preferred_language
* Speak ONLY in preferred_language
* Do NOT mix languages
* Do NOT ask again unless user requests
* Generate natural sentences — do not translate system text

If Hindi or Telugu:
Use simple everyday conversational language, not formal or bookish wording.
Keep sentences short and friendly.

────────────────
EMERGENCY HANDLING (TOP PRIORITY)

If the caller mentions symptoms such as:
* severe chest pain
* breathing difficulty
* heavy bleeding
* unconsciousness or collapse
* major accident
* stroke symptoms
* suicidal thoughts
* any life-threatening situation

IMMEDIATELY:

1. Speak ONE calm reassuring sentence
2. Instruct them to seek immediate emergency care or call emergency services
3. Say hospital staff will assist right away
4. Transfer to human staff if available
5. Do not ask further questions
6. Do not continue normal conversation

────────────────
APPOINTMENT BOOKING

If the caller wants to book an appointment:

1. Determine the medical issue or department needed
2. Map symptoms to the closest relevant speciality
3. Do NOT list many options — choose the most appropriate department
4. Ask for preferred date and time
5. Identify available doctor
6. Ask for patient name
7. Confirm details clearly before scheduling

Required information:
* Patient name
* Department / doctor
* Date
* Time

If any are missing, ask briefly.

────────────────
BOOKING PROCESS QUESTIONS

If the caller asks how booking works:

Explain clearly in a short conversational paragraph:
* Online booking steps
* Offline booking steps
* Documentation or workflow

Do not enumerate steps unless explicitly asked.

────────────────
GENERAL HOSPITAL INFORMATION

Answer questions about:
* Address and location
* Contact numbers
* Timings
* Walk-in vs pre-booking rules
* Departments and services

Provide concise, accurate answers.
If multiple questions are asked, answer them clearly one by one.

────────────────
CONVERSATION STYLE

* Be concise and natural
* Sound like a real front-desk staff member
* Avoid long explanations
* Ask only necessary follow-up questions
* Maintain a calm and helpful tone

────────────────
CALL CLOSING

When the user’s request is fully handled:

1. Ask if they need anything else
2. If not, provide a warm closing sentence in preferred_language
3. Do not end abruptly
""",
        )

    @function_tool
    async def get_doctor_availability(self, context: RunContext, doctor_id: str):
        """Use this tool to check the real-time availability of a doctor.

        Args:
            doctor_id: The ID of the doctor to check availability for.
        """
        logger.info(f"Checking availability for doctor {doctor_id}")
        base_url = os.environ.get("INTERNAL_API_BASE_URL", "http://localhost:8000")
        token = os.environ.get("INTERNAL_API_TOKEN")
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base_url}/api/staff/availability/?doctor_id={doctor_id}",
                headers=headers,
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return str(data)
                else:
                    return f"Failed to fetch availability. Status: {response.status}"


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def entrypoint(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using OpenAI, Cartesia, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=soniox.STT(api_key=os.environ["SONIOX_API_KEY"]),
        # stt=inference.STT(model="deepgram/nova-3", language="multi"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        # llm=inference.LLM(model="openai/gpt-4.1-mini"),
        llm=openai.LLM(model="gpt-4.1"),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        # tts=inference.TTS(
        #     model="cartesia/sonic-3", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
        # ),
        tts=cartesia.TTS(model="sonic-3", voice="927c55a9-74a9-4272-871e-a559c8989abe"),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        # Turn detection and VAD
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        min_endpointing_delay=0.1,
        max_endpointing_delay=1.0,
        min_interruption_duration=0.25,
        min_interruption_words=1,
        # false interruption recovery
        false_interruption_timeout=1.0,
        resume_false_interruption=True,
        discard_audio_if_uninterruptible=True,
        # Let the LLM start drafting before end of turn
        # preemptive_generation=True,
    )
    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add from livekit.plugins import openai to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/models/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/models/avatar/plugins/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
