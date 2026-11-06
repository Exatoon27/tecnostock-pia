"""CU-04 Traslado entre sucursales (US-07 y US-08): dominio, servicios, SQL, API y panel."""
import time
from dataclasses import asdict
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from src.api.main import crear_app
from src.application.dto import (
    ConsultarStockGlobalQuery,
    CrearApartadoCommand,
    DespacharTransferenciaCommand,
    LineaVentaCommand,
    PagoCommand,
    ProcesarVentaDirectaCommand,
    RecibirTransferenciaCommand,
    SolicitarTransferenciaCommand,
)
from src.domain.errores import (
    RecursoNoEncontrado,
    ReglaNegocioViolada,
    TransicionInvalida,
)
from src.domain.item_serie import EstadoSerie, ItemSerie
from src.domain.transferencia import EstadoTransferencia, Transferencia
from src.domain.valores import SKU, NumeroSerie, SucursalId
from src.infrastructure.contenedor import construir, construir_sql
from src.infrastructure.sql import TransferenciaRow, UnidadDeTrabajoSql

HOY = date(2026, 11, 6)
S, SUC = NumeroSerie, SucursalId
SERIE = "SN-LAP-0001"          # SUC-01, DISPONIBLE en los datos de demostración


def nueva(estado=EstadoSerie.DISPONIBLE):
    return ItemSerie(S(SERIE), SKU("TEC-P001"), SUC("SUC-01"), estado)


def solicitud(origen="SUC-01", destino="SUC-02"):
    return Transferencia.solicitar("TR-0001", S(SERIE), SUC(origen), SUC(destino), HOY)


def nombres(t):
    return [e.nombre for e in t.eventos]


# ---------- dominio: la pieza ----------
def test_la_pieza_cumple_el_ciclo_de_un_traslado_y_cambia_de_sucursal():
    item = nueva()
    item.reservar_para_traslado()
    assert item.estado == EstadoSerie.RESERVADO_TRASLADO
    item.despachar()
    assert item.estado == EstadoSerie.EN_TRANSITO and item.sucursal == SUC("SUC-01")
    item.recibir(SUC("SUC-02"))
    assert item.estado == EstadoSerie.DISPONIBLE and item.sucursal == SUC("SUC-02")


@pytest.mark.parametrize("estado", [EstadoSerie.RESERVADO, EstadoSerie.VENDIDO,
                                    EstadoSerie.EN_TRANSITO,
                                    EstadoSerie.RESERVADO_TRASLADO])
def test_solo_una_pieza_disponible_se_puede_trasladar(estado):
    item = nueva(estado)
    with pytest.raises(TransicionInvalida):
        item.reservar_para_traslado()
    assert item.estado == estado and item.eventos == []


def test_no_se_despacha_ni_se_recibe_fuera_de_orden():
    item = nueva()
    with pytest.raises(TransicionInvalida):
        item.despachar()
    with pytest.raises(TransicionInvalida):
        item.recibir(SUC("SUC-02"))


# ---------- dominio: la orden de traslado ----------
def test_solicitar_crea_la_orden_pendiente_de_despacho():
    t = solicitud()
    assert t.estado == EstadoTransferencia.PENDIENTE_DESPACHO and t.guia is None
    assert nombres(t) == ["TransferenciaSolicitadaEvent"]


def test_origen_y_destino_deben_ser_distintos():
    with pytest.raises(ReglaNegocioViolada, match="distinta"):
        solicitud(origen="SUC-01", destino="SUC-01")


def test_despachar_con_la_serie_correcta_genera_la_guia():
    t = solicitud()
    t.despachar(S(SERIE))
    assert t.estado == EstadoTransferencia.EN_TRANSITO and t.guia == "GT-0001"
    assert nombres(t)[-1] == "TransferenciaDespachadaEvent"


def test_despachar_con_otra_serie_se_rechaza_sin_cambiar_el_estado():
    t = solicitud()
    with pytest.raises(ReglaNegocioViolada, match="no corresponde"):
        t.despachar(S("SN-LAP-0002"))
    assert t.estado == EstadoTransferencia.PENDIENTE_DESPACHO
    assert nombres(t) == ["TransferenciaSolicitadaEvent"]


