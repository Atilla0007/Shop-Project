import os
from http.cookies import SimpleCookie
from importlib import import_module

import socketio
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.asgi import get_asgi_application
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "shopproject.settings")

django_asgi_app = get_asgi_application()

from core.models import ChatMessage, ChatThread  # noqa: E402

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[],
    logger=False,
    engineio_logger=False,
)

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore
User = get_user_model()


def serialize_message(message):
    sender_name = (
        message.sender.username
        if message.sender
        else ("admin" if message.is_admin else "user")
    )
    return {
        "id": message.id,
        "text": message.text,
        "is_admin": message.is_admin,
        "sender": sender_name,
        "created_at": timezone.localtime(message.created_at).strftime("%H:%M"),
    }


@sync_to_async
def get_user_from_scope(scope):
    headers = dict(scope.get("headers") or [])
    raw_cookie = headers.get(b"cookie")
    if not raw_cookie:
        return AnonymousUser()

    cookie = SimpleCookie()
    try:
        cookie.load(raw_cookie.decode())
    except Exception:
        return AnonymousUser()

    session_key = cookie.get(settings.SESSION_COOKIE_NAME)
    if not session_key:
        return AnonymousUser()

    session = SessionStore(session_key.value)
    user_id = session.get("_auth_user_id")
    if not user_id:
        return AnonymousUser()

    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


@sync_to_async
def user_exists(user_id: int) -> bool:
    return User.objects.filter(pk=user_id).exists()


@sync_to_async
def ensure_thread_for_user(user_id: int):
    thread, _ = ChatThread.objects.get_or_create(user_id=user_id)
    return thread


@sync_to_async
def persist_message(thread, sender_id: int, text: str, is_admin: bool):
    sender = User.objects.filter(pk=sender_id).first()
    message = ChatMessage.objects.create(
        thread=thread,
        sender=sender,
        text=text,
        is_admin=is_admin,
        is_read_by_user=not is_admin,
        is_read_by_admin=is_admin,
    )
    return serialize_message(message)


@sio.event
async def connect(sid, environ, auth):
    scope = (environ or {}).get("asgi.scope") or {}
    user = await get_user_from_scope(scope)

    if not user or not user.is_authenticated:
        raise ConnectionRefusedError("authentication_required")

    await ensure_thread_for_user(user.id)
    await sio.save_session(
        sid,
        {
            "user_id": user.id,
            "is_staff": bool(user.is_staff),
        },
    )
    await sio.enter_room(sid, f"user_{user.id}")


@sio.event
async def disconnect(sid):
    return


@sio.event
async def join_thread(sid, data):
    session = await sio.get_session(sid)
    if not session.get("is_staff"):
        return {"status": "error", "error": "permission_denied"}

    try:
        target_user_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        return {"status": "error", "error": "invalid_user"}

    if not await user_exists(target_user_id):
        return {"status": "error", "error": "user_not_found"}

    await ensure_thread_for_user(target_user_id)
    await sio.enter_room(sid, f"user_{target_user_id}")
    return {"status": "ok"}


@sio.event
async def user_message(sid, data):
    session = await sio.get_session(sid)
    user_id = session.get("user_id")
    if not user_id:
        return {"status": "error", "error": "unauthenticated"}

    text = (data.get("message") or "").strip()
    if not text:
        return {"status": "error", "error": "empty_message"}

    thread = await ensure_thread_for_user(user_id)
    payload = await persist_message(thread, user_id, text, is_admin=False)
    await sio.emit("chat_message", payload, room=f"user_{user_id}")
    return {"status": "ok"}


@sio.event
async def admin_message(sid, data):
    session = await sio.get_session(sid)
    if not session.get("is_staff"):
        return {"status": "error", "error": "permission_denied"}

    try:
        target_user_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        return {"status": "error", "error": "invalid_user"}

    if not await user_exists(target_user_id):
        return {"status": "error", "error": "user_not_found"}

    text = (data.get("message") or "").strip()
    if not text:
        return {"status": "error", "error": "empty_message"}

    thread = await ensure_thread_for_user(target_user_id)
    payload = await persist_message(
        thread, session.get("user_id"), text, is_admin=True
    )
    await sio.emit("chat_message", payload, room=f"user_{target_user_id}")
    return {"status": "ok"}


application = socketio.ASGIApp(sio, django_asgi_app)
