# Integración continua: secuencia verde → rojo → verde

Corridas reales de GitHub Actions (`.github/workflows/ci.yml`, trabajos `calidad` e `Integracion con PostgreSQL`).

| # | Resultado | Rama / commit | Corrida |
|---|---|---|---|
| 1 | **Verde** | `main` · "Despliegue en Render: render.yaml, URL de base adaptada al driver…" | https://github.com/Exatoon27/tecnostock-pia/actions/runs/42308452869 |
| 2 | **Rojo** | `ci-demo-rojo` · "Fallo controlado: aserción sin penalización (CI en rojo a propósito)" | https://github.com/Exatoon27/tecnostock-pia/actions/runs/42310506186 |
| 3 | **Verde** | `ci-demo-rojo` · "Revertir el fallo controlado: la prueba vuelve a exigir la penalización del 10 %" | https://github.com/Exatoon27/tecnostock-pia/actions/runs/42310610407 |

**Qué se hizo:** en una rama aparte se cambió a propósito la aserción de `test_penalizacion_10_por_ciento_calculada_en_el_dominio`
para que ignorara la penalización del 10 %. El trabajo `calidad` falló (rojo) y el trabajo de PostgreSQL siguió en verde.
Luego se revirtió el commit y el pipeline volvió a verde. La rama `ci-demo-rojo` no se fusiona con `main`, que es la que está desplegada.
