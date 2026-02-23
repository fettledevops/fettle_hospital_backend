from app.models import Outbound_Hospital,Outbound_assistant,Hospital_model,Patient_model
from celery import shared_task
import requests
import boto3
from dotenv import load_dotenv
load_dotenv()
from django.conf import settings
from openai import OpenAI
from io import BytesIO
from datetime import datetime, timezone

import json
client = OpenAI()
import os
# sample_response={
#     "subscriptionLimits": {
#         "concurrencyBlocked": False,
#         "concurrencyLimit": 10,
#         "remainingConcurrentCalls": 9
#     },
#     "id": "019a9c95-32a0-7ccd-93e9-2655308be9ae",
#     "assistantId": "d82213e0-54fd-4c30-b475-bb2a0b5c91d4",
#     "phoneNumberId": "c18aa5d3-cf3b-4319-bf98-dc141bf9bca7",
#     "type": "outboundPhoneCall",
#     "createdAt": "2025-11-19T14:46:54.880Z",
#     "updatedAt": "2025-11-19T14:46:55.100Z",
#     "orgId": "5be3235c-2ee2-4b19-a316-f3f1f8a9fd6d",
#     "cost": 0,
#     "customer": {
#         "number": "+918360039458"
#     },
#     "status": "queued",
#     "metadata": {
#         "source": "automated_test",
#         "hospital": "1",
#         "department": "1",
#         "patient_id": "1",
#         "patient_name": "1"
#     },
#     "phoneCallProvider": "twilio",
#     "phoneCallProviderId": "CAbd8b6723c5cb01e2911764b28e3ae966",
#     "phoneCallTransport": "pstn",
#     "monitor": {
#         "listenUrl": "wss://phone-call-websocket.aws-us-west-2-backend-production2.vapi.ai/019a9c95-32a0-7ccd-93e9-2655308be9ae/listen",
#         "controlUrl": "https://phone-call-websocket.aws-us-west-2-backend-production2.vapi.ai/019a9c95-32a0-7ccd-93e9-2655308be9ae/control"
#     },
#     "transport": {
#         "callSid": "CAbd8b6723c5cb01e2911764b28e3ae966",
#         "provider": "twilio",
#         "accountSid": "REDACTED",
#         "conversationType": "voice"
#     }
# }
@shared_task
def call_outbound_task(json_payload):
    try:
        ##call
        sleep(5)
        token = os.getenv('VAPI_TOKEN')
        url = "https://api.vapi.ai/call"
        headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }   
        response = requests.post(url, headers=headers, json=json_payload)

        response_vapi=response.json()
    
        task_id = call_outbound_task.request.id
        print("task_id--->",task_id)
        hospital_name=json_payload["metadata"]["hospital"]
        hospital_obj=Hospital_model.objects.get(name=hospital_name)
        vapi_id=response_vapi["id"]
        status=response_vapi["status"]
        try:
            assistant_id=Outbound_assistant.objects.get(hospital=hospital_obj)
        except Exception as e:
            assistant_id=None
        try:
            patient_obj= Patient_model.objects.get(id=response_vapi["metadata"]["patient_id"])
        except Exception as e:
            patient_obj=None
        endedReason="" if "endedReason" not in response_vapi else response_vapi["endedReason"]
        message_s3_link=None
        audio_link=None
        task_id_process=None
        new_call = Outbound_Hospital.objects.create(
            vapi_id=vapi_id,
            status=status,
            assistant_id=assistant_id,
            patient_id=patient_obj,
            endedReason=endedReason,
            message_s3_link=message_s3_link,
            audio_link=audio_link,
            task_id=task_id,
            
        )
        print("donnee")
        return {"error":0,"errorMsg":"","vapi_id":vapi_id}
    except Exception as e:
        return {"error":1,"errorMsg":str(e)}
