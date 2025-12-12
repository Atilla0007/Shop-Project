import os
from dataclasses import dataclass
from typing import List

from openai import OpenAI


@dataclass
class BotResponse:
    reply: str
    handoff: bool


class ShopBot:
    """Lightweight wrapper around OpenAI/OpenRouter chat completions."""

    def __init__(self):
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("No API key provided in env (OPENROUTER_API_KEY or OPENAI_API_KEY)")

        base_url = None
        default_headers = None
        model = os.getenv("OPENROUTER_MODEL")

        if os.getenv("OPENROUTER_API_KEY"):
            base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
            default_headers = {
                "Referer": os.getenv("OPENROUTER_REF", "http://localhost"),
                "X-Title": os.getenv("OPENROUTER_TITLE", "styra-chatbot"),
            }
            model = model or "openai/gpt-4o-mini"
        else:
            # Using OpenAI direct
            model = model or "gpt-4o-mini"

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers=default_headers,
        )
        self.model = model

    def build_messages(
        self,
        user_message: str,
        faq_text: str,
        user_context: str,
        contact_text: str,
    ) -> List[dict]:
        system = (
            "You are the support chatbot for an online shop. "
            "Answer ONLY about this shop. Use provided FAQ/content, user account info, orders, and product list. "
            "If the question is unrelated or sensitive, politely refuse and offer to contact support. "
            "If the answer is unclear from the provided info, set handoff=true."
        )
        instructions = (
            "Return a JSON object with keys: reply (string), handoff (true/false). "
            "Keep reply concise and in Persian. If handoff=true, mention that the question was sent to support and contact info is below."
        )
        context_block = f"User context:\n{user_context}\n\nFAQ/content:\n{faq_text or 'N/A'}\n\nContact info:\n{contact_text}"
        return [
            {"role": "system", "content": system},
            {"role": "system", "content": instructions},
            {"role": "system", "content": context_block},
            {"role": "user", "content": user_message},
        ]

    def ask(self, user_message: str, faq_text: str, user_context: str, contact_text: str) -> BotResponse:
        messages = self.build_messages(user_message, faq_text, user_context, contact_text)
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        import json

        try:
            payload = json.loads(content or "{}")
        except Exception:
            payload = {}
        reply = payload.get("reply") or payload.get("message") or content or "(بدون پاسخ)"
        handoff = bool(payload.get("handoff"))
        return BotResponse(reply=reply, handoff=handoff)


def format_contact_info(
    phone: str,
    telegram: str,
    instagram: str,
    email: str,
) -> str:
    parts = [
        f"تلفن: {phone}" if phone else None,
        f"تلگرام: {telegram}" if telegram else None,
        f"اینستاگرام: {instagram}" if instagram else None,
        f"ایمیل پشتیبانی: {email}" if email else None,
    ]
    return " | ".join([p for p in parts if p])


__all__ = ["ShopBot", "BotResponse", "format_contact_info"]
