# Proyecto: Sistema de Monitoreo de Inventario, Pedidos y Rentabilidad para una Distribuidora a Supermercados

## Tu rol

Eres un ingeniero de software senior full-stack con experiencia en sistemas de inventario (ERP/WMS), visión por computadora aplicada a documentos y machine learning práctico. Vas a construir un sistema completo, listo para producción, para un cliente real. Trabajo como freelancer y voy a mantener este proyecto, así que el código debe ser limpio, modular, documentado y fácil de extender.

**Antes de escribir código:** lee todo este documento, propónme la arquitectura, el modelo de datos (diagrama entidad-relación en Mermaid) y el plan por fases. Hazme las preguntas que consideres críticas. Cuando apruebe, avanza fase por fase y al terminar cada una dime qué hiciste, cómo probarlo y qué sigue.

---

## 1. Contexto del negocio

- La empresa es una **distribuidora** en Bolivia (La Paz). Compra productos a terceros (proveedores) y los entrega a **supermercados** (ej.: Hipermaxi, Ketal, Fidalga… cada cadena con varias sucursales, como "Hipermaxi Zona Sur" o "Hipermaxi Obrajes").
- Tiene **varias ubicaciones físicas** de dos tipos, y la cantidad no es fija (el sistema debe permitir crear N de cada una):
  - **Depósitos**: guardan la mercadería en unidades grandes (fardos, cajas). **No despachan pedidos a clientes**; su salida normal es transferir mercadería a las sucursales.
  - **Sucursales**: reciben mercadería de los depósitos (o directo del proveedor), la fraccionan, **alistan los pedidos y los despachan a los supermercados**. Todo pedido sale siempre de una sucursal.
- **Compra en unidades grandes** (fardo, caja, paquete, docena, bolsa…) pero **vende por unidad pequeña** (un guante, un trapo, un jabón, una viruta).
  - Ejemplo: compra 1 fardo de 100 paños a Bs 250 → el costo unitario es Bs 2,50 por paño.
  - Un mismo producto puede comprarse en distintas presentaciones (caja de 12, fardo de 48) y con distintos precios en el tiempo.
- Moneda: **bolivianos (BOB, Bs)**. Zona horaria: **America/La_Paz**. Toda la interfaz en **español**.

### Cómo trabajan hoy
1. El supermercado envía una **Orden de Compra (OC)**, que puede llegar **en papel o en PDF** (ambas formas son habituales). Contiene: número/código de OC, fecha, quién la emite, cadena y sucursal del supermercado, líneas de productos (código o descripción del supermercado, cantidad, **precio unitario de venta**, total de la línea) y el **total del pedido**.
2. **El precio de venta lo fija la cadena de supermercados y viene en la OC.** Es el mismo para todas las sucursales de una cadena (Hipermaxi Sur y Hipermaxi Obrajes pagan igual). La distribuidora no define el precio de venta: lo toma de la OC.
3. En una **sucursal** de la distribuidora se **alista** el pedido con esa OC y se despacha al supermercado. Hoy la cuenta se lleva a mano.

### Lo que quiere el cliente
1. Saber **cuánto stock queda** de cada producto en **cada ubicación** y en total.
2. Registrar **ingresos** (compras a proveedores: fecha, proveedor, presentación, cantidad, precio de la unidad grande y costo resultante por unidad pequeña) y **salidas** (entregas a supermercados), además de **transferencias** entre depósito y sucursal.
3. **Escanear la OC** (foto desde el celular o PDF) y que el sistema, con IA, extraiga las líneas y **descuente el inventario automáticamente** cuando el pedido quede alistado.
4. Saber **cuánto ganó en cada pedido**: costo de lo entregado vs. precio de venta = ganancia y margen.
5. Registrar **quién** escaneó, confirmó, alistó y entregó cada pedido (trazabilidad completa).
6. **Ganancias** diarias, semanales y mensuales, y **estadísticas** lo más completas posible.
7. **Alertas de stock** y una capa de **machine learning** que agregue valor real.
8. Que quede **preparado para crecer hacia un módulo financiero** completo.

---

## 2. Roles y permisos (RBAC)

