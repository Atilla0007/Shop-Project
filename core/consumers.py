import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import ChatThread, ChatMessage
from asgiref.sync import sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        \"\"\"WebSocket connect: authenticate user and join personal group.\"\"\"
        user = self.scope.get("user")

        # Only authenticated users can connect
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.user = user
        self.group_name = f"chat_{self.user.id}"

        # Ensure the thread exists
        await sync_to_async(ChatThread.objects.get_or_create)(user=self.user)

        # Join the group
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        # Leave the group
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        \"\"\"Handle incoming message: persist and broadcast to group.\"\"\"
        data = json.loads(text_data)
        message = (data.get("message") or "").strip()
        if not message:
            return

        # Persist message in DB (sync helper on separate thread)
        await sync_to_async(self.save_message)(self.user, message)

        # Broadcast message to all group members
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat_message",
                "message": message,
            },
        )

    async def chat_message(self, event):
        \"\"\"Group message handler: send to browser.\"\"\"
        message = event["message"]

        await self.send(
            text_data=json.dumps(
                {
                    "message": message,
                }
            )
        )

    def save_message(self, user, message):
        \"\"\"Sync helper to persist a message.\"\"\"
        thread, _ = ChatThread.objects.get_or_create(user=user)
        ChatMessage.objects.create(
            thread=thread,
            sender=user,
            text=message,
            is_admin=False,
            is_read_by_user=True,
            is_read_by_admin=False,
        )
