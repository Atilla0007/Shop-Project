import json
import time
from pathlib import Path

import logging
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import Count, Max, Q
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .bot import ShopBot, format_contact_info
from .forms import ContactForm
from .models import ChatMessage, ChatThread, ContactMessage, News
from store.models import Category, Order, Product

logger = logging.getLogger(__name__)

def _get_first_staff():
    return User.objects.filter(is_staff=True).order_by("id").first()


def _load_faq_text():
    pdf_path = Path("static/faq.pdf")
    if not pdf_path.exists():
        return ""
    try:
        data = pdf_path.read_bytes()
        # keep it simple: no parser, just marker that content exists
        return f"PDF bytes length: {len(data)} (replace with real FAQ content later)."
    except Exception:
        return ""


def _build_user_context(user):
    orders = (
        Order.objects.filter(user=user)
        .prefetch_related("items", "items__product")
        .order_by("-created_at")[:5]
    )
    products = Product.objects.all().order_by("-id")[:10]

    order_lines = []
    for o in orders:
        items = ", ".join(f"{it.product.name} x{it.quantity}" for it in o.items.all())
        order_lines.append(f"Order #{o.id} on {o.created_at:%Y-%m-%d} items: {items}")

    product_lines = [f"{p.name} - {p.price}" for p in products]

    return (
        f"user: {user.username} | email: {user.email} | joined: {user.date_joined:%Y-%m-%d}\n"
        f"orders: {order_lines or ['none']}\n"
        f"products: {product_lines or ['none']}"
    )


# ----------------------------
#      Public pages (Home / Contact / FAQ)
# ----------------------------

def home(request):
    """Render home page with highlighted products and news."""
    products = Product.objects.all()[:8]
    news = News.objects.all()[:3]
    categories = Category.objects.all()

    context = {
        "products": products,
        "news": news,
        "categories": categories,
    }
    return render(request, "home.html", context)


def contact(request):
    """Handle contact form submission and render the contact page."""
    def _admin_emails():
        return list(
            User.objects.filter(is_superuser=True, email__isnull=False)
            .exclude(email="")
            .values_list("email", flat=True)
        )

    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            message = form.save()
            # Send notification email to superusers
            admin_emails = _admin_emails()
            if admin_emails:
                try:
                    send_mail(
                        subject=f"پیام جدید از فرم تماس: {message.name}",
                        message=f"فرستنده: {message.name}\nایمیل: {message.email}\n\nمتن پیام:\n{message.message}",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=admin_emails,
                        fail_silently=True,
                    )
                except Exception:
                    # Avoid breaking user flow if email sending fails
                    logger.exception("Failed to send contact email to admins")

            return render(request, "contact.html", {
                "form": ContactForm(),
                "success": True,
            })
    else:
        form = ContactForm()

    return render(request, "contact.html", {"form": form})


def news_list(request):
    """List news items."""
    news = News.objects.all()
    return render(request, "news_list.html", {"news": news})


def news_detail(request, pk):
    """Show a single news item."""
    item = get_object_or_404(News, pk=pk)
    latest = News.objects.exclude(pk=pk)[:4]
    return render(request, "news_detail.html", {"item": item, "latest": latest})


def faq(request):
    """Render FAQ page."""
    return render(request, "faq.html")


# ----------------------------
#             User Chat
# ----------------------------

@login_required
def chat(request):
    """Render user chat page (thread ensured)."""
    ChatThread.objects.get_or_create(user=request.user)
    return render(request, "chat.html")


@login_required
def chat_messages(request):
    """Return chat messages for the current user as JSON and mark admin messages as read."""
    thread, _ = ChatThread.objects.get_or_create(user=request.user)

    messages_qs = thread.messages.select_related("sender").order_by("created_at")

    messages_data = []
    for m in messages_qs:
        messages_data.append({
            "id": m.id,
            "text": m.text,
            "is_admin": m.is_admin,
            "sender": m.sender.username if m.sender else ("پشتیبانی" if m.is_admin else "شما"),
            "created_at": timezone.localtime(m.created_at).strftime("%H:%M"),
        })

    # Mark admin messages as read when user fetches them.
    messages_qs.filter(is_admin=True, is_read_by_user=False).update(
        is_read_by_user=True
    )

    return JsonResponse({"messages": messages_data})


