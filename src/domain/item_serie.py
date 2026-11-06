"""Aggregate Root ItemSerie: unidad física única con ciclo de vida (U3)."""
from __future__ import annotations

from enum import Enum

from src.domain.errores import TransicionInvalida
from src.domain.eventos import (
    RaizAgregada,
    SerieBloqueadaEvent,
    SerieEnTransitoEvent,
    SerieLiberadaEvent,
    SerieRecibidaEvent,
    SerieVendidaEvent,
)
from src.domain.valores import SKU, NumeroSerie, SucursalId


class EstadoSerie(str, Enum):
    DISPONIBLE = "DISPONIBLE"
    RESERVADO = "RESERVADO"
    RESERVADO_TRASLADO = "RESERVADO_TRASLADO"   # CU-04: apartada para un traslado
    EN_TRANSITO = "EN_TRANSITO"                 # CU-04: ya salió de la sucursal origen
    VENDIDO = "VENDIDO"
    EN_GARANTIA = "EN_GARANTIA"   # reservado para garantías (PIA)


class ItemSerie(RaizAgregada):
    def __init__(self, numero_serie: NumeroSerie, sku: SKU,
                 sucursal: SucursalId,
                 estado: EstadoSerie = EstadoSerie.DISPONIBLE) -> None:
        super().__init__()
        self.numero_serie = numero_serie
        self.sku = sku
        self.sucursal = sucursal
        self.estado = estado

    @property
    def id_agregado(self) -> str:  # type: ignore[override]
        return self.numero_serie.valor

    def _exigir(self, esperado: EstadoSerie, accion: str) -> None:
        if self.estado != esperado:
            raise TransicionInvalida(
                f"No se puede {accion} una serie en estado "
                f"{self.estado.value}")

    def bloquear_para_reserva(self) -> None:
        self._exigir(EstadoSerie.DISPONIBLE, "reservar")
        self.estado = EstadoSerie.RESERVADO
        self._emitir(SerieBloqueadaEvent, sku=self.sku.valor)

    def liberar(self) -> None:
        self._exigir(EstadoSerie.RESERVADO, "liberar")
        self.estado = EstadoSerie.DISPONIBLE
        self._emitir(SerieLiberadaEvent, motivo="apartado")

    def marcar_como_vendido(self, desde_apartado: bool = False) -> None:
        """Una serie RESERVADA sólo se vende al entregar su propio apartado."""
        esperado = (EstadoSerie.RESERVADO if desde_apartado
                    else EstadoSerie.DISPONIBLE)
        self._exigir(esperado, "vender")
        self.estado = EstadoSerie.VENDIDO
        self._emitir(SerieVendidaEvent, sku=self.sku.valor)

    # --- CU-04: traslado entre sucursales ---
    def reservar_para_traslado(self) -> None:
        self._exigir(EstadoSerie.DISPONIBLE, "trasladar")
        self.estado = EstadoSerie.RESERVADO_TRASLADO
        self._emitir(SerieBloqueadaEvent, sku=self.sku.valor, motivo="traslado")

    def despachar(self) -> None:
        self._exigir(EstadoSerie.RESERVADO_TRASLADO, "despachar")
        self.estado = EstadoSerie.EN_TRANSITO
        self._emitir(SerieEnTransitoEvent, origen=self.sucursal.valor)

    def recibir(self, destino: SucursalId) -> None:
        self._exigir(EstadoSerie.EN_TRANSITO, "recibir")
        self.estado = EstadoSerie.DISPONIBLE
        self.sucursal = destino
        self._emitir(SerieRecibidaEvent, destino=destino.valor)

    def reingresar(self) -> None:
        """Devolución autorizada: VENDIDO -> DISPONIBLE."""
        self._exigir(EstadoSerie.VENDIDO, "reingresar")
        self.estado = EstadoSerie.DISPONIBLE
        self._emitir(SerieLiberadaEvent, motivo="devolucion")
