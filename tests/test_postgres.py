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