| Rol | Puede |
|---|---|
| **Dueño** | Todo. Ve costos, precios, ganancias, márgenes, auditoría completa. Gestiona usuarios, roles, ubicaciones y configuración. Aprueba ajustes de inventario sensibles. |
| **Administrador** | Registrar compras/ingresos, **transferencias entre ubicaciones**, ajustes (merma, rotura, conteo físico), gestionar productos, proveedores y clientes, revisar y corregir pedidos escaneados, ver reportes operativos. Que vea o no la rentabilidad debe poder configurarlo el dueño. |
| **Encargado / Repartidor** | Ver los pedidos asignados, **fotografiar la OC**, revisar y confirmar lo que extrajo la IA, marcar el pedido como alistado y entregado (con foto o firma de recepción opcional), consultar stock disponible. **No ve costos ni ganancias.** |

- Los permisos deben ser granulares (basados en permisos, no roles fijos en el código), para poder crear roles nuevos más adelante (ej.: contador).
- Un usuario puede estar asignado a una o varias ubicaciones.
- **Bitácora de auditoría inmutable**: quién hizo qué, cuándo, desde dónde, valor anterior y nuevo. Nada se borra físicamente: se anula, con motivo.

---

## 3. Requerimientos funcionales

### 3.1 Catálogo
- **Productos**: SKU interno, nombre, categoría, marca, unidad base (unidad de venta), código de barras opcional, foto, stock mínimo y máximo por ubicación, activo/inactivo, y un indicador **"controla fecha de vencimiento"** (sí/no, ver 3.2).
  - La mayoría de los productos **no** vencen (artículos de limpieza). Algunos sí, sobre todo en ciertas temporadas, y ocasionalmente se entregan perecibles (por ejemplo, carne) que no se guardan mucho tiempo. Para el sistema son productos más con el indicador activado; no hace falta un módulo especial de perecibles.
- **Presentaciones / unidades de compra**: por producto, N presentaciones con su factor de conversión a la unidad base (Fardo = 100 u, Caja = 12 u). Las conversiones siempre se resuelven a unidad base.
- **Proveedores**: datos de contacto, NIT, productos que provee e historial de precios.
- **Clientes**: modelar **Cadena** (Hipermaxi) → **Sucursal/punto de entrega** (Hipermaxi Obrajes), con NIT, dirección y contacto.
- **Precios de venta por cadena**: el precio es **por cadena**, igual para todas sus sucursales, y la fuente es la OC. El sistema guarda el **historial de precios por (cadena, producto)** a partir de las OC confirmadas. Sirve como referencia y para validar: si una OC trae un precio distinto del último conocido para esa cadena, se resalta en la revisión y se registra el cambio. El precio de la OC confirmada es el que vale.
- **Equivalencias de códigos**: cada supermercado nombra y codifica los productos a su manera. Tabla de mapeo `(cadena, código/descripción del cliente) → producto interno`. Es clave para la IA (ver 4.2).

### 3.2 Inventario (kardex)
- El inventario se basa en un **libro de movimientos inmutable** (ledger): cada cambio de stock es un movimiento con tipo, producto, ubicación, cantidad en unidad base, costo unitario, usuario, fecha y documento de origen.
- Tipos de movimiento: `COMPRA`, `VENTA/ENTREGA`, `TRANSFERENCIA_SALIDA` / `TRANSFERENCIA_ENTRADA` (en pareja, con estado "en tránsito" opcional), `AJUSTE_POSITIVO` / `AJUSTE_NEGATIVO` (merma, rotura, vencimiento, conteo físico), `DEVOLUCION_CLIENTE`, `DEVOLUCION_PROVEEDOR`, `ANULACION` (reverso).
- El stock actual por ubicación puede estar materializado o cacheado por rendimiento, pero siempre debe poder **recalcularse desde el ledger** y cuadrar.
- **Stock disponible vs. comprometido**: por producto y ubicación, mostrar `stock físico`, `comprometido` (reservado por pedidos confirmados que aún no se alistan) y `disponible = físico − comprometido`.
- **Visualización en unidades grandes**: el stock se guarda en unidad base, pero en depósitos debe poder verse también en presentaciones (ej.: "3 fardos + 20 u").
- **Flujo depósito → sucursal**: las transferencias suelen hacerse en unidades grandes (fardos/cajas) y el sistema las convierte a unidad base. La sucursal maneja el stock fraccionado.
- **Valoración del inventario**: implementa **Costo Promedio Ponderado** por defecto (habitual en Bolivia) y deja la arquitectura lista para **PEPS/FIFO por lotes**. Guarda los lotes de compra (fecha, proveedor, costo) de todos modos.
- **Fechas de vencimiento (solo productos con el indicador activo)**:
  - Al registrar la compra se exige el lote y su fecha de vencimiento. El lote conserva su vencimiento cuando se transfiere entre ubicaciones.
  - En las salidas se sugiere **FEFO** (lo que vence primero sale primero); el usuario puede elegir otro lote.
  - Bloquear o advertir al despachar lotes vencidos o que vencen antes de un umbral configurable.
  - Ajuste de baja por vencimiento, con su costo reflejado como merma.
  - Para los productos sin el indicador, nada de esto aparece en la interfaz, para no complicar el trabajo diario.
