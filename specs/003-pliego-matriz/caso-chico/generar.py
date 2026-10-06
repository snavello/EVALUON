from tests.tenders.pdfs import para, tender_pdf
from pathlib import Path
d = Path("/app/corpus/casos/caso-chico"); d.mkdir(parents=True, exist_ok=True)
pl = tender_pdf([
 [para("SECCIÓN I - CONDICIONES PARTICULARES"),
  para("1. GARANTÍA", "1.1. Los oferentes deberán constituir una garantía del 5 % del monto de la oferta."),
  para("2. PAGO", "2.1. El pago se efectuará a los 90 días corridos de la factura."),
  para("3. ENTREGA", "3.1. Los bienes se entregan dentro de los 15 días hábiles de recibida la orden de compra."),
  para("4. PRESENTACIÓN", "4.1. Los oferentes deberán presentar constancia de visita al lugar de entrega.")],
 [para("SECCIÓN II - ESPECIFICACIONES TÉCNICAS PARTICULARES"),
  para("1. RENGLÓN N° 1 - COMPUTADORA SINTÉTICA", "1.1. La computadora tendrá 16 GB de RAM.", "1.2. La computadora tendrá disco de estado sólido de 512 GB."),
  para("2. RENGLÓN N° 2 - MONITOR SINTÉTICO", "2.1. El monitor tendrá 24 pulgadas.")],
])
ci = tender_pdf([[para("CIRCULAR SINTÉTICA N° 1", "1. Modifícase el punto 1.1 de la Sección II, renglón 1: la computadora tendrá 32 GB de RAM.")]], header=None)
(d/"pliego-sintetico.pdf").write_bytes(pl); (d/"circular-sintetica-1.pdf").write_bytes(ci)
print("ok", len(pl), len(ci))
