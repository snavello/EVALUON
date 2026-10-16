"""Uso de una API externa de modelos, solo con lo público (ADR-0065 a ADR-0068; plan 016).

- `payload.py`: `ExternalPayload`, el único pedido que acepta el cliente. No abre red.
- `client.py`: el único módulo que habla con el proveedor (`urllib`, host fijo, HTTPS).

Este paquete no importa nada al cargarse: quien lo use importa el módulo que necesita
(`from evaluon.ai.external import client`) y llama a su función, para que el doble de las
pruebas (`FakeExternal`) lo alcance. `evaluon/portal/` no importa nada de acá
(`tests/portal/test_no_outbound.py`).
"""
