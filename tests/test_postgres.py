"""Integración contra PostgreSQL real (docker compose --profile tests run --rm tests).

Se omite si no hay TEST_DATABASE_URL, así la suite local sigue siendo rápida.
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from src.api.main import crear_app
from src.infrastructure.contenedor import construir_sql
from src.infrastructure.sql import Base

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="sin TEST_DATABASE_URL")


@pytest.fixture
def api():
    engine = create_engine(URL)
    Base.metadata.drop_all(engine)       # arranque limpio y repetible
    engine.dispose()
    return TestClient(crear_app(construir_sql(URL)), headers={"X-Rol": "CAJERO"})


def test_apartado_persiste_y_el_panel_lo_ve(api):
    r = api.post("/apartados", json={"cliente_id": "TEC-C001",
                                     "numero_serie": "SN-LAP-0001", "anticipo": "67.20"})
    assert r.status_code == 201
    folio = r.json()["folio"]
    datos = api.get("/panel/datos").json()
    assert folio in [a["folio"] for a in datos["apartados"]]
    serie = next(s for s in datos["series"] if s["numero_serie"] == "SN-LAP-0001")
    assert serie["estado"] == "RESERVADO"


def test_regla_de_negocio_se_rechaza_igual_en_postgres(api):
    r = api.post("/apartados", json={"cliente_id": "TEC-C002",
                                     "numero_serie": "SN-LAP-0002", "anticipo": "1"})
    assert r.status_code == 422 and "20%" in r.json()["detail"]


def test_un_rechazo_no_deja_la_serie_bloqueada(api):
    api.post("/apartados", json={"cliente_id": "TEC-C002",
                                 "numero_serie": "SN-LAP-0002", "anticipo": "1"})
    serie = next(s for s in api.get("/panel/datos").json()["series"]
                 if s["numero_serie"] == "SN-LAP-0002")
    assert serie["estado"] == "DISPONIBLE"


def test_traslado_completo_en_postgres(api):
    r = api.post("/transferencias", headers={"X-Rol": "VENDEDOR"},
                 json={"numero_serie": "SN-LAP-0003", "sucursal_destino": "SUC-01"})
    assert r.status_code == 201
    folio = r.json()["folio"]
    alm = {"X-Rol": "ALMACEN"}
    assert api.post(f"/transferencias/{folio}/despacho", headers=alm,
                    json={"numero_serie": "SN-LAP-0003"}).status_code == 200
    assert api.post(f"/transferencias/{folio}/recepcion", headers=alm,
                    json={"numero_serie": "SN-LAP-0003", "sucursal_id": "SUC-01"}
                    ).json()["estado"] == "RECIBIDA"
    serie = next(s for s in api.get("/panel/datos").json()["series"]
                 if s["numero_serie"] == "SN-LAP-0003")
    assert (serie["estado"], serie["sucursal"]) == ("DISPONIBLE", "SUC-01")


def test_reiniciar_datos_en_postgres():
    from datetime import date
    from decimal import Decimal

    from src.application.dto import CrearApartadoCommand
    from src.domain.item_serie import EstadoSerie
    from src.domain.valores import NumeroSerie
    from src.infrastructure.contenedor import reiniciar_datos

    engine = create_engine(URL)
    Base.metadata.drop_all(engine)
    engine.dispose()
    c = construir_sql(URL)
    c.apartados.crear_apartado(
        CrearApartadoCommand("TEC-C001", "SN-LAP-0001", Decimal("67.20")), date(2026, 11, 6))
    reiniciar_datos(c)
    with c.uow_factory() as uow:
        assert len(uow.apartados.listar()) == 5
        assert uow.items.find_by_serie(NumeroSerie("SN-LAP-0001")).estado == EstadoSerie.DISPONIBLE
