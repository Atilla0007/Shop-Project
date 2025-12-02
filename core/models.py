from django.db import models
from django.contrib.auth.models import User


class News(models.Model):
    title = models.CharField(max_length=200)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "خبر"
        verbose_name_plural = "اخبار"

    def __str__(self):
        return self.title


class ContactMessage(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "پیام تماس"
        verbose_name_plural = "پیام‌های تماس"

    def __str__(self):
        return f"{self.name} - {self.email}"


class ChatThread(models.Model):
    """یک گفت‌وگو برای هر کاربر"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='chat_thread')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "گفتگو"
        verbose_name_plural = "گفتگوها"

    def __str__(self):
        return f"گفتگو با {self.user.username}"


class ChatMessage(models.Model):
    """
    پیام در یک گفتگو
    - sender: هر کسی که پیام را فرستاده (کاربر یا ادمین)
    - is_admin: آیا فرستنده ادمین است؟
    - is_read_by_admin: آیا ادمین این پیام کاربر را دیده؟
    - is_read_by_user: آیا کاربر این پیام ادمین را دیده؟
    """
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_messages')
    text = models.TextField()
    is_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read_by_admin = models.BooleanField(default=False)
    is_read_by_user = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']
        verbose_name = "پیام چت"
        verbose_name_plural = "پیام‌های چت"

    def __str__(self):
        who = "ادمین" if self.is_admin else (self.sender.username if self.sender else "کاربر")
        return f"{who}: {self.text[:30]}"
