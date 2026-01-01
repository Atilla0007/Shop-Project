
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, UserCreationForm


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = get_user_model()
        fields = ("username", "email", "password1", "password2")

    def clean_username(self):
        return (self.cleaned_data.get("username") or "").strip()

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            return email

        user_model = get_user_model()
        email_field = user_model.get_email_field_name()
        users = user_model._default_manager.filter(
            **{f"{email_field}__iexact": email},
            is_active=True,
        )
        if not any(u.has_usable_password() for u in users):
            raise forms.ValidationError("ایمیلی با این مشخصات ثبت نشده است.")
        return email


class PasswordResetRequestForm(PasswordResetForm):
    email = forms.EmailField(
        label="ایمیل",
        widget=forms.EmailInput(attrs={"class": "input", "autocomplete": "email"}),
    )

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()


class SetPasswordConfirmForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="رمز عبور جدید",
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "new-password"}),
    )
    new_password2 = forms.CharField(
        label="تکرار رمز عبور جدید",
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "new-password"}),
    )
