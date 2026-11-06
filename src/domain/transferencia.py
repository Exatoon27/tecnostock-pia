"""Aggregate Root Transferencia (CU-04): traslado de una pieza entre sucursales.

PENDIENTE_DESPACHO --despachar--> EN_TRANSITO --recibir--> RECIBIDA
Cada paso exige escanear la serie de la pieza (BRD, levantamiento p.4).
"""
from __future__ import annotations

from datetime import date
from enum import Enum

from src.domain.errores import ReglaNegocioViolada, TransicionInvalida
from src.domain.eventos import (
    RaizAgregada,
    TransferenciaDespachadaEvent,
    TransferenciaRecibidaEvent,
    TransferenciaSolicitadaEvent,
)
from src.domain.valores import NumeroSerie, SucursalId


class EstadoTransferencia(str, Enum):
    PENDIENTE_DESPACHO = "PENDIENTE_DESPACHO"
    EN_TRANSITO = "EN_TRANSITO"
    RECIBIDA = "RECIBIDA"


ACTIVAS = (EstadoTransferencia.PENDIENTE_DESPACHO, EstadoTransferencia.EN_TRANSITO)


class Transferencia(RaizAgregada):
    def __init__(self, folio: str, numero_serie: NumeroSerie, origen: SucursalId,
                 destino: SucursalId, fecha_solicitud: date) -> None:
        super().__init__()
        self.folio = folio
        self.numero_serie = numero_serie
        self.origen = origen
        self.destino = destino
        self.fecha_solicitud = fecha_solicitud
        self.estado = EstadoTransferencia.PENDIENTE_DESPACHO
        self.guia: str | None = None

    @property
    def id_agregado(self) -> str:  # type: ignore[override]
        return self.folio

    @classmethod
    def solicitar(cls, folio: str, numero_serie: NumeroSerie, origen: SucursalId,
                  destino: SucursalId, hoy: date) -> Transferencia:
        if origen == destino:
            raise ReglaNegocioViolada(
                "La sucursal destino debe ser distinta a la de origen")
        t = cls(folio, numero_serie, origen, destino, hoy)
        t._emitir(TransferenciaSolicitadaEvent, serie=numero_serie.valor,
                  origen=origen.valor, destino=destino.valor)
        return t

    def _exigir(self, esperado: EstadoTransferencia, accion: str) -> None:
        if self.estado != esperado:
            raise TransicionInvalida(
                f"No se puede {accion} un traslado en estado {self.estado.value}")

    def _validar_escaneo(self, escaneada: NumeroSerie) -> None:
        if escaneada != self.numero_serie:
            raise ReglaNegocioViolada(
                f"La serie escaneada no corresponde al traslado {self.folio}")

    def despachar(self, escaneada: NumeroSerie) -> None:
        self._exigir(EstadoTransferencia.PENDIENTE_DESPACHO, "despachar")
        self._validar_escaneo(escaneada)
        self.guia = "GT-" + self.folio.split("-")[-1]
        self.estado = EstadoTransferencia.EN_TRANSITO
        self._emitir(TransferenciaDespachadaEvent, guia=self.guia)

    def recibir(self, escaneada: NumeroSerie, sucursal: SucursalId) -> None:
        self._exigir(EstadoTransferencia.EN_TRANSITO, "recibir")
        self._validar_escaneo(escaneada)
        if sucursal != self.destino:
            raise ReglaNegocioViolada(
                f"La pieza debe recibirse en la sucursal destino {self.destino.valor}")
        self.estado = EstadoTransferencia.RECIBIDA
        self._emitir(TransferenciaRecibidaEvent, destino=self.destino.valor)
