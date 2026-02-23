from app.models import Outbound_Hospital,Outbound_assistant,Hospital_model,Patient_model,Inbound_Hospital
from celery import shared_task
import requests
import boto3
from dotenv import load_dotenv
load_dotenv()
from django.conf import settings
from openai import OpenAI
from io import BytesIO
from datetime import datetime, timezone
from time import sleep
import json
from phone_calling.livekit_calling import dispatch_call
from twilio.rest import Client
import os
import traceback
TWILIO_ACCOUNT_SID = os.getenv('ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('AUTH_TOKEN')
import pytz
def whatsapp_msg(msg):
    try:
        client = Client(TWILIO_ACCOUNT_SID,TWILIO_AUTH_TOKEN)
        message = client.messages.create(
        from_='whatsapp:+14155238886',
        #   content_sid='HXb5b62575e6e4ff6129ad7c8efe1f983e',
        body=msg,
        to='whatsapp:+919010827279'
        )
        print("message--->",message.sid)
        return message.sid
    except Exception as e:
        print("error in whatsapp_msg--->",str(e))
        return {"error":1,"errorMsg":str(e)}

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
        phone_number=json_payload["customer"]["number"]
        id_key=json_payload["customer"]["id_key"]
        dispatch_call(phone_number, id_key)
        # response = requests.post(url, headers=headers, json=json_payload)

        # response_vapi=response.json()
    
        task_id = call_outbound_task.request.id
        print("task_id--->",task_id)
        hospital_name=json_payload["metadata"]["hospital"]
        hospital_obj=Hospital_model.objects.get(name=hospital_name)
        vapi_id=id_key
        status="in-progress"
        try:
            assistant_id=Outbound_assistant.objects.get(hospital=hospital_obj)
        except Exception as e:
            assistant_id=None
        try:
            patient_obj= Patient_model.objects.get(id=json_payload["metadata"]["patient_id"])
        except Exception as e:
            patient_obj=None
        endedReason=""
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
        tb = traceback.format_exc()
        print("Traceback error:\n", tb)
        return {"error":1,"errorMsg":str(e),"traceback": tb}

def json_audio(patient_id,text,called_at,duration):
    system_prompt = """
    You are a hospital call analysis agent. Your role is to analyze call transcripts between hospital staff/assistants and patients, and produce a structured JSON output summarizing the interaction.

    ### IMPORTANT: Language Policy
    The conversations should primarily be in **English, Hindi, or Telugu**. 
    If you detect a language barrier where the patient speaks a different language (e.g., Spanish), 
    please note this in the `remarks` and mark `escalation_required: true`.

    The JSON must strictly follow this format:

    {
    "call_status": "string (connected/not_connected)",
    "call_outcome": "string (positive/negative/escalated/no_feedback)",
    "remarks": "string (brief summary of the call including key factor i..e time,medicine, language barrier, etc)",
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
    client = OpenAI()
    response = client.chat.completions.create(
    model="gpt-4o",
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
def read_from_s3_buket(bucket_name,key):
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        return {"error":0,"text":s3.get_object(Bucket=bucket_name, Key=key)["Body"].read().decode("utf-8")}
    except Exception as e:
        print(str(e))
        return {"error":1,"errorMsg":str(e)}
@shared_task
def process_outbound_calls(json_payload):
    if json_payload["is_livekit"]:
        try:
            db_outbound_hospital_id=json_payload["id"]
            print("db_outbound_hospital_id->",db_outbound_hospital_id)
            vapi_id=json_payload["vapi_id"]
            patient_idd=json_payload['patient_id']
            mobile_no=json_payload["mobile_no"]
            hospital_name=json_payload["hospital_name"]
            endedReason=""
            task_id_process = process_outbound_calls.request.id
            status="ended"
            transcript=read_from_s3_buket(settings.LIVEKIT_BUCKET_NAME,f"transcripts/{vapi_id}.json")
            calls_metadata=read_from_s3_buket(settings.LIVEKIT_BUCKET_NAME,f"calls/{vapi_id}.json")
            if transcript["error"]==0 and calls_metadata["error"]==0:
                transcript=json.loads(transcript["text"])
                calls_metadata=json.loads(calls_metadata["text"])
                recording_url="s3://"+settings.LIVEKIT_BUCKET_NAME+"/"+"video_record"+"/"+vapi_id+".ogg"
                started_at=calls_metadata["dialed_at"]
                ended_at=calls_metadata["ended_at"]
                text_message=""
                for i in transcript["items"]:
                    if i["type"] == "message":
                        text_message+=i["role"] + " : " + i["content"][0] + "\n"
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
                call_progress='not_happened'
                call_duration = round((datetime.fromisoformat(ended_at) - datetime.fromisoformat(started_at)).total_seconds() / 60, 2)
                json_response=json_audio(patient_idd,text_message,started_at,call_duration)
                call_progress=json_response['call_status']
                if json_response['call_outcome']=='negative' or json_response['call_outcome']=='escalated':
                    json_response['escalation_required']=True
                if json_response['call_status']=='not_connected':
                    json_response['escalation_required']=False
                    json_response['community_added']=False
                department=Patient_model.objects.get(id=patient_idd).department
                print("json_response--->",json_response)
                if "error" not in json_response and json_response['call_status']=='connected':
                    started_at_utc = datetime.fromisoformat(calls_metadata["dialed_at"])
                    started_at_utc = pytz.utc.localize(started_at_utc)

                    started_at_ist = started_at_utc.astimezone(
                        pytz.timezone("Asia/Kolkata")
                    ).replace(tzinfo=None)
                    started_at_ist = started_at_ist.isoformat(sep=" ", timespec="seconds")

                    call_feedback_payload={"call_duration":call_duration,"call_outcome":json_response["call_outcome"],"call_status":json_response["call_status"],"called_at":started_at_ist,"called_by":json_response["called_by"],"community_added":json_response["community_added"],"escalation_required":json_response["escalation_required"],"patient_id":patient_idd,"remarks":json_response["remarks"],"revisit_encouraged":json_response["revisit_encouraged"]}
                    url_call=url_backend+"/api/callfeedback/"
                    call_res = requests.post(url_call,headers=headers_url,json=call_feedback_payload).json()
                    print("call_res1-->",call_res,call_feedback_payload)
                    if json_response['escalation_required']==True:
                        escalation_payload={"patient_id":patient_idd,"issue_description":json_response['remarks'],"department":department}
                        url_escalation=url_backend+"/api/escalationfeedback/"
                        patient = Patient_model.objects.get(id=patient_idd)

                        
                        ended_at_utc = datetime.fromisoformat(calls_metadata["ended_at"])
                        ended_at_utc = pytz.utc.localize(ended_at_utc)

                        ended_at_ist = ended_at_utc.astimezone(
                            pytz.timezone("Asia/Kolkata")
                        ).replace(tzinfo=None)

                        message = (
                            f"patient_name: {patient.patient_name}\n"
                            f"mobile_no: {patient.mobile_no}\n"
                            f"escalated_At: {ended_at_ist}\n\n"
                            f"issue_description: {json_response['remarks']}")
                        whatsapp_msg(message)
                        call_escalation = requests.post(url_escalation,headers=headers_url,json=escalation_payload).json()

                        ##call api
                    if json_response['community_added']==True:
                        community_payload={"patient_id":patient_idd,"engagement_type":"post","department":department}
                        url_community=url_backend+"/api/communityfeedback/"
                        call_community = requests.post(url_community,headers=headers_url,json=community_payload).json()
                else:
                    call_progress='not_connected'
                    call_feedback_payload={"call_outcome":"no_feedback","call_status":"not_connected","called_by":"Vapi Agent","community_added":False,"escalation_required":False,"patient_id":patient_idd,"remarks":False,"revisit_encouraged":False,"called_at":started_at}     
                    url_call=url_backend+"/api/callfeedback/"
                    call_res = requests.post(url_call,headers=headers_url,json=call_feedback_payload).json()
                    print("call_res-->",call_res,call_feedback_payload)
                objj=Outbound_Hospital.objects.get(id=db_outbound_hospital_id)
                objj.status=status
                objj.endedReason=endedReason
                objj.started_at=started_at
                objj.ended_at=ended_at
                objj.message_s3_link="s3://"+settings.LIVEKIT_BUCKET_NAME+"/"+"transcripts"+"/"+vapi_id+".json"
                objj.audio_link=recording_url
                objj.task_id_process=task_id_process
                objj.calling_process=call_progress
                objj.save()
                return {"error":0,"errorMsg":"","text_message":text_message}
                
            else:
                return {"error":1,"errorMsg":"Entries are not found in the bucket"}

        except Exception as e:  
            tb = traceback.format_exc()
            print("Traceback error:\n", str(e),"\n",tb,"\n")
            return {"error":1,"errorMsg":str(e),"traceback": tb}
    else:
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
            if len(endedReason)==0:
                return {"error":0,"errorMsg":"","text_message":"calling phase, the call has not ended"}
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
                call_progress='not_happened'
                if len(recording_url)!=0:
                    call_duration = round((datetime.fromisoformat(ended_at) - datetime.fromisoformat(started_at)).total_seconds() / 60, 2)
                    json_response=json_audio(patient_idd,text_message,started_at,call_duration)
                    json_response['call_status']='connected'
                    call_progress='connected'
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
                        print("call_res1-->",call_res,call_feedback_payload)
                        if json_response['escalation_required']==True:
                            escalation_payload={"patient_id":patient_idd,"issue_description":json_response['remarks'],"department":department}
                            url_escalation=url_backend+"/api/escalationfeedback/"
                            patient = Patient_model.objects.get(id=patient_idd)
                            # def make_naive(dt, tz_name='Asia/Kolkata'):
                            #     import pytz

                            #     if dt is None:
                            #         return None

                            #     target_tz = pytz.timezone(tz_name)

                            #     # If datetime is timezone-aware → convert to IST → drop tzinfo
                            #     if dt.tzinfo is not None:
                            #         return dt.astimezone(target_tz).replace(tzinfo=None)

                            #     # If datetime is naive → assume UTC → convert to IST
                            #     return pytz.utc.localize(dt).astimezone(target_tz).replace(tzinfo=None)
                            # escalated_at = make_naive(ended_at, tz_name='Asia/Kolkata')

                            # message = (
                            #     f"patient_name: {patient.patient_name}\n"
                            #     f"mobile_no: {patient.mobile_no}\n"
                            #     f"escalated_At: {escalated_at}\n\n"
                            #     f"issue_description: {json_response['remarks']}")
                            # whatsapp_msg(message)
                            # whatsapp_msg("patient_name: "+Patient_model.objects.get(id=patient_idd).patient_name+"\nmobile_no: "+Patient_model.objects.get(id=patient_idd).mobile_no+"\nescalated_At:"+datetime.fromisoformat(ended_at)+"\n\n\nissue_description: "+json_response['remarks'])
                            call_escalation = requests.post(url_escalation,headers=headers_url,json=escalation_payload).json()

                            ##call api
                        if json_response['community_added']==True:
                            community_payload={"patient_id":patient_idd,"engagement_type":"post","department":department}
                            url_community=url_backend+"/api/communityfeedback/"
                            call_community = requests.post(url_community,headers=headers_url,json=community_payload).json()
                            ##call api
                else:
                    call_progress='not_connected'
                    call_feedback_payload={"call_outcome":"no_feedback","call_status":"not_connected","called_by":"Vapi Agent","community_added":False,"escalation_required":False,"patient_id":patient_idd,"remarks":False,"revisit_encouraged":False,"called_at":started_at}     
                    url_call=url_backend+"/api/callfeedback/"
                    call_res = requests.post(url_call,headers=headers_url,json=call_feedback_payload).json()
                    print("call_res-->",call_res,call_feedback_payload)
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
            if started_at!=None:
                objj.started_at=started_at
            if ended_at!=None:
                objj.ended_at=ended_at
            objj.message_s3_link="s3://"+settings.AWS_STORAGE_BUCKET_NAME+"/"+hospital_name+"/"+unique_filename
            objj.audio_link=recording_url
            objj.task_id_process=task_id_process
            objj.calling_process=call_progress
            objj.save()
            return {"error":0,"errorMsg":"","text_message":text_message}
        except Exception as e:
            tb = traceback.format_exc()
            print("Traceback error:\n", str(e),"\n",tb,"\n")
            return {"error":1,"errorMsg":str(e),"traceback": tb}
@shared_task
def inbound_call_task(json_payload):
    try:
        sleep(1)
                    token = os.getenv('VAPI_TOKEN')
        vapi_id=str(json_payload["id"])
        print("vapi_id--->",vapi_id)
        url = f"https://api.vapi.ai/call/{vapi_id}"

        headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }   
        task_id = inbound_call_task.request.id
        sample_response = requests.get(url, headers=headers).json()
        
        vapi_response=sample_response
        print("vapi_response--->",vapi_response)
        to_phone_number=sample_response["customer"]["number"]
        from_phone_number=sample_response["artifact"]["variableValues"]["phoneNumber"]["number"]
        status=vapi_response["status"]
        endedReason="" if "endedReason" not in vapi_response else vapi_response["endedReason"]
        recording_url="" if "recordingUrl" not in vapi_response else vapi_response["recordingUrl"]
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
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        unique_filename = f"{vapi_id}_{to_phone_number}.txt"
        content_type = "text/plain"
        text_message_bytes = text_message.encode("utf-8")  # convert string → bytes
        file_obj = BytesIO(text_message_bytes)
        
        s3.upload_fileobj(
                file_obj,
                settings.AWS_STORAGE_BUCKET_NAME,
                f"InboundCalls/{unique_filename}",
                ExtraArgs={"ContentType":content_type}
            )
        new_call=Inbound_Hospital.objects.create(
            vapi_id=vapi_id,
            status=status,
            endedReason=endedReason,
            started_at=started_at,
            ended_at=ended_at,
            
            message_s3_link="s3://"+settings.AWS_STORAGE_BUCKET_NAME+"/"+"InboundCalls"+"/"+unique_filename,
            audio_link=recording_url,
            task_id=task_id,
            from_phone_number=from_phone_number,
            to_phone_numnber=to_phone_number
            # endedReason=endedReason,
        )
        print("done")
        return {"error":0,"errorMsg":"","text_message":"inbound call done"}
    except Exception as e:
        
        tb = traceback.format_exc()
        print("Traceback error:\n", tb)
        return {"error":1,"errorMsg":str(e),"traceback": tb}
       
@shared_task
def process_inbound_calls(json_payload):
    try:
        import pandas as pd
        db_outbound_hospital_id=json_payload["patient_id"]
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
        task_id_process = process_inbound_calls.request.id
        sample_response = requests.get(url, headers=headers).json()
        vapi_response=sample_response
        print("vapi_response--->",vapi_response)
        is_400=False
        if "statusCode" in vapi_response:
            if vapi_response["statusCode"]==400:
                is_400=True
        if is_400:
            is_400=True
            df=pd.read_excel(r"C:\fettle_backend_new_consider_this\phone_calling\outbound_calls_2025-11-04_to_2025-12-29 (3).xlsx")
            df.fillna("",inplace=True)
            df_patient=df[df['patient_id']==patient_idd]
            
            response = requests.get(list(df_patient['transcription_link'])[0])

            if response.status_code == 200:
                content = response.text
            vapi_response={"status":"ended","endedReason":list(df_patient['endedReason'])[0],"recordingUrl":list(df_patient["audio_link"])[0],"startedAt":list(df_patient['started_at'])[0].isoformat(),"endedAt":list(df_patient["ended_at"])[0].isoformat(),"messages":content,}
        status=vapi_response["status"]
        print("status---->",status)
        mobile_no=json_payload["to_phone_number"]
        endedReason="" if "endedReason" not in vapi_response else vapi_response["endedReason"]
        if len(endedReason)==0:
            return {"error":0,"errorMsg":"","text_message":"calling phase,the call has not ended"}
        recording_url="" if "recordingUrl" not in vapi_response else vapi_response["recordingUrl"]
        print("recording_url",)
        # hospital_name=json_payload["hospital_name"]
        started_at=None if "startedAt" not in vapi_response else vapi_response["startedAt"]
        ended_at=None if "endedAt" not in vapi_response else vapi_response["endedAt"]
        text_message=""
        
        if "messages" not in vapi_response:
            message_s3_link=""
        else:
            messages_response=vapi_response["messages"]
            if is_400==False:
                for i in messages_response[1:]:
                    # print("i-->",i)
                    if ("message" in i) and ("role" in i):
                        text_message += f"{i['role']}: {i['message']}\n\n"
            else:
                text_message=vapi_response['messages']
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
            print("token-->",token)
            headers_url = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            call_progress='not_happened'
            if len(recording_url)!=0:
                call_duration = round((datetime.fromisoformat(ended_at) - datetime.fromisoformat(started_at)).total_seconds() / 60, 2)
                json_response=json_audio(patient_idd,text_message,started_at,call_duration)
                json_response['call_status']='connected'
                call_progress='connected'
                if json_response['call_outcome']=='negative' or json_response['call_outcome']=='escalated':
                    json_response['escalation_required']=True
                if json_response['call_status']=='not_connected':
                    json_response['escalation_required']=False
                    json_response['community_added']=False
                department=Inbound_Hospital.objects.get(id=patient_idd).department
                print("json_response--->",json_response)
                if "error" not in json_response:
                    
                    call_feedback_payload={"call_duration":call_duration,"call_outcome":json_response["call_outcome"],"call_status":json_response["call_status"],"called_at":started_at,"called_by":json_response["called_by"],"community_added":json_response["community_added"],"escalation_required":json_response["escalation_required"],"patient_id":patient_idd,"remarks":json_response["remarks"],"revisit_encouraged":json_response["revisit_encouraged"]}
                    url_call=url_backend+"/api/callfeedback_inbound/"
                    call_res = requests.post(url_call,headers=headers_url,json=call_feedback_payload).json()
                    print("call_res1--->",call_res,call_feedback_payload)
                    if json_response['escalation_required']==True:
                        escalation_payload={"patient_id":patient_idd,"issue_description":json_response['remarks'],"department":department}
                        url_escalation=url_backend+"/api/escalationfeedback_inbound/"
                        call_escalation = requests.post(url_escalation,headers=headers_url,json=escalation_payload).json()

                        ##call api
                    if json_response['community_added']==True:
                        community_payload={"patient_id":patient_idd,"engagement_type":"post","department":department}
                        url_community=url_backend+"/api/communityfeedback_inbound/"
                        call_community = requests.post(url_community,headers=headers_url,json=community_payload).json()
                        ##call api

            else:
                print("calling api")
                call_progress="not_connected"
                call_feedback_payload={"call_outcome":"no_feedback","call_status":"not_connected","called_by":"Vapi Agent","community_added":False,"escalation_required":False,"patient_id":patient_idd,"remarks":False,"revisit_encouraged":False,"called_at":started_at}
                url_call=url_backend+"/api/callfeedback_inbound/"
                call_res = requests.post(url_call,headers=headers_url,json=call_feedback_payload).json()
                print("call_res-->",call_res,call_feedback_payload)

        except Exception as e:
            pass
        # s3 = boto3.client(
        #     "s3",
        #     aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        #     aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        #     region_name=settings.AWS_S3_REGION_NAME,
        # )
        # unique_filename = f"{vapi_id}_{mobile_no}.txt"
        # content_type = "text/plain"
        # text_message_bytes = text_message.encode("utf-8")  # convert string → bytes
        # file_obj = BytesIO(text_message_bytes)
        
        # s3.upload_fileobj(
        #         file_obj,
        #         settings.AWS_STORAGE_BUCKET_NAME,
        #         f"Inbound/{unique_filename}",
        #         ExtraArgs={"ContentType":content_type}
        #     )
        ##update db
        print("started_at",started_at)
        
        objj=Inbound_Hospital.objects.get(id=db_outbound_hospital_id)
        
        objj.status=status
        objj.endedReason=endedReason
        if started_at!=None:
            objj.started_at=started_at
        if ended_at!=None:
            objj.ended_at=ended_at
        # objj.message_s3_link="s3://"+settings.AWS_STORAGE_BUCKET_NAME+"/"+"Inbound"+"/"+unique_filename
        objj.audio_link=recording_url
        objj.task_id_process=task_id_process
        objj.calling_process=call_progress
        objj.save()
        return {"error":0,"errorMsg":"","text_message":text_message}
    except Exception as e:
        print(str(e))
        return {"error":1,"errorMsg":str(e)}
        
    
    