def test_no_se_puede_despachar_dos_veces():
    t = solicitud()
    t.despachar(S(SERIE))
    with pytest.raises(TransicionInvalida):
        t.despachar(S(SERIE))
    assert nombres(t).count("TransferenciaDespachadaEvent") == 1


def test_no_se_recibe_antes_de_despachar():
    t = solicitud()
    with pytest.raises(TransicionInvalida):
        t.recibir(S(SERIE), SUC("SUC-02"))


def test_recibir_en_otra_sucursal_se_rechaza():
    t = solicitud()
    t.despachar(S(SERIE))
    with pytest.raises(ReglaNegocioViolada, match="SUC-02"):
        t.recibir(S(SERIE), SUC("SUC-03"))
    assert t.estado == EstadoTransferencia.EN_TRANSITO


def test_recibir_con_otra_serie_se_rechaza():
    t = solicitud()
    t.despachar(S(SERIE))
    with pytest.raises(ReglaNegocioViolada, match="no corresponde"):
        t.recibir(S("SN-LAP-0002"), SUC("SUC-02"))


def test_recibir_cierra_la_orden():
    t = solicitud()
    t.despachar(S(SERIE))
    t.recibir(S(SERIE), SUC("SUC-02"))
    assert t.estado == EstadoTransferencia.RECIBIDA
    assert nombres(t)[-1] == "TransferenciaRecibidaEvent"
    with pytest.raises(TransicionInvalida):
        t.recibir(S(SERIE), SUC("SUC-02"))


# ---------- servicios de aplicación (memoria) ----------
def pedir(c, serie=SERIE, destino="SUC-02"):
    return c.transferencias.solicitar(SolicitarTransferenciaCommand(serie, destino), HOY)


def estado(c, serie=SERIE):
    return c.almacen.items[serie].estado


def test_solicitar_reserva_la_pieza_en_el_origen(c):
    dto = pedir(c)
    assert (dto.folio, dto.estado, dto.origen, dto.destino) == (
        "TR-0001", "PENDIENTE_DESPACHO", "SUC-01", "SUC-02")
    assert estado(c) == EstadoSerie.RESERVADO_TRASLADO
    assert "TransferenciaSolicitadaEvent" in [e.nombre for e in c.bus.publicados]


def test_ciclo_completo_deja_la_pieza_disponible_en_el_destino(c):
    dto = pedir(c)
    d = c.transferencias.despachar(DespacharTransferenciaCommand(dto.folio, SERIE))
    assert d.estado == "EN_TRANSITO" and d.guia == "GT-0001"
    assert estado(c) == EstadoSerie.EN_TRANSITO
    r = c.transferencias.recibir(RecibirTransferenciaCommand(dto.folio, SERIE, "SUC-02"))
    assert r.estado == "RECIBIDA"
    assert estado(c) == EstadoSerie.DISPONIBLE
    assert c.almacen.items[SERIE].sucursal.valor == "SUC-02"


def test_una_pieza_apartada_no_se_puede_trasladar(c):
    c.apartados.crear_apartado(CrearApartadoCommand("TEC-C001", SERIE, Decimal("67.20")), HOY)
    with pytest.raises(TransicionInvalida, match="trasladar"):
        pedir(c)
    assert c.almacen.transferencias == {}


def test_una_pieza_en_traslado_no_se_vende_ni_se_aparta(c):
    pedir(c)
    with pytest.raises(ReglaNegocioViolada):
        c.apartados.crear_apartado(
            CrearApartadoCommand("TEC-C001", SERIE, Decimal("67.20")), HOY)
    with pytest.raises(TransicionInvalida):
        c.ventas.procesar_venta_directa(ProcesarVentaDirectaCommand(
            "SUC-01", [LineaVentaCommand("TEC-P001", SERIE)],
            [PagoCommand("EFECTIVO", Decimal("336.00"))]), HOY)
    assert estado(c) == EstadoSerie.RESERVADO_TRASLADO


def test_destino_igual_al_origen_no_deja_rastro(c):
    with pytest.raises(ReglaNegocioViolada):
        pedir(c, destino="SUC-01")
    assert estado(c) == EstadoSerie.DISPONIBLE and c.almacen.transferencias == {}


