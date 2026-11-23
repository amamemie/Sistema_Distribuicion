# DESIGN.md — Sistema visual del sistema de inventario

Fuente de verdad visual del frontend. Inspirado en la sobriedad de Linear (escalera de
superficies, bordes finos, un solo acento, tipografía con tracking negativo), adaptado a una
herramienta de trabajo diario con tema claro **y** oscuro, y a celulares de gama baja.
No se copia ninguna marca: el acento, la escena y la voz son propios.

## 1. Principios

1. **Herramienta, no vitrina.** Se usa 8 horas al día: contraste cómodo, densidad legible,
   nada que distraiga al registrar pedidos, cobros o compras.
2. **Un solo acento.** El turquesa marca la acción principal, el foco y la selección. Los
   colores de estado (éxito, aviso, peligro, info) solo comunican estado, siempre con texto o icono.
3. **La profundidad la dan las superficies**, no las sombras: lienzo → superficie → elevada,
   con bordes de 1 px. Sombra solo en lo que flota (menús, modales, toasts).
4. **El 3D es un momento, no un decorado:** una escena en el login y en la portada del inicio.
   El resto de la app se mueve con micro-interacciones cortas.
5. **Movimiento con permiso:** con `prefers-reduced-motion` todo queda quieto y visible.

## 2. Color (tokens semánticos)

Se definen como variables CSS en `src/index.css` y se usan con clases de Tailwind
(`bg-lienzo`, `text-tinta`, `border-linea`, `bg-acento`…). Los componentes nunca usan colores
crudos (`slate-500`, `#fff`).

| Token | Claro | Oscuro | Uso |
|---|---|---|---|
| `lienzo` | `#f6f7f9` | `#0c1017` | Fondo de la página |
| `superficie` | `#ffffff` | `#131922` | Tarjetas, tablas, barra lateral |
| `superficie-2` | `#f1f3f6` | `#1a212c` | Hover de filas, cabeceras de tabla, chips |
| `superficie-3` | `#e9ecf1` | `#212937` | Seleccionado, menús |
| `linea` | `#e3e7ed` | `#252e3b` | Bordes y divisores |
| `linea-fuerte` | `#8a94a3` | `#5b677a` | Bordes de campos (≥ 3:1) |
| `tinta` | `#11161d` | `#e8ecf2` | Títulos y texto principal |
| `tinta-2` | `#3f4957` | `#b4bfcd` | Texto secundario |
| `tinta-3` | `#5f6a7a` | `#8592a3` | Ayudas, metadatos (≥ 4.5:1 sobre superficie) |
| `acento` | `#0f766e` | `#2dd4bf` | Botón principal, enlaces, foco, selección |
| `acento-hover` | `#115e59` | `#5eead4` | Hover del acento |
| `sobre-acento` | `#ffffff` | `#04201d` | Texto sobre el acento |
| `acento-suave` | `#e6f4f2` | `#0f2a28` | Fondo de selección, ítem activo del menú |
| `exito` / `exito-suave` | `#166534` / `#e8f5ec` | `#4ade80` / `#10291a` | Entregado, cobrado |
| `aviso` / `aviso-suave` | `#854d0e` / `#fbf3e1` | `#facc15` / `#2b240c` | Alistado, por vencer |
| `peligro` / `peligro-suave` | `#b91c1c` / `#fcebeb` | `#f87171` / `#2e1517` | Vencido, anulado, errores |
| `info` / `info-suave` | `#1d4ed8` / `#e9effd` | `#7aa2ff` / `#141f3a` | Confirmado, información |

- **Oscuro descansado:** el lienzo es azul-grafito (`#0c1017`), nunca negro puro. **Claro sin
  blanco agresivo:** el lienzo es gris muy suave y las tarjetas blancas resaltan sobre él.
- **Gráficos:** las series siguen usando `--serie-1..8`, paleta validada para daltonismo
  (claro y oscuro). No se cambian sin volver a validarlas.
