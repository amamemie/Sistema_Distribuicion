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
| D-06 | Pedidos "manuales" | ~~Reemplazada por D-20.~~ Todo pedido nace de una OC (foto o PDF). "Manual" significa que todo lo extraído es editable; si la lectura falla, los datos se pueden cargar a mano con la OC adjunta. | 2026-11-14 |
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
| D-19 | Documento del pedido | El pedido se registra con la **nota de recepción** de la cadena (ya no con la OC); el stock se descuenta con sus cantidades al alistar. El número del pedido sigue siendo el **N.º de O/C** de la nota (control de duplicados); el N.º de la nota se anota en observaciones. La "U/N" es la sucursal del supermercado que recibe. Sin cambios en la base de datos. | 2026-11-15 |
| D-20 | Pedidos a mano | **Reemplaza a D-06.** Además de subir la nota (PDF o foto), se puede crear un pedido a mano, sin documento, escribiendo cadena, sucursal, fecha y productos. El N.º de O/C es opcional; si se escribe, se sigue controlando que no se repita. | 2026-11-15 |
| D-21 | Cálculos automáticos | El usuario solo escribe cantidad y precio: el total de cada línea (cantidad × precio), el subtotal y el total (subtotal − descuento) se calculan solos. El descuento no tiene columna propia: es la diferencia entre la suma de las líneas y el total guardado. | 2026-11-15 |
| D-22 | Códigos de producto | El código (SKU) de cada producto es su **código de fábrica** de la nota de recepción; el nombre, la descripción tal cual figura en la nota. Los precios de compra los dará el cliente más adelante. | 2026-11-15 |
| D-23 | Canal de avisos | Las alertas se ven **solo dentro del sistema** (campanita y centro de notificaciones). Queda lista la interfaz para sumar correo, WhatsApp o Telegram. | 2026-11-15 |
| D-24 | Entrega del proveedor | El proveedor entrega en **1 a 3 días**: se usan 3 días por defecto; se puede ajustar por proveedor. | 2026-11-15 |
| D-25 | Cobertura de stock | Al reponer, la sucursal apunta a **1 semana** de venta y el depósito a **1 mes**. Si un producto tiene mínimo/máximo cargado, manda ese valor. | 2026-11-15 |
| D-26 | Margen bajo | Un pedido con margen **menor al 10 %** genera aviso; el margen negativo genera alerta crítica. | 2026-11-15 |
| D-27 | Cobro de las cadenas | Los supermercados pagan a **30-40 días**, por **transferencia bancaria**, y pagan **todo lo de un mes junto**. Se registra lo que deben y lo que pagaron; lo pagado queda como cuenta saldada. | 2026-11-15 |
| D-28 | Pagos con diferencia | Si la cadena encuentra un error (en la nota o la factura) deposita **menos** y lo notifica; la diferencia debe quedar registrada con su motivo. | 2026-11-15 |
| D-29 | Compras al contado | La empresa compra **al contado** casi siempre; el crédito con proveedores es excepcional. | 2026-11-15 |
| D-30 | Impuestos | La empresa quiere contabilizar el **IVA (13 %)** y el **IT (3 %)** de sus facturas. | 2026-11-15 |
| D-31 | Gastos operativos | Se registran: gasolina del vehículo, taxis, sueldos de los empleados, luz y agua (sucursales La Paz y Cochabamba) y alquiler de los depósitos (La Paz, sobre todo, y Cochabamba). | 2026-11-15 |

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

## Decisiones técnicas tomadas en la Fase 3 (a confirmar con el cliente)

| # | Tema | Implementado | Cómo cambiarlo |
|---|---|---|---|
| T-16 | Qué es una venta y su fecha | Pedidos ALISTADOS o ENTREGADOS, con la **fecha del pedido** (la de la nota de recepción). Cifras de las líneas, netas de devoluciones. | Usar la fecha de alistado o de entrega: un cambio en `reportes/consultas.py`. |
| T-17 | Rotación y días de inventario | Rotación = unidades vendidas en el período ÷ stock actual. Días de inventario = stock actual ÷ venta diaria promedio del período. | Con inventario promedio histórico (reconstruido del libro de movimientos) si el cliente lo prefiere. |
| T-18 | Sin movimiento | Con stock y sin ventas ni transferencias de salida desde esa ubicación en los últimos N días (30 por defecto, elegible). Lo que nunca salió se cuenta desde que ingresó (lo recién comprado no es "inmovilizado"). | — |
| T-19 | Quién ve qué | `reportes.operativos` (Administrador): unidades, facturación, rankings, inventario en unidades, usuarios. `reportes.rentabilidad` (Dueño, asignable a otros roles): además costos, ganancias, márgenes, valor a costo, mermas en Bs y precios de compra. | Desde Roles y permisos. |

