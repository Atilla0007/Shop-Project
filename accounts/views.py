from django.shortcuts import render, redirect
from django.contrib.auth import login, logout   # 👈 این خط مهمه
from .forms import SignupForm


def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = SignupForm()
    return render(request, 'accounts/signup.html', {'form': form})


def logout_view(request):
    """خروج کاربر و هدایت به صفحه اصلی"""
    logout(request)
    return redirect('home')   # یا redirect('/')
