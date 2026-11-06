"""API REST (FastAPI): controladores delgados; las reglas viven en el dominio."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from src.application.dto import (
    ConsultarStockGlobalQuery,
    CrearApartadoCommand,
    DespacharTransferenciaCommand,
    LineaVentaCommand,
    PagoCommand,
    ProcesarDevolucionCommand,
    ProcesarVentaDirectaCommand,
    RecibirTransferenciaCommand,
    RegistrarAbonoCommand,
    SolicitarTransferenciaCommand,
)
from src.domain.autorizacion import Accion, exigir
from src.domain.errores import (
    DatosInvalidos,
    NoAutenticado,
    NoAutorizado,
    PagoRechazado,
    RecursoNoEncontrado,
    ReglaNegocioViolada,
    ServicioNoDisponible,
    TransicionInvalida,
)
from src.infrastructure.contenedor import Contenedor, construir_desde_entorno

ESTADOS_HTTP = {
    DatosInvalidos: 422, ReglaNegocioViolada: 422, TransicionInvalida: 409,
    NoAutorizado: 403, NoAutenticado: 401, RecursoNoEncontrado: 404, PagoRechazado: 402,
    ServicioNoDisponible: 503,
}


class ApartadoIn(BaseModel):
    cliente_id: str
    numero_serie: str
    anticipo: Decimal
    sucursal_id: str | None = None
    fecha: date | None = None


class AbonoIn(BaseModel):
    monto: Decimal
    fecha: date | None = None


class VencimientosIn(BaseModel):
    fecha: date | None = None


class LineaIn(BaseModel):
    sku: str
    numero_serie: str | None = None


class PagoIn(BaseModel):
    metodo: str
    monto: Decimal


class VentaIn(BaseModel):
    sucursal_id: str
    lineas: list[LineaIn]
    pagos: list[PagoIn]
    fecha: date | None = None


class TrasladoIn(BaseModel):
    numero_serie: str
    sucursal_destino: str
    fecha: date | None = None


class DespachoIn(BaseModel):
    numero_serie: str            # la serie que se escanea


class RecepcionIn(BaseModel):
    numero_serie: str            # la serie que se escanea
    sucursal_id: str             # sucursal que recibe


class DevolucionIn(BaseModel):
    ticket_id: str
    numero_serie: str
    clave_supervisor: str = ""
    motivo: str = ""
    empaque_original: bool = True
    accesorios_completos: bool = True
    dano_cliente: bool = False
    fecha: date | None = None


def crear_app(c: Contenedor | None = None) -> FastAPI:
    c = c or construir_desde_entorno()
    app = FastAPI(title="TecnoStock API",
                  description="Apartados, ventas con serie y devoluciones (Equipo 5)")
    app.state.contenedor = c

    def _registrar(exc_tipo: type[Exception], status: int) -> None:
        @app.exception_handler(exc_tipo)
        def _h(_, exc):
            return JSONResponse(status_code=status,
                                content={"detail": str(exc)})

    for tipo, status in ESTADOS_HTTP.items():
        _registrar(tipo, status)

    def requiere(accion: Accion):
        def dependencia(x_rol: str | None = Header(None)) -> None:
            exigir(x_rol, accion)
        return Depends(dependencia)

    def hoy(f: date | None) -> date:
        return f or date.today()

    @app.get("/", include_in_schema=False)
    def panel():
        return FileResponse(Path(__file__).parent / "panel.html")

    @app.get("/panel/datos", include_in_schema=False,
             dependencies=[requiere(Accion.CONSULTAR_PANEL)])
    def panel_datos():
        return c.panel.handle(date.today())

    @app.get("/stock", dependencies=[requiere(Accion.CONSULTAR_STOCK)])
    def stock(sku: str | None = Query(None), sucursal_id: str | None = Query(None)):
        return [asdict(x) for x in
                c.stock.handle(ConsultarStockGlobalQuery(sku, sucursal_id))]

    @app.get("/apartados/{folio}", dependencies=[requiere(Accion.CONSULTAR_APARTADO)])
    def obtener_apartado(folio: str):
        return asdict(c.apartados.consultar(folio))

    @app.post("/apartados", status_code=201,
              dependencies=[requiere(Accion.CREAR_APARTADO)])
    def crear_apartado(b: ApartadoIn):
        return asdict(c.apartados.crear_apartado(
            CrearApartadoCommand(b.cliente_id, b.numero_serie, b.anticipo,
                                 b.sucursal_id), hoy(b.fecha)))

    @app.post("/apartados/{folio}/abonos",
              dependencies=[requiere(Accion.REGISTRAR_ABONO)])
    def registrar_abono(folio: str, b: AbonoIn):
        return asdict(c.apartados.registrar_abono(
            RegistrarAbonoCommand(folio, b.monto), hoy(b.fecha)))

    @app.post("/apartados/{folio}/entrega",
              dependencies=[requiere(Accion.ENTREGAR_APARTADO)])
    def entregar(folio: str):
        return asdict(c.apartados.entregar_apartado(folio))

    @app.post("/procesos/vencimientos",
              dependencies=[requiere(Accion.PROCESAR_VENCIMIENTOS)])
    def vencimientos(b: VencimientosIn):
        return asdict(c.apartados.procesar_vencimientos(hoy(b.fecha)))

    @app.post("/ventas", status_code=201,
              dependencies=[requiere(Accion.PROCESAR_VENTA)])
    def vender(b: VentaIn):
        cmd = ProcesarVentaDirectaCommand(
            b.sucursal_id,
            [LineaVentaCommand(x.sku, x.numero_serie) for x in b.lineas],
            [PagoCommand(p.metodo, p.monto) for p in b.pagos])
        return asdict(c.ventas.procesar_venta_directa(cmd, hoy(b.fecha)))

    @app.post("/devoluciones", status_code=201,
              dependencies=[requiere(Accion.PROCESAR_DEVOLUCION)])
    def devolver(b: DevolucionIn):
        cmd = ProcesarDevolucionCommand(
            b.ticket_id, b.numero_serie, b.clave_supervisor, b.motivo,
            b.empaque_original, b.accesorios_completos, b.dano_cliente)
        return asdict(c.devoluciones.procesar_devolucion_especial(
            cmd, hoy(b.fecha)))

    @app.post("/transferencias", status_code=201,
              dependencies=[requiere(Accion.SOLICITAR_TRASLADO)])
    def solicitar_traslado(b: TrasladoIn):
        return asdict(c.transferencias.solicitar(
            SolicitarTransferenciaCommand(b.numero_serie, b.sucursal_destino),
            hoy(b.fecha)))

    @app.get("/transferencias/{folio}",
             dependencies=[requiere(Accion.CONSULTAR_TRASLADO)])
    def obtener_traslado(folio: str):
        return asdict(c.transferencias.consultar(folio))

    @app.post("/transferencias/{folio}/despacho",
              dependencies=[requiere(Accion.DESPACHAR_TRASLADO)])
    def despachar_traslado(folio: str, b: DespachoIn):
        return asdict(c.transferencias.despachar(
            DespacharTransferenciaCommand(folio, b.numero_serie)))

    @app.post("/transferencias/{folio}/recepcion",
              dependencies=[requiere(Accion.RECIBIR_TRASLADO)])
    def recibir_traslado(folio: str, b: RecepcionIn):
        return asdict(c.transferencias.recibir(
            RecibirTransferenciaCommand(folio, b.numero_serie, b.sucursal_id)))

    return app


app = crear_app()
