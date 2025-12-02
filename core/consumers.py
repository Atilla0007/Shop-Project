import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import ChatThread, ChatMessage
from asgiref.sync import sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """
        اتصال وب‌سوکت کاربر به یک گروه اختصاصی براساس ID کاربر.
        """
        user = self.scope.get("user")

        # فقط کاربران لاگین‌کرده اجازه اتصال دارند
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.user = user
        self.group_name = f"chat_{self.user.id}"

        # ایجاد Thread اگر وجود نداشته باشد
        await sync_to_async(ChatThread.objects.get_or_create)(user=self.user)

        # عضویت در گروه
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        # ترک کردن گروه
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """
        دریافت پیام از کلاینت، ذخیره در دیتابیس و ارسال برای همه اعضای گروه.
        """
        data = json.loads(text_data)
        message = (data.get("message") or "").strip()
        if not message:
            return

        # ذخیره پیام در دیتابیس (تابع sync روی Thread جداگانه)
        await sync_to_async(self.save_message)(self.user, message)

        # ارسال پیام به تمامی اعضای گروه
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat_message",
                "message": message,
            },
        )

    async def chat_message(self, event):
        """
        هندلر پیام گروه – ارسال به مرورگر.
        """
        message = event["message"]

        await self.send(
            text_data=json.dumps(
                {
                    "message": message,
                }
            )
        )

    def save_message(self, user, message):
        """
        تابع همگام برای ذخیره پیام در دیتابیس.
        """
        thread, _ = ChatThread.objects.get_or_create(user=user)
        ChatMessage.objects.create(
            thread=thread,
            sender=user,
            text=message,
            is_admin=False,
            is_read_by_user=True,
            is_read_by_admin=False,
        )
