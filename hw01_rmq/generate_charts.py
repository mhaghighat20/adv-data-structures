"""
Generate comparison charts from experiment_terminal_output.txt.

Outputs PNG files under charts/ for use in comparison_report.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "charts"
SOURCE = ROOT / "experiment_terminal_output.txt"

SHORT_NAMES = {
    "AP-Treap (Proposed)": "AP-Treap",
    "Sparse Table": "Sparse",
    "Sparse Table (rebuild)": "Sparse",
    "Block Decomposition": "Block",
    "Block Decomposition (rebuild)": "Block",
    "Fischer-Heun": "Fischer",
    "Fischer-Heun (rebuild)": "Fischer",
}

METHOD_ORDER = ["AP-Treap", "Sparse", "Block", "Fischer"]
METHOD_COLORS = {
    "AP-Treap": "#1f77b4",
    "Sparse": "#ff7f0e",
    "Block": "#2ca02c",
    "Fischer": "#d62728",
}


def _to_bytes(value: float, unit: str) -> float:
    unit = unit.upper()
    factor = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}[unit]
    return value * factor


def parse_terminal_output(text: str) -> tuple[dict, list[dict]]:
    """Return (static_metrics, dynamic_rows)."""
    static: dict[str, dict] = {}
    dynamic: list[dict] = []

    # build time=... | peak memory=... | structure memory≈...
    build_re = re.compile(
        r"Building (?P<name>.+?) \.\.\.\n"
        r"\s+build time=(?P<build>[0-9.]+)s \| "
        r"peak memory=(?P<peak>[0-9.]+) (?P<peak_u>B|KB|MB|GB) \| "
        r"structure memory≈(?P<struct>[0-9.]+) (?P<struct_u>B|KB|MB|GB)",
        re.M,
    )
    for m in build_re.finditer(text):
        name = SHORT_NAMES.get(m.group("name").strip(), m.group("name").strip())
        static.setdefault(name, {})
        static[name]["build_s"] = float(m.group("build"))
        static[name]["peak_bytes"] = _to_bytes(float(m.group("peak")), m.group("peak_u"))
        static[name]["struct_bytes"] = _to_bytes(float(m.group("struct")), m.group("struct_u"))

    q_re = re.compile(
        r"Query batch \((?P<name>.+?)\s*\):\s+"
        r"[0-9.]+ ms\s+\((?P<us>[0-9.]+) microseconds per query\)"
    )
    for m in q_re.finditer(text):
        name = SHORT_NAMES.get(m.group("name").strip(), m.group("name").strip())
        static.setdefault(name, {})
        static[name]["us_per_query"] = float(m.group("us"))

    # PART C summary rows
    row_re = re.compile(
        r"^(?P<scenario>burst_arrival|update_heavy|query_heavy|mixed_waves|sliding_churn)\s+"
        r"(?P<method>.+?)\s+"
        r"(?P<total>[0-9.]+)\s+"
        r"(?P<query>[0-9.]+)\s+"
        r"(?P<mem>[0-9.]+)\s+(?P<mem_u>B|KB|MB|GB)\s+"
        r"(?P<acc>[0-9.]+)\s+"
        r"(?P<uqr>[0-9.]+)\s+"
        r"(?P<fail>\d+)\s*$",
        re.M,
    )
    for m in row_re.finditer(text):
        method = SHORT_NAMES.get(m.group("method").strip(), m.group("method").strip())
        dynamic.append(
            {
                "scenario": m.group("scenario"),
                "method": method,
                "total_s": float(m.group("total")),
                "query_s": float(m.group("query")),
                "peak_bytes": _to_bytes(float(m.group("mem")), m.group("mem_u")),
                "accuracy": float(m.group("acc")),
                "update_query_ratio": float(m.group("uqr")),
                "failed": int(m.group("fail")),
            }
        )

    return static, dynamic


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.grid": True,
            "grid.alpha": 0.25,
            "font.size": 10,
        }
    )


def _grouped_bars(
    scenarios: list[str],
    series: dict[str, list[float]],
    ylabel: str,
    title: str,
    path: Path,
    log_scale: bool = False,
) -> None:
    x = np.arange(len(scenarios))
    n = len(METHOD_ORDER)
    width = 0.8 / n
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for i, method in enumerate(METHOD_ORDER):
        vals = series[method]
        ax.bar(
            x + (i - (n - 1) / 2) * width,
            vals,
            width,
            label=method,
            color=METHOD_COLORS[method],
        )
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios, rotation=15, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if log_scale:
        ax.set_yscale("log")
    ax.legend(ncols=4, loc="upper center", bbox_to_anchor=(0.5, 1.14))
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def _static_bars(static: dict[str, dict], key: str, ylabel: str, title: str, path: Path, log_scale: bool = False) -> None:
    methods = [m for m in METHOD_ORDER if m in static]
    vals = [static[m][key] for m in methods]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    colors = [METHOD_COLORS[m] for m in methods]
    ax.bar(methods, vals, color=colors)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if log_scale:
        ax.set_yscale("log")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.3g}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def _heatmap(scenarios: list[str], series: dict[str, list[float]], title: str, path: Path, cbar_label: str) -> None:
    mat = np.array([series[m] for m in METHOD_ORDER], dtype=float)
    fig, ax = plt.subplots(figsize=(10, 4.2))
    im = ax.imshow(mat, aspect="auto", cmap="YlOrRd")
    ax.set_xticks(range(len(scenarios)))
    ax.set_xticklabels(scenarios, rotation=15, ha="right")
    ax.set_yticks(range(len(METHOD_ORDER)))
    ax.set_yticklabels(METHOD_ORDER)
    ax.set_title(title)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            ax.text(j, i, f"{mat[i, j]:.3g}", ha="center", va="center", fontsize=8)
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label(cbar_label)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def _speedup_vs_sparse(scenarios: list[str], totals: dict[str, list[float]], path: Path) -> None:
    sparse = np.array(totals["Sparse"], dtype=float)
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(scenarios))
    for method in ["AP-Treap", "Block", "Fischer"]:
        speedup = sparse / np.maximum(np.array(totals[method], dtype=float), 1e-12)
        ax.plot(x, speedup, marker="o", linewidth=2, label=method, color=METHOD_COLORS[method])
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=1, label="Sparse baseline (=1)")
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios, rotation=15, ha="right")
    ax.set_ylabel("Speedup vs Sparse (total time)")
    ax.set_title("Relative speedup versus Sparse Table across stream scenarios")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    _style()
    OUTPUT_DIR.mkdir(exist_ok=True)
    text = SOURCE.read_text(encoding="utf-8")
    static, dynamic = parse_terminal_output(text)
    if not dynamic:
        raise SystemExit("No dynamic rows parsed. Run: python main.py  (then re-run this script)")

    scenarios = []
    for row in dynamic:
        if row["scenario"] not in scenarios:
            scenarios.append(row["scenario"])

    def series(field: str) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {m: [] for m in METHOD_ORDER}
        for sc in scenarios:
            for method in METHOD_ORDER:
                hit = next(r for r in dynamic if r["scenario"] == sc and r["method"] == method)
                val = hit[field]
                if field == "peak_bytes":
                    val = val / (1024 * 1024)  # MB
                out[method].append(val)
        return out

    totals = series("total_s")
    queries = series("query_s")
    peaks = series("peak_bytes")

    _grouped_bars(
        scenarios,
        totals,
        ylabel="Total time (s)",
        title="Stream scenarios: total runtime by method",
        path=OUTPUT_DIR / "stream_total_time.png",
        log_scale=True,
    )
    _grouped_bars(
        scenarios,
        queries,
        ylabel="Query time (s)",
        title="Stream scenarios: query time by method",
        path=OUTPUT_DIR / "stream_query_time.png",
        log_scale=True,
    )
    _grouped_bars(
        scenarios,
        peaks,
        ylabel="Peak memory (MB)",
        title="Stream scenarios: peak memory by method",
        path=OUTPUT_DIR / "stream_peak_memory.png",
        log_scale=False,
    )
    _heatmap(
        scenarios,
        totals,
        title="Heatmap of total runtime (seconds)",
        path=OUTPUT_DIR / "stream_total_time_heatmap.png",
        cbar_label="seconds",
    )
    _speedup_vs_sparse(scenarios, totals, OUTPUT_DIR / "stream_speedup_vs_sparse.png")

    if static:
        _static_bars(
            static,
            "build_s",
            "Build time (s)",
            "Static baseline: preprocess / build time (n=1,000,000)",
            OUTPUT_DIR / "static_build_time.png",
            log_scale=True,
        )
        _static_bars(
            static,
            "us_per_query",
            "Microseconds per query",
            "Static baseline: query latency",
            OUTPUT_DIR / "static_query_latency.png",
            log_scale=True,
        )
        # convert peak to MB for chart
        static_mb = {
            m: {**static[m], "peak_mb": static[m]["peak_bytes"] / (1024 * 1024)}
            for m in static
        }
        _static_bars(
            static_mb,
            "peak_mb",
            "Peak memory (MB)",
            "Static baseline: peak memory during build",
            OUTPUT_DIR / "static_peak_memory.png",
            log_scale=True,
        )

    print(f"Wrote charts to {OUTPUT_DIR}")
    for p in sorted(OUTPUT_DIR.glob("*.png")):
        print(f"  - {p.name}")


if __name__ == "__main__":
    main()