def test_serie_o_folio_inexistentes_dan_404(c):
    with pytest.raises(RecursoNoEncontrado):
        pedir(c, serie="SN-NOEXISTE-1")
    with pytest.raises(RecursoNoEncontrado):
        c.transferencias.consultar("TR-9999")


def test_un_escaneo_equivocado_no_cambia_nada(c):
    dto = pedir(c)
    with pytest.raises(ReglaNegocioViolada):
        c.transferencias.despachar(DespacharTransferenciaCommand(dto.folio, "SN-LAP-0002"))
    assert estado(c) == EstadoSerie.RESERVADO_TRASLADO
    assert c.transferencias.consultar(dto.folio).estado == "PENDIENTE_DESPACHO"


def test_el_stock_muestra_piezas_en_transito_y_reservadas_para_traslado(c):
    dto = pedir(c)
    fila = lambda: next(x for x in c.stock.handle(ConsultarStockGlobalQuery("TEC-P001", "SUC-01")))  # noqa: E731
    assert (fila().disponibles, fila().reservados, fila().en_transito) == (1, 1, 0)
    c.transferencias.despachar(DespacharTransferenciaCommand(dto.folio, SERIE))
    assert (fila().disponibles, fila().reservados, fila().en_transito) == (1, 0, 1)
    c.transferencias.recibir(RecibirTransferenciaCommand(dto.folio, SERIE, "SUC-02"))
    destino = next(x for x in c.stock.handle(ConsultarStockGlobalQuery("TEC-P001", "SUC-02")))
    assert destino.disponibles == 3        # 2 que ya tenía + la que llegó


def test_la_consulta_de_stock_responde_en_menos_de_3_segundos():          # CON-01
    c = construir()
    inicio = time.perf_counter()
    c.stock.handle(ConsultarStockGlobalQuery())
    assert time.perf_counter() - inicio < 3


# ---------- SQL ----------
def test_el_ciclo_completo_persiste_en_sql():
    sc = construir_sql()
    dto = sc.transferencias.solicitar(SolicitarTransferenciaCommand(SERIE, "SUC-02"), HOY)
    sc.transferencias.despachar(DespacharTransferenciaCommand(dto.folio, SERIE))
    sc.transferencias.recibir(RecibirTransferenciaCommand(dto.folio, SERIE, "SUC-02"))
    with sc.uow_factory() as uow:
        item = uow.items.find_by_serie(S(SERIE))
        t = uow.transferencias.find_by_id(dto.folio)
        assert (item.estado, item.sucursal.valor) == (EstadoSerie.DISPONIBLE, "SUC-02")
        assert (t.estado, t.guia) == (EstadoTransferencia.RECIBIDA, "GT-0001")
        assert [x.folio for x in uow.transferencias.listar()] == ["TR-0001"]
        assert uow.transferencias.siguiente_folio() == "TR-0002"


def test_la_base_impide_dos_traslados_activos_de_la_misma_pieza():
    sc = construir_sql()
    sc.transferencias.solicitar(SolicitarTransferenciaCommand(SERIE, "SUC-02"), HOY)
    with pytest.raises(IntegrityError):
        with UnidadDeTrabajoSql(sc.sesiones, sc.bus) as uow:
            uow.session.add(TransferenciaRow(
                folio="TR-0099", numero_serie=SERIE, origen="SUC-01", destino="SUC-03",
                estado="PENDIENTE_DESPACHO", fecha_solicitud=HOY))
            uow.session.flush()


def test_un_rechazo_en_sql_revierte_la_reserva_de_la_pieza():
    sc = construir_sql()
    with pytest.raises(ReglaNegocioViolada):
        sc.transferencias.solicitar(SolicitarTransferenciaCommand(SERIE, "SUC-01"), HOY)
    with sc.uow_factory() as uow:
        assert uow.items.find_by_serie(S(SERIE)).estado == EstadoSerie.DISPONIBLE
        assert uow.transferencias.listar() == []


# ---------- API y permisos ----------
def api(rol):
    return TestClient(crear_app(construir()), headers={"X-Rol": rol})


