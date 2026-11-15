# Arquitectura

Especificación: [`PROMPT_sistema_inventario.md`](../PROMPT_sistema_inventario.md) ·
Decisiones del cliente: [`decisiones-negocio.md`](decisiones-negocio.md) ·
ADRs: [`adr/`](adr/)

## Visión general

```
 Celulares / PC  ──HTTP(S)──►  Caddy (web)
                                 ├── /          → frontend estático (React PWA)
                                 └── /api/*     → backend (FastAPI)
                                                    ├── PostgreSQL (datos, auditoría)
                                                    └── Redis ◄── worker (Celery: OCR, alertas, ML)
```

**Monolito modular**: un solo despliegue, dividido en módulos de dominio con límites claros.

```
backend/app/
├── core/            configuración, BD, seguridad, errores, logs, esquemas comunes
├── modules/
│   ├── identidad/     usuarios, roles, permisos, sesiones, auditoría        ✅ Fase 0
│   ├── organizacion/  empresa, ubicaciones (depósito/sucursal)              ✅ Fase 0
│   ├── catalogo/      categorías, marcas, productos, presentaciones         ✅ Fase 1
│   ├── proveedores/   proveedores y productos que proveen                   ✅ Fase 1
│   ├── clientes/      cadenas y sucursales de supermercado                  ✅ Fase 1
│   │                  (precios por cadena y equivalencias: Fase 2)
│   ├── compras/       compras, costos prorrateados, historial de precios    ✅ Fase 1
│   ├── inventario/    motor, libro, saldos, CPP, lotes, transferencias,     ✅ Fase 1
│   │                  ajustes, conteos, kardex, verificación
│   ├── pedidos/       OC → pedido, estados, rentabilidad, equivalencias     ✅ Fase 2a
│   ├── documentos/    archivos; lectura de OC: OCR local y plantillas      ✅ Fase 2b
│   ├── reportes/      consultas de solo lectura, exportación                Fase 3
│   ├── alertas/       reglas y notificaciones                               Fase 4
│   └── ml/            pronóstico, reposición, anomalías                     Fase 4
└── workers/         tareas Celery
```

Cada módulo sigue la misma forma:

| Archivo | Responsabilidad |
|---|---|
| `models.py` | Tablas (SQLAlchemy) |
| `schemas.py` | Entrada/salida de la API (Pydantic) |
| `servicios.py` | Casos de uso: validan, modifican, auditan y hacen `commit` (una transacción por caso de uso) |
| `api.py` | Rutas delgadas: permisos + llamada al servicio |
| `dominio.py` | Lógica pura sin BD (conversiones, CPP, rentabilidad), cuando exista |

## Principios

1. **El stock solo cambia a través de `app/modules/inventario/motor.py`**, que bloquea el saldo
   (`SELECT … FOR UPDATE`, en orden determinista para evitar bloqueos cruzados), valida, escribe el
   movimiento y actualiza saldo, CPP y lote. El servicio que lo llama audita y hace `commit`.
   Una prueba con dos transacciones simultáneas verifica que no se puede vender dos veces lo mismo.
2. **Libro de movimientos inmutable** (trigger en PostgreSQL). Nada se edita ni se borra: se anula
   con movimientos de reverso (mismo lote y costo). `GET /api/inventario/verificacion` recalcula los
   saldos desde el libro y los compara con los materializados.
3. **Bitácora de auditoría inmutable**, protegida por un trigger de PostgreSQL (ni la aplicación
   puede modificarla). Guarda usuario, acción, entidad, antes/después, IP y fecha.
4. **Permisos granulares.** Los permisos se definen en código
   (`app/modules/identidad/permisos.py`); los roles se arman en la base de datos. El Dueño siempre
   tiene todos.
5. **Multiempresa desde el inicio:** las tablas de negocio llevan `empresa_id`.
6. **Tipos exactos:** dinero `NUMERIC(14,2)`, costo unitario `NUMERIC(18,6)`, cantidades
   `NUMERIC(14,3)` en unidad base, fechas `timestamptz` (zona America/La_Paz en la interfaz).
7. **Eventos de dominio** en la tabla `evento_dominio` (*outbox*): `CompraRegistrada`,
   `CompraAnulada`, `TransferenciaRealizada`, `AjusteAplicado`. Alertas, ML y finanzas los
   consumirán sin acoplarse a quien los produjo.
