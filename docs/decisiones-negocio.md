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
| D-16 | Cantidad de la OC (Hipermaxi) | La cantidad del pedido es **"Cant. OC"** (lo que piden). "Cant. Dpcho." normalmente es igual y no se usa. | 2026-11-14 |
| D-17 | Unidad de medida en la OC | La columna U/M ("PCE") siempre significa **unidades**: no hay conversión de paquetes (confirma D-10). | 2026-11-14 |
| D-18 | Anotaciones del supermercado | La columna "Recepción" (escrita a mano por el encargado del supermercado) no es relevante: la lectura la ignora. | 2026-11-14 |

## Decisiones técnicas tomadas en la Fase 1 (a confirmar con el cliente)

| # | Tema | Implementado | Cómo cambiarlo |
|---|---|---|---|
| T-01 | Ajustes "sensibles" | Todo ajuste de alguien sin permiso de aprobación queda pendiente (umbral Bs 0). | Configurar `umbral_ajuste_bs` en la empresa para que los ajustes menores se apliquen solos. |
| T-02 | Stock negativo | No se permite en ningún caso. | La especificación pide que el dueño pueda habilitarlo; queda pendiente porque complica la trazabilidad por lotes. Se implementará si el cliente lo necesita. |
| T-03 | Acceso por ubicación | Encargados operan solo en sus ubicaciones asignadas; Dueño y Administrador en todas (`ubicaciones.todas`). Todos ven el stock de todas las ubicaciones. | Desde Roles y permisos. |
| T-04 | Transferencias de lotes vencidos | No se transfieren unidades vencidas; se dan de baja con un ajuste por vencimiento. | — |

## Decisiones técnicas tomadas en la Fase 2a (a confirmar con el cliente)

| # | Tema | Implementado | Cómo cambiarlo |
|---|---|---|---|
| T-05 | Stock vencido | Al confirmar solo se reserva stock de lotes no vencidos; al alistar nunca sale un lote vencido. | — |
| T-06 | Merma al alistar | Sigue la regla de ajustes (T-01): si la registra un encargado queda pendiente hasta que el dueño la apruebe. | Umbral `umbral_ajuste_bs`. |
| T-07 | Avisos de la revisión | Diferencias aritméticas y precio distinto del último **avisan pero no bloquean** (la OC impresa puede tener redondeos). Bloquean: falta la OC, datos de cabecera, producto sin elegir, stock insuficiente, OC duplicada. | — |
| T-08 | Quién anula | El encargado puede descartar su propio borrador; anular un pedido confirmado o alistado requiere `pedidos.anular` (Dueño y Administrador). | Desde Roles y permisos. |
| T-09 | Devoluciones | Las registra quien tiene `pedidos.anular`. Lo devuelto vuelve al stock y se descuenta del ingreso; si llegó dañado se registra luego como merma. | — |
| T-10 | Visibilidad | El encargado ve solo los pedidos que él cargó (D-05); con `pedidos.ver_todos` se ven todos. | Desde Roles y permisos. |
| T-11 | Documentos | Se guardan en el disco del equipo de la oficina y entran en el respaldo diario. Máximo 15 MB por archivo y 20 archivos por pedido. | Variables `ARCHIVO_MAX_MB`. |

## Decisiones técnicas tomadas en la Fase 2b

| # | Tema | Implementado |
|---|---|---|
| T-12 | Cuándo se lee | Automáticamente al subir la OC a un borrador sin líneas; luego, solo con «Volver a leer» (reemplaza lo cargado). |
| T-13 | Producto automático | Solo por equivalencia aprendida o código; el parecido de nombres solo sugiere (p. ej. talla 8 vs 8.5 es fácil de confundir). |
| T-14 | Campos dudosos | Confianza menor a 85 % se resalta en ámbar; si las cuentas no cuadran, se avisa. |
| T-15 | Red | El backend y el worker no tienen salida a internet (las OC no salen del equipo). |

## Pendientes de validar

- Muestras reales de OC de cada cadena (D-09) para la lectura automática (Fase 2b).

- Acceso desde celulares fuera de la red de la oficina y cómo obtener HTTPS (necesario para la cámara). Ver [ADR 0002](adr/0002-despliegue-en-oficina.md).
