import json
import time
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Max, Count, Q
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import ChatThread, ChatMessage, ContactMessage, News
from .forms import ContactForm
from store.models import Product, Category, Order


# ----------------------------
#      صفحات عمومی (Home…)
# ----------------------------

def home(request):
    """
    صفحه اصلی:
    - چند محصول برای نمایش (پرفروش / جدید)
    - آخرین اخبار
    - لیست دسته‌بندی‌ها برای پاپ‌آپ دسته‌بندی
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
    صفحه تماس با ما + ذخیره فرم در ContactMessage
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
    لیست کامل اخبار
    """
    news = News.objects.all()
    return render(request, "news_list.html", {"news": news})


def faq(request):
    """
    صفحه سوالات متداول (استاتیک)
    """
    return render(request, "faq.html")


# ----------------------------
#             Chat – کاربر
# ----------------------------

@login_required
def chat(request):
    """
    صفحه‌ی اصلی چت کاربر (غیر از ویجت شناور).
    فقط قالب را رندر می‌کند، پیام‌ها با AJAX گرفته می‌شوند.
    """
    ChatThread.objects.get_or_create(user=request.user)
    return render(request, "chat.html")


@login_required
def chat_messages(request):
    """
    گرفتن لیست پیام‌های چت کاربر جاری (برای صفحه چت و ویجت شناور).
    خروجی: JSON شامل آرایه‌ی پیام‌ها.
    """
    thread, _ = ChatThread.objects.get_or_create(user=request.user)

    messages_qs = thread.messages.select_related("sender").order_by("created_at")

    messages_data = []
    for m in messages_qs:
        messages_data.append({
            "id": m.id,
            "text": m.text,
            "is_admin": m.is_admin,
            "sender": m.sender.username if m.sender else ("پشتیبان" if m.is_admin else "شما"),
            "created_at": timezone.localtime(m.created_at).strftime("%H:%M"),
        })

    # وقتی کاربر پیام‌های ادمین را می‌بیند، برای کاربر "خوانده‌شده" می‌شوند
    messages_qs.filter(is_admin=True, is_read_by_user=False).update(
        is_read_by_user=True
    )

    return JsonResponse({"messages": messages_data})


@login_required
@require_http_methods(["POST"])
def chat_send(request):
    """
    ارسال پیام جدید توسط کاربر (از صفحه چت و از ویجت شناور).
    انتظار: POST با فیلد 'message'
    """
    text = (request.POST.get("message") or "").strip()
    if not text:
        return JsonResponse({"status": "error", "error": "پیام خالی است"}, status=400)

    thread, _ = ChatThread.objects.get_or_create(user=request.user)

    ChatMessage.objects.create(
        thread=thread,
        sender=request.user,
        text=text,
        is_admin=False,
        is_read_by_user=True,   # چون کاربر خودش فرستاده است
        is_read_by_admin=False,
    )

    return JsonResponse({"status": "ok"})


@login_required
def chat_stream(request):
    """
    SSE Stream برای Real-Time Chat
    """
    def event_stream():
        thread, _ = ChatThread.objects.get_or_create(user=request.user)
        last_check_time = timezone.now()

        while True:
            # چک کردن پیام‌های جدید
            new_messages = thread.messages.filter(
                created_at__gt=last_check_time,
                is_admin=True  # فقط پیام‌های ادمین
            ).exists()

            if new_messages:
                data = json.dumps({
                    'type': 'new_message',
                    'timestamp': timezone.now().isoformat()
                })
                yield f"data: {data}\n\n"

            last_check_time = timezone.now()
            time.sleep(2)  # هر 2 ثانیه چک کن
    
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


# ----------------------------
#             Chat – ادمین
# ----------------------------

@staff_member_required
def admin_chat(request, user_id=None):
    """
    پنل چت ادمین.
    - ستون اول: لیست Threadها همراه با آخرین پیام و تعداد پیام خوانده‌نشده
    - ستون وسط: چت فعال
    - ستون سوم: اطلاعات کاربر و سفارش‌ها
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

    # اضافه کردن آخرین زمان به هر thread
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
    گرفتن پیام‌های یک Thread خاص برای ادمین.
    """
    thread = get_object_or_404(ChatThread, user_id=user_id)
    messages_qs = thread.messages.select_related("sender").order_by("created_at")

    messages_data = []
    for m in messages_qs:
        messages_data.append({
            "id": m.id,
            "text": m.text,
            "is_admin": m.is_admin,
            "sender": m.sender.username if m.sender else ("پشتیبان" if m.is_admin else "کاربر"),
            "created_at": timezone.localtime(m.created_at).strftime("%H:%M"),
        })

    # علامت‌گذاری پیام‌های کاربر به عنوان خوانده‌شده توسط ادمین
    messages_qs.filter(is_admin=False, is_read_by_admin=False).update(
        is_read_by_admin=True
    )

    return JsonResponse({"messages": messages_data})


@staff_member_required
@require_http_methods(["POST"])
def admin_chat_send(request, user_id):
    """
    ارسال پیام توسط ادمین برای یک کاربر مشخص.
    """
    text = (request.POST.get("message") or "").strip()
    if not text:
        return JsonResponse({"status": "error", "error": "پیام خالی است"}, status=400)

    thread = get_object_or_404(ChatThread, user_id=user_id)

    ChatMessage.objects.create(
        thread=thread,
        sender=request.user,
        text=text,
        is_admin=True,
        is_read_by_admin=True,
        is_read_by_user=False,
    )

    return JsonResponse({"status": "ok"})


@staff_member_required
def admin_chat_stream(request, user_id):
    """
    SSE Stream برای Admin Real-Time Chat
    """
    def event_stream():
        thread = get_object_or_404(ChatThread, user_id=user_id)
        last_check_time = timezone.now()
        
        while True:
            # چک کردن پیام‌های جدید از کاربر
            new_messages = thread.messages.filter(
                created_at__gt=last_check_time,
                is_admin=False  # فقط پیام‌های کاربر
            ).exists()
            
            if new_messages:
                data = json.dumps({
                    'type': 'new_message',
                    'timestamp': timezone.now().isoformat()
                })
                yield f"data: {data}\n\n"
            
            last_check_time = timezone.now()
            time.sleep(2)  # هر 2 ثانیه چک کن
    
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response