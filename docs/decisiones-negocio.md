# Decisiones de negocio

Respuestas del cliente que complementan la especificación (`PROMPT_sistema_inventario.md`).
Si una regla de aquí contradice la especificación, **manda este documento**.

| # | Tema | Decisión | Fecha |
|---|---|---|---|
| D-01 | Fuente de verdad | La especificación es `PROMPT_sistema_inventario.md`. El documento preliminar anterior (`doc1.docx`) queda descartado. | 2026-11-14 |
| D-02 | Stock insuficiente | En la revisión de la OC, el encargado ajusta a mano las cantidades (incluso a 0) antes de confirmar. **No se puede reservar más de lo disponible.** Un pedido puede confirmarse y entregarse incompleto respecto a la OC. Se conservan la cantidad de la OC y la confirmada por separado. | 2026-11-14 |
| D-03 | Anulación | Se puede anular en BORRADOR, CONFIRMADO (libera la reserva) y ALISTADO (revierte movimientos). **Un pedido ENTREGADO no se puede anular.** | 2026-11-14 |
| D-04 | Costo promedio | El CPP se lleva **por ubicación**. La salida a un supermercado usa el CPP de la sucursal que despacha. Una transferencia sale al CPP del origen y recalcula el CPP del destino. | 2026-11-14 |
| D-05 | Asignación de pedidos | No hay asignación: el trabajador que escanea la OC registra el pedido y queda como responsable. | 2026-11-14 |
| D-06 | Pedidos "manuales" | Todo pedido nace de una OC (foto o PDF). "Manual" significa que todo lo extraído es editable; si la lectura falla, los datos se pueden cargar a mano con la OC adjunta. | 2026-11-14 |
| D-07 | Terminología | **Depósito** y **Sucursal** (de la empresa); **Sucursal de supermercado** (del cliente). En código: `Ubicacion(tipo=DEPOSITO\|SUCURSAL)`, `Cadena`, `SucursalCliente`. | 2026-11-14 |
| D-08 | IA sin costo | La lectura de OC no puede tener costo mensual por uso: OCR local y gratuito. Un servicio en la nube gratuito podrá activarse en el futuro como opción, **desactivado por defecto**. | 2026-11-14 |
| D-09 | Muestras de OC | El cliente entregará OC reales de cada cadena para diseñar y probar la lectura. | 2026-11-14 |
| D-10 | Unidad de la OC | Las cadenas piden **por unidad** (unidad base del producto) y el precio de la OC es **por unidad**. | 2026-11-14 |
| D-11 | Alistado menor | Al alistar puede salir menos de lo confirmado. Los productos encontrados en mal estado se registran como merma (ajuste negativo con motivo "rotura/mal estado") vinculada al pedido. | 2026-11-14 |
| D-12 | Rechazos en la entrega | Son muy raros. Si ocurren, se registran como DEVOLUCION_CLIENTE después de la entrega. | 2026-11-14 |
| D-13 | Transferencias | Se mueven **al instante** (llegan el mismo día) y llega lo que se envió: no se usa el estado "en tránsito" ni se registran diferencias de recepción. | 2026-11-14 |
| D-14 | Infraestructura | El sistema corre en **un equipo de la oficina** y se usa desde 4–5 dispositivos (PC y celulares). Se busca costo de servidor cero o mínimo. | 2026-11-14 |
| D-15 | Volumen | Hasta ~10 OC por día en el peor caso; varias cadenas con formatos distintos. | 2026-11-14 |

## Pendientes de validar

- Acceso desde celulares fuera de la red de la oficina y cómo obtener HTTPS (necesario para la cámara). Ver [ADR 0002](adr/0002-despliegue-en-oficina.md).
