"""US-06: avisos a 5 y 2 días del vencimiento de un apartado (SMS y correo simulados)."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from src.api.main import crear_app
from src.application.dto import RegistrarAbonoCommand
from src.domain.apartado import Apartado
from src.domain.valores import MontoMonetario, NumeroSerie, SucursalId
from src.infrastructure.contenedor import construir, construir_sql

M = MontoMonetario.de
CREADO = date(2026, 11, 1)           # fecha límite: 2026-12-01


def apartado(anticipo="200.00"):
    return Apartado.crear("AP-1", "C1", NumeroSerie("SN-0001"),
                          SucursalId("SUC-01"), M("1000.00"), M(anticipo), CREADO)


def a_dias(dias_restantes):
    return apartado().fecha_limite - timedelta(days=dias_restantes)


# ---------- dominio ----------
def test_los_dias_para_vencer_se_cuentan_hasta_la_fecha_limite():
    ap = apartado()
    assert ap.fecha_limite == date(2026, 12, 1)
    assert ap.dias_para_vencer(date(2026, 11, 26)) == 5


@pytest.mark.parametrize("restantes, esperado", [
    (6, None), (5, 5), (4, None), (3, None), (2, 2), (1, None), (0, None)])
def test_solo_se_avisa_a_5_y_a_2_dias(restantes, esperado):
    assert apartado().aviso_pendiente(a_dias(restantes)) == esperado


def test_un_aviso_ya_enviado_no_se_repite():
    ap = apartado()
    ap.registrar_aviso(5, a_dias(5))
    assert ap.aviso_pendiente(a_dias(5)) is None
    assert ap.aviso_pendiente(a_dias(2)) == 2          # el de 2 días sigue pendiente
    ap.registrar_aviso(2, a_dias(2))
    assert ap.avisos == {5, 2}


def test_registrar_el_aviso_emite_el_evento_con_el_saldo_y_la_fecha_limite():
    ap = apartado()
    ap.extraer_eventos()
    ap.registrar_aviso(5, a_dias(5))
    e = ap.eventos[-1]
    assert e.nombre == "AvisoVencimientoEvent"
    assert (e.datos["dias"], e.datos["saldo"], e.datos["fecha_limite"]) == (
        5, "800.00", "2026-12-01")


def test_un_apartado_liquidado_ya_no_recibe_avisos():           # cancela las alertas
    ap = apartado()
    ap.registrar_abono(M("800.00"), a_dias(10))
    assert ap.aviso_pendiente(a_dias(5)) is None


def test_un_apartado_vencido_no_recibe_avisos():
    ap = apartado()
    ap.evaluar_vencimiento(ap.fecha_limite + timedelta(days=1))
    assert ap.aviso_pendiente(a_dias(2)) is None


# ---------- servicio (memoria) ----------
# Datos de demostración: AP-0001 y AP-0002 vencen el 2026-11-29; AP-0003 el 2026-11-30.
def test_avisa_a_los_clientes_con_apartados_a_5_dias(c):
    r = c.apartados.procesar_avisos(date(2026, 11, 24))
    assert [(a.folio, a.dias) for a in r.avisos] == [("AP-0001", 5), ("AP-0002", 5)]
    primero = r.avisos[0]
    assert (primero.cliente_id, primero.saldo, primero.fecha_limite) == (
        "TEC-C004", "496.00", date(2026, 11, 29))
    assert primero.telefono and primero.correo


def test_procesar_dos_veces_el_mismo_dia_no_duplica_los_avisos(c):
    assert len(c.apartados.procesar_avisos(date(2026, 11, 24)).avisos) == 2
    assert c.apartados.procesar_avisos(date(2026, 11, 24)).avisos == []


def test_a_2_dias_se_envia_el_segundo_aviso(c):
    c.apartados.procesar_avisos(date(2026, 11, 24))
    r = c.apartados.procesar_avisos(date(2026, 11, 27))
    assert [(a.folio, a.dias) for a in r.avisos] == [("AP-0001", 2), ("AP-0002", 2)]


def test_el_aviso_llega_al_gestor_de_notificaciones_con_sms_y_correo(c):
    c.apartados.procesar_avisos(date(2026, 11, 24))
    msg = c.avisos_enviados.mensajes
    assert len(msg) == 2 and "SMS y correo" in msg[0]
    assert "AP-0001" in msg[0] and "5 días" in msg[0] and "496.00" in msg[0]


def test_un_cliente_que_liquida_antes_deja_de_recibir_avisos(c):
    c.apartados.registrar_abono(RegistrarAbonoCommand("AP-0001", Decimal("496.00")),
                                date(2026, 11, 20))
    r = c.apartados.procesar_avisos(date(2026, 11, 24))
    assert [a.folio for a in r.avisos] == ["AP-0002"]


def test_sin_apartados_por_vencer_no_hay_avisos(c):
    assert c.apartados.procesar_avisos(date(2026, 11, 6)).avisos == []


# ---------- SQL ----------
def test_los_avisos_enviados_persisten_y_no_se_repiten_en_sql():
    sc = construir_sql()
    assert len(sc.apartados.procesar_avisos(date(2026, 11, 24)).avisos) == 2
    assert sc.apartados.procesar_avisos(date(2026, 11, 24)).avisos == []
    with sc.uow_factory() as uow:
        assert uow.apartados.find_by_id("AP-0001").avisos == {5}
    assert len(sc.apartados.procesar_avisos(date(2026, 11, 27)).avisos) == 2


# ---------- API y permisos ----------
def test_api_procesa_avisos_con_fecha_y_devuelve_el_resumen():
    cli = TestClient(crear_app(construir()), headers={"X-Rol": "SISTEMA"})
    r = cli.post("/procesos/avisos", json={"fecha": "2026-11-24"})
    assert r.status_code == 200
    assert [a["folio"] for a in r.json()["avisos"]] == ["AP-0001", "AP-0002"]
    assert cli.post("/procesos/avisos", json={"fecha": "2026-11-24"}).json()["avisos"] == []


@pytest.mark.parametrize("rol, status", [("SISTEMA", 200), ("SUPERVISOR", 200),
                                         ("ADMINISTRADOR", 200), ("CAJERO", 403),
                                         ("VENDEDOR", 403), ("ALMACEN", 403)])
def test_api_permisos_de_avisos(rol, status):
    cli = TestClient(crear_app(construir()), headers={"X-Rol": rol})
    assert cli.post("/procesos/avisos", json={}).status_code == status
