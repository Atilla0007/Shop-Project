import logging
import os
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


def send_sms(to: str, message: str) -> None:
    backend = getattr(settings, 'SMS_BACKEND', 'console')
    if backend == 'console':
        logger.info('SMS(to=%s): %s', to, message)
        try:
            base_dir = getattr(settings, 'BASE_DIR', None)
            if base_dir:
                out_dir = os.path.join(base_dir, 'tmp', 'sms')
                os.makedirs(out_dir, exist_ok=True)
                filename = os.path.join(out_dir, 'sms.log')
                with open(filename, 'a', encoding='utf-8') as f:
                    f.write(f"TO: {to}\n{message}\n{'-'*40}\n")
        except Exception:
            logger.exception("Failed to write SMS to tmp log")
        return

    if backend == 'kavenegar':
        api_key = getattr(settings, 'KAVENEGAR_API_KEY', '') or os.getenv('KAVENEGAR_API_KEY', '')
        sender = getattr(settings, 'KAVENEGAR_SENDER', '') or os.getenv('KAVENEGAR_SENDER', '')
        if not api_key or not sender:
            raise RuntimeError('KAVENEGAR_API_KEY/KAVENEGAR_SENDER not configured')

        # https://api.kavenegar.com/v1/{API-KEY}/sms/send.json
        url = f'https://api.kavenegar.com/v1/{api_key}/sms/send.json'
        payload = urlencode({'receptor': to, 'sender': sender, 'message': message}).encode('utf-8')
        with urlopen(url, data=payload, timeout=10) as resp:
            resp.read()
        return

    raise ValueError(f'Unknown SMS_BACKEND: {backend}')