- **El costo de cada salida se congela** en el movimiento al momento de la venta (snapshot), para que la ganancia histórica no cambie si después varían los costos.
- No se permite stock negativo salvo que el dueño lo habilite en la configuración. Si a una sucursal no le alcanza el stock para un pedido, el sistema avisa y sugiere **transferir desde un depósito** (o desde otra sucursal) y permite crear esa transferencia en un clic.
- **Conteo físico / toma de inventario**: el usuario registra lo contado, el sistema muestra las diferencias y genera los ajustes al aprobarlos.
- Ver **kardex por producto** (entradas, salidas, saldo y costo) filtrable por ubicación y rango de fechas.

### 3.3 Compras (ingresos)
- Registrar una compra: proveedor, fecha, número de factura/nota, ubicación de destino, líneas (producto, presentación, cantidad de unidades grandes, precio por unidad grande). El sistema calcula: unidades base que ingresan, **costo por unidad pequeña**, total.
- Permitir costos adicionales prorrateables (flete, carga) que se suman al costo unitario.
- (Deseable) También escanear la factura del proveedor con la misma IA de OCR.

### 3.4 Pedidos de supermercado (flujo principal)
Estados: `BORRADOR` (recién escaneado) → `CONFIRMADO` → `ALISTADO` → `ENTREGADO` | `ANULADO`.

**Efecto de cada estado en el inventario (regla de negocio central):**

| Estado | Qué pasa con el stock |
|---|---|
| `BORRADOR` | Nada. Solo datos extraídos pendientes de revisión. |
| `CONFIRMADO` | Se **reserva** el stock en la sucursal (sube el *comprometido*, baja el *disponible*). El stock físico no cambia. |
| `ALISTADO` | Se **descuenta el stock físico**: se generan los movimientos de salida, se libera la reserva, se congela el costo y se calcula la ganancia. Es el momento del descuento real. |
| `ENTREGADO` | No mueve stock. Registra quién entregó, cuándo y la constancia de recepción (foto o firma, opcional). |
| `ANULADO` | Si estaba confirmado, libera la reserva. Si ya estaba alistado o entregado, genera movimientos de reverso (devolución al stock) con motivo obligatorio. |

1. El encargado abre la app en el celular, elige la **sucursal de despacho** (solo se listan ubicaciones de tipo sucursal; por defecto, la del usuario) y carga la OC por cualquiera de estas vías:
   - **Foto** con la cámara del celular (OC en papel), con varias páginas si hace falta.
   - **Archivo PDF** (OC digital), que puede ser un PDF con texto o un escaneo; también de varias páginas.
   - Imagen ya guardada en el teléfono o la computadora.
2. La IA extrae: número de OC, fecha, cadena, sucursal del supermercado, emisor, líneas (descripción/código, cantidad, **precio unitario**, **total de línea**) y **total del pedido**. Cada campo con **nivel de confianza**.
3. El sistema empareja cada línea con un producto interno (ver 4.2) y muestra una **pantalla de revisión**:
   - Documento original al lado de los datos extraídos; campos de baja confianza resaltados; líneas sin emparejar marcadas.
   - **Validaciones aritméticas**: `cantidad × precio unitario = total de línea` y `suma de líneas = total del pedido`. Cualquier diferencia se resalta (suele indicar un error de lectura).
   - Comparación del precio de cada línea con el último precio conocido de esa cadena para ese producto.
   - Verificación de stock disponible en la sucursal elegida, con la opción de pedir una transferencia desde el depósito si no alcanza.