8. **Mensajes al usuario en español**, nunca trazas técnicas. Logs estructurados en JSON.

## Seguridad (Fase 0)

- Contraseñas con Argon2. Verificación con tiempo constante también para correos inexistentes.
- Sesión en cookie `httpOnly` + `SameSite=Lax` (`Secure` con HTTPS). Solo se guarda el hash del
  token en la base.
- CSRF: token por sesión, enviado en la cabecera `X-CSRF-Token` en toda petición que modifica datos.
- Bloqueo tras 5 intentos fallidos por correo (o 20 por IP) en 15 minutos.
- Desactivar un usuario o restablecer su contraseña cierra todas sus sesiones.
- Siempre queda al menos un Dueño activo.
- Caddy añade cabeceras de seguridad y limita el tamaño de las subidas.

## Modelo de datos

Implementado en la Fase 0: `empresa`, `ubicacion`, `usuario`, `rol`, `permiso`, `rol_permiso`,
`usuario_rol`, `usuario_ubicacion`, `sesion`, `intento_login`, `auditoria`.

Implementado en la Fase 1: `categoria`, `marca`, `producto`, `presentacion`, `limite_stock`,
`proveedor`, `proveedor_producto`, `cadena`, `sucursal_cliente`, `compra`, `compra_linea`,
`compra_costo`, `lote`, `stock_ubicacion`, `stock_lote`, `movimiento`, `transferencia`,
`transferencia_linea`, `ajuste`, `ajuste_linea`, `conteo_fisico`, `conteo_linea`, `evento_dominio`.

### Reglas de inventario implementadas (Fase 1)

- Cantidades siempre en **unidad base**; cada línea congela su presentación y factor.
- **Costo de compra por unidad** = (subtotal de la línea + su parte de los costos adicionales) ÷
  unidades base. Los adicionales se prorratean según el importe de cada línea.
- **CPP por ubicación** (D-04): las entradas lo recalculan; las salidas no lo cambian y se valoran a él.
- **Lotes para todos los productos**: cada compra o ajuste positivo crea un lote. Las salidas toman
  el lote indicado o, si no, FEFO y luego FIFO. Las transferencias no envían unidades vencidas.
- **Disponible = físico − comprometido.** Transferencias y ajustes solo usan el disponible
  (las reservas de pedidos llegan en la Fase 2).
- **Acceso por ubicación**: se opera solo en las ubicaciones asignadas, salvo con el permiso
  `ubicaciones.todas` (Dueño y Administrador por defecto). Ver stock es global.
- **Ajustes**: se aplican al instante si quien los registra tiene `inventario.aprobar_ajuste` o si
  el valor no supera `empresa.configuracion.umbral_ajuste_bs` (por defecto 0); si no, quedan
  pendientes de aprobación. Merma, rotura y vencimiento solo disminuyen.
- **Conteo físico**: se cuenta, se ven las diferencias contra el stock actual y al aprobar se
  genera un ajuste aplicado.
- **Anulaciones** de compras y transferencias: solo si la mercadería sigue disponible donde ingresó.

Diagrama previsto (las fases siguientes pueden ajustarlo):

### Identidad, organización y catálogo

```mermaid
erDiagram
  EMPRESA ||--o{ UBICACION : tiene
  EMPRESA ||--o{ USUARIO : emplea
  USUARIO }o--o{ ROL : usuario_rol
  ROL }o--o{ PERMISO : rol_permiso
  USUARIO }o--o{ UBICACION : usuario_ubicacion
  USUARIO ||--o{ SESION : abre
  USUARIO ||--o{ AUDITORIA : genera
  CATEGORIA ||--o{ PRODUCTO : clasifica
  MARCA ||--o{ PRODUCTO : fabrica
  PRODUCTO ||--o{ PRESENTACION : "se compra en"
  PRODUCTO ||--o{ PRODUCTO_UBICACION : "min/max por"
  UBICACION ||--o{ PRODUCTO_UBICACION : ""
  PROVEEDOR ||--o{ PROVEEDOR_PRODUCTO : provee
  PRODUCTO ||--o{ PROVEEDOR_PRODUCTO : ""

  UBICACION { uuid id  string nombre  enum tipo  bool activo }
  PRODUCTO { uuid id  string sku  string nombre  string unidad_base  string codigo_barras  bool controla_vencimiento  bool activo }
  PRESENTACION { uuid id  string nombre  numeric factor  bool activo }
  AUDITORIA { bigint id  string accion  string entidad  string entidad_id  jsonb antes  jsonb despues  string ip  timestamptz fecha }
```

