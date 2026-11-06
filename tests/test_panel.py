"""Panel para el cliente: datos en lenguaje de negocio y página servida en '/'."""
from fastapi.testclient import TestClient

from src.api.main import crear_app
from src.infrastructure.contenedor import construir, construir_sql


def _cliente(fabrica, rol="CAJERO"):
    return TestClient(crear_app(fabrica()), headers={"X-Rol": rol} if rol else {})


def test_panel_html_se_sirve_sin_rol():
    r = _cliente(construir, None).get("/")
    assert r.status_code == 200 and "TecnoStock" in r.text


def test_panel_datos_exige_rol():
    assert _cliente(construir, None).get("/panel/datos").status_code == 401
    assert _cliente(construir, "CLIENTE").get("/panel/datos").status_code == 403


def test_panel_datos_memoria_y_sql_coinciden():
    mem = _cliente(construir).get("/panel/datos").json()
    sql = _cliente(construir_sql).get("/panel/datos").json()
    mem.pop("hoy"), sql.pop("hoy")
    assert mem == sql
    ap = mem["apartados"][0]
    assert ap["cliente"] and ap["producto"] and ap["folio"].startswith("AP-")
    assert mem["clientes"] and mem["productos"] and mem["series"]
