"""Usuario propio de EVALUON con su rol (REQ-016; plan 001, "Modelo de datos").

Es el modelo de usuario desde la primera migración (`AUTH_USER_MODEL`). No usa los grupos
ni los permisos de Django (ADR-0005): el rol es un campo con dos valores, y la
comprobación está en `permissions.py`.
"""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    READ = "read", "Lectura"
    READ_WRITE = "read_write", "Lectura y escritura"


class UserManager(BaseUserManager):
    def create_user(self, username, password, role, **extra_fields):
        """Crea un usuario con su rol y guarda la clave con el primer algoritmo
        configurado (Argon2id). No valida el largo de la clave: eso lo hace quien da el
        alta, con `validate_password`."""
        if not username:
            raise ValueError("Falta el nombre de usuario.")
        user = self.model(
            username=self.model.normalize_username(username), role=role, **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    username = models.CharField(
        "usuario",
        max_length=150,
        unique=True,
        validators=[UnicodeUsernameValidator()],
    )
    role = models.CharField("rol", max_length=10, choices=Role.choices)
    is_active = models.BooleanField("activo", default=True)
    date_joined = models.DateTimeField("fecha de alta", default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["role"]

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=["read", "read_write"]),
                name="accounts_user_role_valid",
            ),
        ]

    def __str__(self):
        return self.username
