from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class News(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    summary = models.CharField(max_length=300, blank=True)
    text = models.TextField()
    cover_image = models.FileField(upload_to="projects/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "?????"
        verbose_name_plural = "????????"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title, allow_unicode=True) or "project"
            candidate = base
            suffix = 1
            while News.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)


class Download(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="downloads/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "دانلود"
        verbose_name_plural = "دانلودها"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title, allow_unicode=True) or "download"
            candidate = base
            suffix = 1
            while Download.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)


class ContactMessage(models.Model):
    INQUIRY_TYPE_CHOICES = (
        ("product", "??????? ?????"),
        ("service", "??????? ?????"),
        ("consultation", "??????? ??????"),
        ("other", "???? ?????"),
    )

    SERVICE_PACKAGE_CHOICES = (
        ("normal", "???? Normal"),
        ("vip", "???? VIP"),
        ("cip", "???? CIP"),
    )

    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    company = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=120, blank=True)
    inquiry_type = models.CharField(max_length=20, choices=INQUIRY_TYPE_CHOICES, default="consultation")
    service_package = models.CharField(max_length=20, choices=SERVICE_PACKAGE_CHOICES, blank=True)
    product_interest = models.ForeignKey(
        "store.Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inquiries",
    )
    message = models.TextField()
    STATUS_CHOICES = (
        ("new", "New"),
        ("replied", "Replied"),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "??????? ??????"
        verbose_name_plural = "??????????? ??????"

    def __str__(self):
        return f"{self.name} - {self.email}"


class SiteVisit(models.Model):
    session_key = models.CharField(max_length=40, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="site_visits",
    )
    visited_on = models.DateField(default=timezone.localdate, db_index=True)
    first_path = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Site visit"
        verbose_name_plural = "Site visits"
        constraints = [
            models.UniqueConstraint(
                fields=["session_key", "visited_on"], name="uniq_site_visit_session_day"
            )
        ]

    def __str__(self):
        return f"{self.session_key} @ {self.visited_on}"


class DailyVisitStat(models.Model):
    date = models.DateField(unique=True, db_index=True)
    total_hits = models.PositiveIntegerField(default=0)
    unique_sessions = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Daily visit stat"
        verbose_name_plural = "Daily visit stats"

    def __str__(self):
        return f"{self.date} - {self.total_hits}"


class ShippingSettings(models.Model):
    shipping_fee = models.PositiveIntegerField(default=0, verbose_name="????? ?????? (?????)")
    free_shipping_min_total = models.PositiveIntegerField(
        default=0, verbose_name="????? ???? ???? ????? ?????? (?????)"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "??????? ??????"
        verbose_name_plural = "??????? ??????"

    def __str__(self):
        return "??????? ??????"

    @classmethod
    def get_solo(cls) -> "ShippingSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class DiscountCode(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="?? ?????")
    source_code = models.CharField(max_length=50, blank=True, db_index=True, verbose_name="?? ????")
    percent = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name="???? ?????",
    )
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_discount_codes",
        verbose_name="????? ???????",
    )
    max_uses = models.PositiveIntegerField(null=True, blank=True, verbose_name="?????? ????? ???????")
    max_uses_per_user = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="?????? ????? ???? ?? ?????"
    )
    uses_count = models.PositiveIntegerField(default=0, verbose_name="????? ???????")
    is_active = models.BooleanField(default=True, verbose_name="????")
    is_public = models.BooleanField(default=False, verbose_name="????? ?????")
    public_message = models.CharField(max_length=200, blank=True, verbose_name="??? ?????")
    valid_from = models.DateTimeField(null=True, blank=True, verbose_name="???? ??????")
    valid_until = models.DateTimeField(null=True, blank=True, verbose_name="????? ??????")
    min_items_subtotal = models.PositiveIntegerField(null=True, blank=True, verbose_name="????? ???? ??? (?????)")
    max_items_subtotal = models.PositiveIntegerField(null=True, blank=True, verbose_name="?????? ???? ??? (?????)")
    eligible_products = models.ManyToManyField(
        "store.Product",
        blank=True,
        related_name="discount_codes",
        verbose_name="??????? ?????",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "?? ?????"
        verbose_name_plural = "????? ?????"

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper().replace(" ", "")
        super().save(*args, **kwargs)
        if self.is_public:
            DiscountCode.objects.filter(is_public=True).exclude(pk=self.pk).update(is_public=False)

    @property
    def banner_text(self) -> str:
        if self.public_message:
            return self.public_message
        return f"?? ????? {self.code} ?? {self.percent}% ????? ???? ????????? ?????"

    def __str__(self):
        return self.code


class DiscountRedemption(models.Model):
    """Represents a successful usage of a discount code by a user/order."""

    discount_code = models.ForeignKey(
        DiscountCode,
        on_delete=models.CASCADE,
        related_name="redemptions",
        verbose_name="?? ?????",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="discount_redemptions",
        verbose_name="?????",
    )
    order_id = models.PositiveIntegerField(verbose_name="????? ?????")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "??????? ?? ?? ?????"
        verbose_name_plural = "??????????? ?? ?????"
        constraints = [
            models.UniqueConstraint(
                fields=["discount_code", "order_id"], name="uniq_discount_code_order"
            )
        ]

    def __str__(self) -> str:
        return f"{self.discount_code.code} -> {self.order_id}"


class PaymentSettings(models.Model):
    card_number = models.CharField(max_length=32, blank=True, verbose_name="????? ????")
    card_holder = models.CharField(max_length=120, blank=True, verbose_name="??? ???? ????")
    telegram_username = models.CharField(max_length=64, blank=True, verbose_name="??????? ?????? (???? @)")
    whatsapp_number = models.CharField(max_length=20, blank=True, verbose_name="????? ??????")
    company_phone = models.CharField(max_length=32, blank=True, verbose_name="???? ????")
    company_email = models.EmailField(blank=True, verbose_name="????? ????")
    company_address = models.TextField(blank=True, verbose_name="????")
    company_website = models.URLField(blank=True, verbose_name="??????")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "??????? ??????"
        verbose_name_plural = "??????? ??????"

    def __str__(self):
        return "??????? ??????"

    @classmethod
    def get_solo(cls) -> "PaymentSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
