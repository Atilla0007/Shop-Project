from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
    DEBUG=True,
)
class AuthFlowTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.password = "StrongPass123!"

    def test_signup_creates_user(self):
        response = self.client.post(
            reverse("signup"),
            data={
                "email": "newuser@example.com",
                "username": "newuser",
                "password1": self.password,
                "password2": self.password,
                "accept_terms": "1",
            },
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            self.user_model.objects.filter(email__iexact="newuser@example.com").exists()
        )

    def test_signup_duplicate_email_shows_error(self):
        self.user_model.objects.create_user(
            username="existing",
            email="dup@example.com",
            password=self.password,
        )
        response = self.client.post(
            reverse("signup"),
            data={
                "email": "dup@example.com",
                "username": "another",
                "password1": self.password,
                "password2": self.password,
                "accept_terms": "1",
            },
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "این ایمیل قبلاً ثبت شده است")
        self.assertEqual(
            self.user_model.objects.filter(email__iexact="dup@example.com").count(),
            1,
        )

    def test_login_with_email_success(self):
        self.user_model.objects.create_user(
            username="loginuser",
            email="login@example.com",
            password=self.password,
        )
        response = self.client.post(
            reverse("login"),
            data={"email": "login@example.com", "password": self.password},
            secure=True,
        )
        self.assertEqual(response.status_code, 302)

    def test_login_wrong_password_fails(self):
        self.user_model.objects.create_user(
            username="loginuser2",
            email="login2@example.com",
            password=self.password,
        )
        response = self.client.post(
            reverse("login"),
            data={"email": "login2@example.com", "password": "wrongpass"},
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "رمز عبور نادرست است.")

    def test_password_reset_existing_email_sends(self):
        self.user_model.objects.create_user(
            username="resetuser",
            email="reset@example.com",
            password=self.password,
        )
        response = self.client.post(
            reverse("password_reset"),
            data={"email": "reset@example.com"},
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_password_reset_unknown_email_errors(self):
        response = self.client.post(
            reverse("password_reset"),
            data={"email": "unknown@example.com"},
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "کاربری با این ایمیل وجود ندارد.")
        self.assertEqual(len(mail.outbox), 0)
