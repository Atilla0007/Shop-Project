from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator


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
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='chat_thread')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "گفتگو"
        verbose_name_plural = "گفتگوها"

    def __str__(self):
        return f"گفتگو با {self.user.username}"


class ChatMessage(models.Model):
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


class ShippingSettings(models.Model):
    shipping_fee = models.PositiveIntegerField(default=0, verbose_name="هزینه ارسال (تومان)")
    free_shipping_min_total = models.PositiveIntegerField(default=0, verbose_name="حداقل مبلغ برای ارسال رایگان (تومان)")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "تنظیمات ارسال"
        verbose_name_plural = "تنظیمات ارسال"

    def __str__(self):
        return "تنظیمات ارسال"

    @classmethod
    def get_solo(cls) -> "ShippingSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class DiscountCode(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="کد تخفیف")
    percent = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name="درصد تخفیف",
    )
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    is_public = models.BooleanField(default=False, verbose_name="نمایش در بنر")
    public_message = models.CharField(max_length=200, blank=True, verbose_name="متن بنر (اختیاری)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "کد تخفیف"
        verbose_name_plural = "کدهای تخفیف"

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper().replace(" ", "")
        super().save(*args, **kwargs)
        if self.is_public:
            DiscountCode.objects.filter(is_public=True).exclude(pk=self.pk).update(is_public=False)

    @property
    def banner_text(self) -> str:
        if self.public_message:
            return self.public_message
        return f"کد تخفیف {self.code}: {self.percent}٪ تخفیف روی کالاها"

    def __str__(self):
        return self.code


class PaymentSettings(models.Model):
    card_number = models.CharField(max_length=32, blank=True, verbose_name="شماره کارت")
    card_holder = models.CharField(max_length=120, blank=True, verbose_name="نام صاحب کارت")
    telegram_username = models.CharField(max_length=64, blank=True, verbose_name="آیدی تلگرام (بدون @)")
    whatsapp_number = models.CharField(max_length=20, blank=True, verbose_name="شماره واتساپ")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "تنظیمات پرداخت"
        verbose_name_plural = "تنظیمات پرداخت"

    def __str__(self):
        return "تنظیمات پرداخت"

    @classmethod
    def get_solo(cls) -> "PaymentSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