4. El usuario corrige lo necesario y **confirma** → se reserva el stock. *Nunca se mueve inventario sin confirmación humana.*
5. Cuando el pedido está listo, el encargado lo marca como **ALISTADO** → se descuenta el inventario. En productos con vencimiento, se elige o confirma el lote (FEFO sugerido).
6. Al despachar y entregar, se marca **ENTREGADO**.
7. **Detección de duplicados**: no permitir registrar dos veces el mismo número de OC de la misma cadena.
8. Se guardan el **documento original** (imagen o PDF), el JSON crudo extraído, las correcciones y quién escaneó, confirmó, alistó y entregó, y cuándo.
9. **Rentabilidad del pedido** (se calcula al alistar): ingreso (precios de la OC), costo (costo congelado de cada línea), ganancia bruta y margen %, por línea y total.
10. También debe poder crearse un pedido **manualmente**, sin documento.

### 3.5 Alertas
- Stock bajo el mínimo (por ubicación y global), con distinción entre **sucursal baja → reponer desde el depósito** y **depósito bajo → comprar al proveedor**; quiebre de stock; pedidos confirmados que no pueden alistarse por falta de stock; precio de una OC distinto del último conocido para esa cadena; sobre-stock, productos sin movimiento en X días, lotes próximos a vencer, margen negativo o inusualmente bajo en un pedido, OC duplicada, diferencias grandes en conteos físicos.
- Centro de notificaciones dentro de la app; arquitectura lista para canales externos (email, WhatsApp, Telegram) mediante una interfaz de notificadores.
- **Sugerencias de reposición en dos niveles**, basadas en el consumo y el pronóstico (ver 4.3):
  - **Depósito → sucursal**: qué transferir a cada sucursal y cuánto, en fardos o cajas.
  - **Proveedor → depósito**: qué comprar, cuánto (en unidades grandes del proveedor) y cuándo.

### 3.6 Reportes y dashboard
Dashboard del dueño con filtros por rango de fechas, ubicación, cadena, sucursal de cliente, categoría y producto:
- **Ganancias** diarias, semanales, mensuales y anuales (ingreso, costo, ganancia, margen), con comparación contra el período anterior.
- Pedido más caro, pedido de mayor ganancia, pedidos de menor margen.
- Productos más entregados (en unidades y en Bs), productos más rentables y menos rentables.
- Ranking de clientes (cadenas y sucursales) por volumen, facturación y ganancia.
- Valor del inventario a costo, por ubicación.
- Rotación de inventario y días de inventario por producto.
- Productos sin movimiento / stock inmovilizado.
- Mermas y ajustes por período (en Bs).
- Historial de precios de compra por producto y proveedor (gráfico).
- Rendimiento por usuario (pedidos escaneados/entregados, tasa de corrección de la IA).
- Precisión de la IA en el tiempo (% de campos corregidos).
- **Exportar** a Excel y PDF en todos los reportes.

---

## 4. Inteligencia artificial / Machine Learning

Sé pragmático: **no entrenes un OCR desde cero**. Usa modelos preentrenados para la lectura y aplica ML propio donde el negocio genera datos propios.

### 4.1 Extracción de datos de la OC (papel y PDF)
- Las OC llegan **en papel (se fotografían) y en PDF**; el sistema debe manejar las dos con el mismo flujo de revisión:
  - **PDF con capa de texto** (generado digitalmente): extrae primero el texto y las tablas directamente (pdfplumber/PyMuPDF), que es más barato y exacto, y usa el modelo para estructurarlo. Si la extracción es pobre, cae al camino de visión.
  - **PDF escaneado o foto**: convierte cada página a imagen y usa visión.
  - Soporta documentos de varias páginas y une las líneas de todas en un solo pedido.
  - Es probable que cada cadena use su propio formato de OC: guarda la cadena detectada para medir la precisión por formato y, si hace falta, ajustar las instrucciones de extracción por cadena.
