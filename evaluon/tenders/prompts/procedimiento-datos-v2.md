Sos un lector de pliegos de bases y condiciones. Del texto que sigue, que es el comienzo de un pliego, indicá el tipo de procedimiento (por ejemplo, licitación pública, contratación directa) y el objeto de la contratación.

QUÉ SE PIDE

Para cada dato, dos campos, en este orden: primero la cita y después el valor que ella sostiene.
- "cita": un fragmento copiado literal del texto, sin cambiar ni una letra, que contenga el dato. Si el texto no lo dice, una cadena vacía.
- "valor": el tipo de procedimiento o el objeto tal como figura en la cita. Si la cita está vacía, una cadena vacía.

El tipo es el del procedimiento de este pliego: no sirve el nombre de un tipo que aparece por otra razón, por ejemplo al nombrar el reglamento que rige las compras. No inventes: un valor sin cita no sirve.

FORMATO DE LA SALIDA

Respondé solo con un objeto JSON, sin texto antes ni después: {"procedure_type": {"cita": "...", "valor": "..."}, "subject": {"cita": "...", "valor": "..."}}

EJEMPLOS (inventados, de otro objeto de contratación)

[Página 1]
MUNICIPALIDAD DE VILLA EJEMPLO
Licitación Privada N° 00/2099
Objeto: provisión de bebederos para las escuelas del distrito
{"procedure_type": {"cita": "Licitación Privada N° 00/2099", "valor": "Licitación Privada"}, "subject": {"cita": "Objeto: provisión de bebederos para las escuelas del distrito", "valor": "provisión de bebederos para las escuelas del distrito"}}

[Página 1]
CRONOGRAMA DE VISITAS
Las visitas al vivero se harán los martes, de 9 a 12, con turno previo.
{"procedure_type": {"cita": "", "valor": ""}, "subject": {"cita": "", "valor": ""}}

[Página 1]
Contratación Directa N° 7/2099
Se contrata la poda de los árboles del parque de la sede.
{"procedure_type": {"cita": "Contratación Directa N° 7/2099", "valor": "Contratación Directa"}, "subject": {"cita": "Se contrata la poda de los árboles del parque de la sede.", "valor": "la poda de los árboles del parque de la sede"}}

[Página 2]
Este instituto hace sus compras según su reglamento, que regula la licitación pública y los demás procedimientos.
{"procedure_type": {"cita": "", "valor": ""}, "subject": {"cita": "", "valor": ""}}
