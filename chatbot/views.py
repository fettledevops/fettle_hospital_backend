"""
chatbot/views.py — Dermatology AI Consultation API

Implemented fixes:
  FIX 1: AI is silent in dermatologist_review and final_output modes
  FIX 2: Face detection (skin_image step) and PII detection (report_image step)
  FIX 3: Image deduplication by URL before saving to conversation
  FIX 4: Doctor draft uses get_doctor_draft_format() from GlobalConfig
  FIX 6: Robust AI response extraction with fallback message
"""

import base64
import json
import os
import threading
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from project.jwt_auth import JWTAuthentication, create_token

from .langgraph_prep import run_education_graph, run_internal_consultation
from .models import DermatologyPatient, DermatologyThread, GlobalConfig
from .system_ins import GENERAL_EDUCATION_SYSTEM, get_doctor_draft_format


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _openai_client():
    """Return an OpenAI client using the env API key."""
    from openai import OpenAI
    return OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))


def save_image_file(image_file, folder: str = 'dermatology_images') -> str:
    """Save an uploaded image file and return a server-accessible URL."""
    ext = 'jpg'
    if image_file.name and '.' in image_file.name:
        ext = image_file.name.rsplit('.', 1)[-1].lower()
    filename = f"{folder}/{uuid.uuid4().hex}.{ext}"
    path = default_storage.save(filename, ContentFile(image_file.read()))
    base_url = os.environ.get('BACKEND_BASE_URL', '').rstrip('/')
    media_url = getattr(settings, 'MEDIA_URL', '/media/')
    return f"{base_url}{media_url}{path}"


def check_image_for_face(image_file) -> bool:
    """
    FIX 2: AI vision check — asks LLM to reply FACE_DETECTED or NO_FACE.
    Returns True when a face is detected.
    """
    try:
        data = image_file.read()
        image_file.seek(0)
        b64 = base64.b64encode(data).decode('utf-8')
        client = _openai_client()
        resp = client.chat.completions.create(
            model='gpt-4o',
            max_tokens=10,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image_url',
                        'image_url': {
                            'url': f'data:image/jpeg;base64,{b64}',
                            'detail': 'low',
                        },
                    },
                    {
                        'type': 'text',
                        'text': (
                            'Does this image contain a human face with '
                            'clearly visible eyes, nose, and mouth together? '
                            'Reply FACE_DETECTED or NO_FACE only.'
                        ),
                    },
                ],
            }],
        )
        result = resp.choices[0].message.content.strip().upper()
        return 'FACE_DETECTED' in result
    except Exception as exc:  # noqa: BLE001
        print(f'Face detection error (allowing through): {exc}')
        return False


def check_report_for_pii(image_file) -> bool:
    """
    FIX 2: AI vision check — asks LLM to reply PII_DETECTED or PII_CLEAR.
    Returns True when personal information is visible.
    """
    try:
        data = image_file.read()
        image_file.seek(0)
        b64 = base64.b64encode(data).decode('utf-8')
        client = _openai_client()
        resp = client.chat.completions.create(
            model='gpt-4o',
            max_tokens=10,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image_url',
                        'image_url': {
                            'url': f'data:image/jpeg;base64,{b64}',
                            'detail': 'low',
                        },
                    },
                    {
                        'type': 'text',
                        'text': (
                            'Does this image contain clearly readable personal information '
                            'such as a patient name, date of birth, phone number, or ID number? '
                            'Reply PII_DETECTED or PII_CLEAR only.'
                        ),
                    },
                ],
            }],
        )
        result = resp.choices[0].message.content.strip().upper()
        return 'PII_DETECTED' in result
    except Exception as exc:  # noqa: BLE001
        print(f'PII detection error (allowing through): {exc}')
        return False


