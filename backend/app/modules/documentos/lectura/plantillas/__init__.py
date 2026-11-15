"""Plantillas de interpretación por cadena. Para agregar una cadena nueva: crear su módulo con
una clase que implemente `Plantilla` y registrarla en `PLANTILLAS`."""

from app.modules.documentos.lectura.plantillas.base import Plantilla
from app.modules.documentos.lectura.plantillas.generica import PlantillaGenerica
from app.modules.documentos.lectura.plantillas.hipermaxi import PlantillaHipermaxi

PLANTILLAS: list[Plantilla] = [PlantillaHipermaxi()]
GENERICA = PlantillaGenerica()

__all__ = ["GENERICA", "PLANTILLAS", "Plantilla"]
