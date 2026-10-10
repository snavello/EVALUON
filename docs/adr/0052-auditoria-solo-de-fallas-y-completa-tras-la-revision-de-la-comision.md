# ADR-0052 · Auditoría solo de fallas por feature y completa después de la revisión de la Comisión

Estado: aceptado · Fecha: 2026-10-10 · Decidió: responsable del proyecto

Reemplaza en parte a ADR-0036 (puntos 1 y 2).

## Contexto

La feature 014 llega a su auditoría después de muchas vueltas y por encima de lo previsto en tiempo y consumo. El responsable espera que la Comisión Evaluadora, en su primera revisión del producto, pida cambios.

Decisión literal: «Limita La auditoría solo limitada a cuestiones de errores o fallas funcionales . Se hará una auditoría completa después de una primera revisión por parte de la comisión evaluadora que seguramente aplicará cambios».

## Decisión

1. **Auditoría por feature (etapa 6):** solo errores y fallas funcionales. Comprende lo que no anda, lo que da un resultado equivocado y lo que se presenta como hecho sin respaldo (P3). La exposición de datos reservados en el repositorio (P4) se sigue controlando porque la constitución no admite excepción. Nada más bloquea ni se revisa.
2. **Auditoría completa (cumplimiento formal, trazabilidad, documentación, seguridad, constitución):** una sola vez, después de la primera revisión del producto por la Comisión Evaluadora y de los cambios que pida, no antes del piloto.
3. Lo formal que se vea antes se anota en la lista de revisión y no bloquea (como en ADR-0036, punto 3).

## Alternativas

- Mantener ADR-0036, con la auditoría de buen funcionamiento por feature y la de cumplimiento antes del piloto. Así se audita dos veces algo que la Comisión va a cambiar.

## Consecuencias

- Cambian `CLAUDE.md`, la definición del agente `auditor` y la hoja de ruta.
- El piloto puede empezar sin la auditoría de cumplimiento. Esa auditoría queda después de la revisión de la Comisión.
