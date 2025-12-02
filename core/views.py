import json
import time
from pathlib import Path

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
        items = ", ".join(f"{it.product.title} x{it.quantity}" for it in o.items.all())
        order_lines.append(f"Order #{o.id} on {o.created_at:%Y-%m-%d} items: {items}")

    product_lines = [f"{p.title} - {p.price}" for p in products]

    return (
        f"user: {user.username} | email: {user.email} | joined: {user.date_joined:%Y-%m-%d}\n"
        f"orders: {order_lines or ['none']}\n"
        f"products: {product_lines or ['none']}"
    )


# ----------------------------
#      طµظپط­ط§طھ ط¹ظ…ظˆظ…غŒ (Homeâ€¦)
# ----------------------------

def home(request):
    """
    طµظپط­ظ‡ ط§طµظ„غŒ:
    - ع†ظ†ط¯ ظ…ط­طµظˆظ„ ط¨ط±ط§غŒ ظ†ظ…ط§غŒط´ (ظ¾ط±ظپط±ظˆط´ / ط¬ط¯غŒط¯)
    - ط¢ط®ط±غŒظ† ط§ط®ط¨ط§ط±
    - ظ„غŒط³طھ ط¯ط³طھظ‡â€Œط¨ظ†ط¯غŒâ€Œظ‡ط§ ط¨ط±ط§غŒ ظ¾ط§ظ¾â€Œط¢ظ¾ ط¯ط³طھظ‡â€Œط¨ظ†ط¯غŒ
    """
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
    """
    طµظپط­ظ‡ طھظ…ط§ط³ ط¨ط§ ظ…ط§ + ط°ط®غŒط±ظ‡ ظپط±ظ… ط¯ط± ContactMessage
    """
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            return render(request, "contact.html", {
                "form": ContactForm(),
                "success": True,
            })
    else:
        form = ContactForm()

    return render(request, "contact.html", {"form": form})


def news_list(request):
    """
    ظ„غŒط³طھ ع©ط§ظ…ظ„ ط§ط®ط¨ط§ط±
    """
    news = News.objects.all()
    return render(request, "news_list.html", {"news": news})


def faq(request):
    """
    طµظپط­ظ‡ ط³ظˆط§ظ„ط§طھ ظ…طھط¯ط§ظˆظ„ (ط§ط³طھط§طھغŒع©)
    """
    return render(request, "faq.html")


# ----------------------------
#             Chat â€“ ع©ط§ط±ط¨ط±
# ----------------------------

@login_required
def chat(request):
    """
    طµظپط­ظ‡â€ŒغŒ ط§طµظ„غŒ ع†طھ ع©ط§ط±ط¨ط± (ط؛غŒط± ط§ط² ظˆغŒط¬طھ ط´ظ†ط§ظˆط±).
    ظپظ‚ط· ظ‚ط§ظ„ط¨ ط±ط§ ط±ظ†ط¯ط± ظ…غŒâ€Œع©ظ†ط¯طŒ ظ¾غŒط§ظ…â€Œظ‡ط§ ط¨ط§ AJAX ع¯ط±ظپطھظ‡ ظ…غŒâ€Œط´ظˆظ†ط¯.
    """
    ChatThread.objects.get_or_create(user=request.user)
    return render(request, "chat.html")


@login_required
def chat_messages(request):
    """
    ع¯ط±ظپطھظ† ظ„غŒط³طھ ظ¾غŒط§ظ…â€Œظ‡ط§غŒ ع†طھ ع©ط§ط±ط¨ط± ط¬ط§ط±غŒ (ط¨ط±ط§غŒ طµظپط­ظ‡ ع†طھ ظˆ ظˆغŒط¬طھ ط´ظ†ط§ظˆط±).
    ط®ط±ظˆط¬غŒ: JSON ط´ط§ظ…ظ„ ط¢ط±ط§غŒظ‡â€ŒغŒ ظ¾غŒط§ظ…â€Œظ‡ط§.
    """
    thread, _ = ChatThread.objects.get_or_create(user=request.user)

    messages_qs = thread.messages.select_related("sender").order_by("created_at")

    messages_data = []
    for m in messages_qs:
        messages_data.append({
            "id": m.id,
            "text": m.text,
            "is_admin": m.is_admin,
            "sender": m.sender.username if m.sender else ("ظ¾ط´طھغŒط¨ط§ظ†" if m.is_admin else "ط´ظ…ط§"),
            "created_at": timezone.localtime(m.created_at).strftime("%H:%M"),
        })

    # ظˆظ‚طھغŒ ع©ط§ط±ط¨ط± ظ¾غŒط§ظ…â€Œظ‡ط§غŒ ط§ط¯ظ…غŒظ† ط±ط§ ظ…غŒâ€Œط¨غŒظ†ط¯طŒ ط¨ط±ط§غŒ ع©ط§ط±ط¨ط± "ط®ظˆط§ظ†ط¯ظ‡â€Œط´ط¯ظ‡" ظ…غŒâ€Œط´ظˆظ†ط¯
    messages_qs.filter(is_admin=True, is_read_by_user=False).update(
        is_read_by_user=True
    )

    return JsonResponse({"messages": messages_data})


