"""Lectura automática de la OC de un pedido (Fase 2b).

1. Al subir la OC a un borrador vacío se crea una `Lectura` PENDIENTE y se encola.
2. El worker la procesa: OCR local → plantilla → `OCLeida` → completa el borrador (cadena,
   sucursal del supermercado, número, fechas, total y líneas con su producto si ya se conoce).
3. El encargado revisa y confirma como siempre. Al confirmar se guardan las correcciones: así
   se mide la precisión por formato y se sabe qué ajustar.

Nunca mueve inventario: solo llena el borrador.
"""

import logging
import time
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.tiempo import ahora, hoy
from app.modules.clientes.models import Cadena
from app.modules.documentos import servicios as documentos
from app.modules.documentos.lectura.interpretar import interpretar
from app.modules.documentos.lectura.modelos import OCLeida
from app.modules.documentos.lectura.ocr import ExtractorDocumento, ExtractorLocal
from app.modules.identidad import auditoria
from app.modules.identidad.contexto import Contexto
from app.modules.identidad.models import Usuario
from app.modules.pedidos import dominio
from app.modules.pedidos.models import (
    EstadoLectura,
    EstadoPedido,
    Lectura,
    Pedido,
    PedidoEvento,
    PedidoLinea,
)

logger = logging.getLogger(__name__)
_SIMILITUD_SUCURSAL = 0.6


# ================================================================ solicitar y encolar


def ultima(db: Session, pedido_id: uuid.UUID) -> Lectura | None:
    return db.scalars(
        select(Lectura).where(Lectura.pedido_id == pedido_id).order_by(Lectura.created_at.desc())
    ).first()


def solicitar(db: Session, ctx: Contexto, pedido: Pedido, *, reemplazar: bool) -> Lectura | None:
    """Crea la lectura (sin commit). Devuelve None si ya hay una en curso."""
    previa = ultima(db, pedido.id)
    if previa and previa.estado in (EstadoLectura.PENDIENTE, EstadoLectura.PROCESANDO):
        if reemplazar:
            previa.reemplazar = True
        return None
    lectura = Lectura(
        empresa_id=ctx.empresa_id,
        pedido_id=pedido.id,
        reemplazar=reemplazar,
        solicitado_por_id=ctx.usuario.id,
    )
    db.add(lectura)
    db.flush()
    return lectura


def debe_leer_al_subir(db: Session, pedido: Pedido) -> bool:
    """Se lee sola la OC de un borrador todavía vacío."""
    return get_settings().lectura_automatica and not pedido.lineas


def encolar(lectura_id: uuid.UUID) -> None:
    """Envía la lectura al worker (llamar después del commit)."""
    from app.workers.celery_app import celery_app

    try:
        celery_app.send_task("pedidos.leer_oc", args=[str(lectura_id)])
    except Exception:  # Redis caído: queda registrada como fallida y se puede reintentar
        logger.exception("No se pudo encolar la lectura %s", lectura_id)
        with SessionLocal() as db:
            lectura = db.get(Lectura, lectura_id)
            if lectura and lectura.estado == EstadoLectura.PENDIENTE:
                lectura.estado = EstadoLectura.FALLIDA
                lectura.error = "No se pudo iniciar la lectura automática. Intente de nuevo."
                db.commit()


# ================================================================ procesar (worker)


def procesar(
    lectura_id: uuid.UUID,
    extractor: ExtractorDocumento | None = None,
    sesion: Callable[[], AbstractContextManager[Session]] = SessionLocal,
) -> None:
    """Cuerpo de la tarea: lee los documentos del pedido y completa el borrador."""
    extractor = extractor or ExtractorLocal()
    with sesion() as db:
        lectura = db.get(Lectura, lectura_id)
        if lectura is None or lectura.estado != EstadoLectura.PENDIENTE:
            return
        lectura.estado = EstadoLectura.PROCESANDO
        lectura.motor = extractor.nombre
        db.commit()
        inicio = time.monotonic()
        try:
            pedido = db.get(Pedido, lectura.pedido_id)
            assert pedido is not None
            archivos = [
                (documentos.ruta_absoluta(d.archivo).read_bytes(), d.archivo.tipo_mime)
                for d in pedido.documentos
                if d.activo
            ]
            if not archivos:
                raise ValueError("El pedido no tiene documentos.")
            palabras = extractor.extraer(archivos)
            oc = interpretar(palabras)
            lectura.palabras = [
                [
                    p.texto,
                    round(p.x0),
                    round(p.y0),
                    round(p.x1),
                    round(p.y1),
                    round(p.confianza, 3),
                    p.pagina,
                ]
                for p in palabras
            ]
            lectura.resultado = jsonable_encoder(oc.model_dump())
            lectura.plantilla = oc.plantilla
            lectura.confianza = Decimal(str(round(oc.confianza_global * 100, 2)))
            lectura.aritmetica_ok = oc.aritmetica_ok
            lectura.estado = EstadoLectura.COMPLETADA
            texto = " ".join(p.texto for p in palabras)
            _aplicar_si_corresponde(db, lectura, oc, texto)
        except Exception as error:
            db.rollback()
            logger.exception("Falló la lectura %s", lectura_id)
            lectura = db.get(Lectura, lectura_id)
            assert lectura is not None
            lectura.estado = EstadoLectura.FALLIDA
            lectura.error = (
                "No se pudo leer el documento. Cargue los datos a mano. "
                f"({type(error).__name__}: {error})"
            )[:500]
        lectura.duracion_ms = int((time.monotonic() - inicio) * 1000)
        lectura.terminada_at = ahora()
        db.commit()


