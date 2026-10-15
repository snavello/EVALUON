# ADR-0063 · Bloqueo, sesión y cambio de clave con lo que trae Django

Estado: propuesto (versión 3, mínima) · Fecha: 2026-10-14 · Propuso: planificador (plan 007) · Decidió: —

Enmienda el ADR-0005 en un punto: la clave olvidada.

## Contexto

REQ-111 a REQ-115 piden bloqueo tras 5 intentos durante 15 minutos (también en comandos), desbloqueo en el equipo, registro con la computadora de origen, cambio de clave con la clave inicial obligatoria y cierre de sesión a los 30 minutos y a las 8 horas.

Django 6.1 no trae bloqueo. Sí trae la vista de cambio de clave y los validadores de largo y de claves comunes [1].

## Alternativas

- **A. Código propio sobre Django:** un backend de bloqueo, que es el único backend; un middleware de sesión; y los comandos `desbloquear_usuario`, `ver_accesos` y `clave_inicial`.
  - **Se gana:** cubre los comandos, que no tienen pedido web; todo queda en el mismo `audit_event`; sin bibliotecas nuevas.
  - **Se pierde:** es código propio, que se cubre con tests.
- **B. django-axes 8.3.1** (11 de febrero de 2026) [2]:
  - no declara Django 6.1;
  - exige el pedido web en cada ingreso [3], que los comandos no tienen;
  - guarda su registro aparte;
  - su organización, Jazzband, anunció su cierre en marzo de 2026 [4].

## Decisión

Se propone **A**. El responsable del sistema es el usuario con rol de lectura y escritura, con su clave en cada comando, como ya hace `rol_comision`.

**Enmienda al ADR-0005:** la clave olvidada se resuelve con `clave_inicial`, que obliga a cambiarla y deja registro, y no con `changepassword`. Al aceptar este ADR, el Coordinador lo anota en el ADR-0005.

## Consecuencias

- **Más fácil:** pantalla y comandos comparten bloqueo, mensaje y registro.
- **Más difícil:** mantener el código propio y sus tests.
- **Para revertir:** sacar el backend y los middleware de `settings.py`.

## Fuentes

Consultadas el 2026-10-14.

1. Django 6.1, manejo de claves: https://docs.djangoproject.com/en/6.1/topics/auth/passwords/
2. django-axes en PyPI: https://pypi.org/pypi/django-axes/json
3. django-axes, uso: https://django-axes.readthedocs.io/en/stable/3_usage.html
4. Jazzband, «Wind-Down Plan»: https://jazzband.co/news/2026/03/14/wind-down-plan
