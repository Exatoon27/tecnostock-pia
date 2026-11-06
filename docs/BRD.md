# TecnoStock — Documento de Requerimientos del Negocio (BRD)

**Equipo 5** · Componentes de Lógica de Negocio · FIME UANL · versión integrada para el PIA (6 nov 2026)
**Origen:** BRD de U2 (10/09/2026), refinado con las reglas del levantamiento y con el estado real de la solución.
**Cómo leerlo:** está escrito para quien dirige el negocio. Los términos técnicos se explican en el [glosario](analisis/Glosario_U2.pdf); la correspondencia con el código está en [trazabilidad.md](trazabilidad.md).

---

## 1. Contexto

TecnoStock es una cadena de **cinco tiendas** de electrónica (equipos de cómputo, telefonía, accesorios y componentes). Vende en mostrador y ofrece **apartados**: el cliente deja un anticipo y la tienda le reserva la pieza por un tiempo limitado. Cada tienda maneja su propio inventario físico y, para los productos de alto valor, cada pieza se identifica con un **número de serie único** desde que llega al almacén hasta que se entrega al cliente.

Procesos del día a día: venta en caja, control de existencias, apartados, traslados de mercancía entre tiendas, devoluciones y garantías.

## 2. Problemas que se quieren resolver

| Código | Problema | Causa | Impacto en el negocio |
|---|---|---|---|
| ISS-01 | El inventario del sistema no coincide con el físico | Las 5 tiendas no se sincronizan en tiempo real | Falsos agotados, cancelaciones y ventas perdidas |
| ISS-02 | Se vende por error una pieza que ya estaba apartada | El sistema no la bloquea al recibir el anticipo | Clientes molestos, reembolsos forzados, daño a la reputación |
| ISS-03 | Es difícil rastrear números de serie | Captura manual o fragmentada en caja y traslados | Garantías complicadas, riesgo de fraude, demoras en almacén |
| ISS-04 | Las devoluciones se aceptan con criterios distintos | Depende del criterio de cada empleado | Pérdidas por mercancía no elegible y discusiones en caja |

## 3. Oportunidad

| Qué se busca | Resultado esperado |
|---|---|
| Inventario unificado de las 5 tiendas, actualizado tras cada operación | Saber con exactitud qué hay y vender entre sucursales |
| Reserva automática de la pieza en cuanto hay un anticipo | Cero ventas de piezas apartadas |
| Escaneo obligatorio del número de serie en recepción, cobro y traslado | Historial confiable de cada pieza y garantías más ágiles |
| Políticas de postventa validadas por el sistema | Criterio uniforme en toda la cadena y menos pérdidas |

## 4. Quién participa

| Rol | Qué hace |
|---|---|
| Cliente | Elige productos, paga completo o aparta con anticipo, pide devoluciones o garantías |
| Vendedor | Asesora, consulta existencias en toda la red y formaliza ventas o traslados |
| Cajero | Cobra, escanea las series, emite comprobantes y recibe devoluciones |
| Supervisor | Autoriza cancelaciones y devoluciones, aprueba ajustes de inventario y traslados |
| Almacén | Recibe mercancía, captura series, empaca y confirma la llegada entre tiendas |

## 5. Alcance

1. **Inventario unificado y series:** estado en tiempo real de cada pieza (Disponible, Reservada, En tránsito) en las 5 tiendas; la serie se escanea para entrar o salir.
2. **Cobro y facturación:** efectivo, tarjeta y pagos combinados; comprobante fiscal con las series vendidas.
3. **Apartados:** anticipo desde 20 %, bloqueo de la pieza, cuenta regresiva de 30 días y avisos al cliente.
4. **Traslados entre tiendas:** solicitud, despacho, tránsito y recepción con doble escaneo de serie.
5. **Devoluciones y servicio técnico:** plazo de 15 días, estado físico del producto y clave del Supervisor.

## 6. Necesidades

| ID | Necesidad | Descripción | Prioridad |
|---|---|---|---|
| N-01 | Stock global | Ver y actualizar en tiempo real las existencias de las 5 tiendas | Alta |
| N-02 | Bloqueo por apartado | Descontar de lo vendible cualquier pieza con anticipo mínimo del 20 % | Alta |
| N-03 | Serie obligatoria | Exigir el número de serie en comprobantes y movimientos de almacén | Alta |
| N-04 | Devoluciones controladas | Aplicar plazos y exigir la clave del Supervisor | Media |
| N-05 | Traslados entre tiendas | Solicitar, enviar y rastrear traslados | Media |
| N-06 | Avisos de vencimiento | Recordar al cliente por SMS y correo antes de que venza su apartado | Baja |

## 7. Restricciones

| ID | Tipo | Regla | Efecto en el sistema |
|---|---|---|---|
| CON-01 | Operativa | Las búsquedas de disponibilidad o serie responden en **menos de 3 segundos** | Consultas rápidas sin detener las cajas |
| CON-02 | Seguridad | **Solo el Supervisor** autoriza cancelaciones y devoluciones | Se pide su clave antes de continuar |
| CON-03 | Técnica | No se cierra una venta o despacho si falta leer la serie | Se niega el ticket o la guía |
| CON-04 | Privacidad | Los datos de clientes cumplen la ley de protección de datos personales | Datos sensibles protegidos y poco visibles |
| CON-05 | Infraestructura | Las tiendas operan con internet comercial estándar | Debe existir una opción local si se cae la red |

