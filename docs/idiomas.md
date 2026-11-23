# Idiomas de la interfaz (español / inglés)

- **Biblioteca:** i18next + react-i18next, con detección del idioma del navegador. La elección se
  guarda en `localStorage` (`idioma`).
- **Claves:** el propio texto en español: `t('Registrar cobro')`. El español no necesita archivo;
  `frontend/src/i18n/en.json` traduce cada frase. Variables con `{{nombre}}`:
  `t('Hay {{n}} alerta(s) crítica(s) por revisar', { n })`.
- **Formatos:** `lib/formato.ts` usa `es-BO` o `en-US` según el idioma (montos «Bs 1.234,56» /
  «Bs 1,234.56»), siempre en hora de La Paz.
- **Cambio de idioma:** `components/ConIdioma.tsx` vuelve a montar la app; la URL y los datos en
  caché se conservan.
- **Servidor:** `api()` envía `Accept-Language` con el idioma activo.

## Agregar o cambiar un texto

1. Escribir el texto en español dentro de `t('…')` en el componente.
2. Agregar su traducción en `en.json` (misma clave, mismas variables `{{x}}`).
3. `npm test` verifica que las variables coincidan.

## Pendiente (se muestra en español aunque la interfaz esté en inglés)

Estos textos los genera el **backend** y todavía no se traducen:

- Mensajes de error y de validación de la API (`ReglaNegocio`, `Conflicto`…).
- Títulos, descripciones, indicadores y columnas de los **reportes** y sus exportaciones a
  Excel/PDF.
- Títulos y mensajes de las **alertas** y los nombres de los métodos de pronóstico.
- Descripciones de los **permisos** y de los roles iniciales.

El mecanismo ya está listo del lado del cliente (`Accept-Language`). Para traducirlos, el backend
debe leer esa cabecera y elegir el texto; se recomienda hacerlo por módulo, con pruebas.

Los datos del negocio (productos, clientes, ubicaciones, números de documento) nunca se traducen.
