from django import forms

from .models import ProductReview


class ProductReviewForm(forms.ModelForm):
    class Meta:
        model = ProductReview
        fields = ("name", "email", "rating", "comment")
        widgets = {
            "name": forms.TextInput(attrs={"class": "input"}),
            "email": forms.EmailInput(attrs={"class": "input"}),
            "rating": forms.NumberInput(attrs={"class": "input", "min": 1, "max": 5}),
            "comment": forms.Textarea(attrs={"class": "textarea", "rows": 4}),
        }
