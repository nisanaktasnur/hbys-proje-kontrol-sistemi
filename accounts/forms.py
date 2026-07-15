from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from accounts.models import Role


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Kullanıcı Adı",
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Şifre",
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}),
    )

    error_messages = {
        "invalid_login": "Kullanıcı adı veya şifre hatalı.",
        "inactive": "Hesabınız henüz onaylanmamış veya devre dışı bırakılmış.",
    }


class RegisterForm(UserCreationForm):
    full_name = forms.CharField(
        label="Ad Soyad",
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    role = forms.ChoiceField(
        label="Talep Edilen Rol",
        choices=[
            (Role.PROJE_YONETICISI, Role.PROJE_YONETICISI),
            (Role.TEKNIK_LIDER, Role.TEKNIK_LIDER),
            (Role.YONETICI, Role.YONETICI),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = User
        fields = ("username", "full_name", "role", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Kullanıcı Adı"
        self.fields["password1"].label = "Şifre"
        self.fields["password2"].label = "Şifre Tekrar"
        for name in self.fields:
            if "class" not in self.fields[name].widget.attrs:
                self.fields[name].widget.attrs["class"] = "form-control"

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_active = True
        if commit:
            user.save()
        return user
