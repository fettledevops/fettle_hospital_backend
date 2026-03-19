from app.models import (
    Outbound_Hospital,
    Outbound_assistant,
    Hospital_model,
    Patient_model,
    Inbound_Hospital,
)
from celery import shared_task
import requests
import boto3
from dotenv import load_dotenv

load_dotenv()
from django.conf import settings
from openai import OpenAI
from io import BytesIO
from datetime import datetime, timedelta
from time import sleep
import json
from phone_calling.livekit_calling import dispatch_call
import os
import traceback
import pytz

# CloudConnect WhatsApp Configuration
CLOUDCONNECT_WA_URL = "https://api.cloudconnect.in/whatsapp/send"
CLOUDCONNECT_WA_KEY = os.getenv("CLOUDCONNECT_WA_KEY")
INTERNAL_API_BASE_URL = os.getenv(
    "INTERNAL_API_BASE_URL", "https://hospital.fettleconnect.com:8000"
)
INTERNAL_API_EMAIL = os.getenv("INTERNAL_API_EMAIL")
INTERNAL_API_PASSWORD = os.getenv("INTERNAL_API_PASSWORD")


def cloudconnect_whatsapp_msg(msg, to_number="+919010827279"):
    """
    Sends a WhatsApp message via CloudConnect API.
    """
    try:
        payload = {"to": to_number, "message": msg, "api_key": CLOUDCONNECT_WA_KEY}
        # response = requests.post(CLOUDCONNECT_WA_URL, json=payload)
        print(f"CloudConnect WhatsApp Sent to {to_number}: {msg}")
        return {"status": "success"}
    except Exception as e:
        print(f"WhatsApp Error: {str(e)}")
        return {"error": 1, "errorMsg": str(e)}


@shared_task
def call_outbound_task(json_payload):
    try:
        sleep(5)
        phone_number = json_payload["customer"]["number"]
        id_key = json_payload["customer"]["id_key"]

        # Restore native LiveKit dispatch
        dispatch_call(phone_number, id_key)

        task_id = call_outbound_task.request.id
        hospital_name = json_payload["metadata"]["hospital"]
        hospital_obj = Hospital_model.objects.get(name=hospital_name)
        vapi_id = id_key
        status = "in-progress"

        try:
            assistant_id = Outbound_assistant.objects.get(hospital=hospital_obj)
        except:
            assistant_id = None

        try:
            patient_obj = Patient_model.objects.get(
                id=json_payload["metadata"]["patient_id"]
            )
        except:
            patient_obj = None

        campaign_id = json_payload["metadata"].get("campaign_id")
        campaign_obj = None
        if campaign_id:
            from app.models import Campaign

            try:
                campaign_obj = Campaign.objects.get(id=campaign_id)
            except:
                pass

        Outbound_Hospital.objects.create(
            vapi_id=vapi_id,
            status=status,
            assistant_id=assistant_id,
            patient_id=patient_obj,
            campaign=campaign_obj,
            task_id=task_id,
            calling_process="not_happened",
        )
        return {"error": 0, "vapi_id": vapi_id}
    except Exception as e:
        tb = traceback.format_exc()
        print("Traceback error:\n", tb)
        return {"error": 1, "errorMsg": str(e), "traceback": tb}


def json_audio(patient_id, text, called_at, duration):
    system_prompt = """
    You are a hospital call analysis agent. Your role is to analyze call transcripts between hospital staff/assistants and patients, and produce a structured JSON output summarizing the interaction.

    ### IMPORTANT: Language Policy
    The conversations should primarily be in English, Hindi, or Telugu. 
    If you detect a language barrier where the patient speaks a different language (e.g., Spanish), 
    please note this in the remarks and mark escalation_required: true.

    The JSON must strictly follow this format:
    {
    "call_status": "string (connected/not_connected)",
    "call_outcome": "string (positive/negative/escalated/no_feedback)",
    "remarks": "string (brief summary of the call)",
    "issue_description": "string (detailed explanation if escalation_required is true)",
    "called_by": "CloudConnect Agent",
    "community_added": "boolean",
    "revisit_encouraged": "boolean",
    "escalation_required": "boolean"
    }

    ### Output Rules:
    1. call_status: "connected" or "not_connected"
    2. call_outcome: "positive", "negative", "escalated", or "no_feedback"
    3. called_by: Always "CloudConnect Agent" unless another name is mentioned.
    """

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Analyze transcript:\n{text}\ncalled_at: {called_at}",
            },
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    result = response.choices[0].message.content
    try:
        parsed_json = json.loads(result)
        parsed_json["patient_id"] = patient_id
        parsed_json["called_at"] = called_at
        parsed_json["call_duration"] = duration
        return parsed_json
    except:
        return {"error": 1}