def test_api_flujo_completo_con_los_puestos_correctos():
    c = construir()
    app = crear_app(c)
    vend = TestClient(app, headers={"X-Rol": "VENDEDOR"})
    alm = TestClient(app, headers={"X-Rol": "ALMACEN"})
    r = vend.post("/transferencias", json={"numero_serie": SERIE, "sucursal_destino": "SUC-02",
                                           "fecha": "2026-11-06"})
    assert r.status_code == 201 and r.json()["estado"] == "PENDIENTE_DESPACHO"
    folio = r.json()["folio"]
    r = alm.post(f"/transferencias/{folio}/despacho", json={"numero_serie": SERIE})
    assert r.status_code == 200 and r.json()["guia"] == "GT-0001"
    r = alm.post(f"/transferencias/{folio}/recepcion",
                 json={"numero_serie": SERIE, "sucursal_id": "SUC-02"})
    assert r.status_code == 200 and r.json()["estado"] == "RECIBIDA"
    assert alm.get(f"/transferencias/{folio}").json()["estado"] == "RECIBIDA"


def test_api_errores_409_422_404():
    c = construir()
    app = crear_app(c)
    sup = TestClient(app, headers={"X-Rol": "SUPERVISOR"})
    folio = sup.post("/transferencias", json={"numero_serie": SERIE, "sucursal_destino": "SUC-02"}
                     ).json()["folio"]
    assert sup.post(f"/transferencias/{folio}/recepcion",
                    json={"numero_serie": SERIE, "sucursal_id": "SUC-02"}).status_code == 409
    assert sup.post(f"/transferencias/{folio}/despacho",
                    json={"numero_serie": "SN-LAP-0002"}).status_code == 422
    assert sup.post("/transferencias", json={"numero_serie": "SN-LAP-0002",
                                             "sucursal_destino": "SUC-01"}).status_code == 422
    assert sup.get("/transferencias/TR-9999").status_code == 404


@pytest.mark.parametrize("rol, ruta, status", [
    ("CAJERO", "/transferencias", 403),
    ("ALMACEN", "/transferencias", 403),
])
def test_api_permisos_para_solicitar(rol, ruta, status):
    r = api(rol).post(ruta, json={"numero_serie": SERIE, "sucursal_destino": "SUC-02"})
    assert r.status_code == status


def test_api_solo_almacen_o_supervisor_despachan_y_reciben():
    c = construir()
    app = crear_app(c)
    folio = TestClient(app, headers={"X-Rol": "VENDEDOR"}).post(
        "/transferencias", json={"numero_serie": SERIE, "sucursal_destino": "SUC-02"}).json()["folio"]
    for rol in ("VENDEDOR", "CAJERO"):
        cli = TestClient(app, headers={"X-Rol": rol})
        assert cli.post(f"/transferencias/{folio}/despacho",
                        json={"numero_serie": SERIE}).status_code == 403
        assert cli.post(f"/transferencias/{folio}/recepcion",
                        json={"numero_serie": SERIE, "sucursal_id": "SUC-02"}).status_code == 403


def test_api_stock_incluye_piezas_en_transito():
    c = construir()
    app = crear_app(c)
    sup = TestClient(app, headers={"X-Rol": "SUPERVISOR"})
    folio = sup.post("/transferencias", json={"numero_serie": SERIE, "sucursal_destino": "SUC-02"}
                     ).json()["folio"]
    sup.post(f"/transferencias/{folio}/despacho", json={"numero_serie": SERIE})
    fila = next(x for x in sup.get("/stock", params={"sku": "TEC-P001", "sucursal_id": "SUC-01"}).json())
    assert fila["en_transito"] == 1 and "en_transito" in asdict(
        c.stock.handle(ConsultarStockGlobalQuery("TEC-P001", "SUC-01"))[0])


# ---------- panel ----------
def test_el_panel_lista_traslados_y_sucursales():
    c = construir()
    app = crear_app(c)
    cli = TestClient(app, headers={"X-Rol": "SUPERVISOR"})
    cli.post("/transferencias", json={"numero_serie": SERIE, "sucursal_destino": "SUC-02"})
    datos = cli.get("/panel/datos").json()
    assert datos["sucursales"] == ["SUC-01", "SUC-02", "SUC-03", "SUC-04", "SUC-05"]
    t = datos["transferencias"][0]
    assert (t["folio"], t["estado"], t["origen"], t["destino"]) == (
        "TR-0001", "PENDIENTE_DESPACHO", "SUC-01", "SUC-02")
    assert t["producto"] == "Laptop 01"