@login_required
@require_http_methods(["POST"])
def chat_send(request):
    """
    ط§ط±ط³ط§ظ„ ظ¾غŒط§ظ… ط¬ط¯غŒط¯ طھظˆط³ط· ع©ط§ط±ط¨ط± (ط§ط² طµظپط­ظ‡ ع†طھ ظˆ ط§ط² ظˆغŒط¬طھ ط´ظ†ط§ظˆط±).
    ط§ظ†طھط¸ط§ط±: POST ط¨ط§ ظپغŒظ„ط¯ 'message'
    """
    text = (request.POST.get("message") or "").strip()
    if not text:
        return JsonResponse({"status": "error", "error": "ظ¾غŒط§ظ… ط®ط§ظ„غŒ ط§ط³طھ"}, status=400)

    thread, _ = ChatThread.objects.get_or_create(user=request.user)

    receiver = _get_first_staff()

    ChatMessage.objects.create(
        thread=thread,
        sender=request.user,
        receiver=receiver,
        text=text,
        is_admin=False,
        is_read_by_user=True,   # ع†ظˆظ† ع©ط§ط±ط¨ط± ط®ظˆط¯ط´ ظپط±ط³طھط§ط¯ظ‡ ط§ط³طھ
        is_read_by_admin=False,
    )

    return JsonResponse({"status": "ok"})


@login_required
def chat_stream(request):
    """
    SSE Stream ط¨ط±ط§غŒ Real-Time Chat
    """
    def event_stream():
        thread, _ = ChatThread.objects.get_or_create(user=request.user)
        last_check_time = timezone.now()

        while True:
            # ع†ع© ع©ط±ط¯ظ† ظ¾غŒط§ظ…â€Œظ‡ط§غŒ ط¬ط¯غŒط¯
            new_messages = thread.messages.filter(
                created_at__gt=last_check_time,
                is_admin=True  # ظپظ‚ط· ظ¾غŒط§ظ…â€Œظ‡ط§غŒ ط§ط¯ظ…غŒظ†
            ).exists()

            if new_messages:
                data = json.dumps({
                    'type': 'new_message',
                    'timestamp': timezone.now().isoformat()
                })
                yield f"data: {data}\n\n"

            last_check_time = timezone.now()
            time.sleep(2)  # ظ‡ط± 2 ط«ط§ظ†غŒظ‡ ع†ع© ع©ظ†
    
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


# ----------------------------
#             Chat â€“ ط§ط¯ظ…غŒظ†
# ----------------------------

