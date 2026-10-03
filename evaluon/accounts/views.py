"""Ingreso y salida con las vistas de Django (REQ-016; ADR-0005, "Acceso").

El ingreso da un único mensaje de error, sin decir si falló el usuario o la clave. La
salida (`LogoutView`, solo por formulario) anula la sesión en la base.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView as DjangoLoginView

LOGIN_ERROR = "Usuario o clave incorrectos"


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Usuario",
        max_length=150,
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Clave",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    # Mismo texto para usuario inexistente, clave incorrecta y usuario dado de baja.
    error_messages = {
        "invalid_login": LOGIN_ERROR,
        "inactive": LOGIN_ERROR,
    }


class LoginView(DjangoLoginView):
    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True
