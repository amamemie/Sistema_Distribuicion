# ADR 0003 — Lectura de órdenes de compra sin costo por uso

- **Estado:** aceptada en principio (2026-11-14); el diseño detallado se hace en la Fase 2b con
  OC reales del cliente.

## Contexto

La especificación sugería un modelo multimodal de pago. El cliente exige costo mensual cero (D-08).
Volumen bajo (≤10 OC/día), pocas cadenas, cada una con su propio formato. Hay OC en PDF con
texto, PDF escaneados y fotos de papel.

## Decisión

Canal de lectura local, gratuito, detrás de la interfaz `DocumentExtractor`:

1. **PDF con texto** → `pdfplumber`/PyMuPDF extraen texto y tablas (exacto y gratis).
2. **Foto o PDF escaneado** → preprocesamiento con OpenCV (rotación, perspectiva, contraste) →
   **PaddleOCR** en CPU (texto + posiciones).
3. **Detección de la cadena** (palabras clave, NIT, disposición) y **plantilla por cadena**
   (columnas, patrones) que convierte el texto en JSON validado con Pydantic.
4. **Validaciones aritméticas** (cantidad × precio = total de línea; suma = total) como señal
   de calidad, más la confianza del OCR.
5. **Emparejamiento** de productos: equivalencia conocida → código → búsqueda difusa
   (`pg_trgm`/rapidfuzz) → sugerencias. Cada corrección alimenta la tabla de equivalencias.
6. Pantalla de revisión obligatoria: **nunca se mueve inventario sin confirmación humana**.

Un extractor en la nube con nivel gratuito podrá añadirse más adelante como opción secundaria,
**desactivado por defecto** (los datos no salen del servidor salvo que el dueño lo active).

## Consecuencias

- En PDF con texto, la lectura será casi perfecta; en fotos, buena pero con errores que corrige
  el encargado.
- Cada cadena nueva requiere una plantilla (trabajo de configuración, no de programación mayor).
- Las correcciones guardadas permiten medir la precisión y, más adelante, entrenar un modelo
  propio pequeño para clasificar columnas.
- La Fase 2a (pedidos con carga manual sobre la OC adjunta) no depende de este componente.