## Decisiones técnicas tomadas en la Fase 4 (a confirmar con el cliente)

| # | Tema | Implementado | Cómo cambiarlo |
|---|---|---|---|
| T-20 | Pronóstico | Por sucursal y producto, con las unidades alistadas por semana (hasta 52). Se prueban promedio, promedio móvil (4 semanas) y suavizado exponencial y se usa el de menor error en las últimas semanas. Menos de 4 semanas: promedio y confianza baja. Se recalcula cada lunes 03:00 y con el botón «Recalcular». | Parámetros en `alertas/dominio.py`. |
| T-21 | Demanda del depósito | Es la suma de la de las sucursales que abastece. El depósito de cada sucursal es el **origen más frecuente de sus transferencias** (hoy: Cochabamba → Sucursal Cochabamba, La Paz → Sucursal Central); sin historial, el depósito con más stock. | Se elige otro origen al crear la transferencia. |
| T-22 | Stock de seguridad | 95 % de nivel de servicio: 1,65 × desviación de la demanda × √(días de reposición). Punto de reorden = demanda durante la reposición + seguridad. | `Z_SERVICIO` en `alertas/dominio.py`. |
| T-23 | Fardos y cajas | La sugerencia se redondea hacia arriba a la presentación más grande que no supere lo sugerido; si ninguna cabe, en unidades. | — |
| T-24 | Ruido con poco historial | El sobre-stock calculado por pronóstico solo avisa con confianza media o alta (o si se superó un máximo cargado). El stock bajo y el quiebre avisan siempre. | — |
| T-25 | Anomalías | Valor atípico = se aparta más de 3,5 desviaciones robustas (mediana y MAD) de la historia de esa cadena y producto (pedidos), del producto (compras) o del motivo (mermas). Hace falta un mínimo de historia (5; 3 en compras). | `atipico()` en `alertas/dominio.py`. |

## Decisiones técnicas tomadas en la Fase 5 (a confirmar con el cliente)

| # | Tema | Implementado | Cómo cambiarlo |
|---|---|---|---|
| T-26 | Cuenta por cobrar | Cada pedido **entregado** es una cuenta por cobrar por su ingreso (lo alistado menos lo devuelto), con el descuento de la nota aplicado en proporción. Vence a los **40 días** de la entrega. Una devolución después del pago deja **saldo a favor** de la cadena. | Plazo en Finanzas → Impuestos → Parámetros. |
| T-27 | Cobros | Una transferencia se reparte entre los pedidos que paga: lo aplicado debe sumar exactamente lo transferido. Si pagaron menos, la diferencia **queda pendiente** o se **cierra con motivo** (D-28). Un N.º de operación no se registra dos veces para la misma cadena. Los cobros se anulan con motivo, nunca se borran. | — |
| T-28 | Impuestos | **IVA 13 %** sobre lo facturado en el mes (la venta se reconoce al entregar), menos el **13 % de las compras y gastos con factura** del mes. Si el crédito es mayor, el sobrante pasa al mes siguiente (sin actualización por UFV). **IT 3 %** sobre lo facturado (sin compensar con el IUE). Es una referencia para el contador. | Porcentajes en Parámetros. |
| T-29 | Estado de resultados | Resultado de gestión con montos que incluyen IVA: ventas − costo de lo vendido − gastos − IVA − IT. El IVA se calcula **sobre lo vendido** (ventas menos el costo comprado con factura y los gastos con factura), para que una compra grande no infle la ganancia del mes en que se compra. | `finanzas/reportes.py`. |
| T-30 | Compras | Por defecto **al contado y con factura**: se consideran pagadas el día de la compra. A crédito exigen fecha de vencimiento y se marcan como pagadas en Finanzas → Por pagar (avisa 3 días antes). | En el formulario de compra. |
| T-31 | Cobro por el total | Pedido del dueño: se cobra contra **el total que debe cada empresa**, no pedido por pedido. La transferencia se aplica sola **de la entrega más antigua a la más reciente**; no puede superar lo que debe. Lo que no se va a pagar se **rebaja con motivo** («Rebajar saldo»), también de lo más antiguo; se puede anular. Por pagar sí se muestra compra por compra, con el total por proveedor. | `repartir()` en `finanzas/dominio.py`. |

## Pendientes de validar

- Muestras reales de notas de recepción de las demás cadenas (D-09, D-19) para la lectura automática.
- Precios de compra reales de los productos (D-22): el stock actual es imaginario, con costo provisional ≈ 70 % del precio de venta. Sus compras de prueba están marcadas «con factura» y generan un crédito fiscal ficticio en octubre de 2026 (Finanzas → Impuestos).

- Acceso desde celulares fuera de la red de la oficina y cómo obtener HTTPS (necesario para la cámara). Ver [ADR 0002](adr/0002-despliegue-en-oficina.md).
