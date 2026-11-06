"""Redibuja el BPMN de U2 (TecnoStock) como 4 diagramas legibles con carriles.

Fuente de verdad: docs/analisis/BPMN_U2.pdf (imagen). Cada caja, decisión y flujo del
original está aquí; sólo cambia la presentación (un diagrama por proceso, texto grande).

    python tools/generar_bpmn.py        # escribe docs/analisis/bpmn/*.svg
"""
from __future__ import annotations

import textwrap
from html import escape
from pathlib import Path

SALIDA = Path(__file__).resolve().parent.parent / "docs" / "analisis" / "bpmn"

FONT = 16
ROW_H = 190
LANE_LABEL_W = 64
COL_W = 270
NODE = {"task": (196, 72), "gate": (214, 112), "start": (196, 58), "end": (196, 58), "call": (196, 72)}
WRAP = {"task": 23, "gate": 15, "start": 23, "end": 23, "call": 23}
COLORES = {"start": ("#e3f4ea", "#1f7a3d", 2), "end": ("#fbe3df", "#a63a2b", 4),
           "task": ("#ffffff", "#0c3a33", 1.6), "gate": ("#fdf3d0", "#8a6d1a", 1.8),
           "call": ("#e0edfb", "#1d5fa8", 1.8)}


class Diagrama:
    def __init__(self, titulo: str, subtitulo: str, carriles: list[tuple[str, int]]):
        self.titulo, self.subtitulo = titulo, subtitulo
        self.carriles = carriles                 # (nombre, filas)
        self.nodos: dict[str, dict] = {}
        self.flujos: list[dict] = []
        self.top = 96
        self.lane_top, y = {}, self.top
        for nombre, filas in carriles:
            self.lane_top[nombre] = y
            y += filas * ROW_H
        self.alto = y + 70

    def nodo(self, id, tipo, carril, col, texto, fila=0, dato=None):
        w, h = NODE[tipo]
        cx = LANE_LABEL_W + 40 + 107 + col * COL_W
        cy = self.lane_top[carril] + fila * ROW_H + ROW_H / 2 - 14
        self.nodos[id] = dict(tipo=tipo, x=cx, y=cy, w=w, h=h, texto=texto, dato=dato)

    def flujo(self, a, b, etiqueta="", sa="r", sb="l", xm=None, ym=None, lseg=0):
        self.flujos.append(dict(a=a, b=b, etiqueta=etiqueta, sa=sa, sb=sb, xm=xm, ym=ym, lseg=lseg))

    # -- geometría --
    def _punto(self, id, lado):
        n = self.nodos[id]
        dx, dy = {"r": (n["w"] / 2, 0), "l": (-n["w"] / 2, 0),
                  "t": (0, -n["h"] / 2), "b": (0, n["h"] / 2)}[lado]
        return n["x"] + dx, n["y"] + dy

    def _ruta(self, f):
        (xs, ys), (xd, yd) = self._punto(f["a"], f["sa"]), self._punto(f["b"], f["sb"])
        sa, sb = f["sa"], f["sb"]
        if sa in "rl" and sb in "rl":
            if abs(ys - yd) < 1:
                return [(xs, ys), (xd, yd)]
            xm = f["xm"] if f["xm"] is not None else (xs + xd) / 2
            return [(xs, ys), (xm, ys), (xm, yd), (xd, yd)]
        if sa in "rl" and sb in "tb":
            return [(xs, ys), (xd, ys), (xd, yd)]
        if sa in "tb" and sb in "rl":
            return [(xs, ys), (xs, yd), (xd, yd)]
        ym = f["ym"] if f["ym"] is not None else (ys + yd) / 2
        if abs(xs - xd) < 1:
            return [(xs, ys), (xd, yd)]
        return [(xs, ys), (xs, ym), (xd, ym), (xd, yd)]

    # -- dibujo --
    @staticmethod
    def _texto(cx, cy, texto, ancho, negrita=False, tam=FONT):
        lineas = textwrap.wrap(texto, ancho) or [""]
        y0 = cy - (len(lineas) - 1) * (tam + 3) / 2
        peso = ' font-weight="700"' if negrita else ""
        tsp = "".join(f'<tspan x="{cx:.0f}" y="{y0 + i * (tam + 3):.0f}">{escape(t)}</tspan>'
                      for i, t in enumerate(lineas))
        return f'<text text-anchor="middle" dominant-baseline="central" font-size="{tam}"{peso}>{tsp}</text>'

    def svg(self) -> str:
        ancho = LANE_LABEL_W + 80 + (max((n["x"] for n in self.nodos.values())) - LANE_LABEL_W) + 150
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho:.0f}" height="{self.alto}" '
               f'viewBox="0 0 {ancho:.0f} {self.alto}" font-family="Segoe UI, Arial, sans-serif" fill="#15221f">',
               '<defs><marker id="f" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" '
               'orient="auto-start-reverse"><path d="M0 0 10 5 0 10z" fill="#15221f"/></marker></defs>',
               '<rect width="100%" height="100%" fill="#ffffff"/>',
               f'<text x="24" y="38" font-size="26" font-weight="700">{escape(self.titulo)}</text>',
               f'<text x="24" y="66" font-size="16" fill="#5b6965">{escape(self.subtitulo)}</text>']
        for i, (nombre, filas) in enumerate(self.carriles):
            y, h = self.lane_top[nombre], filas * ROW_H
            fondo = "#f3f6f4" if i % 2 == 0 else "#ffffff"
            out.append(f'<rect x="0" y="{y}" width="{ancho:.0f}" height="{h}" fill="{fondo}" stroke="#9fb0aa"/>')
            out.append(f'<rect x="0" y="{y}" width="{LANE_LABEL_W}" height="{h}" fill="#0c3a33"/>')
            palabras = nombre.upper().split()
            for k, palabra in enumerate(palabras):
                off = 34 + (k - (len(palabras) - 1) / 2) * 20
                out.append(f'<text transform="translate({off} {y + h / 2}) rotate(-90)" text-anchor="middle" '
                           f'dominant-baseline="central" font-size="16" font-weight="700" fill="#eef7f4">'
                           f'{escape(palabra)}</text>')
        for f in self.flujos:
            pts = self._ruta(f)
            d = " ".join(f"{x:.0f},{y:.0f}" for x, y in pts)
            out.append(f'<polyline points="{d}" fill="none" stroke="#15221f" stroke-width="1.8" '
                       f'stroke-linejoin="round" marker-end="url(#f)"/>')
        for id, n in self.nodos.items():
            fill, stroke, sw = COLORES[n["tipo"]]
            x, y, w, h = n["x"], n["y"], n["w"], n["h"]
            if n["tipo"] == "gate":
                forma = f'<polygon points="{x},{y - h / 2} {x + w / 2},{y} {x},{y + h / 2} {x - w / 2},{y}"'
            elif n["tipo"] in ("start", "end"):
                forma = (f'<rect x="{x - w / 2}" y="{y - h / 2}" width="{w}" height="{h}" rx="{h / 2}"')
            else:
                forma = f'<rect x="{x - w / 2}" y="{y - h / 2}" width="{w}" height="{h}" rx="9"'
            out.append(f'{forma} fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
            if n["tipo"] == "call":
                out.append(f'<rect x="{x - w / 2 + 5}" y="{y - h / 2 + 5}" width="{w - 10}" height="{h - 10}" '
                           f'rx="6" fill="none" stroke="{stroke}" stroke-width="1"/>')
            out.append(self._texto(x, y, n["texto"], WRAP[n["tipo"]], negrita=n["tipo"] in ("start", "end")))
            if n["dato"]:
                dx, dy = x, y + h / 2 + 34
                out.append(f'<line x1="{x}" y1="{y + h / 2}" x2="{dx}" y2="{dy - 20}" stroke="#5b6965" '
                           f'stroke-dasharray="4 3"/>')
                out.append(f'<path d="M{dx - 86} {dy - 20} h160 l12 12 v36 h-172z" fill="#ffffff" stroke="#5b6965"/>')
                out.append(self._texto(dx, dy, n["dato"], 25, tam=13))
        for f in self.flujos:
            if f["etiqueta"]:
                pts = self._ruta(f)
                i = f["lseg"] % (len(pts) - 1)
                (x1, y1), (x2, y2) = pts[i], pts[i + 1]
                if y1 == y2:                       # tramo horizontal: etiqueta encima
                    lx, ly, anchor = x1 + (12 if x2 >= x1 else -12), y1 - 10, "start" if x2 >= x1 else "end"
                else:                              # tramo vertical: etiqueta al lado
                    lx, ly, anchor = x1 + 10, y1 + (22 if y2 > y1 else -10), "start"
                out.append(f'<text x="{lx:.0f}" y="{ly:.0f}" font-size="15" font-weight="700" '
                           f'text-anchor="{anchor}" paint-order="stroke" stroke="#ffffff" stroke-width="5">'
                           f'{escape(f["etiqueta"])}</text>')
        out.append(self._leyenda(ancho))
        out.append("</svg>")
        return "\n".join(out)

    def _leyenda(self, ancho):
        y, x = self.alto - 34, 24
        items = [("start", "Inicio"), ("task", "Actividad"), ("gate", "Decisión"), ("end", "Fin"), ("call", "Pasa a otro proceso")]
        partes = []
        for tipo, txt in items:
            fill, stroke, sw = COLORES[tipo]
            partes.append(f'<rect x="{x}" y="{y}" width="34" height="18" rx="{9 if tipo in ("start", "end") else 4}" '
                          f'fill="{fill}" stroke="{stroke}" stroke-width="{min(sw, 2)}"/>'
                          f'<text x="{x + 42}" y="{y + 14}" font-size="14" fill="#5b6965">{txt}</text>')
            x += 42 + len(txt) * 8 + 26
        return "".join(partes)


def consulta() -> Diagrama:
    d = Diagrama("Proceso 1 · Consulta de disponibilidad y traslado entre sucursales",
                 "Todo empieza cuando un cliente pide algo al Vendedor. Origen: BPMN de U2.",
                 [("Cliente", 1), ("Vendedor", 3), ("Almacén", 1)])
    d.nodo("s", "start", "Cliente", 0, "Solicitud del cliente")
    d.nodo("t1", "task", "Vendedor", 1, "Consultar disponibilidad del producto en el sistema", 0, dato="Ficha de producto (SKU)")
    d.nodo("g1", "gate", "Vendedor", 2, "¿Hay en la tienda local?", 0)
    d.nodo("g2", "gate", "Vendedor", 3, "¿Hay en otra sucursal?", 1)
    d.nodo("t2", "task", "Vendedor", 4, "Solicitar transferencia entre sucursales", 1)
    d.nodo("fin", "end", "Cliente", 3, "Cancelado: sin existencias")
    d.nodo("a1", "task", "Almacén", 5, "Escanear la serie y despachar el paquete", dato="Guía de traslado")
    d.nodo("a2", "task", "Almacén", 6, "Confirmar la recepción escaneando la serie")
    d.nodo("g3", "gate", "Vendedor", 7, "¿Qué solicita el cliente?", 0)
    d.nodo("c1", "call", "Vendedor", 8.6, "Proceso 2: Venta directa", 0)
    d.nodo("c2", "call", "Vendedor", 8.6, "Proceso 3: Apartado", 1)
    d.nodo("c3", "call", "Vendedor", 8.6, "Proceso 4: Devolución", 2)
    d.flujo("s", "t1", sa="b", sb="l")
    d.flujo("t1", "g1")
    d.flujo("g1", "g3", "Sí")
    d.flujo("g1", "g2", "No", sa="b", sb="l")
    d.flujo("g2", "t2", "Sí")
    d.flujo("g2", "fin", "No", sa="t", sb="b")
    d.flujo("t2", "a1", sa="r", sb="t")
    d.flujo("a1", "a2")
    d.flujo("a2", "g3", sa="r", sb="l", xm=d.nodos["g3"]["x"] - 130)
    d.flujo("g3", "c1", "Venta directa", sa="r", sb="l")
    d.flujo("g3", "c2", "Apartado", sa="b", sb="l", lseg=-1)
    d.flujo("g3", "c3", "Devolución", sa="b", sb="l", lseg=-1)
    return d


def venta() -> Diagrama:
    d = Diagrama("Proceso 2 · Venta directa",
                 "El número de serie se exige sólo para los equipos que lo requieren. Origen: BPMN de U2.",
                 [("Cliente", 1), ("Cajero", 1)])
    d.nodo("s", "start", "Cliente", 0, "Quiere comprar")
    d.nodo("g", "gate", "Cajero", 1, "¿El producto requiere número de serie?")
    d.nodo("t1", "task", "Cajero", 2, "Escanear el código de serie de la pieza", dato="Registro de serie validado")
    d.nodo("t2", "task", "Cajero", 3, "Procesar el cobro (varios métodos de pago)")
    d.nodo("t3", "task", "Cajero", 4, "Generar el ticket fiscal y entregar el producto", dato="Ticket / comprobante fiscal")
    d.nodo("e", "end", "Cliente", 5, "Venta concluida con éxito")
    d.flujo("s", "g", sa="b", sb="l")
    d.flujo("g", "t1", "Sí")
    d.flujo("g", "t2", "No", sa="b", sb="b", ym=d.nodos["g"]["y"] + 106)
    d.flujo("t1", "t2")
    d.flujo("t2", "t3")
    d.flujo("t3", "e", sa="r", sb="b")
    return d


def apartado() -> Diagrama:
    d = Diagrama("Proceso 3 · Apartado de un producto",
                 "Anticipo mínimo del 20 % y 30 días para liquidar. Origen: BPMN de U2.",
                 [("Cliente", 1), ("Cajero", 1), ("Sistema automático", 1)])
    d.nodo("s", "start", "Cliente", 0, "Quiere apartar")
    d.nodo("t1", "task", "Cajero", 1, "Registrar los datos del cliente y el anticipo (mínimo 20 %)")
    d.nodo("s1", "task", "Sistema automático", 2, "Reservar la pieza en el stock de inmediato", dato="Comprobante de apartado")
    d.nodo("g", "gate", "Sistema automático", 3, "¿Liquida el saldo en 30 días o menos?")
    d.nodo("t2", "task", "Cajero", 4, "Registrar el pago del saldo, escanear la serie y entregar")
    d.nodo("s2", "task", "Sistema automático", 4.4, "Liberar la pieza y aplicar penalización del 10 %")
    d.nodo("ok", "end", "Cliente", 5.2, "Apartado liquidado y entregado")
    d.nodo("venc", "end", "Cliente", 6.4, "Apartado cancelado por vencimiento")
    d.flujo("s", "t1", sa="b", sb="l")
    d.flujo("t1", "s1", sa="r", sb="t")
    d.flujo("s1", "g")
    d.flujo("g", "t2", "Sí", sa="t", sb="l")
    d.flujo("g", "s2", "No (día 31)")
    d.flujo("t2", "ok", sa="r", sb="b")
    d.flujo("s2", "venc", sa="r", sb="b")
    return d


def devolucion() -> Diagrama:
    d = Diagrama("Proceso 4 · Devolución de un producto",
                 "Plazo de 15 días, producto en buen estado y clave del Supervisor. Origen: BPMN de U2.",
                 [("Cliente", 1), ("Cajero", 1), ("Supervisor", 1)])
    d.nodo("s", "start", "Cliente", 0, "Pide una devolución")
    d.nodo("t1", "task", "Cajero", 1, "Solicitar el comprobante y verificar que no pasen de 15 días")
    d.nodo("g1", "gate", "Cajero", 2, "¿Dentro de los 15 días?")
    d.nodo("tiempo", "end", "Cliente", 3, "Devolución rechazada por tiempo")
    d.nodo("t2", "task", "Supervisor", 3, "Inspeccionar estado físico, empaque y accesorios")
    d.nodo("g2", "gate", "Supervisor", 4, "¿Estado óptimo?")
    d.nodo("dano", "end", "Cliente", 4, "Devolución rechazada por daño")
    d.nodo("t3", "task", "Supervisor", 5, "Ingresar la clave de autenticación del Supervisor")
    d.nodo("t4", "task", "Cajero", 6, "Emitir nota de crédito o reembolso y reingresar la serie", dato="Nota de crédito / entrada a stock")
    d.nodo("ok", "end", "Cliente", 7, "Devolución procesada con éxito")
    d.flujo("s", "t1", sa="b", sb="l")
    d.flujo("t1", "g1")
    d.flujo("g1", "tiempo", "No", sa="t", sb="l")
    d.flujo("g1", "t2", "Sí", sa="b", sb="l")
    d.flujo("t2", "g2")
    d.flujo("g2", "dano", "No", sa="t", sb="b")
    d.flujo("g2", "t3", "Sí")
    d.flujo("t3", "t4")
    d.flujo("t4", "ok", sa="r", sb="b")
    return d


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre, fab in [("1_consulta_y_traslado", consulta), ("2_venta_directa", venta),
                        ("3_apartado", apartado), ("4_devolucion", devolucion)]:
        (SALIDA / f"{nombre}.svg").write_text(fab().svg(), encoding="utf-8")
        print("escrito", nombre)


if __name__ == "__main__":
    main()