## 8. Supuestos

| ID | Supuesto | Si falla |
|---|---|---|
| ASM-01 | Las 5 tiendas tienen internet continuo y lectores de código en cada caja | Se detiene el cobro; se necesita modo contingencia |
| ASM-02 | Las laptops y celulares traen número de serie legible desde fábrica | Se retrasa la recepción en almacén |
| ASM-03 | El personal adoptará el sistema y capturará todos los datos | Errores de captura y resistencia al cambio |

## 9. Cómo sabremos que funcionó

| ID | Meta | Cómo se mide |
|---|---|---|
| SCR-01 | 0 % de ventas por error de piezas apartadas | Quejas e incidencias del mes |
| SCR-02 | 100 % de coincidencia entre series físicas y registradas | Auditorías periódicas de inventario |
| SCR-03 | 30 % menos tiempo en caja con productos de serie | Marcas de tiempo del sistema |
| SCR-04 | 0 % de devoluciones fuera de política o sin clave de Supervisor | Auditoría del registro de operaciones |

## 10. Reglas del negocio (lo que el sistema debe respetar)

Resumen de las 20 respuestas del levantamiento. La columna **Estado** indica qué hace hoy la solución (detalle y pruebas en [trazabilidad.md](trazabilidad.md)).

| ID | Regla | Estado |
|---|---|---|
| RN-01 | El anticipo de un apartado es de **al menos 20 %** del precio; no puede pasar del total | Implementada |
| RN-02 | Un apartado dura **30 días naturales**. El día 30 sigue vigente; al cumplirse el día 31 vence | Implementada |
| RN-03 | Al vencer, la pieza vuelve a estar disponible y el anticipo **no se devuelve en efectivo**: queda como saldo a favor con **penalización de 10 %** | Implementada |
| RN-04 | Un cliente puede tener **máximo 3 apartados activos** a la vez | Implementada |
| RN-05 | Al registrar el anticipo, la pieza queda **reservada** y ya no se puede vender a otra persona | Implementada |
| RN-06 | Se avisa al cliente **5 y 2 días antes** del vencimiento, por SMS y correo | No implementada (solo hay aviso simulado al vencer) |
| RN-07 | Devolución: dentro de **15 días**, con empaque original y accesorios completos, y **clave del Supervisor** | Implementada |
| RN-08 | Si el daño es culpa del cliente, la devolución se bloquea; si es falla de fábrica, hay cambio o nota de crédito | Parcial (hay nota de crédito; no distingue el cambio directo) |
| RN-09 | El Cajero solo elige método de pago, escanea series y captura datos de facturación; descuentos especiales, cancelaciones y devoluciones son del Supervisor | Parcial (permisos por puesto sí; facturación no) |
| RN-10 | Almacén solo consulta existencias, registra entradas y salidas y confirma traslados; no toca precios ni garantías | Implementada (permisos por puesto) |
| RN-11 | Un número de serie **no puede repetirse** en toda la cadena | Implementada |
| RN-12 | Los productos con serie **no se venden sin ella** | Implementada |
| RN-13 | Si se paga con varios métodos, la **suma debe ser exactamente el total** | Implementada |
| RN-14 | Los pagos con tarjeta pasan por el banco: aprobado, rechazado o sin servicio | Implementada (banco simulado) |
| RN-15 | Traslado: solicitud → pieza reservada → en tránsito → recepción con segundo escaneo | No implementada |
| RN-16 | En la recepción de mercancía se escanea cada serie; no se guarda el lote si falta alguna | No implementada (las series iniciales se cargan por archivo) |
| RN-17 | Un ajuste de inventario requiere solicitud de Almacén y firma del Supervisor | No implementada |
| RN-18 | La factura se genera en **máximo 24 horas** con las series vinculadas | No implementada |
| RN-19 | Una pieza enviada a garantía con el proveedor sale del inventario vendible | No implementada |
| RN-20 | Si se cae la red, la caja trabaja en modo local y sincroniza al volver | No implementada |
| RN-21 | Un apartado exige datos del cliente (nombre, celular, correo) y de la pieza (SKU, serie, precio, anticipo, sucursal) | Implementada |
| RN-22 | La consulta de existencias muestra, por tienda, las piezas disponibles, reservadas y en tránsito, y responde en menos de 3 segundos | Parcial (sin "en tránsito"; el tiempo no se midió) |

## 11. Qué incluye esta entrega y qué no

**Funciona hoy:** ventas con serie y pagos combinados, apartados completos (anticipo, abonos, entrega, vencimiento y saldo a favor), devoluciones con clave de Supervisor, consulta de existencias y permisos por puesto. Se opera desde un **panel en lenguaje de negocio**; la parte técnica (API) queda para el equipo de Sistemas.

**Pendiente (planeado, no incluido):** traslados entre tiendas, avisos programados a 5 y 2 días, recepción de lotes, ajustes de inventario, facturación, garantías con proveedor, modo sin red y reportes. Cada uno aparece en la matriz de trazabilidad como "No implementado".

## 12. Supuestos del equipo por validar con el cliente

- El apartado vence al cumplirse el día 31; la devolución procede hasta el día 15 inclusive.
- Si el anticipo cubre el total, el apartado nace ya pagado.
- Almacén puede entregar un apartado ya liquidado.
- En el panel, el puesto se elige a mano; en producción lo daría el inicio de sesión de cada empleado.
