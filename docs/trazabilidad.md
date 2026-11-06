# Trazabilidad: necesidad → historia → regla → componente → prueba

Todo lo de esta tabla se puede comprobar en el repositorio. Las pruebas están en `tests/`; los casos **CP-xx** son filas de [`matriz_pruebas.csv`](matriz_pruebas.csv) y los **E01–E15** son los escenarios de [`bitacora.md`](../bitacora.md).
Estado: **Implementado** · **Parcial** (se explica qué falta) · **No implementado** (planeado).

## 1. Las 15 historias de usuario

| Historia | Regla | Componente (código) | Pruebas | Estado |
|---|---|---|---|---|
| US-01 Consultar disponibilidad en las 5 tiendas | RN-22 · N-01 · CON-01 | `ConsultarStockGlobalQueryHandler`, `GET /stock` (disponibles, reservadas y en tránsito), panel › Inventario | `test_stock_query`, `test_stock_global_agrupa_por_sku_y_sucursal`, `test_stock_global_filtra_por_sucursal_y_no_modifica`, `test_consulta_de_stock_sobre_sql`, CP-54, CP-55 | **Implementado** (la prueba CP-55 verifica que responde en menos de 3 s con los datos de demostración) |
| US-02 Vender capturando la serie | RN-12 · N-03 | `Venta.cerrar`, `NumeroSerie`, `VentaApplicationService.procesar_venta_directa` | CP-22, CP-23, E13 | **Implementado** (la serie se elige/captura; no hay lector de código de barras) |
| US-03 Apartar con anticipo mínimo de 20 % | RN-01 · RN-21 · N-02 | `Apartado.crear`, `PorcentajeAnticipo`, `AnticipoMinimoSpec`, `ApartadoApplicationService.crear_apartado` | CP-01 a CP-04, CP-41, CP-45, CP-46, E01, E02 | **Implementado** |
| US-04 Bloquear la pieza al apartar | RN-05 · N-02 | `ItemSerie.bloquear_para_reserva`, `SerieDisponibleSpec` | CP-16, CP-19, E01, E05 | **Implementado** |
| US-05 Liberar el producto por vencimiento | RN-02 · RN-03 | `Apartado.evaluar_vencimiento`, `procesar_vencimientos`, `ApartadoVencidoEventHandler` | CP-05 a CP-09, E09, E10, E11 | **Parcial**: la regla completa funciona, pero se ejecuta a demanda (botón o `POST /procesos/vencimientos`), sin programador nocturno; el aviso es simulado |
| US-06 Recibir avisos a 5 y 2 días | RN-06 · N-06 | `Apartado.aviso_pendiente` y `registrar_aviso`, `ApartadoApplicationService.procesar_avisos`, `AvisoVencimientoEventHandler`, `POST /procesos/avisos`, panel | CP-58 a CP-63 | **Parcial**: avisa a 5 y 2 días, no repite y quien liquida deja de recibirlos; el SMS y el correo son simulados y el proceso se ejecuta a demanda, sin temporizador automático |
| US-07 Solicitar traslado entre sucursales | RN-15 · N-05 | `Transferencia.solicitar`, `ItemSerie.reservar_para_traslado`, `TransferenciaApplicationService.solicitar`, `POST /transferencias`, panel › Traslados | CP-48 a CP-50, CP-56, E16, E17 | **Implementado** |
| US-08 Confirmar salida y llegada con escaneo | RN-15 · N-05 | `Transferencia.despachar` y `recibir`, `ItemSerie.despachar` y `recibir`, `POST /transferencias/{folio}/despacho` y `/recepcion` | CP-48, CP-51 a CP-53, CP-57, E18, E19, E20 | **Implementado** (guía GT-xxxx al despachar; segundo escaneo al recibir) |
| US-09 Solicitar autorización para devolver | RN-07 | `PoliticaDevolucionDomainService`, `DentroDePlazoSpec`, `DEVOLUCION_ELEGIBLE` | CP-24, CP-28, E14, E15 | **Implementado** |
| US-10 El Supervisor autoriza o niega | RN-07 · RN-08 · CON-02 | `ISupervisorAuthDomainService`, `EmpaqueCompletoSpec`, `DanoClienteSpec` | CP-25, CP-26, CP-27, CP-40, E14 | **Implementado** (nota de crédito; el cambio directo no se distingue) |
| US-11 Escanear series al recibir mercancía | RN-11 · RN-16 | PK de `ItemSerie` (serie única), carga inicial por CSV | CP-18 | **Parcial**: la serie no puede repetirse, pero no existe el proceso de recepción de lotes |
| US-12 Cobrar con varios métodos de pago | RN-13 · RN-14 | `Venta.cerrar` (suma = total), `IPasarelaPagos` | CP-20, CP-21, CP-34 a CP-37 | **Implementado** (banco simulado) |
| US-13 Autorizar ajustes de inventario | RN-17 | — | — | **No implementado** |
| US-14 Operar sin conexión | RN-20 · CON-05 | — | — | **No implementado** |
| US-15 Reportes e indicadores | — (no hay regla propia en el levantamiento) | — | — | **No implementado** |

