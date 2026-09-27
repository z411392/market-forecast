from __future__ import annotations

import argparse
import csv
import hashlib
import math
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

START_DATE = date(2022, 7, 18)
TRAIN_END = date(2025, 11, 25)
EVAL_START = date(2025, 12, 4)
H = 5
BLOCK = 20
REPS = 5000
SEED = 20260926
TOL = 1e-12

HASHES = {
    "GOOGL": "2c09055672391ba0724d0918ddc86f621254154be20ef457c28b7a62f6ff34ba",
    "NVDA": "99323dc9644f2a5955f1b6119b2d75c7c6dcce8c7b2938be81c610871c5dc54c",
    "QQQ": "18fd0c5050c348516f616da8abcc764707f4aa669b7ba022a12ce1362954243e",
    "TSM": "f66835e9328fbe261472a8a693efb898ee144b1d90cfb38c0732037cc58abec4",
    "2330": "e26c29335402363c4a1b8aae35bb26e63bb1577bed74173f5b914f7258ca3d47",
    "2317": "98a0b83bb2ced641603a6b248853a0fc288a80d06cae4f8212ab813d54866c5c",
    "2454": "791626c2890e5aad95d19abc4e4c84586686394b9f81b4fa2d53363465792847",
}
FORECAST = {
    "har": "P4_FORECAST_HAR_LEVEL_VAR5",
    "garch": "P4_FORECAST_GARCH_VAR5",
    "harq": "P4_FORECAST_HARQ_VAR5",
    "ewma": "P4_FORECAST_EWMA_VAR5",
    "naive": "P4_FORECAST_NAIVE_VAR5",
}
EXPORTED = {
    "har": "P4_QLIKE_HAR",
    "garch": "P4_QLIKE_GARCH",
    "harq": "P4_QLIKE_HARQ",
    "ewma": "P4_QLIKE_EWMA",
    "naive": "P4_QLIKE_NAIVE",
}
MODELS = ("global", "har", "garch", "harq", "ewma", "naive")
COMPARISONS = (
    ("har", "global"),
    ("garch", "global"),
    ("har", "garch"),
    ("harq", "har"),
    ("ewma", "har"),
    ("naive", "har"),
)


def args():
    p = argparse.ArgumentParser(description="Replay Task #13 final Pine comparator")
    for s in ("googl", "nvda", "qqq", "tsm", "2330", "2317", "2454"):
        p.add_argument(f"--{s}", type=Path, required=True)
    p.add_argument("--output-dir", type=Path)
    return p.parse_args()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def num(row, key):
    value = row[key].strip()
    return float(value) if value else math.nan


def mean_roll(values, window):
    out = np.full(values.size, np.nan)
    for i in range(window - 1, values.size):
        sample = values[i - window + 1 : i + 1]
        if np.all(np.isfinite(sample)):
            out[i] = sample.mean()
    return out


def load(symbol, market, path):
    dates, counts, rv = [], [], []
    forecasts = {name: [] for name in FORECAST}
    exported = {name: [] for name in EXPORTED}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"time", "P4_INTRABAR_COUNT_5M", "P4_RV_WHOLE_DAY_5M", *FORECAST.values(), *EXPORTED.values()}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{symbol}: missing columns {sorted(missing)}")
        for row in reader:
            d = datetime.fromtimestamp(int(float(row["time"])), tz=timezone.utc).date()
            if d < START_DATE:
                continue
            dates.append(d)
            counts.append(num(row, "P4_INTRABAR_COUNT_5M"))
            rv.append(num(row, "P4_RV_WHOLE_DAY_5M"))
            for name, column in FORECAST.items():
                forecasts[name].append(num(row, column))
            for name, column in EXPORTED.items():
                exported[name].append(num(row, column))
    dates = np.array(dates, dtype=object)
    counts = np.array(counts, dtype=float)
    rv = np.array(rv, dtype=float)
    count_ok = np.isin(counts, [78.0, 42.0]) if market == "us" else counts == 53.0
    rv = np.where(count_ok & np.isfinite(rv) & (rv > 0), rv, np.nan)
    rv5, rv22 = mean_roll(rv, 5), mean_roll(rv, 22)
    y5 = np.full(rv.size, np.nan)
    for i in range(rv.size - H):
        future = rv[i + 1 : i + H + 1]
        if np.all(np.isfinite(future)):
            y5[i] = future.mean()
    with np.errstate(divide="ignore", invalid="ignore"):
        xd, xw, z = np.log(rv / rv22), np.log(rv5 / rv22), np.log(y5 / rv22)
    return {
        "dates": dates,
        "rv22": rv22,
        "y5": y5,
        "xd": xd,
        "xw": xw,
        "z": z,
        "forecast": {k: np.array(v, dtype=float) for k, v in forecasts.items()},
        "exported": {k: np.array(v, dtype=float) for k, v in exported.items()},
    }


def eligible(panel):
    return np.isfinite(panel["rv22"]) & np.isfinite(panel["y5"]) & np.isfinite(panel["xd"]) & np.isfinite(panel["xw"]) & np.isfinite(panel["z"])