@staff_member_required
def admin_chat(request, user_id=None):
    """
    ظ¾ظ†ظ„ ع†طھ ط§ط¯ظ…غŒظ†.
    - ط³طھظˆظ† ط§ظˆظ„: ظ„غŒط³طھ Threadظ‡ط§ ظ‡ظ…ط±ط§ظ‡ ط¨ط§ ط¢ط®ط±غŒظ† ظ¾غŒط§ظ… ظˆ طھط¹ط¯ط§ط¯ ظ¾غŒط§ظ… ط®ظˆط§ظ†ط¯ظ‡â€Œظ†ط´ط¯ظ‡
    - ط³طھظˆظ† ظˆط³ط·: ع†طھ ظپط¹ط§ظ„
    - ط³طھظˆظ† ط³ظˆظ…: ط§ط·ظ„ط§ط¹ط§طھ ع©ط§ط±ط¨ط± ظˆ ط³ظپط§ط±ط´â€Œظ‡ط§
    """
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

    # ط§ط¶ط§ظپظ‡ ع©ط±ط¯ظ† ط¢ط®ط±غŒظ† ط²ظ…ط§ظ† ط¨ظ‡ ظ‡ط± thread
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
    """
    ع¯ط±ظپطھظ† ظ¾غŒط§ظ…â€Œظ‡ط§غŒ غŒع© Thread ط®ط§طµ ط¨ط±ط§غŒ ط§ط¯ظ…غŒظ†.
    """
    thread = get_object_or_404(ChatThread, user_id=user_id)
    messages_qs = thread.messages.select_related("sender").order_by("created_at")

    messages_data = []
    for m in messages_qs:
        messages_data.append({
            "id": m.id,
            "text": m.text,
            "is_admin": m.is_admin,
            "sender": m.sender.username if m.sender else ("ظ¾ط´طھغŒط¨ط§ظ†" if m.is_admin else "ع©ط§ط±ط¨ط±"),
            "created_at": timezone.localtime(m.created_at).strftime("%H:%M"),
        })

    # ط¹ظ„ط§ظ…طھâ€Œع¯ط°ط§ط±غŒ ظ¾غŒط§ظ…â€Œظ‡ط§غŒ ع©ط§ط±ط¨ط± ط¨ظ‡ ط¹ظ†ظˆط§ظ† ط®ظˆط§ظ†ط¯ظ‡â€Œط´ط¯ظ‡ طھظˆط³ط· ط§ط¯ظ…غŒظ†
    messages_qs.filter(is_admin=False, is_read_by_admin=False).update(
        is_read_by_admin=True
    )

    return JsonResponse({"messages": messages_data})


@staff_member_required
@require_http_methods(["POST"])
def admin_chat_send(request, user_id):
    """
    ط§ط±ط³ط§ظ„ ظ¾غŒط§ظ… طھظˆط³ط· ط§ط¯ظ…غŒظ† ط¨ط±ط§غŒ غŒع© ع©ط§ط±ط¨ط± ظ…ط´ط®طµ.
    """
    text = (request.POST.get("message") or "").strip()
    if not text:
        return JsonResponse({"status": "error", "error": "ظ¾غŒط§ظ… ط®ط§ظ„غŒ ط§ط³طھ"}, status=400)

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
    """
    SSE Stream ط¨ط±ط§غŒ Admin Real-Time Chat
    """
    def event_stream():
        thread = get_object_or_404(ChatThread, user_id=user_id)
        last_check_time = timezone.now()
        
        while True:
            # ع†ع© ع©ط±ط¯ظ† ظ¾غŒط§ظ…â€Œظ‡ط§غŒ ط¬ط¯غŒط¯ ط§ط² ع©ط§ط±ط¨ط±
            new_messages = thread.messages.filter(
                created_at__gt=last_check_time,
                is_admin=False  # ظپظ‚ط· ظ¾غŒط§ظ…â€Œظ‡ط§غŒ ع©ط§ط±ط¨ط±
            ).exists()
            
            if new_messages:
                data = json.dumps({
                    'type': 'new_message',
                    'timestamp': timezone.now().isoformat()
                })
                yield f"data: {data}\n\n"
            
            last_check_time = timezone.now()
            time.sleep(2)  # ظ‡ط± 2 ط«ط§ظ†غŒظ‡ ع†ع© ع©ظ†
    
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
    """
    Endpoint for chatbot: saves user message, asks LLM with context, saves bot reply.
    """
    text = (request.POST.get("message") or "").strip()
    if not text:
        return JsonResponse({"status": "error", "error": "متن پيام خالي است"}, status=400)

    thread, _ = ChatThread.objects.get_or_create(user=request.user)
    receiver = _get_first_staff()

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
        bot_reply = "در حال حاضر ربات در دسترس نيست. لطفاً بعداً تلاش کنيد."
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
                subject="درخواست پشتيباني چت",
                message=f"User {request.user.username} asked: {text}\nReply: {bot_reply}",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", support_email),
                recipient_list=[support_email],
                fail_silently=True,
            )

    return JsonResponse({"status": "ok", "reply": bot_reply, "handoff": handoff})