- Usa un **modelo de lenguaje multimodal con visión** (por ejemplo, la API de Claude) para leer el documento y devolver **JSON estructurado y validado** contra un esquema (Pydantic/Zod).
- Encapsula el proveedor detrás de una interfaz `DocumentExtractor`, para poder cambiarlo o tener un **fallback** con OCR open source (PaddleOCR / Tesseract + parsing) sin tocar el resto del sistema.
- Preprocesa la imagen (corrección de rotación y perspectiva, recorte, contraste) para mejorar la lectura de fotos de celular.
- Proceso **asíncrono** (cola de tareas) con estado visible en la interfaz; reintentos; límite de costos y registro del consumo de la API.
- Guarda el documento, la respuesta cruda y las correcciones del usuario: ese dataset sirve para medir la precisión y mejorar el sistema.
- Usa las validaciones aritméticas (líneas vs. total) como señal automática de calidad de la lectura.
- Las claves de la API van en variables de entorno, nunca en el código.

### 4.2 Emparejamiento inteligente de productos (aprende con el uso)
- Para cada línea extraída, busca el producto interno en este orden: (1) mapeo exacto ya conocido para esa cadena; (2) coincidencia por código de barras/código; (3) **búsqueda difusa + embeddings semánticos** sobre nombre y descripción (por ejemplo, pgvector); (4) sugerencias ordenadas por puntaje para que el usuario elija.
- Cada vez que el usuario confirma o corrige un emparejamiento, **se guarda en la tabla de equivalencias**: el sistema mejora solo y cada vez requiere menos correcciones. Mostrar esta métrica.

### 4.3 Pronóstico de demanda y reposición
- Modelo de series de tiempo por producto (y por cliente cuando haya datos suficientes) para predecir la demanda de las próximas semanas. Empieza con un modelo simple y robusto (promedios móviles / suavizado exponencial / Prophet o statsmodels) y evalúalo con backtesting; escala a modelos más complejos solo si mejoran el error.
- Con el pronóstico, calcula **punto de reorden, stock de seguridad y días de cobertura**, y genera la sugerencia de compra.
- Reentrenamiento programado (job semanal). Mientras no haya historial suficiente, usa reglas simples y muestra que la predicción tiene baja confianza.

### 4.4 Detección de anomalías
- Marcar pedidos con cantidades o precios fuera de lo habitual para ese cliente o producto, precios de compra anómalos, mermas inusuales y diferencias de inventario sospechosas.

---

## 5. Requerimientos no funcionales

- **Mobile-first para el repartidor**: la app debe funcionar muy bien en celulares Android de gama media, como **PWA** instalable, con acceso a la cámara. Tolerar mala conexión (cola de subida de fotos y reintentos).
- **Dinero con tipos decimales exactos** (nunca float). Cantidades en unidad base como enteros o decimales controlados.
- Transacciones atómicas en toda operación de inventario; control de concurrencia (dos personas descontando el mismo producto al mismo tiempo).
- Seguridad: autenticación con JWT o sesiones seguras, contraseñas con hash fuerte, rate limiting, validación de entrada, CORS correcto, archivos subidos validados.
- Imágenes en almacenamiento de objetos compatible con S3 (MinIO en local).
- **Multi-empresa listo** (columna de tenant o diseño que lo permita), por si en el futuro vendo el sistema a otras distribuidoras.
- Respaldos automáticos de la base de datos.
- Tests: unitarios del dominio (costeo, conversiones, cálculo de ganancia, kardex), de integración de la API y al menos un E2E del flujo "escanear OC → confirmar → stock descontado → ganancia calculada".
- Logs estructurados y manejo de errores claro para el usuario final (mensajes en español, no stack traces).

---

## 6. Stack tecnológico sugerido

Elige tú la tecnología más conveniente y **justifica tu elección**. Mi sugerencia de partida (puedes cambiarla si tienes buenas razones):