def _aplicar_si_corresponde(db: Session, lectura: Lectura, oc: OCLeida, texto: str) -> None:
    pedido = db.scalars(
        select(Pedido).where(Pedido.id == lectura.pedido_id).with_for_update(of=Pedido)
    ).one()
    if pedido.estado != EstadoPedido.BORRADOR or (pedido.lineas and not lectura.reemplazar):
        return  # alguien ya cargó datos a mano: el resultado queda disponible, sin pisarlos
    usuario = db.get(Usuario, lectura.solicitado_por_id)
    assert usuario is not None
    ctx = Contexto(usuario=usuario, ip=None, user_agent="lectura automática")
    aplicar(db, ctx, pedido, oc, texto)
    lectura.aplicada = True


# ================================================================ aplicar al borrador


def _normalizar(texto: str | None) -> str:
    return dominio.normalizar_descripcion(texto) or ""


def _cadena(db: Session, ctx: Contexto, oc: OCLeida, texto: str) -> Cadena | None:
    cadenas = list(
        db.scalars(
            select(Cadena).where(Cadena.empresa_id == ctx.empresa_id, Cadena.activo.is_(True))
        )
    )
    buscado = _normalizar(oc.cadena_texto)
    for c in cadenas:
        if buscado and _normalizar(c.nombre) == buscado:
            return c
    texto_n = _normalizar(texto)
    encontradas = [c for c in cadenas if _normalizar(c.nombre) and _normalizar(c.nombre) in texto_n]
    return encontradas[0] if len(encontradas) == 1 else None


def _sucursal(cadena: Cadena, destino: str | None) -> tuple[uuid.UUID | None, float]:
    """Sucursal del supermercado más parecida al texto «Enviar a…» de la OC."""
    if not destino:
        return None, 0.0
    objetivo = _normalizar(destino)
    mejor, puntaje = None, 0.0
    for s in cadena.sucursales:
        if not s.activo:
            continue
        nombre = _normalizar(s.nombre)
        valor = max(
            SequenceMatcher(None, objetivo, nombre).ratio(),
            # "HIPERMAXI COTA COTA LA PAZ" contiene "hipermaxi cota cota"
            0.95 if nombre and nombre in objetivo else 0.0,
        )
        if valor > puntaje:
            mejor, puntaje = s.id, valor
    return (mejor, round(puntaje, 3)) if puntaje >= _SIMILITUD_SUCURSAL else (None, 0.0)


