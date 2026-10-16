# Hoja de compliance inventada (T-290; REQ-121; ADR-0067)

`hoja.txt` es una hoja de compliance **inventada**: el oferente, los legajos, las fechas, las
personas y la aseguradora no existen (P4). Cada párrafo (separado por una línea en blanco) lleva
la palabra clave improbable `ZORVANTIQ`, para poder buscarla en todo lo que llega al registro y al
doble del cliente externo.

La usan `tests/ai/test_external_guard.py` y `tests/ai/test_external_ledger.py`: se carga como
documento de tipo `compliance` de una oferta del caso chico, y ninguna prueba admite que un
pedido externo registrado contenga uno de sus párrafos, ocho palabras seguidas de uno de ellos
ni la palabra clave. La prueba de humo con el proveedor real (T-292) usa la misma hoja.
