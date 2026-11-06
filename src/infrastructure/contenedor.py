"""Raíz de composición: arma servicios + infraestructura (memoria o SQL)."""
from __future__ import annotations

import os
import weakref
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from src.application.manejadores import (
    ApartadoVencidoEventHandler,
    AvisoVencimientoEventHandler,
)
from src.application.servicios import (
    ApartadoApplicationService,
    ConsultarPanelQueryHandler,
    ConsultarStockGlobalQueryHandler,
    DevolucionApplicationService,
    TransferenciaApplicationService,
    VentaApplicationService,
)
from src.domain.devolucion import PoliticaDevolucionDomainService
from src.domain.puertos import IPasarelaPagos
from src.domain.repositorios import IUnitOfWork
from src.infrastructure.carga_csv import cargar_almacen
from src.infrastructure.memoria import (
    Almacen,
    BusEventos,
    SupervisorAuthMemoria,
    UnidadDeTrabajoMemoria,
)
from src.infrastructure.pasarela import PasarelaSimulada
from src.infrastructure.sql import (
    ClienteRow,
    SupervisorAuthSql,
    UnidadDeTrabajoSql,
    crear_engine,
    sembrar,
)


@dataclass
class Contenedor:
    bus: BusEventos
    uow_factory: Callable[[], IUnitOfWork]
    apartados: ApartadoApplicationService
    ventas: VentaApplicationService
    devoluciones: DevolucionApplicationService
    transferencias: TransferenciaApplicationService
    stock: ConsultarStockGlobalQueryHandler
    panel: ConsultarPanelQueryHandler
    notificaciones: ApartadoVencidoEventHandler
    avisos_enviados: AvisoVencimientoEventHandler
    almacen: Almacen | None = None          # sólo con persistencia en memoria
    sesiones: sessionmaker | None = None    # sólo con SQL


def _armar(bus, fabrica, politica, pasarela, **extra) -> Contenedor:
    notif = ApartadoVencidoEventHandler()
    bus.suscribir("ApartadoVencidoEvent", notif)
    avisos = AvisoVencimientoEventHandler()
    bus.suscribir("AvisoVencimientoEvent", avisos)
    return Contenedor(
        bus, fabrica, ApartadoApplicationService(fabrica),
        VentaApplicationService(fabrica, pasarela or PasarelaSimulada()),
        DevolucionApplicationService(fabrica, politica),
        TransferenciaApplicationService(fabrica),
        ConsultarStockGlobalQueryHandler(fabrica),
        ConsultarPanelQueryHandler(fabrica), notif, avisos, **extra)


def construir(almacen: Almacen | None = None,
              pasarela: IPasarelaPagos | None = None) -> Contenedor:
    """Persistencia en memoria (pruebas rápidas y demo)."""
    almacen = almacen or cargar_almacen()
    bus = BusEventos()
    uow = UnidadDeTrabajoMemoria(almacen, bus)
    politica = PoliticaDevolucionDomainService(SupervisorAuthMemoria(almacen))
    return _armar(bus, lambda: uow, politica, pasarela, almacen=almacen)


def construir_sql(url: str = "sqlite+pysqlite:///:memory:",
                  pasarela: IPasarelaPagos | None = None,
                  sembrar_datos: bool = True) -> Contenedor:
    """Persistencia SQLAlchemy. Siembra los CSV sólo si la base está vacía."""
    engine = crear_engine(url)
    sesiones = sessionmaker(engine, expire_on_commit=False)
    if sembrar_datos:
        with sesiones() as s:
            vacia = not s.scalar(select(func.count()).select_from(ClienteRow))
        if vacia:
            sembrar(sesiones, cargar_almacen())
    bus = BusEventos()
    politica = PoliticaDevolucionDomainService(SupervisorAuthSql(sesiones))
    contenedor = _armar(bus, lambda: UnidadDeTrabajoSql(sesiones, bus), politica,
                        pasarela, sesiones=sesiones)
    weakref.finalize(contenedor, engine.dispose)   # cierra conexiones al soltarlo
    return contenedor


def normalizar_url(url: str) -> str:
    """Los proveedores (Render, Heroku...) entregan postgres:// o postgresql://;
    SQLAlchemy necesita nombrar el driver instalado (psycopg 3)."""
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


def construir_desde_entorno() -> Contenedor:
    """DATABASE_URL definida -> SQL; si no, memoria (12-Factor)."""
    url = os.getenv("DATABASE_URL")
    if url:
        return construir_sql(normalizar_url(url), sembrar_datos=os.getenv("SEED_DATA", "1") == "1")
    return construir()