def train_rows(data, held):
    xs, ys = [], []
    for symbol, panel in data.items():
        if symbol == held:
            continue
        before = np.array([d <= TRAIN_END for d in panel["dates"]], dtype=bool)
        mask = eligible(panel) & before
        xs.append(np.column_stack((panel["xd"][mask], panel["xw"][mask])))
        ys.append(panel["z"][mask])
    return np.vstack(xs), np.concatenate(ys)


def qlike(actual, predicted):
    ratio = actual / predicted
    return ratio - np.log(ratio) - 1.0


def evaluate(data, held):
    panel = data[held]
    mask = eligible(panel) & np.array([d >= EVAL_START for d in panel["dates"]], dtype=bool)
    for forecast in panel["forecast"].values():
        mask &= np.isfinite(forecast) & (forecast > 0)
    tx, ty = train_rows(data, held)
    scaler = StandardScaler().fit(tx)
    model = Ridge(alpha=1.0).fit(scaler.transform(tx), ty)
    test_x = np.column_stack((panel["xd"][mask], panel["xw"][mask]))
    global_pred = panel["rv22"][mask] * np.exp(model.predict(scaler.transform(test_x)))
    losses = {"global": qlike(panel["y5"][mask], global_pred)}
    for name, forecast in panel["forecast"].items():
        losses[name] = qlike(panel["y5"][mask], forecast[mask])
    return {"dates": panel["dates"][mask], "mask": mask, "losses": losses}


def block_ci(values):
    rng = np.random.default_rng(SEED)
    starts = np.arange(values.size - BLOCK + 1)
    blocks = math.ceil(values.size / BLOCK)
    means = np.empty(REPS)
    for i in range(REPS):
        chosen = rng.choice(starts, size=blocks, replace=True)
        sample = np.concatenate([values[start : start + BLOCK] for start in chosen])[: values.size]
        means[i] = sample.mean()
    lo, hi = np.quantile(means, [0.025, 0.975])
    return float(values.mean()), float(lo), float(hi)


def date_means(evals, markets, model, market):
    by_date = {}
    for symbol, result in evals.items():
        if market is not None and markets[symbol] != market:
            continue
        for d, loss in zip(result["dates"], result["losses"][model], strict=True):
            by_date.setdefault(d, []).append(float(loss))
    return np.array([np.mean(by_date[d]) for d in sorted(by_date)], dtype=float)


def alignment(data, evals, markets):
    rows, worst = [], 0.0
    for symbol, panel in data.items():
        for name in FORECAST:
            diffs = []
            for origin in np.flatnonzero(evals[symbol]["mask"]):
                matured = origin + H
                if matured >= panel["dates"].size or not np.isfinite(panel["exported"][name][matured]):
                    continue
                calc = qlike(np.array([panel["y5"][origin]]), np.array([panel["forecast"][name][origin]]))[0]
                diffs.append(abs(float(calc - panel["exported"][name][matured])))
            if not diffs:
                raise AssertionError(f"{symbol} {name}: no alignment overlap")
            maximum = max(diffs)
            worst = max(worst, maximum)
            rows.append({"symbol": symbol, "market": markets[symbol], "model": name, "n_overlap": len(diffs), "max_abs_diff": maximum})
    if worst > TOL:
        raise AssertionError(f"alignment worst={worst:.17g} > {TOL:.17g}")
    return rows


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    a = args()
    specs = (
        ("GOOGL", "us", a.googl), ("NVDA", "us", a.nvda), ("QQQ", "us", a.qqq), ("TSM", "us", a.tsm),
        ("2330", "taiwan", getattr(a, "2330")), ("2317", "taiwan", getattr(a, "2317")), ("2454", "taiwan", getattr(a, "2454")),
    )
    for symbol, _, path in specs:
        if sha(path) != HASHES[symbol]:
            raise ValueError(f"{symbol}: input hash mismatch")
    markets = {symbol: market for symbol, market, _ in specs}
    data = {symbol: load(symbol, market, path) for symbol, market, path in specs}
    evals = {symbol: evaluate(data, symbol) for symbol in data}
    parity = alignment(data, evals, markets)
    per_symbol = [
        {"symbol": symbol, "market": markets[symbol], "n_eval": result["dates"].size, **{f"{model}_qlike": float(result["losses"][model].mean()) for model in MODELS}}
        for symbol, result in evals.items()
    ]
    bootstrap = []
    for scope, market in (("overall", None), ("us", "us"), ("taiwan", "taiwan")):
        losses = {model: date_means(evals, markets, model, market) for model in MODELS}
        for first, second in COMPARISONS:
            mean, lo, hi = block_ci(losses[first] - losses[second])
            bootstrap.append({"scope": scope, "comparison": f"{first}_minus_{second}", "n_dates": len(losses[first]), "mean_delta": mean, "ci_025": lo, "ci_975": hi})
    if a.output_dir is not None:
        write_csv(a.output_dir / "per_symbol_qlike.csv", per_symbol)
        write_csv(a.output_dir / "bootstrap_comparisons.csv", bootstrap)
        write_csv(a.output_dir / "alignment_parity.csv", parity)
    print("PASS", max(row["max_abs_diff"] for row in parity))
    for row in bootstrap:
        print(row)


if __name__ == "__main__":
    main()
