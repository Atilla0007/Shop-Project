
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
        if user_model._default_manager.filter(**{f"{email_field}__iexact": email}).exists():
            raise forms.ValidationError("این ایمیل قبلاً ثبت شده است.")
        return email


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="ایمیل",
        widget=forms.EmailInput(attrs={"class": "input", "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="رمز عبور",
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "current-password"}),
    )

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get("email")
        if not email:
            return cleaned

        user_model = get_user_model()
        email_field = user_model.get_email_field_name()
        if not user_model._default_manager.filter(
            **{f"{email_field}__iexact": email},
            is_active=True,
        ).exists():
            raise forms.ValidationError("کاربری با این ایمیل وجود ندارد.")
        return cleaned


class PasswordResetRequestForm(PasswordResetForm):
    email = forms.EmailField(
        label="ایمیل",
        widget=forms.EmailInput(attrs={"class": "input", "autocomplete": "email"}),
    )

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
            raise forms.ValidationError("کاربری با این ایمیل وجود ندارد.")
        return email


class SetPasswordConfirmForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="رمز عبور جدید",
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "new-password"}),
    )
    new_password2 = forms.CharField(
        label="تکرار رمز عبور جدید",
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "new-password"}),
    )