def _extract_ai_response(result: dict) -> str:
    """
    FIX 6: Iterate messages in reverse to find the last valid text content.
    Falls back to a safe error message if nothing is found.
    """
    ai_response = ''
    for msg in reversed(result.get('messages', [])):
        if hasattr(msg, 'content'):
            if isinstance(msg.content, str) and msg.content.strip():
                ai_response = msg.content.strip()
                break
            elif isinstance(msg.content, list):
                for part in msg.content:
                    if (
                        isinstance(part, dict)
                        and part.get('type') == 'text'
                        and part.get('text', '').strip()
                    ):
                        ai_response = part['text'].strip()
                        break
        if ai_response:
            break
    if not ai_response:
        ai_response = "I'm sorry, I was unable to generate a response. Please try again."
    return ai_response


def _get_or_create_patient(email: str, name: str = '') -> DermatologyPatient:
    patient, created = DermatologyPatient.objects.get_or_create(
        email=email,
        defaults={'name': name or email.split('@')[0]},
    )
    if not created and name and name != email.split('@')[0] and patient.name != name:
        patient.name = name
        patient.save(update_fields=['name'])
    return patient


def _get_active_thread(patient: DermatologyPatient) -> DermatologyThread:
    """Return the latest active thread, creating one if none exists."""
    thread = (
        DermatologyThread.objects
        .filter(patient=patient, status='active')
        .order_by('-created_at')
        .first()
    )
    if not thread:
        thread = DermatologyThread.objects.create(
            patient=patient,
            name='Consultation',
            mode='general_education',
        )
    return thread


def _trigger_draft_generation(thread: DermatologyThread) -> None:
    """
    FIX 4: Generate the AI doctor draft in a background thread.
    Uses get_doctor_draft_format() for the system prompt.
    """
    try:
        system_prompt = get_doctor_draft_format()
        intake = thread.intake_data or {}
        conv = thread.conversation or []

        user_content = (
            f'Patient Intake Summary:\n'
            f'- Duration: {intake.get("duration", "Not provided")}\n'
            f'- Symptoms: {intake.get("symptoms", "Not provided")}\n'
            f'- Location: {intake.get("location", "Not provided")}\n'
            f'- Medications Tried: {intake.get("meds", "Not provided")}\n'
            f'- Prior History: {intake.get("history", "Not provided")}\n\n'
            'Generate strictly following the format. Do not use any other format.'
        )

        draft = run_internal_consultation(system_prompt, conv, user_content)
        if draft:
            # Refresh thread from DB in case it was updated
            thread.refresh_from_db()
            thread.draft_response = draft
            thread.save(update_fields=['draft_response'])
    except Exception as exc:  # noqa: BLE001
        print(f'Draft generation error: {exc}')


def _collect_intake_images(thread: DermatologyThread) -> list:
    """Collect all image URLs from intake_data and conversation."""
    intake = thread.intake_data or {}
    seen = set()
    images = []
    for url in intake.get('skin_images', []) + intake.get('report_images', []):
        if url not in seen:
            images.append(url)
            seen.add(url)
    for msg in (thread.conversation or []):
        for url in (msg.get('images') or []):
            if url not in seen:
                images.append(url)
                seen.add(url)
    return images


# ---------------------------------------------------------------------------
# Auth Views
# ---------------------------------------------------------------------------

