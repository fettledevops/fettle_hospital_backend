# Migration Guide: LiveKit to CloudConnect for Agentic Voice AI

This document outlines the necessary changes to the Fettle Backend when migrating from **LiveKit** to **CloudConnect** for handling voice agent telephony.

## 1. Backend Code Refactoring

The current system has two execution paths in `phone_calling/tasks.py`: one for **LiveKit** and one for **Vapi.ai**.

### `phone_calling/livekit_calling.py`
-   **Current:** Uses `livekit-api` to dispatch agents (`agent_dispatch.create_dispatch`) into a WebRTC room.
-   **Change:** This module will likely be **deprecated**. If CloudConnect is used as a SIP Trunk for Vapi.ai, you should transition all calls to the Vapi-only path. If you are building a custom SIP handler, you will need to replace this with a SIP signaling library (like `scapy` or a custom SIP gateway).

### `phone_calling/tasks.py`
-   **Current:** The `is_livekit: true` branch pulls transcripts and audio from `settings.LIVEKIT_BUCKET_NAME` on S3.
-   **Change:** You must implement a **Webhook Handler** for CloudConnect (or Vapi via CloudConnect) to receive the final call recording and transcript. You will need to manually upload these to your S3 bucket (`fettle-audio-transcript`) to ensure the **Admin Dashboard** and **Excel Exports** still function.

## 2. Termination & Origination URLs

Unlike LiveKit, which uses WebRTC signaling, CloudConnect uses **SIP (Session Initiation Protocol)**. This replaces your current **Twilio Elastic SIP Trunking** configuration.

### SIP Trunk Replacement
-   **Current (Twilio):** You likely use `your-trunk.pstn.twilio.com` for termination and Twilio's IP ranges for origination.
-   **New (CloudConnect):** You must replace these with CloudConnect's SIP endpoints.
    -   **Outbound (Termination) URL:** Use CloudConnect's regional SBC address (e.g., `sbc.cloudconnect.in`).
    -   **Inbound (Origination) URL:** You must configure CloudConnect to point to your SIP URI. If using Vapi as the bridge, this will be `sip:call-id@sip.vapi.ai`.

### IP White-listing & Hosting (AWS Static Indian IP)
Your application is hosted on an **AWS Static Indian IP**. This is a critical asset for regulatory compliance and low-latency SIP signaling.
-   **Termination:** You must provide your AWS Static IP to CloudConnect so they can white-list it for outbound calls. This ensures CloudConnect only accepts SIP traffic coming from your authorized backend.
-   **Origination:** When CloudConnect sends an inbound call (origination), it will target your SIP URI. If you are self-hosting a SIP server (like FreeSwitch or Asterisk) on your AWS instance, ensure CloudConnect's signaling IPs are allowed through your **AWS Security Group** on ports `5060 (UDP)` and `10000-20000 (UDP)`.
-   **URL Compatibility:** The URLs are **not the same**. LiveKit uses `wss://` or `https://`, while CloudConnect uses `sip:` or `sips:`.

## 3. AWS Infrastructure & Middleware

Your AWS "Middleware" currently supports the following:

-   **RDS (PostgreSQL):** No changes needed.
-   **S3 (`fettle-audio-transcript` / `livekit-fettle`):** You must ensure your new CloudConnect flow still writes files here. Your current `process_outbound_calls` task expects to find files in S3 to perform AI analysis (`json_audio`).
-   **Security Groups:** If you run your own SIP signaling (not via Vapi), you must open:
    -   **UDP 5060:** For SIP Signaling.
    -   **UDP 10000-20000:** For RTP (Real-time Transport Protocol) audio packets.

## 4. Agentic Voice AI Strategy

Your "Agentic" logic (OpenAI/GPT-4 for call analysis) is currently triggered in `process_outbound_calls`.

-   **Recommendation:** Use **Vapi.ai as the Bridge**. 
    1. Configure CloudConnect as a SIP Trunk in the Vapi.ai Dashboard.
    2. Update the `Outbound_call` view in `phone_calling/views.py` to only trigger Vapi calls.
    3. Ensure the **WhatsApp Escalation** (via Twilio) in `tasks.py` remains connected to the `patient_id` passed through the call metadata.
    4. Your `json_audio` logic (analysis) should continue to run on the transcript provided by the new provider.

## 5. Summary of URLs/Keys
-   **LiveKit (Old):** `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`.
-   **CloudConnect (New):** `SIP_TRUNK_ID`, `SIP_SERVER_IP`, `SIP_USER`, `SIP_PASSWORD`.
