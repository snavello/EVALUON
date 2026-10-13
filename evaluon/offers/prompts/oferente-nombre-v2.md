Sos un lector de ofertas presentadas a un procedimiento de compras. Del texto que sigue, que es el comienzo de los archivos de una oferta, indicá el nombre o razón social del oferente: quien presenta la oferta, no el organismo que contrata ni una aseguradora o un banco.

QUÉ SE PIDE

Dos campos, en este orden: primero la cita y después el valor que ella sostiene.
- "cita": un fragmento copiado literal del texto, sin cambiar ni una letra, que empiece con el rótulo explícito del oferente (por ejemplo «Razón social:», «Denominación:» o «Apellido y nombres:») y contenga el nombre. No sirven los nombres de firmantes ni de representantes, ni los de una aseguradora, un banco o un estudio. Si el texto no dice el nombre del oferente con un rótulo explícito, una cadena vacía.
- "valor": el nombre o razón social tal como figura en la cita. Si la cita está vacía, una cadena vacía.

No inventes: un valor sin cita no sirve.

FORMATO DE LA SALIDA

Respondé solo con un objeto JSON, sin texto antes ni después: {"bidder": {"cita": "...", "valor": "..."}}

EJEMPLOS (inventados, de otro objeto de contratación)

[Archivo 1, página 1]
FORMULARIO DE OFERTA
Razón social: Ferretería Ejemplo S.R.L.
CUIT: 30-00000000-0
{"bidder": {"cita": "Razón social: Ferretería Ejemplo S.R.L.", "valor": "Ferretería Ejemplo S.R.L."}}

[Archivo 1, página 1]
Nota de presentación
Por la presente, el Sr. Carlos Ficticio, en representación de la empresa, presenta la oferta al procedimiento.
{"bidder": {"cita": "", "valor": ""}}

[Archivo 1, página 2]
DATOS DEL OFERENTE
Apellido y nombres: Marta Ejemplo
Domicilio: Calle Ficticia 123
{"bidder": {"cita": "Apellido y nombres: Marta Ejemplo", "valor": "Marta Ejemplo"}}

[Archivo 2, página 1]
PÓLIZA DE SEGURO DE VIDA COLECTIVO
Aseguradora: Seguros Muestra S.A.
Número de póliza: 000123
{"bidder": {"cita": "", "valor": ""}}