@login_required
@require_http_methods(["POST"])
def chat_send(request):
    """Send a user chat message via AJAX."""
    text = (request.POST.get("message") or "").strip()
    if not text:
        return JsonResponse({"status": "error", "error": "متن پیام نمی‌تواند خالی باشد."}, status=400)

    thread, _ = ChatThread.objects.get_or_create(user=request.user)

    receiver = _get_first_staff()

    msg = ChatMessage.objects.create(
        thread=thread,
        sender=request.user,
        receiver=receiver,
        text=text,
        is_admin=False,
        is_read_by_user=True,   # user sent it, so it is already read by user
        is_read_by_admin=False,
    )

    return JsonResponse({
        "status": "ok",
        "message_id": msg.id,
        "created_at": timezone.localtime(msg.created_at).strftime("%H:%M"),
    })


@login_required
def chat_stream(request):
    """Server-Sent Events stream for user chat notifications."""
    def event_stream():
        thread, _ = ChatThread.objects.get_or_create(user=request.user)
        last_check_time = timezone.now()

        while True:
            # Check if new admin messages exist since last check
            new_messages = thread.messages.filter(
                created_at__gt=last_check_time,
                is_admin=True  # only notify admin messages
            ).exists()

            if new_messages:
                data = json.dumps({
                    'type': 'new_message',
                    'timestamp': timezone.now().isoformat()
                })
                yield f"data: {data}\n\n"

            last_check_time = timezone.now()
            time.sleep(2)  # polling interval
    
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


# ----------------------------
#             Admin Chat
# ----------------------------

@staff_member_required
def admin_chat(request, user_id=None):
    """Admin chat dashboard with threads and optional active thread."""
    threads = (
        ChatThread.objects.select_related("user")
        .annotate(
            last_message_time=Max("messages__created_at"),
            unread_count=Count(
                "messages",
                filter=Q(messages__is_admin=False, messages__is_read_by_admin=False),
            ),
        )
        .order_by("-last_message_time")
    )

    # Attach last_message_time for UI sorting
    for t in threads:
        t.last_time = t.last_message_time

    active_thread = None
    user_orders = None

    if user_id is not None:
        active_thread = get_object_or_404(ChatThread, user_id=user_id)
        if active_thread.user:
            user_orders = (
                Order.objects.filter(user=active_thread.user)
                .prefetch_related("items", "items__product")
                .order_by("-created_at")
            )

    context = {
        "threads": threads,
        "active_thread": active_thread,
        "user_orders": user_orders,
    }
    return render(request, "admin_chat.html", context)


@staff_member_required
def admin_chat_messages(request, user_id):
    """Return messages for a user thread to admin, marking user messages as read."""
    thread = get_object_or_404(ChatThread, user_id=user_id)
    messages_qs = thread.messages.select_related("sender").order_by("created_at")

    messages_data = []
    for m in messages_qs:
        messages_data.append({
            "id": m.id,
            "text": m.text,
            "is_admin": m.is_admin,
            "sender": m.sender.username if m.sender else ("پشتیبانی" if m.is_admin else "کاربر"),
            "created_at": timezone.localtime(m.created_at).strftime("%H:%M"),
        })

    # Mark user messages as read by admin
    messages_qs.filter(is_admin=False, is_read_by_admin=False).update(
        is_read_by_admin=True
    )

    return JsonResponse({"messages": messages_data})


