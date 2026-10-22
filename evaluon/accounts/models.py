"""Usuario propio de EVALUON con su rol (REQ-016; plan 001, "Modelo de datos").

Es el modelo de usuario desde la primera migración (`AUTH_USER_MODEL`). No usa los grupos
ni los permisos de Django (ADR-0005): el rol es un campo con dos valores, y la
comprobación está en `permissions.py`.

El rol de la Comisión (plan 003, "Roles") es otro campo, independiente del rol de la
normativa: ninguno (`''`), operador o evaluador.
"""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    READ = "read", "Lectura"
    READ_WRITE = "read_write", "Lectura y escritura"


class CommissionRole(models.TextChoices):
    NONE = "", "Ninguno"
    OPERATOR = "operator", "Operador"
    EVALUATOR = "evaluator", "Evaluador"


class Theme(models.TextChoices):
    """Tema de la pantalla (REQ-134; ADR-0074): gris y blanco, o negro."""

    LIGHT = "claro", "Gris y blanco"
    DARK = "negro", "Negro"


# Fotos personales (REQ-136; ADR-0073): hasta 10 por usuario y 2 MiB cada una.
PHOTO_SLOTS = 10
PHOTO_MAX_BYTES = 2 * 1024 * 1024


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
    commission_role = models.CharField(
        "rol de la Comisión",
        max_length=10,
        choices=CommissionRole.choices,
        default=CommissionRole.NONE,
        blank=True,
    )
    theme = models.CharField(
        "tema", max_length=10, choices=Theme.choices, default=Theme.LIGHT
    )
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
            models.CheckConstraint(
                condition=models.Q(commission_role__in=["", "operator", "evaluator"]),
                name="accounts_user_commission_role_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(theme__in=["claro", "negro"]),
                name="accounts_user_theme_valid",
            ),
        ]

    def __str__(self):
        return self.username


class Photo(models.Model):
    """Foto personal de un usuario, ya ajustada (REQ-136, REQ-137; ADR-0073).

    Se guarda en la base como el resto de los archivos del sistema. La ranura (0 a 9) es única
    por usuario: eso hace valer el máximo de 10 aun con dos subidas a la vez. Solo la ve su dueño.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="photos", verbose_name="usuario"
    )
    slot = models.PositiveSmallIntegerField("ranura")
    content = models.BinaryField("contenido")
    sha256 = models.CharField("huella SHA-256", max_length=64)
    width = models.PositiveIntegerField("ancho")
    height = models.PositiveIntegerField("alto")
    size = models.PositiveIntegerField("tamaño en bytes")
    created_at = models.DateTimeField("fecha de alta", default=timezone.now)

    class Meta:
        verbose_name = "foto"
        verbose_name_plural = "fotos"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(slot__gte=0, slot__lte=PHOTO_SLOTS - 1),
                name="accounts_photo_slot_valid",
            ),
            models.UniqueConstraint(
                fields=["user", "slot"], name="accounts_photo_user_slot_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(size__lte=PHOTO_MAX_BYTES),
                name="accounts_photo_size_max",
            ),
        ]

    def __str__(self):
        return f"{self.user} · foto {self.slot}"