**Resumen:** 9 implementadas, 3 parciales y 3 no implementadas.

## 2. Necesidades, restricciones y criterios de éxito

| Elemento | Cómo lo cubre la solución | Pruebas / evidencia | Estado |
|---|---|---|---|
| N-01 Stock global | `GET /stock`, panel › Inventario | ver US-01 | Implementado |
| N-02 Bloqueo por apartado | `Apartado` + `ItemSerie` en una sola operación atómica | CP-16, CP-19, CP-31, E01, E05 | Implementado |
| N-03 Serie obligatoria | `Venta.cerrar`, serie única | CP-18, CP-22, CP-23 | Implementado |
| N-04 Devoluciones controladas | `PoliticaDevolucionDomainService` | CP-24 a CP-28 | Implementado |
| N-05 Traslados entre tiendas | `Transferencia`, `TransferenciaApplicationService`, panel › Traslados | CP-48 a CP-57, E16 a E20 | Implementado |
| N-06 Avisos de vencimiento | `procesar_avisos`, `AvisoVencimientoEventHandler` (simulado) | CP-58 a CP-63 | Parcial (simulado y a demanda) |
| CON-01 Respuesta < 3 s | consultas de lectura separadas (CQRS) | CP-55 (con los datos de demostración) | Cubierto en pruebas |
| CON-02 Solo el Supervisor autoriza | matriz de permisos por puesto + clave | CP-27, CP-38, CP-40 | Implementado |
| CON-03 No cerrar sin serie | `Venta.cerrar` | CP-22 | Implementado |
| CON-04 Datos personales | sin datos reales en el repositorio; el cliente exige nombre, teléfono y correo | CP-46 | Parcial (sin cifrado) |
| CON-05 Sin internet | — | — | No implementado |
| SCR-01 0 % ventas de piezas apartadas | la pieza reservada no se vende | CP-16, E13 | Cubierto por regla |

## 3. Decisiones de arquitectura

| Decisión (ADR de U3) | Dónde se ve en el código | Pruebas |
|---|---|---|
| ADR-01 Domain Model | `src/domain/` sin dependencias de web ni de base de datos | `test_dominio.py` |
| ADR-02 CQRS básico | `src/application/dto.py` (comandos y consultas), `ConsultarStockGlobalQueryHandler`, `ConsultarPanelQueryHandler` | CP-44, `test_panel.py` |
| ADR-03 Repository + Unit of Work | `src/domain/repositorios.py`, `src/infrastructure/memoria.py` y `sql.py` | CP-29 a CP-32, `test_postgres.py` |

## 4. Diferencias entre el diseño (U2/U3) y el código

Estas diferencias son intencionales y están justificadas en [`trazabilidad_y_diferencias.md`](trazabilidad_y_diferencias.md). Las que afectan al reporte:

- **Tecnología:** el código es **Python con FastAPI y SQLAlchemy** y la base de datos es **PostgreSQL**. Cualquier mención de SQL Server, Dapper o C# en documentos anteriores era ilustrativa y no corresponde a la implementación.
- **Nombres:** el modelo de lectura del stock se llama `StockGlobalDTO` (no `StockGlobalReadModelDTO`).
- **Traslados (CU-04):** ya existen `Transferencia` e `ITransferenciaRepository`. El servicio de aplicación se llama `TransferenciaApplicationService` (en el diseño de U3 se nombró `InventarioApplicationService`).
- Se añadieron `Cliente` y `Producto` y varias consultas a los repositorios (`listar()`, `contar_activos()`, etc.).
