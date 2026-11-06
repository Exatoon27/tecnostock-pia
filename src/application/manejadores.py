"""Reacciones a Domain Events, desacopladas del dominio (hallazgo SOLID-S, U3)."""
from __future__ import annotations

from src.domain.eventos import EventoDominio


class AvisoVencimientoEventHandler:
    """Simula el SMS y el correo de aviso a 5 y 2 días del vencimiento."""

    def __init__(self) -> None:
        self.mensajes: list[str] = []

    def __call__(self, evento: EventoDominio) -> None:
        d = evento.datos
        self.mensajes.append(
            f"SMS y correo a {d['cliente']}: su apartado {evento.agregado_id} vence en "
            f"{d['dias']} días ({d['fecha_limite']}); saldo pendiente {d['saldo']} MXN")


class ApartadoVencidoEventHandler:
    """Simula el aviso SMS/correo al cliente cuando un apartado vence."""

    def __init__(self) -> None:
        self.notificaciones: list[str] = []

    def __call__(self, evento: EventoDominio) -> None:
        self.notificaciones.append(
            f"SMS/correo a {evento.datos['cliente']}: apartado "
            f"{evento.agregado_id} vencido; saldo a favor "
            f"{evento.datos['saldo_a_favor']} MXN")
