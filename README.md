# TecnoStock — Apartados, ventas y devoluciones

**Producto Integrador de Aprendizaje (PIA)** · Componentes de Lógica de Negocio · FIME UANL · Equipo 5
Repositorio: https://github.com/Exatoon27/tecnostock-pia · Sistema desplegado: https://tecnostock-7k73.onrender.com (panel en `/`, Swagger en `/docs`; plan gratuito: si lleva un rato sin visitas, tarda en despertar)

---

## Para el negocio

TecnoStock es una cadena de 5 tiendas de electrónica. Este sistema controla tres cosas que hoy generan errores:

1. **Apartados.** El cliente deja al menos el 20 % y la pieza queda reservada 30 días. Si no liquida, la pieza se libera y el anticipo queda como saldo a favor (con 10 % de penalización). Nadie puede vender por error una pieza apartada.
2. **Ventas con número de serie.** Cada equipo se vende con su serie, y si se paga con varios métodos la suma debe ser exacta.
3. **Devoluciones.** Se aceptan dentro de 15 días, con empaque y accesorios completos, y siempre con la clave de un Supervisor.

### Cómo usarlo
Abre el sistema en el navegador (`http://localhost:8000/`). Arriba a la derecha eliges tu puesto (Cajero, Vendedor, Supervisor, Almacén o Administrador).

| Quiero… | Dónde |
|---|---|
| Ver los apartados y cuánto debe cada cliente | Pestaña **Apartados** |
| Cobrar un abono o entregar un apartado ya pagado | Botón en la tarjeta del apartado |
| Apartar una pieza | **Nuevo apartado** |
| Vender | **Nueva venta** |
| Recibir una devolución | **Registrar devolución** (pide la clave del Supervisor) |
| Mover una pieza a otra tienda | **Nuevo traslado**; después Almacén la despacha y la tienda destino la recibe, escaneando la serie (pestaña **Traslados**) |
| Ver qué piezas hay y en qué tienda | Pestaña **Inventario** |
| Liberar los apartados que ya vencieron | **Revisar apartados vencidos** |

El panel nunca muestra códigos técnicos: si algo no se puede hacer, explica por qué ("El anticipo debe ser al menos 20 % del total…", "El puesto de Almacén no tiene permiso para esta operación").

### Qué incluye hoy y qué no
Funciona: ventas con serie y pagos combinados, apartados completos, devoluciones con Supervisor, **traslados entre sucursales**, consulta de existencias y permisos por puesto.
Todavía no: avisos programados a 5 y 2 días, recepción de lotes, ajustes de inventario, facturación, garantías, modo sin red y reportes. Detalle en [`docs/BRD.md`](docs/BRD.md) y [`docs/trazabilidad.md`](docs/trazabilidad.md).

---

## Para Sistemas (instalación, ejecución y pruebas)

### Con Docker (recomendado)
```bash
docker compose up --build                         # PostgreSQL + aplicación -> http://localhost:8000
docker compose --profile tests run --rm tests     # pruebas contra PostgreSQL real
docker compose down -v                            # apaga y borra los datos
```
La configuración va por variables de entorno (12-Factor). Copia `.env.example` a `.env` para cambiar usuario, contraseña o puerto; no se suben secretos.

| URL | Para quién |
|---|---|
| `/` | Panel del negocio |
| `/docs` · `/openapi.json` | Documentación técnica de la API (Swagger) |