def read_from_s3_bucket(bucket_name, key):
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        return {
            "error": 0,
            "text": s3.get_object(Bucket=bucket_name, Key=key)["Body"]
            .read()
            .decode("utf-8"),
        }
    except Exception as e:
        return {"error": 1, "errorMsg": str(e)}


@shared_task
def process_outbound_calls(json_payload):
    try:
        db_id = json_payload["id"]
        vapi_id = json_payload["vapi_id"]  # room_name
        patient_id = json_payload["patient_id"]
        mobile_no = json_payload["mobile_no"]
        hospital_name = json_payload["hospital_name"]

        # Pull from LiveKit storage
        transcript_res = read_from_s3_bucket(
            settings.LIVEKIT_BUCKET_NAME, f"transcripts/{vapi_id}.json"
        )
        metadata_res = read_from_s3_bucket(
            settings.LIVEKIT_BUCKET_NAME, f"calls/{vapi_id}.json"
        )

        if transcript_res["error"] == 0 and metadata_res["error"] == 0:
            transcript = json.loads(transcript_res["text"])
            metadata = json.loads(metadata_res["text"])
            recording_url = (
                f"s3://{settings.LIVEKIT_BUCKET_NAME}/video_record/{vapi_id}.ogg"
            )
            started_at = metadata["dialed_at"]
            ended_at = metadata["ended_at"]

            text_message = ""
            for item in transcript["items"]:
                if item["type"] == "message":
                    text_message += f"{item['role']} : {item['content'][0]}\n"

            # Internal Loopback Auth
            url_backend = INTERNAL_API_BASE_URL
            if not INTERNAL_API_EMAIL or not INTERNAL_API_PASSWORD:
                return {
                    "error": 1,
                    "msg": "INTERNAL_API_EMAIL and INTERNAL_API_PASSWORD must be configured",
                }

            res_login = requests.post(
                f"{url_backend}/api/login/",
                json={
                    "email": INTERNAL_API_EMAIL,
                    "password": INTERNAL_API_PASSWORD,
                    "is_admin": True,
                },
            ).json()
            headers_url = {
                "Authorization": f"Bearer {res_login['token']}",
                "Content-Type": "application/json",
            }

            call_duration = round(
                (
                    datetime.fromisoformat(ended_at)
                    - datetime.fromisoformat(started_at)
                ).total_seconds()
                / 60,
                2,
            )
            json_response = json_audio(
                patient_id, text_message, started_at, call_duration
            )

            if (
                "error" not in json_response
                and json_response.get("call_status") == "connected"
            ):
                # Sync Feedback
                requests.post(
                    f"{url_backend}/api/callfeedback/",
                    headers=headers_url,
                    json={
                        "call_duration": call_duration,
                        "call_outcome": json_response["call_outcome"],
                        "call_status": "connected",
                        "called_at": started_at,
                        "called_by": "CloudConnect Agent",
                        "community_added": json_response.get("community_added", False),
                        "escalation_required": json_response.get(
                            "escalation_required", False
                        ),
                        "patient_id": patient_id,
                        "remarks": json_response.get("remarks", ""),
                        "revisit_encouraged": json_response.get(
                            "revisit_encouraged", False
                        ),
                    },
                )

                if json_response.get("escalation_required"):
                    requests.post(
                        f"{url_backend}/api/escalationfeedback/",
                        headers=headers_url,
                        json={
                            "patient_id": patient_id,
                            "issue_description": json_response["remarks"],
                            "department": Patient_model.objects.get(
                                id=patient_id
                            ).department,
                        },
                    )
                    cloudconnect_whatsapp_msg(
                        f"Escalation for {mobile_no}: {json_response['remarks']}"
                    )

            # Update DB Record
            obj = Outbound_Hospital.objects.get(id=db_id)
            obj.status = "ended"
            obj.started_at = started_at
            obj.ended_at = ended_at
            obj.message_s3_link = f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/{hospital_name}/{vapi_id}_{mobile_no}.txt"
            obj.audio_link = recording_url
            obj.calling_process = json_response.get("call_status", "not_connected")
            obj.save()

            return {"status": "success"}
        return {"error": 1, "msg": "Metadata missing"}
    except Exception as e:
        return {"error": 1, "msg": str(e)}


@shared_task
def inbound_call_task(json_payload):
    return {"status": "automated_via_sip"}


@shared_task
def process_inbound_calls(json_payload):
    # Similar to outbound but for Inbound_Hospital model
    try:
        room_name = json_payload["vapi_id"]
        # Logic to pull from S3 and update Inbound_Hospital
        return {"status": "success"}
    except Exception as e:
        return {"error": 1, "msg": str(e)}