- `color-scheme` y `<meta name="theme-color">` siguen al tema (`#f6f7f9` / `#0c1017`).
- Contraste: todo texto ≥ 4.5:1, texto grande y bordes de controles ≥ 3:1, en ambos temas.

## 3. Tipografía

- **Familia:** Inter Variable, empaquetada (`@fontsource-variable/inter`), sin fuentes remotas.
  Respaldo: `system-ui`.
- **Números:** `font-variant-numeric: tabular-nums` en montos, cantidades, tablas e indicadores.

| Token | Tamaño / interlineado | Peso | Tracking | Uso |
|---|---|---|---|---|
| `display` | 36 / 1.1 (móvil 28) | 600 | −0.8 px | Saludo del inicio, título del login |
| `titulo` | 24 / 1.2 (móvil 22) | 600 | −0.4 px | Título de cada página |
| `subtitulo` | 17 / 1.35 | 600 | −0.2 px | Títulos de tarjetas y secciones |
| `cuerpo` | 14 / 1.5 | 400 | 0 | Texto general, tablas |
| `cuerpo-lg` | 16 / 1.5 | 400 | 0 | Campos en celular (evita zoom en iOS) |
| `meta` | 12 / 1.4 | 500 | 0 | Etiquetas, ayudas, fechas |
| `ceja` | 11 / 1.3 | 600 | +0.6 px, mayúsculas | Cabeceras de tabla, secciones del menú |
| `cifra` | 28 / 1.1 | 600 | −0.6 px, tabular | Indicadores (KPI) |

Títulos con `text-wrap: balance`. Puntos suspensivos con «…».

## 4. Espaciado, radios y elevación

- **Base 4 px.** Escala: 4 · 8 · 12 · 16 · 20 · 24 · 32 · 48.
- Tarjeta: padding 20 px (móvil 16). Entre tarjetas: 12–16 px. Entre secciones: 24–32 px.
- **Radios:** `sm` 6 px (insignias, chips) · `md` 8 px (botones, campos) · `lg` 12 px
  (tarjetas, tablas) · `xl` 16 px (modales, portada) · `full` (avatares, interruptores).
- **Elevación:**

| Nivel | Tratamiento | Uso |
|---|---|---|
| 0 | `lienzo` | Fondo |
| 1 | `superficie` + borde `linea` | Tarjetas, tablas |
| 2 | `superficie` + borde + sombra `0 1px 2px rgb(0 0 0 / .04), 0 4px 12px rgb(0 0 0 / .04)` | Tarjeta al pasar el mouse |
| 3 | `superficie` + borde + sombra `0 12px 32px rgb(0 0 0 / .14)` (oscuro `.45`) | Menús, modales, toasts |

En oscuro se agrega un brillo de 1 px en el borde superior de lo elevado
(`inset 0 1px 0 rgb(255 255 255 / .04)`).

## 5. Movimiento

| Token | Duración | Curva | Uso |
|---|---|---|---|
| `rapido` | 120 ms | `cubic-bezier(.2,0,0,1)` | Hover, press, foco |
| `base` | 200 ms | `cubic-bezier(.2,0,0,1)` | Cambio de página, menús, tabs |
| `entrada` | 320 ms | `cubic-bezier(.16,1,.3,1)` | Modales, portada, aparición escalonada |

- **Hover:** tarjetas enlazadas suben 2 px y pasan a elevación 2; botones aclaran/oscurecen y
  bajan 1 px al presionar.
- **Cambio de página:** fundido + desplazamiento de 6 px, ≤ 200 ms.
- **Indicadores:** las cifras cuentan hasta su valor (≤ 600 ms) al aparecer por primera vez.
- **Listas:** aparición escalonada (30 ms por fila, máximo 8 filas) solo en la primera carga.
- **Modales y menús:** entran escalando de 0.97 a 1 con profundidad (`translateZ`/sombra).
- **Profundidad en tarjetas de indicadores (opcional, a confirmar):** inclinación 3D de hasta
  4° que sigue al mouse, solo con puntero fino; nunca en formularios ni tablas.
