# ADR 0003 — Lectura de órdenes de compra sin costo por uso

- **Estado:** aceptada e implementada en la Fase 2b (2026-11-14), con 7 OC reales de Hipermaxi.

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

## Implementación (Fase 2b)

- **Motor:** RapidOCR (los mismos modelos PP-OCR de PaddleOCR exportados a ONNX, en CPU). Se
  prefirió a PaddleOCR directo por ser mucho más liviano de instalar (sin paddlepaddle) y traer
  los modelos dentro del paquete: no descarga nada al ejecutarse.
- **Privacidad:** la telemetría de ONNX Runtime se apaga y los contenedores `backend` y `worker`
  están en una red Docker interna **sin salida a internet**; solo `web` (Caddy) y `db` (puerto
  local para respaldos) tienen red externa.
- **Orientación:** se prueban las rotaciones en una versión reducida y se elige la más legible
  (las fotos llegan a menudo de costado); se tolera inclinación leve al agrupar renglones.
- **Plantillas:** `hipermaxi` (Documento de Aviso de Despacho) y `generica` (cualquier formato:
  toma como línea todo renglón donde cantidad x precio = total).
- **Resultados con las 6 OC de noviembre (fotos tal como llegaron):**
  - plantilla Hipermaxi: 99,1 % de los campos correctos; cantidades, precios, totales, número,
    fechas, destino y total de las 6 OC sin errores; 3 códigos mal leídos (el producto igual se
    reconoce por la descripción). Unos 10 s por página en el equipo de desarrollo.
  - lectura genérica (como si el formato fuera desconocido): número, fecha, destino y total
    correctos en las 6; ~86 % de cantidades, precios y totales de línea.
- **Aprendizaje:** al confirmar se guardan las correcciones y la precisión de cada lectura
  (`lectura_oc`), y las equivalencias de productos por cadena (Fase 2a).