- **Backend**: Python + FastAPI (encaja con el ecosistema de ML), SQLAlchemy 2 + Alembic, Pydantic.
- **Base de datos**: PostgreSQL (+ pgvector para embeddings).
- **Tareas asíncronas**: Celery o RQ/Arq + Redis (OCR, reentrenamiento, alertas, reportes pesados).
- **Frontend**: React + TypeScript + Vite, Tailwind + shadcn/ui, TanStack Query, una librería de gráficos (Recharts/ECharts), PWA.
- **ML**: pandas, scikit-learn, statsmodels/Prophet, rapidfuzz, un modelo de embeddings.
- **Infraestructura**: Docker Compose para desarrollo y producción, Nginx/Caddy, variables en `.env`, listo para desplegar en un VPS.
- **Documentación de la API**: OpenAPI/Swagger automático.

---

## 7. Escalabilidad hacia el módulo financiero (fase futura, pero diseñar desde ya)

No lo implementes todavía, pero **diseña la arquitectura y el modelo de datos para que se pueda agregar sin rehacer nada**:
- **Cuentas por cobrar**: los supermercados suelen pagar a crédito (30/60/90 días). Pedido entregado → documento por cobrar → pagos parciales → antigüedad de saldos.
- **Cuentas por pagar** a proveedores.
- **Gastos operativos** (transporte, combustible, sueldos, alquiler) para pasar de ganancia bruta a **ganancia neta**.
- Flujo de caja, estado de resultados, balance; idealmente con base en **contabilidad de partida doble** (asientos generados automáticamente desde compras, ventas y pagos).
- Impuestos de Bolivia (IVA 13 %, IT 3 %) e integración futura con **facturación electrónica del SIN**.
- Organiza el código en **módulos de dominio independientes** (catálogo, inventario, compras, ventas/pedidos, IA, reportes, usuarios/auditoría y, más adelante, finanzas), comunicados mediante servicios o eventos de dominio (ej.: `PedidoConfirmado`, `CompraRegistrada`), para que finanzas solo tenga que suscribirse a esos eventos.

---

## 8. Plan de trabajo por fases

1. **Fase 0 – Base**: estructura del monorepo, Docker Compose, base de datos, autenticación, roles/permisos, auditoría, CI con lint y tests.
2. **Fase 1 – Núcleo de inventario**: catálogo, presentaciones y conversiones, ubicaciones, proveedores, clientes (cadena → sucursal), compras, transferencias, ajustes, kardex, costo promedio ponderado, stock por ubicación.
3. **Fase 2 – Pedidos + IA de escaneo**: flujo completo de OC con foto y PDF, extracción, reserva al confirmar y descuento al alistar, pantalla de revisión, emparejamiento inteligente, confirmación, descuento, rentabilidad por pedido, PWA móvil.
4. **Fase 3 – Reportes y dashboard**: todas las métricas de 3.6, exportación a Excel/PDF.
5. **Fase 4 – Alertas y ML**: alertas, pronóstico de demanda, sugerencias de reposición, anomalías, métricas de precisión de la IA.
6. **Fase 5 – (futuro) Finanzas**: según la sección 7.

---

## 9. Entregables

- Código completo y funcional, con `docker compose up` como único paso para levantarlo en local.
- **Datos semilla realistas**: productos de limpieza y consumo típicos (paños, virutas, guantes, jabones, detergentes, esponjas, bolsas…) con sus presentaciones, algunos productos **con vencimiento** (incluido un perecible como carne) con lotes y fechas, 2 depósitos y 2 sucursales, varios proveedores, cadenas con sucursales (Hipermaxi Sur, Hipermaxi Obrajes, Ketal, Fidalga…), usuarios de prueba para cada rol, y meses de historial de compras y pedidos para que el dashboard y el ML tengan datos.
- **OC de ejemplo** (generadas) para probar el escaneo: al menos una foto de papel, un PDF digital con texto y un PDF escaneado, de cadenas distintas.
- `README.md` en español: instalación, variables de entorno, usuarios de prueba, arquitectura, cómo correr los tests y cómo desplegar en producción.
- Documento de arquitectura y diagrama ER en Mermaid.
- Manual de usuario breve por rol.

## 10. Reglas de trabajo

- Explica las decisiones importantes antes de implementarlas.
- Commits pequeños y descriptivos por funcionalidad.
- No dejes TODOs críticos sin avisarme; lista al final de cada fase lo pendiente y los riesgos.
- Si algo de este documento es ambiguo o contradictorio, pregúntame en lugar de suponer.