@staff_member_required
@require_http_methods(["POST"])
def admin_chat_send(request, user_id):
    """Admin sends a chat message to a user."""
    text = (request.POST.get("message") or "").strip()
    if not text:
        return JsonResponse({"status": "error", "error": "متن پیام نمی‌تواند خالی باشد."}, status=400)

    thread = get_object_or_404(ChatThread, user_id=user_id)

    ChatMessage.objects.create(
        thread=thread,
        sender=request.user,
        receiver=thread.user,
        text=text,
        is_admin=True,
        is_read_by_admin=True,
        is_read_by_user=False,
    )

    return JsonResponse({"status": "ok"})


@staff_member_required
def admin_chat_stream(request, user_id):
    """SSE stream for admin chat notifications."""
    def event_stream():
        thread = get_object_or_404(ChatThread, user_id=user_id)
        last_check_time = timezone.now()
        
        while True:
            new_messages = thread.messages.filter(
                created_at__gt=last_check_time,
                is_admin=False  # only notify admin about user messages
            ).exists()
            
            if new_messages:
                data = json.dumps({
                    'type': 'new_message',
                    'timestamp': timezone.now().isoformat()
                })
                yield f"data: {data}\n\n"
            
            last_check_time = timezone.now()
            time.sleep(2)  # polling interval
    
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response

@login_required
@require_http_methods(["POST"])
def chat_bot(request):
    """Chatbot endpoint: saves user message, calls LLM, saves bot reply."""
    if not request.user.is_authenticated:
        return JsonResponse({"status": "error", "error": "login_required"}, status=401)

    message_id = (request.POST.get("message_id") or "").strip()
    msg_obj = None
    if message_id:
        try:
            msg_obj = ChatMessage.objects.select_related("thread").get(
                id=message_id,
                thread__user=request.user,
                is_admin=False,
            )
        except ChatMessage.DoesNotExist:
            msg_obj = None

    if msg_obj:
        text = (msg_obj.text or "").strip()
        thread = msg_obj.thread
    else:
        text = (request.POST.get("message") or "").strip()
        if not text:
            return JsonResponse({"status": "error", "error": "متن پیام نمی‌تواند خالی باشد."}, status=400)

        thread, _ = ChatThread.objects.get_or_create(user=request.user)

    receiver = _get_first_staff()
    if not msg_obj:
        ChatMessage.objects.create(
            thread=thread,
            sender=request.user,
            receiver=receiver,
            text=text,
            is_admin=False,
            is_read_by_user=True,
            is_read_by_admin=False,
        )

    faq_text = _load_faq_text()
    contact_text = format_contact_info(
        phone=getattr(settings, "SUPPORT_PHONE", "xxx-xxx-xxxx"),
        telegram=getattr(settings, "SUPPORT_TELEGRAM", "@shop_support"),
        instagram=getattr(settings, "SUPPORT_INSTAGRAM", "@shop_insta"),
        email=getattr(settings, "SUPPORT_EMAIL", "support@example.com"),
    )
    user_context = _build_user_context(request.user)

    try:
        bot = ShopBot()
        resp = bot.ask(text, faq_text, user_context, contact_text)
        bot_reply = resp.reply
        handoff = resp.handoff
    except Exception:
        logger.exception("chatbot error")
        bot_reply = "در حال حاضر ربات در دسترس نیست. لطفاً بعداً تلاش کنید."
        handoff = True

    ChatMessage.objects.create(
        thread=thread,
        sender=receiver,
        receiver=request.user,
        text=bot_reply,
        is_admin=True,
        is_read_by_admin=True,
        is_read_by_user=False,
    )

    if handoff:
        support_email = getattr(settings, "SUPPORT_EMAIL", None)
        if support_email:
            send_mail(
                subject="درخواست پشتیبانی جدید",
                message=f"User {request.user.username} asked: {text}\nReply: {bot_reply}",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", support_email),
                recipient_list=[support_email],
                fail_silently=True,
            )

    return JsonResponse({"status": "ok", "reply": bot_reply, "handoff": handoff})
