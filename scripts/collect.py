#!/usr/bin/env python3
"""Colector de liquidaciones crypto (Coinalyze API v1) -> docs/data/.

- Agrega por moneda todos sus futuros perpetuos con quote USD/USDT/USDC de
  todos los exchanges que cubre Coinalyze (base_asset + is_perpetual).
- Intervalo horario: upsert de las ultimas horas; backfill inicial ~62 dias
  (Coinalyze solo conserva 1500-2000 puntos intradia; el archivo del repo es
  el archivo historico definitivo).
- Intervalo diario: historico completo (Coinalyze no purga el diario).

Requiere COINALYZE_API_KEY en el entorno (repo secret). Si falta, sale sin
error para no ensuciar el historial de Actions.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.coinalyze.net/v1"
KEY = os.environ.get("COINALYZE_API_KEY", "").strip()
COINS = ["BTC", "ETH", "SOL", "DOGE", "XRP"]
DATA = Path("docs/data")
BACKFILL_SECONDS = 62 * 86400
DAILY_SINCE = 1567296000  # 2019-09-01, arranque de los perps de BTC
REFETCH_HOURS = 8         # horas que se releen en cada corrida (upsert)
MAX_SYMS_PER_CALL = 20    # limite de la API
RATE_WEIGHT_PER_MIN = 40  # peso por minuto; cada simbolo pesa 1

def get(path, **params):
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{API}/{path}?{qs}", headers={"api_key": KEY})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                payload = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                wait = 20 * (attempt + 1)
                print(f"429 rate limit, reintento en {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise
    # respetar el peso del rate limit (1 por simbolo consultado)
    n = len(str(params.get("symbols", "")).split(",")) if params.get("symbols") else 1
    time.sleep(max(1.0, 60.0 * n / RATE_WEIGHT_PER_MIN))
    return payload

QUOTE_OK = {"USD", "USDT", "USDC"}  # excluye cruces (ETHBTC) y quotes exoticos

def perp_symbols(coin, markets):
    """Todos los perps de la moneda en cualquier exchange (quote USD/USDT/USDC)."""
    return sorted({m["symbol"] for m in markets
                   if m.get("base_asset") == coin
                   and m.get("is_perpetual")
                   and m.get("quote_asset") in QUOTE_OK})

def fetch_liq(symbols, interval, ts_from, ts_to):
    """Devuelve {t: [long, short]} agregando todos los simbolos."""
    agg = {}
    for i in range(0, len(symbols), MAX_SYMS_PER_CALL):
        chunk = symbols[i:i + MAX_SYMS_PER_CALL]
        resp = get("liquidation-history", symbols=",".join(chunk),
                   interval=interval, **{"from": ts_from, "to": ts_to,
                                         "convert_to_usd": "true"})
        for mkt in resp:
            for row in mkt.get("history", []):
                t = int(row["t"])
                slot = agg.setdefault(t, [0.0, 0.0])
                slot[0] += float(row.get("l") or 0.0)
                slot[1] += float(row.get("s") or 0.0)
    return agg

def load_points(path, key):
    if path.exists():
        try:
            return {int(p[0]): [float(p[1]), float(p[2])]
                    for p in json.loads(path.read_text()).get(key, [])}
        except Exception:
            pass
    return {}

def main():
    if not KEY:
        print("COINALYZE_API_KEY no configurada; se omite la recoleccion.")
        return
    backfill = "--backfill" in sys.argv
    now = int(time.time())
    DATA.mkdir(parents=True, exist_ok=True)
    markets = get("future-markets")
    meta_coins = []
    for coin in COINS:
        syms = perp_symbols(coin, markets)
        if not syms:
            print(f"{coin}: sin mercados perp, se omite")
            continue
        path = DATA / f"{coin.lower()}.json"
        hourly = load_points(path, "hourly")
        daily = load_points(path, "daily")
        h_from = now - BACKFILL_SECONDS if (backfill or not hourly) \
            else max(hourly) - REFETCH_HOURS * 3600
        h = fetch_liq(syms, "1hour", h_from, now + 3600)
        hourly.update(h)
        d = fetch_liq(syms, "daily", DAILY_SINCE, now + 86400)
        daily.update(d)
        out = {
            "coin": coin,
            "exchanges": len(syms),
            "hourly": [[t, round(v[0], 2), round(v[1], 2)]
                       for t, v in sorted(hourly.items())],
            "daily": [[t, round(v[0], 2), round(v[1], 2)]
                      for t, v in sorted(daily.items())],
        }
        path.write_text(json.dumps(out, separators=(",", ":")))
        meta_coins.append({"coin": coin, "symbols": len(syms),
                           "hourly_points": len(hourly), "daily_points": len(daily)})
        print(f"{coin}: {len(syms)} perps | hourly {len(h)} nuevos ({len(hourly)} total) | daily {len(d)} ({len(daily)} total)", flush=True)
    meta = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "Coinalyze API v1 (agregado de todos los exchanges por moneda)",
            "coins": meta_coins}
    (DATA / "meta.json").write_text(json.dumps(meta, indent=2))
    print("OK")

if __name__ == "__main__":
    main()