class GoogleAuthView(APIView):
    """
    POST /auth/google/
    Patient authentication via Google OAuth or Magic Link.
    Creates or retrieves a DermatologyPatient and returns a signed JWT.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data.get('email')
        name = request.data.get('name', '')
        if not email:
            return Response({'error': 1, 'msg': 'Email is required'}, status=400)
        try:
            patient = _get_or_create_patient(email, name)
            token = create_token(
                {
                    'user_id': str(patient.id),
                    'email': patient.email,
                    'name': patient.name,
                    'role': 'patient',
                },
                timeout=10080,  # 7 days
            )
            return Response({'token': token, 'name': patient.name, 'email': patient.email, 'error': 0})
        except Exception as exc:  # noqa: BLE001
            return Response({'error': 1, 'msg': str(exc)}, status=500)


class DermatologyValidateTokenView(APIView):
    """
    GET /api/validate_token/
    Validates patient or doctor tokens and returns user info.
    Handles both 'patient' (DermatologyPatient) and 'doctor' (Doctor_model) roles.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = []

    def get(self, request):
        try:
            email = request.email
            role = request.role
            if role == 'patient':
                patient = DermatologyPatient.objects.get(email=email)
                return Response({
                    'error': 0,
                    'name': patient.name,
                    'email': patient.email,
                    'role': 'patient',
                })
            else:
                # Delegate to existing Doctor_model for doctor tokens
                from app.models import Doctor_model
                doctor = Doctor_model.objects.get(email=email)
                return Response({
                    'error': 0,
                    'name': doctor.name,
                    'email': doctor.email,
                    'role': 'doctor',
                })
        except Exception as exc:  # noqa: BLE001
            return Response({'error': 1, 'msg': str(exc)})


# ---------------------------------------------------------------------------
# Patient Chat Views
# ---------------------------------------------------------------------------

