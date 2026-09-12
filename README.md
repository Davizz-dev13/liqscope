# LiqScope

Dashboard propio de liquidaciones de futuros de cripto: cuánto se liquida por hora, día, semana y mes, separando posiciones largas de cortas.

**[Ver el dashboard](https://davizz-dev13.github.io/liqscope/)**

## Cómo funciona

- **Datos**: [Coinalyze API v1](https://api.coinalyze.net/v1/doc/) (`/liquidation-history`). Por cada moneda se agregan todos sus futuros perpetuos (USDT/USD/USDC) de todos los exchanges que cubre la API, en USD.
- **Recolección**: GitHub Action cada hora (`collect.yml`) que actualiza `docs/data/*.json`. Coinalyze solo conserva ~2 meses de granularidad horaria, así que el histórico horario vive en este repo y crece solo; el diario se relee entero en cada corrida (la API no lo purga).
- **Página**: estática en `docs/` (GitHub Pages), sin backend. Selector de moneda (BTC, ETH, SOL, DOGE, XRP) y de periodo (hora / día / semana / mes), con barras apiladas largos vs cortos.

## Configuración

1. Crear una API key gratuita en [coinalyze.net](https://coinalyze.net/account/api-key/) (registro de 1 minuto).
2. En el repo: Settings → Secrets and variables → Actions → `COINALYZE_API_KEY` con la key.
3. Lanzar el workflow "Recolectar liquidaciones" a mano con `backfill=true` una vez para cargar el histórico inicial.

Monedas seguidas: constante `COINS` en `scripts/collect.py`.

## Aviso

Proyecto personal de seguimiento, no asesoramiento financiero.
