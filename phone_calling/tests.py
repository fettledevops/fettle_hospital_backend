import importlib
import sys
import types


def load_tasks_module(monkeypatch):
    fake_livekit_module = types.ModuleType("phone_calling.livekit_calling")

    def fake_dispatch_call(phone_number, id_key):
        return None

    fake_livekit_module.dispatch_call = fake_dispatch_call
    monkeypatch.setitem(
        sys.modules, "phone_calling.livekit_calling", fake_livekit_module
    )
    if "phone_calling.tasks" in sys.modules:
        del sys.modules["phone_calling.tasks"]
    return importlib.import_module("phone_calling.tasks")


def test_cloudconnect_whatsapp_msg_returns_success(monkeypatch):
    tasks = load_tasks_module(monkeypatch)
    result = tasks.cloudconnect_whatsapp_msg("hello", "+911234567890")
    assert result == {"status": "success"}


def test_read_from_s3_bucket_success(monkeypatch):
    tasks = load_tasks_module(monkeypatch)

    class FakeBody:
        def read(self):
            return b"sample text"

    class FakeS3:
        def get_object(self, Bucket, Key):
            return {"Body": FakeBody()}

    monkeypatch.setattr(tasks.boto3, "client", lambda *args, **kwargs: FakeS3())
    result = tasks.read_from_s3_bucket("bucket", "key")
    assert result == {"error": 0, "text": "sample text"}


def test_read_from_s3_bucket_failure(monkeypatch):
    tasks = load_tasks_module(monkeypatch)

    def fake_client(*args, **kwargs):
        raise RuntimeError("s3 down")

    monkeypatch.setattr(tasks.boto3, "client", fake_client)
    result = tasks.read_from_s3_bucket("bucket", "key")
    assert result["error"] == 1
    assert "s3 down" in result["errorMsg"]


def test_inbound_call_task_returns_expected_response(monkeypatch):
    tasks = load_tasks_module(monkeypatch)
    result = tasks.inbound_call_task.run({"vapi_id": "room-1"})
    assert result == {"status": "automated_via_sip"}


def test_process_inbound_calls_success(monkeypatch):
    tasks = load_tasks_module(monkeypatch)
    result = tasks.process_inbound_calls.run({"vapi_id": "room-1"})
    assert result == {"status": "success"}


def test_process_inbound_calls_missing_vapi_id_returns_error(monkeypatch):
    tasks = load_tasks_module(monkeypatch)
    result = tasks.process_inbound_calls.run({})
    assert result["error"] == 1
    assert "vapi_id" in result["msg"]
