"""Restaurar los datos de demostración (por si alguien mueve el sistema en línea)."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from src.api.main import crear_app
from src.application.dto import CrearApartadoCommand, SolicitarTransferenciaCommand
from src.domain.item_serie import EstadoSerie
from src.domain.valores import NumeroSerie
from src.infrastructure.contenedor import construir, construir_sql, reiniciar_datos

HOY = date(2026, 11, 6)


def mover(c):
    """Cambia datos: apartado nuevo, traslado y un aviso enviado."""
    c.apartados.crear_apartado(CrearApartadoCommand("TEC-C001", "SN-LAP-0001", Decimal("67.20")), HOY)
    c.transferencias.solicitar(SolicitarTransferenciaCommand("SN-LAP-0003", "SUC-01"), HOY)
    c.apartados.procesar_avisos(date(2026, 11, 24))


def panel(c):
    with c.uow_factory() as uow:
        return (len(uow.apartados.listar()), len(uow.transferencias.listar()),
                uow.items.find_by_serie(NumeroSerie("SN-LAP-0001")).estado,
                uow.apartados.find_by_id("AP-0001").avisos)


@pytest.mark.parametrize("fabrica", [construir, construir_sql], ids=["memoria", "sql"])
def test_reiniciar_deja_los_datos_como_al_inicio(fabrica):
    c = fabrica()
    inicial = panel(c)
    assert inicial == (5, 0, EstadoSerie.DISPONIBLE, set())
    mover(c)
    assert panel(c) != inicial
    reiniciar_datos(c)
    assert panel(c) == inicial


def test_despues_de_reiniciar_se_puede_volver_a_operar():
    c = construir_sql()
    mover(c)
    reiniciar_datos(c)
    assert c.apartados.crear_apartado(
        CrearApartadoCommand("TEC-C001", "SN-LAP-0001", Decimal("67.20")), HOY).folio == "AP-0006"


# ---------- endpoint protegido por clave ----------
def test_sin_clave_configurada_el_endpoint_no_existe(monkeypatch):
    monkeypatch.delenv("RESET_TOKEN", raising=False)
    cli = TestClient(crear_app(construir()))
    assert cli.post("/admin/reiniciar", headers={"X-Reset-Token": "x"}).status_code == 404


@pytest.mark.parametrize("cabeceras", [{}, {"X-Reset-Token": "otra"}])
def test_con_clave_incorrecta_o_ausente_se_rechaza_y_no_cambia_nada(monkeypatch, cabeceras):
    monkeypatch.setenv("RESET_TOKEN", "secreta-123")
    c = construir()
    mover(c)
    antes = panel(c)
    assert TestClient(crear_app(c)).post("/admin/reiniciar", headers=cabeceras).status_code == 403
    assert panel(c) == antes


def test_con_la_clave_correcta_restaura_los_datos(monkeypatch):
    monkeypatch.setenv("RESET_TOKEN", "secreta-123")
    c = construir_sql()
    mover(c)
    r = TestClient(crear_app(c)).post("/admin/reiniciar", headers={"X-Reset-Token": "secreta-123"})
    assert r.status_code == 200
    assert panel(c) == (5, 0, EstadoSerie.DISPONIBLE, set())


def test_el_endpoint_no_aparece_en_la_documentacion_publica():
    rutas = TestClient(crear_app(construir())).get("/openapi.json").json()["paths"]
    assert "/admin/reiniciar" not in rutas