### Despliegue en Render (plan gratuito)
El archivo `render.yaml` describe la aplicación (con el `Dockerfile`) y su base PostgreSQL.
1. Crear cuenta en [render.com](https://render.com) (se puede entrar con GitHub) y darle acceso a este repositorio.
2. **New → Blueprint**, elegir el repositorio y confirmar. Render construye la imagen, crea la base y conecta ambas con `DATABASE_URL`.
3. La URL pública abre el panel en `/` y Swagger en `/docs`. Ya está publicado en la dirección indicada arriba.

Notas del plan gratuito: el servicio se apaga tras 15 minutos sin visitas y tarda en despertar (abrirlo antes de una demostración); la base gratuita expira a los 30 días.

### Sin Docker
```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1   |   Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest --cov=src --cov-fail-under=80    # 327 pasan y 4 (PostgreSQL) se omiten sin TEST_DATABASE_URL
python -m ruff check src tests
uvicorn src.api.main:app --reload                 # http://127.0.0.1:8000/
```
Persistencia: sin `DATABASE_URL` usa **memoria**; con `sqlite+pysqlite:///./tecnostock.db` o `postgresql+psycopg://…` usa **SQLAlchemy**.
Las peticiones llevan `X-Rol: CAJERO|VENDEDOR|SUPERVISOR|ALMACEN|ADMINISTRADOR|SISTEMA`.

### Estructura
```
docs/
  BRD.md                 requerimientos del negocio (lenguaje de negocio)
  trazabilidad.md        necesidad -> historia -> regla -> componente -> prueba
  analisis/              U2: BRD, User Stories con Gherkin, glosario, BPMN (+ bpmn/ legible)
  architecture/          U3: ADR, diagramas DDD y de secuencia, informe, matriz de trazabilidad
  api/openapi.json       contrato de la API
  evidencias/            resultados de pruebas, cobertura, CI y capturas del panel
src/
  domain/                Aggregates (Apartado, ItemSerie, Venta), Value Objects, Specifications,
                         Domain Events, política de devolución, interfaces de repositorio
  application/           servicios de aplicación, Commands/Queries/DTOs (CQRS), manejadores de eventos
  infrastructure/        repositorios + Unit of Work (memoria y SQLAlchemy), bus de eventos,
                         pasarela de pagos simulada, carga de CSV, contenedor
  api/                   FastAPI + panel (panel.html)
tests/                   unitarias, integración (SQLite y PostgreSQL), mocks, autorización, API, panel
.github/workflows/       CI: lint, pruebas con cobertura >= 80 %, escenarios, integración con PostgreSQL
Dockerfile · docker-compose.yml · .env.example
```

### Reglas y dónde viven
Ver la tabla completa en [`docs/trazabilidad.md`](docs/trazabilidad.md). Resumen:

| Regla | Dónde vive | Prueba |
|---|---|---|
| Anticipo ≥ 20 % (y ≤ total) | `PorcentajeAnticipo`, `AnticipoMinimoSpec`, `Apartado.crear` | E01, E02 |
| Máx. 3 apartados activos por cliente | `LimiteApartadosSpec` | E04 |
| Serie reservada no se vende ni se reserva de nuevo | `ItemSerie`, `SerieDisponibleSpec` | E05, E13 |
| Vigencia 30 días: día 30 vigente, día 31 vence | `Apartado.evaluar_vencimiento` | E09, E10 |
| Penalización 10 % → saldo a favor | `Apartado` | E10 |
| Abonos ≤ saldo; no se abona a un apartado vencido | `Apartado` | E07, E08, E11 |
| Venta: serie obligatoria y pagos = total | `Venta.cerrar` | `tests/test_dominio.py` |
| Devolución ≤ 15 días, empaque y accesorios, sin daño del cliente | `DEVOLUCION_ELEGIBLE` | E14, E15 |
| Devolución exige clave de Supervisor | `PoliticaDevolucionDomainService` | `tests/` |

Estados de `Apartado`: ACTIVO → LIQUIDADO → ENTREGADO; ACTIVO → VENCIDO.
Estados de `ItemSerie`: DISPONIBLE → RESERVADO → (liberada | VENDIDO); VENDIDO → DISPONIBLE (devolución); DISPONIBLE → RESERVADO_TRASLADO → EN_TRANSITO → DISPONIBLE en la sucursal destino (traslado). `EN_GARANTIA` existe en el enum para las garantías.
Estados de `Transferencia`: PENDIENTE_DESPACHO → EN_TRANSITO → RECIBIDA.

### API (referencia técnica; detalle en `/docs`)
| Método y ruta | Caso de uso | Códigos |
|---|---|---|
| `GET /stock?sku=&sucursal_id=` | consulta de existencias (US-01) | 200 |
| `POST /apartados` | apartar (US-03) | 201, 404, 422 |
| `GET /apartados/{folio}` | consulta | 200, 404 |
| `POST /apartados/{folio}/abonos` | abono | 200, 404, 409, 422 |
| `POST /apartados/{folio}/entrega` | entrega | 200, 404, 409 |
| `POST /procesos/vencimientos` | vencimiento de apartados (US-05) | 200 |
| `POST /ventas` | venta con serie (US-02, US-12) | 201, 404, 409, 422 |
| `POST /devoluciones` | devolución (US-09, US-10) | 201, 403, 404, 409, 422 |
| `POST /transferencias` | pedir un traslado (US-07) | 201, 403, 404, 422 |
| `GET /transferencias/{folio}` | consultar un traslado | 200, 404 |
| `POST /transferencias/{folio}/despacho` | despachar con escaneo de serie (US-08) | 200, 403, 404, 409, 422 |
| `POST /transferencias/{folio}/recepcion` | recibir con escaneo de serie (US-08) | 200, 403, 404, 409, 422 |

Transversales: 401 sin o con `X-Rol` desconocido, 403 sin permiso, 402 pago rechazado, 503 pasarela sin respuesta.
Las fechas se reciben en el cuerpo (`fecha`) para pruebas deterministas; por omisión usan hoy.
Las claves de Supervisor de demostración están en `datos/supervisores.csv` (ficticias).

### Calidad
331 pruebas con PostgreSQL (327 sin él) · cobertura 99 % (umbral 80 %) · 57 casos en `docs/matriz_pruebas.csv` · escenarios E01–E20 idénticos en memoria y SQL · 14/14 mutaciones detectadas · CI en `.github/workflows/ci.yml`. Evidencias en `docs/evidencias_U5.md` y `docs/evidencias/`.

### Límites conocidos
- La autenticación es un encabezado `X-Rol` (no hay inicio de sesión real); la autorización por puesto y la clave del Supervisor sí se aplican.
- El proceso de vencimientos se ejecuta a demanda; no hay programador nocturno.
- Los eventos se publican tras el commit sin outbox: si el proceso cae justo después, se pierden.
- La pasarela de pagos y los avisos SMS/correo son simulados.
- Fuera de alcance por ahora: avisos a 5 y 2 días, recepción de lotes, ajustes, facturación, garantías, contingencia sin red y reportes.

Ver también [`docs/trazabilidad_y_diferencias.md`](docs/trazabilidad_y_diferencias.md).