def aplicar(db: Session, ctx: Contexto, pedido: Pedido, oc: OCLeida, texto: str = "") -> None:
    """Completa el borrador con lo leído (sin commit). Los productos solo se asignan solos
    si hay una equivalencia aprendida o coincide el código; si no, quedan para elegir."""
    from app.modules.pedidos import servicios  # evita importación circular

    confianza: dict[str, Any] = dict(oc.confianza)
    cadena = _cadena(db, ctx, oc, texto)
    pedido.cadena_id = cadena.id if cadena else None
    pedido.sucursal_cliente_id = None
    if cadena:
        pedido.sucursal_cliente_id, confianza["sucursal_cliente"] = _sucursal(
            cadena, oc.destino_texto
        )
    avisos = list(oc.avisos)
    numero = oc.numero_oc
    if numero and cadena:
        otro = servicios._duplicado(db, ctx, pedido, cadena_id=cadena.id, numero_oc=numero)
        if otro:
            avisos.append(servicios._mensaje_duplicado(otro))
            numero = None  # no se puede repetir: el usuario decide
    pedido.numero_oc = numero
    pedido.fecha_oc = oc.fecha_oc if oc.fecha_oc and oc.fecha_oc <= hoy() else None
    pedido.fecha_entrega = oc.fecha_entrega
    pedido.emisor = (oc.emisor or "")[:120] or None
    pedido.total_oc = oc.total
    if oc.numero_documento:
        # El pedido se identifica por la O/C; el N.º de la nota de recepción queda anotado (D-19).
        nota = f"Nota de recepción N.º {oc.numero_documento}"
        previas = pedido.observaciones or ""
        if nota not in previas:
            pedido.observaciones = (f"{nota} · {previas}" if previas else nota)[:500]
    confianza["avisos"] = avisos
    if oc.destino_texto:
        confianza["destino_texto"] = oc.destino_texto[:120]
    pedido.confianza = confianza

    lineas = []
    for orden, leida in enumerate(oc.lineas, start=1):
        producto_id = None
        for codigo in (leida.codigo, leida.codigo_alterno, None):
            sugeridas = servicios.sugerencias(
                db,
                ctx,
                cadena_id=pedido.cadena_id,
                codigo=codigo,
                descripcion=leida.descripcion if codigo is None else None,
                limite=1,
            )
            if sugeridas and sugeridas[0].fuente in ("equivalencia", "codigo"):
                producto_id = sugeridas[0].producto.id
                break
            if codigo is None:
                break
        lineas.append(
            PedidoLinea(
                orden=orden,
                codigo_cliente=(leida.codigo or leida.codigo_alterno or "")[:60] or None,
                descripcion_cliente=leida.descripcion[:300],
                producto_id=producto_id,
                cantidad_oc=leida.cantidad if leida.cantidad > 0 else Decimal(1),
                precio_oc=max(leida.precio, Decimal(0)),
                total_linea_oc=leida.total,
                cantidad_confirmada=leida.cantidad if leida.cantidad > 0 else Decimal(1),
                confianza=leida.confianza,
            )
        )
    pedido.lineas = lineas
    db.add(
        PedidoEvento(
            pedido_id=pedido.id,
            tipo="LEIDO",
            usuario_id=ctx.usuario.id,
            detalle=jsonable_encoder(
                {"plantilla": oc.plantilla, "lineas": len(lineas), "cuentas_ok": oc.aritmetica_ok}
            ),
        )
    )
    auditoria.registrar_ctx(
        db,
        ctx,
        accion="pedido.lectura_automatica",
        entidad="pedido",
        entidad_id=pedido.id,
        despues={
            "plantilla": oc.plantilla,
            "numero_oc": pedido.numero_oc,
            "lineas": len(lineas),
            "con_producto": sum(1 for x in lineas if x.producto_id),
        },
    )


# ================================================================ correcciones (al confirmar)


def registrar_correcciones(db: Session, pedido: Pedido) -> None:
    """Compara lo leído con lo confirmado: qué campos corrigió el usuario (sin commit)."""
    lectura = ultima(db, pedido.id)
    if lectura is None or not lectura.aplicada or not lectura.resultado:
        return
    oc = OCLeida.model_validate(lectura.resultado)
    cambios: list[dict[str, Any]] = []
    total = iguales = 0

    def comparar(campo: str, leido: Any, final: Any, linea: int | None = None) -> None:
        nonlocal total, iguales
        total += 1
        if leido == final:
            iguales += 1
        else:
            cambios.append({"campo": campo, "linea": linea, "leido": leido, "final": final})

    comparar("numero_oc", oc.numero_oc, pedido.numero_oc)
    comparar("fecha_oc", oc.fecha_oc, pedido.fecha_oc)
    comparar("total", oc.total, pedido.total_oc)
    for i in range(max(len(oc.lineas), len(pedido.lineas))):
        leida = oc.lineas[i] if i < len(oc.lineas) else None
        final = pedido.lineas[i] if i < len(pedido.lineas) else None
        comparar(
            "cantidad",
            leida.cantidad if leida else None,
            final.cantidad_oc if final else None,
            i + 1,
        )
        comparar(
            "precio", leida.precio if leida else None, final.precio_oc if final else None, i + 1
        )
        comparar(
            "total_linea",
            leida.total if leida else None,
            final.total_linea_oc if final else None,
            i + 1,
        )
    lectura.correcciones = jsonable_encoder(
        {"cambios": cambios, "campos": total, "sin_cambio": iguales}
    )
    lectura.precision = Decimal(str(round(iguales * 100 / total, 2))) if total else None
