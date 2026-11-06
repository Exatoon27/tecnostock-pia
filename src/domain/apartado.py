"""Aggregate Root Apartado: anticipo >= 20%, vigencia 30 días, penalización 10%.

La penalización se calcula AQUÍ (decisión U3: no en la capa de aplicación).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum

from src.domain.errores import DatosInvalidos, TransicionInvalida
from src.domain.eventos import (
    AbonoRegistradoEvent,
    ApartadoCreadoEvent,
    ApartadoEntregadoEvent,
    ApartadoLiquidadoEvent,
    ApartadoVencidoEvent,
    AvisoVencimientoEvent,
    RaizAgregada,
)
from src.domain.valores import (
    MontoMonetario,
    NumeroSerie,
    PorcentajeAnticipo,
    SucursalId,
)

VIGENCIA_DIAS = 30
DIAS_DE_AVISO = (5, 2)       # BRD: aviso a 5 y a 2 días, por SMS y correo
PENALIZACION = Decimal("0.10")


class EstadoApartado(str, Enum):
    ACTIVO = "ACTIVO"
    LIQUIDADO = "LIQUIDADO"
    VENCIDO = "VENCIDO"
    ENTREGADO = "ENTREGADO"


@dataclass(frozen=True)
class Abono:
    monto: MontoMonetario
    fecha: date


class Apartado(RaizAgregada):
    def __init__(self, folio: str, cliente_id: str, numero_serie: NumeroSerie,
                 sucursal: SucursalId, total: MontoMonetario,
                 fecha_creacion: date) -> None:
        super().__init__()
        self.folio = folio
        self.cliente_id = cliente_id
        self.numero_serie = numero_serie
        self.sucursal = sucursal
        self.total = total
        self.fecha_creacion = fecha_creacion
        self.abonos: list[Abono] = []
        self.estado = EstadoApartado.ACTIVO
        self.saldo_a_favor: MontoMonetario | None = None
        self.avisos: set[int] = set()       # avisos ya enviados (5 y/o 2 días)

    @property
    def id_agregado(self) -> str:  # type: ignore[override]
        return self.folio

    @classmethod
    def crear(cls, folio: str, cliente_id: str, numero_serie: NumeroSerie,
              sucursal: SucursalId, total: MontoMonetario,
              anticipo: MontoMonetario, hoy: date) -> Apartado:
        PorcentajeAnticipo.de(anticipo, total)       # invariante del 20%
        ap = cls(folio, cliente_id, numero_serie, sucursal, total, hoy)
        ap.abonos.append(Abono(anticipo, hoy))
        ap._emitir(ApartadoCreadoEvent, cliente=cliente_id,
                   serie=numero_serie.valor, anticipo=str(anticipo))
        if ap.saldo.cantidad == 0:
            ap._liquidar()
        return ap

    # --- consultas ---
    @property
    def fecha_limite(self) -> date:
        return self.fecha_creacion + timedelta(days=VIGENCIA_DIAS)

    def dias_para_vencer(self, hoy: date) -> int:
        return (self.fecha_limite - hoy).days

    def aviso_pendiente(self, hoy: date) -> int | None:
        """Días del aviso que toca enviar hoy (5 o 2), o None. Sólo apartados ACTIVOS:
        quien liquida antes deja de recibir avisos."""
        dias = self.dias_para_vencer(hoy)
        if (self.estado == EstadoApartado.ACTIVO and dias in DIAS_DE_AVISO
                and dias not in self.avisos):
            return dias
        return None

    @property
    def pagado(self) -> MontoMonetario:
        total = MontoMonetario(Decimal("0.00"))
        for a in self.abonos:
            total = total.sumar(a.monto)
        return total

    @property
    def saldo(self) -> MontoMonetario:
        return self.total.restar(self.pagado)

    # --- comandos ---
    def registrar_abono(self, monto: MontoMonetario, hoy: date) -> None:
        if self.estado != EstadoApartado.ACTIVO:
            raise TransicionInvalida(
                f"No se admiten abonos en un apartado {self.estado.value}")
        if hoy > self.fecha_limite:
            raise TransicionInvalida(
                "El plazo de 30 días expiró; el apartado está por vencer")
        if monto.cantidad <= 0:
            raise DatosInvalidos("El abono debe ser mayor a 0")
        if monto.cantidad > self.saldo.cantidad:
            raise DatosInvalidos(
                f"El abono {monto} excede el saldo pendiente {self.saldo}")
        self.abonos.append(Abono(monto, hoy))
        self._emitir(AbonoRegistradoEvent, monto=str(monto),
                     saldo=str(self.saldo))
        if self.saldo.cantidad == 0:
            self._liquidar()

    def evaluar_vencimiento(self, hoy: date) -> bool:
        """True si este llamado venció el apartado (idempotente)."""
        if self.estado != EstadoApartado.ACTIVO or hoy <= self.fecha_limite:
            return False
        penalizacion = self.pagado.por(PENALIZACION)
        self.saldo_a_favor = self.pagado.restar(penalizacion)
        self.estado = EstadoApartado.VENCIDO
        self._emitir(ApartadoVencidoEvent, cliente=self.cliente_id,
                     penalizacion=str(penalizacion),
                     saldo_a_favor=str(self.saldo_a_favor))
        return True

    def registrar_aviso(self, dias: int, hoy: date) -> None:
        self.avisos.add(dias)
        self._emitir(AvisoVencimientoEvent, cliente=self.cliente_id, dias=dias,
                     saldo=str(self.saldo), fecha_limite=self.fecha_limite.isoformat())

    def entregar(self) -> None:
        if self.estado != EstadoApartado.LIQUIDADO:
            raise TransicionInvalida(
                f"Sólo se entrega un apartado LIQUIDADO (está "
                f"{self.estado.value})")
        self.estado = EstadoApartado.ENTREGADO
        self._emitir(ApartadoEntregadoEvent, serie=self.numero_serie.valor)

    def _liquidar(self) -> None:
        self.estado = EstadoApartado.LIQUIDADO
        self._emitir(ApartadoLiquidadoEvent, total=str(self.total))