- Solo se animan `transform` y `opacity`; nunca `transition: all`.
- **`prefers-reduced-motion`:** sin escena 3D (imagen fija), sin conteo ni escalonado, cambios
  instantáneos.

## 6. Escena 3D

- **Dónde:** el panel lateral del login (escritorio) y el fondo de la portada del inicio. En
  ningún otro lugar.
- **Qué:** paquetes de la distribuidora (cajas con cinta, bolsas) flotando en una red de rutas
  que une depósitos y sucursales. Pulsos de luz turquesa viajan por las rutas: el inventario en
  movimiento. Materiales mate, colores del sistema.
- **Cómo:** `@react-three/fiber` + `@react-three/drei`, en un chunk diferido que se carga solo en
  esas dos pantallas. Tope de 30 fps, píxeles a 1.5× máximo, pausa cuando la pestaña no se ve
  o la escena sale de la pantalla.
- **Respaldo:** sin WebGL, con dispositivo lento (`hardwareConcurrency ≤ 4` o `deviceMemory ≤ 2`)
  o con movimiento reducido, se muestra una imagen fija (SVG isométrico) de la misma escena.
- **Celular:** en el login, la escena pasa a ser una franja superior baja; en el inicio se usa la
  imagen fija.

## 7. Componentes

- **Botón:** primario (acento), secundario (superficie + borde), fantasma, peligro. Alto 40 px
  (44 en táctil), radio `md`, texto `cuerpo` 500. Estado de carga con spinner y texto «Guardando…».
- **Campo:** superficie, borde `linea-fuerte`, radio `md`, alto 40 px (44 táctil), foco con anillo
  de 3 px `acento` al 30 %. Error en `peligro` debajo del campo. `<select>` con fondo y color explícitos.
- **Tarjeta:** elevación 1, radio `lg`, padding 20 px.
- **Indicador (KPI):** etiqueta `meta`, cifra `cifra`, variación con flecha e insignia de color
  + texto, icono en un cuadro `acento-suave`.
- **Tabla:** cabecera fija en `superficie-2` con `ceja`; filas de 48 px; hover `superficie-2`;
  números a la derecha y tabulares; en celular se convierte en lista de tarjetas cuando es ancha.
- **Insignia de estado:** fondo `*-suave`, texto del estado, punto de color + palabra.
- **Barra lateral:** `superficie`, ítem activo con fondo `acento-suave`, texto `acento` y barra de
  3 px a la izquierda; secciones con `ceja`.
- **Encabezado:** 56 px, `superficie` translúcida con desenfoque; a la derecha: idioma, tema,
  alertas y usuario (avatar con iniciales y menú).
- **Estados vacíos:** icono en círculo `superficie-2`, una frase y una acción.
- **Cargando:** esqueletos con brillo suave (estático con movimiento reducido).
- **Toasts:** abajo a la derecha (arriba en celular), `aria-live="polite"`.

## 8. Iconografía

Lucide, trazo 1.75, 16–20 px, del color del texto. Decorativos con `aria-hidden`; botones
solo-icono con `aria-label`.

## 9. Idiomas y formatos

- Español (por defecto) e inglés. Selector en el encabezado y en el login; se recuerda.
- Montos: «Bs 1.234,56» (es-BO) / «Bs 1,234.56» (en-US). Fechas con `Intl` en `America/La_Paz`.
- Nombres de productos, clientes y números de documento no se traducen (`translate="no"`).

## 10. Accesibilidad

Enlace «Saltar al contenido», foco visible siempre (`:focus-visible`), objetivos táctiles de
44 px, encabezados en orden, etiquetas visibles en todos los campos, modales con
`overscroll-behavior: contain`, sin bloquear el zoom.

## 11. Sí / No

- **Sí:** un acento escaso; superficies para jerarquía; cifras tabulares; estados con texto.
- **No:** violeta o lila; gradientes atmosféricos en pantallas de trabajo; sombras pesadas;
  más de un botón primario por vista; animaciones que bloqueen el trabajo; escena 3D fuera del
  login y del inicio.