### Compras e inventario

```mermaid
erDiagram
  PROVEEDOR ||--o{ COMPRA : ""
  UBICACION ||--o{ COMPRA : destino
  COMPRA ||--|{ COMPRA_LINEA : ""
  COMPRA ||--o{ COMPRA_COSTO_ADICIONAL : "flete, carga"
  COMPRA_LINEA }o--|| PRESENTACION : "comprada en"
  COMPRA_LINEA ||--|| LOTE : crea
  PRODUCTO ||--o{ LOTE : ""
  UBICACION ||--o{ STOCK_UBICACION : ""
  PRODUCTO ||--o{ STOCK_UBICACION : ""
  STOCK_UBICACION ||--o{ STOCK_LOTE : desglosa
  LOTE ||--o{ STOCK_LOTE : ""
  MOVIMIENTO }o--|| STOCK_UBICACION : afecta
  MOVIMIENTO }o--o| LOTE : ""
  TRANSFERENCIA ||--|{ TRANSFERENCIA_LINEA : ""
  AJUSTE ||--|{ AJUSTE_LINEA : ""
  CONTEO_FISICO ||--|{ CONTEO_LINEA : ""
  CONTEO_FISICO ||--o| AJUSTE : "genera al aprobar"

  COMPRA_LINEA { numeric cantidad_presentacion  numeric factor_snapshot  numeric precio_presentacion  numeric cantidad_base  numeric costo_unitario_base }
  LOTE { uuid id  string codigo  date vencimiento  numeric costo_unitario }
  STOCK_UBICACION { numeric fisico  numeric comprometido  numeric cpp  int version }
  MOVIMIENTO { bigint id  enum tipo  numeric cantidad  numeric costo_unitario  numeric saldo_despues  numeric cpp_despues  string origen_tipo  uuid origen_id  uuid usuario_id  timestamptz fecha }
```

- Las transferencias son inmediatas (D-13): generan `TRANSFERENCIA_SALIDA` y `TRANSFERENCIA_ENTRADA`
  en la misma transacción.
- Cada compra crea un lote interno para todos los productos. En los que no controlan vencimiento
  los lotes se asignan solos (FIFO) y no aparecen en la interfaz; así queda lista la valoración PEPS.

### Clientes, OC y pedidos

```mermaid
erDiagram
  CADENA ||--o{ SUCURSAL_CLIENTE : ""
  CADENA ||--o{ PRECIO_CADENA : historial
  PRODUCTO ||--o{ PRECIO_CADENA : ""
  CADENA ||--o{ EQUIVALENCIA : "codigo cliente"
  PRODUCTO ||--o{ EQUIVALENCIA : ""
  CADENA ||--o{ PLANTILLA_OC : formato
  DOCUMENTO_OC ||--o{ DOCUMENTO_PAGINA : ""
  DOCUMENTO_OC ||--o{ EXTRACCION : intentos
  PEDIDO ||--|| DOCUMENTO_OC : "nace de"
  SUCURSAL_CLIENTE ||--o{ PEDIDO : recibe
  UBICACION ||--o{ PEDIDO : "despacha (sucursal)"
  PEDIDO ||--|{ PEDIDO_LINEA : ""
  PEDIDO_LINEA }o--o| PRODUCTO : emparejada
  PEDIDO_LINEA ||--o{ PEDIDO_LINEA_LOTE : "lotes usados"
  PEDIDO ||--o{ PEDIDO_EVENTO : "quien y cuando"
  PEDIDO ||--o| CONSTANCIA_ENTREGA : ""

  PEDIDO { uuid id  string numero_oc  date fecha_oc  enum estado  numeric total_oc  numeric ingreso  numeric costo  numeric ganancia  numeric margen }
  PEDIDO_LINEA { string codigo_cliente  string descripcion_cliente  numeric cantidad_oc  numeric precio_oc  numeric total_oc  numeric cantidad_confirmada  numeric cantidad_alistada  numeric costo_unitario_snapshot  numeric ganancia  jsonb confianza }
  EXTRACCION { string motor  jsonb json_crudo  jsonb correcciones  numeric confianza_global  bool aritmetica_ok }
```