# sample_response={
#     "startedAt": "2025-11-19T15:46:54.894Z",
#     "endedAt": "2025-11-19T15:48:05.713Z",
#     "status": "ended",
#     "endedReason": "customer-ended-call",
#     "recordingUrl": "https://storage.vapi.ai/019a9ccb-ea3e-777e-924a-d4c8f7483d58-1763567288386-5a73b858-6ed5-4374-a45e-3d026dc67d1d-mono.wav",
#     "messages": [
#         {
#             "role": "system",
#             "time": 1763567214776,
#             "message": "You are a hospital feedback collection agent calling patients about their recent hospital experience. \nSpeak warmly, politely, and like a real hospital staff member — NOT like an AI assistant or translator. \nNever mention you are an assistant.\n\n## Language Selection Rule\nYour first rule is:\n1. Ask the patient which language they prefer to speak in (English or Hindi).\n2. Based on their answer, conduct the ENTIRE call in that chosen language.\n3. Do not switch languages unless the patient explicitly asks.\n\n## Hindi Language Style Guidelines\nIf the user selects Hindi:\n- Use simple, everyday conversational Hindi that an average patient can understand.\n- Avoid overly formal, Sanskrit-heavy, or technical Hindi.\n- Prefer natural phrases such as:\n    - “Report mil gayi?” instead of “Kya aapko aapki report prapt hui?”\n    - “Aapko kis cheez mein madad chahiye?” instead of “Aapko kis vishay mein sahayata avashyak hai?”\n    - “Main samajh sakta/sakti hoon” instead of “Main avdharit karti hoon”\n- Keep sentences short and friendly.\n- Keep the tone empathetic, warm, and human.\n- If you use a medical term, explain it briefly in simple words.\n\n## Call Flow\n1. Greet the patient warmly.\n2. Confirm their name.\n3. Ask whether they received their medical reports.\n4. Ask if everything in their experience was satisfactory.\n\n## Escalation Rules\nIf the patient mentions:\n- delay in receiving reports  \n- incorrect reports  \n- any kind of pain, discomfort, or medical anomaly  \n\nThen:\n- Mark this internally as an escalation.\n- Apologize empathetically.\n- Tell them: “The hospital team will reach out to you shortly regarding this.”\n- Record a clear, detailed description of the issue.\n\nIf no issue is mentioned:\n- Thank them for their feedback.\n- End the call politely.\n\n## Classification Requirements\nPrivately (not said to the user), classify the call into one of:\n- no_issue\n- delay_in_reports\n- incorrect_reports\n- medical_anomaly\n\nIf any issue is detected, mark:\n- escalation_flag = true in your structured output\nEnd every call by saying (in the chosen language):\n“Thank you for your feedback. The hospital team will review your comments.”\n",
#             "secondsFromStart": 0
#         },
#         {
#             "role": "bot",
#             "time": 1763567216026,
#             "source": "",
#             "endTime": 1763567220461,
#             "message": "Hello, This is Amour Hospital calling to ask about your recent visit.",
#             "duration": 3440.000244140625,
#             "secondsFromStart": 1.132
#         },
#         {
#             "role": "user",
#             "time": 1763567223021,
#             "endTime": 1763567232461,
#             "message": "Uh, Hanji Bataya. Punish",
#             "duration": 2280,
#             "metadata": {
#                 "wordLevelConfidence": [
#                     {
#                         "end": 8.55,
#                         "word": "uh",
#                         "start": 8.05,
#                         "language": "en",
#                         "confidence": 0.86157227,
#                         "punctuated_word": "Uh,"
#                     },
#                     {
#                         "end": 9.33,
#                         "word": "hanji",
#                         "start": 9.01,
#                         "language": "en",
#                         "confidence": 0.7060547,
#                         "punctuated_word": "Hanji"
#                     },
#                     {
#                         "end": 9.83,
#                         "word": "bataya",
#                         "start": 9.33,
#                         "language": "en",
#                         "confidence": 0.5454915,
#                         "punctuated_word": "Bataya."
#                     }
#                 ]
#             },
#             "secondsFromStart": 8.05
#         },
#         {
#             "role": "bot",
#             "time": 1763567236381,
#             "source": "",
#             "endTime": 1763567240781,
#             "message": "Aap Khonsa language prefer kartheha na baat karnne keliya Hindi English",
#             "duration": 3720.0009765625,
#             "secondsFromStart": 21.487
#         },
#         {
#             "role": "user",
#             "time": 1763567243392.429,
#             "endTime": 1763567255346,
#             "message": "This call is now being recorded. Uh, Hindi Tea. Punish.",
#             "duration": 3516.071044921875,
#             "metadata": {
#                 "wordLevelConfidence": [
#                     {
#                         "end": 28.702856,
#                         "word": "this",
#                         "start": 28.421429,
#                         "language": "en",
#                         "confidence": 0.99902344,
#                         "punctuated_word": "This"
#                     },
#                     {
#                         "end": 28.984285,
#                         "word": "call",
#                         "start": 28.702856,
#                         "language": "en",
#                         "confidence": 1,
#                         "punctuated_word": "call"
#                     },
#                     {
#                         "end": 29.265715,
#                         "word": "is",
#                         "start": 28.984285,
#                         "language": "en",
#                         "confidence": 1,
#                         "punctuated_word": "is"
#                     },
#                     {
#                         "end": 29.547144,
#                         "word": "now",
#                         "start": 29.265715,
#                         "language": "en",
#                         "confidence": 0.99902344,
#                         "punctuated_word": "now"
#                     },
#                     {
#                         "end": 29.828571,
#                         "word": "being",
#                         "start": 29.547144,
#                         "language": "en",
#                         "confidence": 1,
#                         "punctuated_word": "being"
#                     },
#                     {
#                         "end": 30.11,
#                         "word": "recorded",
#                         "start": 29.828571,
#                         "language": "en",
#                         "confidence": 0.9875488,
#                         "punctuated_word": "recorded."
#                     }
#                 ]
#             },
#             "secondsFromStart": 28.421429
#         },
#         {
#             "role": "bot",
#             "time": 1763567258701,
#             "source": "",
#             "endTime": 1763567263791,
#             "message": "Namaste, Man Amur Hospital ki tarafse Bolrayung Aapka Experience Kesatha Hospital Gesad",
#             "duration": 4599.998046875,
#             "secondsFromStart": 43.807
#         },
#         {
#             "role": "user",
#             "time": 1763567266676,
#             "endTime": 1763567269111,
#             "message": "Spanish. Spanish.",
#             "duration": 590,
#             "metadata": {
#                 "wordLevelConfidence": [
#                     {
#                         "end": 52.205,
#                         "word": "spanish",
#                         "start": 51.705,
#                         "language": "en",
#                         "confidence": 0.55322266,
#                         "punctuated_word": "Spanish."
#                     }
#                 ]
#             },
#             "secondsFromStart": 51.705
#         },
#         {
#             "role": "bot",
#             "time": 1763567273861.003,
#             "source": "",
#             "endTime": 1763567276921,
#             "message": "Philhal Mayanserf Hindi. Ya English me batkar Saktahung.",
#             "duration": 3059.9970703125,
#             "secondsFromStart": 58.9670029296875
#         },
#         {
#             "role": "user",
#             "time": 1763567284121,
#             "endTime": 1763567285821,
#             "message": "Call recording has now ended.",
#             "duration": 1700,
#             "metadata": {
#                 "wordLevelConfidence": [
#                     {
#                         "end": 69.63,
#                         "word": "call",
#                         "start": 69.15,
#                         "language": "en",
#                         "confidence": 0.9970703,
#                         "punctuated_word": "Call"
#                     },
#                     {
#                         "end": 69.95,
#                         "word": "recording",
#                         "start": 69.63,
#                         "language": "en",
#                         "confidence": 0.99902344,
#                         "punctuated_word": "recording"
#                     },
#                     {
#                         "end": 70.19,
#                         "word": "has",
#                         "start": 69.95,
#                         "language": "en",
#                         "confidence": 0.9941406,
#                         "punctuated_word": "has"
#                     },
#                     {
#                         "end": 70.35,
#                         "word": "now",
#                         "start": 70.19,
#                         "language": "en",
#                         "confidence": 1,
#                         "punctuated_word": "now"
#                     },
#                     {
#                         "end": 70.85,
#                         "word": "ended",
#                         "start": 70.35,
#                         "language": "en",
#                         "confidence": 0.9951172,
#                         "punctuated_word": "ended."
#                     }
#                 ]
#             },
#             "secondsFromStart": 69.15
#         }
#     ]
# }
def json_audio(patient_id,text,called_at,duration):
    system_prompt = """
    You are a hospital call analysis agent. Your role is to analyze call transcripts between hospital staff/assistants and patients, and produce a structured JSON output summarizing the interaction.

    The JSON must strictly follow this format:

    {
    "call_status": "string (connected/not_connected)",
    "call_outcome": "string (positive/negative/escalated/no_feedback)",
    "remarks": "string (brief summary of the call including key factor i..e time,medicine ,etc)",
    "issue_description": "string (detailed explanation if escalation_required is true, otherwise empty string)",
    "called_by": "Vapi Agent",
    "community_added": "boolean",
    "revisit_encouraged": "boolean",
    "escalation_required": "boolean"
    }

    ### Output Rules:

    1. **call_status**
    - `"connected"` → if the conversation occurred or was completed.
    - `"not_connected"` → if the call was missed, declined, or incomplete.

    2. **call_outcome**
    - `"positive"` → if the issue was resolved, appointment booked, or patient was satisfied.
    - `"negative"` → if there were complaints, cancellations, or unresolved issues.
    - `"escalated"` → if the matter required escalation or referral to a higher authority.
    - `"no_feedback"` → if no meaningful response or outcome was achieved.

    3. **remarks**
    - Provide any short summary or additional context about the call, if relevant. 
    - This field can remain empty if there is nothing noteworthy.

    4. **issue_description**
    - Include a clear and specific explanation only if `"escalation_required": true` 
        (e.g., "Patient reported severe chest pain", "Complaint about wrong prescription").
    - Otherwise, leave it as an empty string `""`.

    5. **community_added**
    - `true` if the patient was added to a community group, support program, or health initiative.

    6. **revisit_encouraged**
    - `true` if a follow-up consultation or revisit was suggested or booked.

    7. **escalation_required**
    - `true` if there was an emergency, complaint, critical issue, or request for senior intervention.

    8. **called_by**
    - Always `"Vapi Agent"` unless another specific staff name is clearly mentioned.

    Return **only valid JSON** as per the above schema — no explanations, text, or additional formatting.
"""

    
    transcript=text
    response = client.chat.completions.create(
    model="gpt-5.1",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Now analyze the following transcript and provide the JSON payload:\n{transcript}\ncalled_at: {called_at}"}
    ],
    temperature=0.2
)