class ChatView(APIView):
    """
    GET  /api/chat_history/  — fetch conversation history
    POST /api/chat_view/     — send a patient message

    FIX 1: Guard — AI silent in dermatologist_review and final_output modes.
    FIX 2: Face/PII detection on image uploads.
    FIX 3: Image deduplication before storing.
    FIX 6: Robust AI response extraction with fallback.
    """
    authentication_classes = [JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        """GET /api/chat_history/ — returns conversation for active (or specified) thread."""
        try:
            patient = DermatologyPatient.objects.get(email=request.email)
            thread_id = request.query_params.get('thread_id')
            if thread_id:
                try:
                    thread = DermatologyThread.objects.get(id=thread_id, patient=patient)
                except DermatologyThread.DoesNotExist:
                    thread = _get_active_thread(patient)
            else:
                thread = _get_active_thread(patient)
            return Response({
                'error': 0,
                'conv': thread.conversation or [],
                'mode': thread.mode,
                'thread_id': thread.id,
            })
        except DermatologyPatient.DoesNotExist:
            return Response({'error': 1, 'msg': 'Patient not found'})
        except Exception as exc:  # noqa: BLE001
            return Response({'error': 1, 'msg': str(exc)})

    def post(self, request):
        """POST /api/chat_view/ — handle a patient message."""
        try:
            patient = DermatologyPatient.objects.get(email=request.email)

            question = request.POST.get('question', '') or request.data.get('question', '')
            thread_id = request.POST.get('thread_id', '') or request.data.get('thread_id', '')

            # FIX 2: Read step from both POST and data
            step = request.POST.get('step', '') or request.data.get('step', '')
            print(f"DEBUG step='{step}' files={list(request.FILES.keys())}")

            # Resolve thread
            thread = None
            if thread_id:
                try:
                    thread = DermatologyThread.objects.get(id=thread_id, patient=patient)
                except DermatologyThread.DoesNotExist:
                    pass
            if thread is None:
                thread = _get_active_thread(patient)

            # ----------------------------------------------------------------
            # FIX 1: Guard — return empty immediately for silent modes
            # ----------------------------------------------------------------
            if thread.mode in ('dermatologist_review', 'final_output'):
                if question and question not in ('', 'CONFIRM'):
                    conv = list(thread.conversation or [])
                    user_msg: dict = {
                        'id': f'user-{uuid.uuid4().hex}',
                        'role': 'user',
                        'content': question,
                    }
                    images = request.FILES.getlist('image')
                    if images:
                        # FIX 3: Deduplicate existing URLs before saving
                        existing = {u for m in conv for u in (m.get('images') or [])}
                        new_urls = []
                        for img in images:
                            url = save_image_file(img)
                            if url not in existing:
                                new_urls.append(url)
                                existing.add(url)
                        if new_urls:
                            user_msg['images'] = new_urls
                    conv.append(user_msg)
                    thread.conversation = conv
                    thread.save(update_fields=['conversation'])
                return Response({'result': '', 'response': '', 'message': '', 'role': 'ai', 'mode': thread.mode})

            # ----------------------------------------------------------------
            # Payment confirmation
            # ----------------------------------------------------------------
            if question == 'CONFIRM':
                thread.payment_status = 'paid'
                thread.mode = 'post_payment_intake'
                thread.save(update_fields=['payment_status', 'mode'])
                return Response({'result': '', 'role': 'ai', 'mode': thread.mode})

            conv = list(thread.conversation or [])

            # ----------------------------------------------------------------
            # Image upload handling (FIX 2 + FIX 3)
            # ----------------------------------------------------------------
            images = request.FILES.getlist('image')
            new_img_urls: list[str] = []

            if images:
                # FIX 3: collect all existing URLs to deduplicate
                existing_urls: set[str] = {u for m in conv for u in (m.get('images') or [])}

                if step == 'skin_image':
                    # FIX 2: face detection
                    for img in images:
                        if check_image_for_face(img):
                            return Response({
                                'result': 'face detected — no clinical image of skin issue is visible',
                                'response': 'face detected — no clinical image of skin issue is visible',
                                'role': 'ai',
                                'mode': thread.mode,
                            })
                        url = save_image_file(img)
                        if url not in existing_urls:
                            new_img_urls.append(url)
                            existing_urls.add(url)

                elif step == 'report_image':
                    # FIX 2: PII detection
                    for img in images:
                        if check_report_for_pii(img):
                            return Response({
                                'result': 'personal information visible — please redact name or number and re-upload',
                                'response': 'personal information visible — please redact name or number and re-upload',
                                'role': 'ai',
                                'mode': thread.mode,
                            })
                        url = save_image_file(img)
                        if url not in existing_urls:
                            new_img_urls.append(url)
                            existing_urls.add(url)

                else:
                    existing_urls = {u for m in conv for u in (m.get('images') or [])}
                    for img in images:
                        url = save_image_file(img)
                        if url not in existing_urls:
                            new_img_urls.append(url)
                            existing_urls.add(url)

            # ----------------------------------------------------------------
            # Build user message
            # ----------------------------------------------------------------
            user_msg = {'id': f'user-{uuid.uuid4().hex}', 'role': 'user', 'content': question}
            if new_img_urls:
                user_msg['images'] = new_img_urls
            conv.append(user_msg)

            # ----------------------------------------------------------------
            # post_payment_intake: store intake data, return empty
            # (frontend drives the question flow — FIX 1)
            # ----------------------------------------------------------------
            if thread.mode == 'post_payment_intake':
                intake = dict(thread.intake_data or {})

                if step == 'skin_image' and new_img_urls:
                    skin = intake.get('skin_images', [])
                    for u in new_img_urls:
                        if u not in skin:
                            skin.append(u)
                    intake['skin_images'] = skin

                elif step == 'report_image' and new_img_urls:
                    reports = intake.get('report_images', [])
                    for u in new_img_urls:
                        if u not in reports:
                            reports.append(u)
                    intake['report_images'] = reports

                # Detect INTAKE COMPLETE and transition mode
                if 'INTAKE COMPLETE' in question and 'Summary:' in question:
                    for line in question.splitlines():
                        line = line.strip()
                        if line.startswith('Duration:'):
                            intake['duration'] = line[len('Duration:'):].strip()
                        elif line.startswith('Symptoms:'):
                            intake['symptoms'] = line[len('Symptoms:'):].strip()
                        elif line.startswith('Location:'):
                            intake['location'] = line[len('Location:'):].strip()
                        elif line.startswith('Meds:'):
                            intake['meds'] = line[len('Meds:'):].strip()
                        elif line.startswith('History:'):
                            intake['history'] = line[len('History:'):].strip()

                    thread.mode = 'dermatologist_review'
                    thread.intake_data = intake
                    thread.conversation = conv
                    thread.save(update_fields=['mode', 'intake_data', 'conversation'])

                    # Background draft generation
                    t = threading.Thread(target=_trigger_draft_generation, args=(thread,))
                    t.daemon = True
                    t.start()

                    return Response({'result': '', 'role': 'ai', 'mode': 'dermatologist_review'})

                thread.intake_data = intake
                thread.conversation = conv
                thread.save(update_fields=['intake_data', 'conversation'])
                return Response({'result': '', 'role': 'ai', 'mode': thread.mode})

            # ----------------------------------------------------------------
            # general_education: AI responds via LLM
            # FIX 6: robust extraction with fallback
            # ----------------------------------------------------------------
            ai_response = ''
            try:
                ai_response = run_education_graph(
                    GENERAL_EDUCATION_SYSTEM,
                    conv[:-1],  # history before the current message
                    question,
                )
            except Exception as exc:  # noqa: BLE001
                print(f'AI response error: {exc}')

            # FIX 6: fallback
            if not ai_response:
                ai_response = "I'm sorry, I was unable to generate a response. Please try again."

            ai_msg = {'id': f'ai-{uuid.uuid4().hex}', 'role': 'AI', 'content': ai_response}
            conv.append(ai_msg)
            thread.conversation = conv
            thread.save(update_fields=['conversation'])

            return Response({
                'result': ai_response,
                'response': ai_response,
                'message': ai_response,
                'role': 'ai',
                'mode': thread.mode,
            })

        except DermatologyPatient.DoesNotExist:
            return Response({'error': 1, 'msg': 'Patient not found'})
        except Exception as exc:  # noqa: BLE001
            print(f'ChatView error: {exc}')
            return Response({'error': 1, 'msg': str(exc)})


class ConsultationListView(APIView):
    """GET /api/consultation_list/ — list all consultations for a patient."""
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            patient = DermatologyPatient.objects.get(email=request.email)
            threads = DermatologyThread.objects.filter(patient=patient).order_by('-created_at')
            history = [
                {
                    'id': str(t.id),
                    'name': t.name,
                    'mode': t.mode,
                    'status': t.status,
                    'created_at': t.created_at.isoformat(),
                }
                for t in threads
            ]
            return Response({'history': history, 'error': 0})
        except DermatologyPatient.DoesNotExist:
            return Response({'history': [], 'error': 0})
        except Exception as exc:  # noqa: BLE001
            return Response({'error': 1, 'msg': str(exc)})


class ArchiveConsultationView(APIView):
    """POST /api/archive_consultation/ — archive active thread and start a fresh one."""
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            patient = DermatologyPatient.objects.get(email=request.email)
            # Complete all active threads
            DermatologyThread.objects.filter(
                patient=patient, status='active'
            ).update(status='completed')
            # Create new thread
            new_thread = DermatologyThread.objects.create(
                patient=patient,
                name='New Consultation',
                mode='general_education',
            )
            return Response({'error': 0, 'thread_id': new_thread.id, 'msg': 'New consultation started'})
        except DermatologyPatient.DoesNotExist:
            return Response({'error': 1, 'msg': 'Patient not found'})
        except Exception as exc:  # noqa: BLE001
            return Response({'error': 1, 'msg': str(exc)})


# ---------------------------------------------------------------------------
# Doctor Views
# ---------------------------------------------------------------------------

class DoctorChatAPIView(APIView):
    """
    GET  /api/doctor_chat_view/ — list all paid consultations for the doctor dashboard
    POST /api/doctor_chat_view/ — AI-assisted consultation / REGENERATE_DRAFT

    FIX 4: Uses get_doctor_draft_format() for the system prompt.
    """
    authentication_classes = [JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        """Return all paid threads for the doctor dashboard."""
        try:
            threads = (
                DermatologyThread.objects
                .filter(payment_status='paid')
                .select_related('patient')
                .order_by('-created_at')
            )
            conversations = []
            for thread in threads:
                intake_images = _collect_intake_images(thread)
                intake = thread.intake_data or {}
                conversations.append({
                    'id': thread.id,
                    'patient_id': str(thread.patient.id),
                    'patientEmail': thread.patient.email,
                    'patientName': thread.patient.name,
                    'mode': thread.mode,
                    'paymentStatus': thread.payment_status,
                    'status': thread.status,
                    'draftResponse': thread.draft_response or '',
                    'intakeData': {
                        'duration': intake.get('duration', ''),
                        'symptoms': intake.get('symptoms', ''),
                        'location': intake.get('location', ''),
                        'medicationsTried': intake.get('meds', ''),
                        'priorDiagnoses': intake.get('prior_diagnoses', ''),
                        'relevantHealthHistory': intake.get('history', ''),
                        'images': intake_images,
                    },
                    'messages': thread.conversation or [],
                })
            return Response({'conversations': conversations, 'error': 0})
        except Exception as exc:  # noqa: BLE001
            return Response({'error': 1, 'msg': str(exc)})

    def post(self, request):
        """Doctor AI consultation or draft regeneration."""
        try:
            conversation_id = request.POST.get('id', '') or request.data.get('id', '')
            question = request.POST.get('question', '') or request.data.get('question', '')

            thread = DermatologyThread.objects.get(id=conversation_id)

            # Trigger background draft regeneration
            if question == 'REGENERATE_DRAFT':
                t = threading.Thread(target=_trigger_draft_generation, args=(thread,))
                t.daemon = True
                t.start()
                return Response({'result': 'Draft regeneration started', 'error': 0})

            # FIX 4: Use get_doctor_draft_format() for system prompt
            system_prompt = get_doctor_draft_format()
            conv = thread.conversation or []

            ai_response = run_internal_consultation(system_prompt, conv, question)

            # FIX 6: fallback
            if not ai_response:
                ai_response = "I'm sorry, I was unable to generate a response. Please try again."

            return Response({
                'result': ai_response,
                'response': ai_response,
                'message': ai_response,
                'role': 'ai',
                'error': 0,
            })
        except DermatologyThread.DoesNotExist:
            return Response({'error': 1, 'msg': 'Thread not found'})
        except Exception as exc:  # noqa: BLE001
            return Response({'error': 1, 'msg': str(exc)})


class DoctorSendResponseView(APIView):
    """POST /api/doctor_send_response/ — doctor sends final response to patient."""
    authentication_classes = [JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        try:
            conversation_id = request.POST.get('id', '') or request.data.get('id', '')
            message = request.POST.get('question', '') or request.data.get('question', '')

            thread = DermatologyThread.objects.get(id=conversation_id)
            conv = list(thread.conversation or [])

            doctor_msg: dict = {
                'id': f'doctor-{uuid.uuid4().hex}',
                'role': 'doctor',
                'content': message,
                'senderName': 'Dr. Attili',
            }

            images = request.FILES.getlist('image')
            if images:
                # FIX 3: deduplicate
                existing_urls = {u for m in conv for u in (m.get('images') or [])}
                img_urls = []
                for img in images:
                    url = save_image_file(img)
                    if url not in existing_urls:
                        img_urls.append(url)
                        existing_urls.add(url)
                if img_urls:
                    doctor_msg['images'] = img_urls

            conv.append(doctor_msg)
            thread.conversation = conv
            thread.mode = 'final_output'
            thread.save(update_fields=['conversation', 'mode'])

            return Response({'error': 0, 'msg': 'Response sent to patient'})
        except DermatologyThread.DoesNotExist:
            return Response({'error': 1, 'msg': 'Thread not found'})
        except Exception as exc:  # noqa: BLE001
            return Response({'error': 1, 'msg': str(exc)})