- `UNIQUE(empresa_id, cadena_id, numero_oc)` sobre pedidos no anulados (OC duplicadas).
- Cantidades y precios de la OC siempre por unidad base (D-10).
- `cantidad_confirmada ≤ disponible` al confirmar (D-02); `cantidad_alistada ≤ confirmada` (D-11).

### Lectura automática de la OC (Fase 2b)

Al subir la OC a un borrador vacío, el worker la lee (OCR local, ver
[ADR 0003](adr/0003-lectura-de-oc-sin-costo.md)) y completa cadena, sucursal del supermercado (por
parecido con «Enviar a»), número, fechas, total y líneas. El producto de cada línea se asigna solo
si hay una equivalencia aprendida o coincide el código; si no, se ofrecen sugerencias. Los campos
leídos con confianza menor a 85 % se resaltan. Nunca reemplaza lo cargado a mano salvo que el
usuario pulse «Volver a leer», y nunca mueve stock. `GET /api/pedidos/lectura/precision` resume la
precisión por formato a partir de lo que se corrigió al confirmar.

### Reglas de pedidos implementadas (Fase 2a)

| Paso | Qué hace |
|---|---|
| Nuevo | Se elige la sucursal que despacha y se adjuntan fotos/PDF de la OC. Las fotos se reducen en el celular; si no hay señal, quedan en el dispositivo (IndexedDB) y se suben solas al volver la conexión. |
| Borrador | Todo es editable (D-06). La revisión muestra el documento al lado, valida `cantidad × precio = total` y `suma = total OC`, avisa precios distintos del último de la cadena, muestra el disponible en la sucursal y en depósitos (con atajo para transferir) y sugiere el producto: equivalencia aprendida → código → parecido del nombre (pg_trgm). |
| Confirmar | Exige OC adjunta, cadena, sucursal de supermercado, número, fecha y productos en las líneas con cantidad. Bloquea OC duplicadas por cadena (índice único). Reserva solo stock **vigente** y guarda las equivalencias usadas. |
| Alistar | Libera la reserva y descuenta lo alistado (≤ confirmado) de lotes vigentes: FEFO o los lotes elegidos. Congela el costo (CPP de la sucursal) y calcula ingreso, costo, ganancia y margen por línea y total. La merma va a un ajuste ROTURA vinculado al pedido, con la regla de aprobación de ajustes. |
| Entregar | Constancia opcional: quién recibe, foto y firma en pantalla. |
| Anular | Borrador: nada. Confirmado: libera la reserva. Alistado: reverso en los mismos lotes y costo. Entregado: no se anula (D-03). |
| Devolución | Solo después de entregar (D-12): vuelve al stock en los mismos lotes y costo y recalcula la ganancia. |

- El stock reservado está protegido: transferencias y ajustes no pueden tomar unidades vigentes
  comprometidas. La verificación compara el comprometido con los pedidos confirmados.
- Archivos: en disco del servidor (volumen `archivos`, incluido en `scripts/respaldo.sh`),
  validados por contenido (JPG, PNG, WebP, PDF), 15 MB por archivo, 20 por pedido. La tabla
  `archivo` y la historia del pedido son inmutables (trigger).

## Plan por fases

| Fase | Contenido | Estado |
|---|---|---|
| 0 · Base | Monorepo, Docker Compose, BD, autenticación, roles/permisos, ubicaciones, auditoría, CI, PWA base, respaldos | ✅ |
| 1 · Inventario | Catálogo, presentaciones, proveedores, cadenas y sucursales de supermercado, compras con prorrateo, lotes, CPP por ubicación, transferencias, ajustes, conteos, kardex, stock físico/comprometido/disponible | ✅ |
| 2a · Pedidos | OC adjunta (foto/PDF) con carga manual, revisión, validación aritmética, equivalencias, reserva, alistado con FEFO, rentabilidad, entrega con constancia, anulación, devoluciones, duplicados, PWA con cámara y cola de subida | ✅ |
| 2b · Lectura automática | PDF con texto, OCR de fotos, plantillas por cadena, confianza, emparejamiento automático, métricas de precisión | ✅ Hipermaxi + lectura genérica; plantillas de otras cadenas cuando haya muestras |
| 3 · Reportes | Dashboard y métricas, exportación Excel/PDF | Pendiente |
| 4 · Alertas y ML | Alertas, pronóstico, reposición en dos niveles, anomalías | Pendiente |
| 5 · Finanzas | Cuentas por cobrar/pagar, gastos, contabilidad, impuestos | Futuro |