# Extract and format response
    result = response.choices[0].message.content

    try:
        parsed_json = json.loads(result)
        parsed_json["patient_id"]=patient_id
        parsed_json['called_at']=called_at
        parsed_json['call_duration']=duration
        return parsed_json
        
    except json.JSONDecodeError:
        return {"error":1}

@shared_task
def process_outbound_calls(json_payload):
    try:
        db_outbound_hospital_id=json_payload["id"]
        print("db_outbound_hospital_id->",db_outbound_hospital_id)
        vapi_id=json_payload["vapi_id"]
        patient_idd=json_payload['patient_id']
                    token = os.getenv('VAPI_TOKEN')
                    url = f"https://api.vapi.ai/call/{vapi_id}"
        headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }   
        # print("good-->")
        task_id_process = process_outbound_calls.request.id
        sample_response = requests.get(url, headers=headers).json()
        vapi_response=sample_response
        status=vapi_response["status"]
        mobile_no=json_payload["mobile_no"]
        endedReason="" if "endedReason" not in vapi_response else vapi_response["endedReason"]
        recording_url="" if "recordingUrl" not in vapi_response else vapi_response["recordingUrl"]
        print("recording_url",)
        hospital_name=json_payload["hospital_name"]
        started_at=None if "startedAt" not in vapi_response else vapi_response["startedAt"]
        ended_at=None if "endedAt" not in vapi_response else vapi_response["endedAt"]
        text_message=""
        
        if "messages" not in vapi_response:
            message_s3_link=""
        else:
            messages_response=vapi_response["messages"]
            
            for i in messages_response[1:]:
                # print("i-->",i)
                if ("message" in i) and ("role" in i):
                    text_message += f"{i['role']}: {i['message']}\n\n"
        #####processing whether escalated or not######
        try:
            url_backend="https://hospital.fettleconnect.com:8000"
            login_url=url_backend+"/api/login/"
            payload = {
                "email": "admin@gmail.com",
                "password": "admin",
                "is_admin": True
            }
            res_login=requests.post(login_url,json=payload).json()
            token=res_login["token"]
            headers_url = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            if endedReason=='customer-ended-call' or endedReason=='assistant-ended-call' or endedReason=='silence-timed-out':
                call_duration = round((datetime.fromisoformat(ended_at) - datetime.fromisoformat(started_at)).total_seconds() / 60, 2)
                json_response=json_audio(patient_idd,text_message,started_at,call_duration)
                if json_response['call_outcome']=='negative' or json_response['call_outcome']=='escalated':
                    json_response['escalation_required']=True
                if json_response['call_status']=='not_connected':
                    json_response['escalation_required']=False
                    json_response['community_added']=False
                department=Patient_model.objects.get(id=patient_idd).department
                print("json_response--->",json_response)
                if "error" not in json_response:
                    
                    call_feedback_payload={"call_duration":call_duration,"call_outcome":json_response["call_outcome"],"call_status":json_response["call_status"],"called_at":started_at,"called_by":json_response["called_by"],"community_added":json_response["community_added"],"escalation_required":json_response["escalation_required"],"patient_id":patient_idd,"remarks":json_response["remarks"],"revisit_encouraged":json_response["revisit_encouraged"]}
                    url_call=url_backend+"/api/callfeedback/"
                    call_res = requests.post(url_call,headers=headers_url,json=call_feedback_payload).json()
                    if json_response['escalation_required']==True:
                        escalation_payload={"patient_id":patient_idd,"issue_description":json_response['remarks'],"department":department}
                        url_escalation=url_backend+"/api/escalationfeedback/"
                        call_escalation = requests.post(url_escalation,headers=headers_url,json=escalation_payload).json()

                        ##call api
                    if json_response['community_added']==True:
                        community_payload={"patient_id":patient_idd,"engagement_type":"post","department":department}
                        url_community=url_backend+"/api/communityfeedback/"
                        call_community = requests.post(url_community,headers=headers_url,json=community_payload).json()
                        ##call api
                    
        except Exception as e:
            pass
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        unique_filename = f"{vapi_id}_{mobile_no}.txt"
        content_type = "text/plain"
        text_message_bytes = text_message.encode("utf-8")  # convert string → bytes
        file_obj = BytesIO(text_message_bytes)
        
        s3.upload_fileobj(
                file_obj,
                settings.AWS_STORAGE_BUCKET_NAME,
                f"{hospital_name}/{unique_filename}",
                ExtraArgs={"ContentType":content_type}
            )
        ##update db
        print("started_at",started_at)
        objj=Outbound_Hospital.objects.get(id=db_outbound_hospital_id)
        objj.status=status
        objj.endedReason=endedReason
        objj.started_at=started_at
        objj.ended_at=ended_at
        objj.message_s3_link="s3://"+settings.AWS_STORAGE_BUCKET_NAME+"/"+unique_filename
        objj.audio_link=recording_url
        objj.task_id_process=task_id_process
        objj.save()
        return {"error":0,"errorMsg":"","text_message":text_message}
    except Exception as e:
        print(str(e))
        return {"error":1,"errorMsg":str(e)}
        
    
    