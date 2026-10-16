"""
Assignment harness: static baseline + dynamic stream comparison.

Runs:
  1) Static baseline on rmq_data.csv — proposed method + three taught methods.
  2) Dynamic stream scenarios — same event logs for all four methods.
  3) Prints comparison tables and a final cross-scenario summary.
"""

from __future__ import annotations

import time
from typing import List, Sequence

from rmq_block_decomposition import BlockDecompositionRMQ
from rmq_common import (
    DATA_PATH,
    DynamicRunStats,
    build_with_metrics,
    format_bytes,
    load_array,
    make_queries,
    naive_rmq,
    timed_queries,
)
from rmq_dynamic_adapters import DYNAMIC_EMPTY_FACTORIES
from rmq_fischer_heun import FischerHeunRMQ
from rmq_proposed import APTreapRMQ
from rmq_sparse_table import SparseTableRMQ
from rmq_stream import all_scenario_names, build_scenario, replay_stream

# Full static array is large; Sparse Table build is heavy but required by the assignment.
# Stream study uses a prefix so rebuild-based baselines remain tractable.
STREAM_SOURCE_LIMIT = 20_000


def _print_static_section(arr: Sequence[int]) -> None:
    print("=" * 100)
    print("PART A — STATIC BASELINE (no stream; fixed dataset on the table)")
    print("=" * 100)
    n = len(arr)
    print(f"Data file : {DATA_PATH.name}")
    print(f"n         : {n:,}")
    print()

    builders = [
        APTreapRMQ,
        SparseTableRMQ,
        BlockDecompositionRMQ,
        FischerHeunRMQ,
    ]

    structures = []
    build_stats = []
    for cls in builders:
        print(f"Building {cls.name} ...")
        structure, stats = build_with_metrics(cls, arr)
        if isinstance(structure, APTreapRMQ):
            stats.insert_complexity = structure.insert_complexity
            stats.delete_complexity = structure.delete_complexity
        else:
            stats.insert_complexity = "N/A (immutable)"
            stats.delete_complexity = "N/A (immutable)"
        structures.append(structure)
        build_stats.append(stats)
        print(
            f"  build time={stats.build_seconds:.4f}s | "
            f"peak memory={format_bytes(stats.peak_memory_bytes)} | "
            f"structure memory≈{format_bytes(stats.structure_bytes)} | {stats.extra}"
        )
    print()

    queries = make_queries(n, count=12, seed=42)
    naive_answers = [naive_rmq(arr, l, r) for l, r in queries]

    query_times: List[float] = []
    answers: List[List[int]] = []
    for structure in structures:
        elapsed, vals = timed_queries(structure.query, queries, rounds=5)
        query_times.append(elapsed)
        answers.append(vals)
        print(
            f"Query batch ({structure.name:28s}): "
            f"{elapsed * 1e3:.4f} ms  "
            f"({elapsed / len(queries) * 1e6:.3f} microseconds per query)"
        )
    print()

    print("-" * 100)
    print("Static per-query answers (all methods + naive)")
    print("-" * 100)
    header = (
        f"{'#':>2} {'Left':>8} {'Right':>8} "
        f"{'Proposed':>12} {'Sparse':>12} {'Block':>12} {'Fischer':>12} {'Naive':>12} "
        f"{'All match'}"
    )
    print(header)
    all_ok = True
    for i, (l, r) in enumerate(queries):
        vals = [answers[j][i] for j in range(4)] + [naive_answers[i]]
        match = len(set(vals)) == 1
        all_ok = all_ok and match
        print(
            f"{i + 1:>2} {l:>8} {r:>8} "
            f"{vals[0]:>12} {vals[1]:>12} {vals[2]:>12} {vals[3]:>12} {vals[4]:>12} "
            f"{'YES' if match else 'NO'}"
        )
    print(f"\nStatic accuracy (all equal naive): {'YES' if all_ok else 'NO'}")

    print()
    print("-" * 100)
    print("Static comparison table (theory + measured)")
    print("-" * 100)
    print(
        f"{'Method':28} {'Preprocess':>12} {'Insert':>18} {'Delete':>18} "
        f"{'Query':>10} {'Space':>12}"
    )
    for s in build_stats:
        print(
            f"{s.name:28} {s.preprocess_complexity:>12} {s.insert_complexity:>18} "
            f"{s.delete_complexity:>18} {s.query_complexity:>10} {s.space_complexity:>12}"
        )

    print()
    print(
        f"{'Method':28} {'Build time (s)':>14} {'Peak memory':>12} "
        f"{'Structure memory':>16} {'Microseconds per query':>22}"
    )
    for s, qt in zip(build_stats, query_times):
        print(
            f"{s.name:28} {s.build_seconds:14.4f} {format_bytes(s.peak_memory_bytes):>12} "
            f"{format_bytes(s.structure_bytes):>16} {qt / len(queries) * 1e6:22.3f}"
        )
    print()
    print("Static practical notes:")
    print("  - Sparse Table: fastest queries, highest memory, no updates.")
    print("  - Block Decomposition: lightest structure, slower queries.")
    print("  - Fischer-Heun: best classic static tradeoff (O(n)/O(1)).")
    print("  - AP-Treap: competitive static correctness; pays log n per query,")
    print("    but is the only method here that later supports true updates.")
    print()


def _print_final_scenario_summary(all_rows: List[DynamicRunStats]) -> None:
    """Cross-scenario summary table for the terminal (assignment deliverable view)."""
    print("=" * 100)
    print("PART C — FINAL SUMMARY TABLE ACROSS ALL STREAM SCENARIOS")
    print("=" * 100)
    print(
        "Each row is one (scenario, method) pair on the same event log. "
        "Times are wall-clock seconds; accuracy is vs naive ground truth."
    )
    print()
    print(
        f"{'Scenario':16} "
        f"{'Method':32} "
        f"{'Total time (s)':>14} "
        f"{'Query time (s)':>14} "
        f"{'Peak memory':>12} "
        f"{'Accuracy':>8} "
        f"{'Update/query ratio':>18} "
        f"{'Failed queries':>14}"
    )
    print("-" * 140)

    for s in all_rows:
        print(
            f"{s.scenario:16} "
            f"{s.name:32} "
            f"{s.time_total:14.4f} "
            f"{s.time_query:14.4f} "
            f"{format_bytes(s.peak_memory_bytes):>12} "
            f"{s.extras.get('accuracy', 0):8.3f} "
            f"{s.extras.get('update_query_ratio', 0):18.2f} "
            f"{s.failed_queries:14d}"
        )

    print()
    print("-" * 100)
    print("Fastest method per scenario (by total time)")
    print("-" * 100)
    print(
        f"{'Scenario':16} "
        f"{'Fastest method':32} "
        f"{'Total time (s)':>14} "
        f"{'Accuracy':>8} "
        f"{'Update/query ratio':>18}"
    )
    scenarios = []
    for s in all_rows:
        if s.scenario not in scenarios:
            scenarios.append(s.scenario)
    for scenario in scenarios:
        group = [r for r in all_rows if r.scenario == scenario]
        best = min(group, key=lambda r: r.time_total)
        print(
            f"{scenario:16} "
            f"{best.name:32} "
            f"{best.time_total:14.4f} "
            f"{best.extras.get('accuracy', 0):8.3f} "
            f"{best.extras.get('update_query_ratio', 0):18.2f}"
        )
    print()


def _print_dynamic_section(source: Sequence[int]) -> List[DynamicRunStats]:
    print("=" * 100)
    print("PART B — DYNAMIC DATA STREAM (insert / delete / query on live state)")
    print("=" * 100)
    print(f"Stream source prefix : {len(source):,} values from {DATA_PATH.name}")
    print(f"Scenarios            : {', '.join(all_scenario_names())}")
    print()

    print("-" * 100)
    print("Dynamic theory table (eager costs for classics; AP-Treap true dynamic)")
    print("-" * 100)
    print(
        f"{'Method':32} {'Preprocess':>12} {'Insert':>14} {'Delete':>14} "
        f"{'Query':>14} {'Memory':>12}"
    )
    theory_rows = [
        ("AP-Treap (Proposed)", "O(1)*", "O(log n)", "O(log n)", "O(log n)", "O(n)"),
        ("Sparse Table (rebuild)", "O(n log n)", "O(n log n)", "O(n log n)", "O(1)", "O(n log n)"),
        ("Block Decomposition (rebuild)", "O(n)", "O(n)", "O(n)", "O(√n)", "O(n)"),
        ("Fischer-Heun (rebuild)", "O(n)", "O(n)", "O(n)", "O(1)", "O(n)"),
    ]
    for row in theory_rows:
        print(f"{row[0]:32} {row[1]:>12} {row[2]:>14} {row[3]:>14} {row[4]:>14} {row[5]:>12}")
    print("* proposed starts empty in the stream; pulse absorbs appends.")
    print("Measured classic policy = lazy rebuild-on-query (see README.md).")
    print()

    all_rows: List[DynamicRunStats] = []

    for scenario in all_scenario_names():
        events = build_scenario(scenario, source, seed=7)
        print("=" * 100)
        print(f"Scenario: {scenario}   | event count={len(events)}")
        print("=" * 100)

        rows: List[DynamicRunStats] = []
        for name, factory in DYNAMIC_EMPTY_FACTORIES.items():
            print(f"  running {name} ...", flush=True)
            stats = replay_stream(factory, events, scenario_name=scenario, verify_every_query=True)
            rows.append(stats)
            all_rows.append(stats)
            acc = stats.extras.get("accuracy", 0.0)
            uqr = stats.extras.get("update_query_ratio", 0.0)
            print(
                f"    total time={stats.time_total:.4f}s | "
                f"insert time={stats.time_insert:.4f}s | "
                f"delete time={stats.time_delete:.4f}s | "
                f"append time={stats.time_append:.4f}s | "
                f"query time={stats.time_query:.4f}s | "
                f"peak memory={format_bytes(stats.peak_memory_bytes)} | "
                f"accuracy={acc:.3f} | "
                f"update/query ratio={uqr:.2f} | "
                f"failed queries={stats.failed_queries}"
            )

        print()
        print(
            f"{'Method':32} "
            f"{'Total time (s)':>14} "
            f"{'Insert time (s)':>15} "
            f"{'Delete time (s)':>15} "
            f"{'Append time (s)':>15} "
            f"{'Query time (s)':>14} "
            f"{'Peak memory':>12} "
            f"{'Accuracy':>8} "
            f"{'Failed queries':>14}"
        )
        for s in rows:
            print(
                f"{s.name:32} "
                f"{s.time_total:14.4f} "
                f"{s.time_insert:15.4f} "
                f"{s.time_delete:15.4f} "
                f"{s.time_append:15.4f} "
                f"{s.time_query:14.4f} "
                f"{format_bytes(s.peak_memory_bytes):>12} "
                f"{s.extras.get('accuracy', 0):8.3f} "
                f"{s.failed_queries:14d}"
            )
        print()

    _print_final_scenario_summary(all_rows)

    print("-" * 100)
    print("Decision guide (where what fits)")
    print("-" * 100)
    print("  Load pattern              | Prefer")
    print("  --------------------------|-------------------------------")
    print("  Static / query-only       | Fischer-Heun or Sparse Table")
    print("  Memory-tight static       | Block Decomposition")
    print("  Append-heavy stream       | AP-Treap (pulse helps)")
    print("  Update-heavy stream       | AP-Treap (true O(log n) updates)")
    print("  Sliding-window churn      | AP-Treap")
    print("  Rare updates, many queries| Lazy Fischer-Heun rebuild may compete")
    print()
    return all_rows


def main() -> None:
    t0 = time.perf_counter()
    arr = load_array()
    print(f"Loaded {len(arr):,} values in {time.perf_counter() - t0:.3f}s\n")

    _print_static_section(arr)

    stream_source = arr[:STREAM_SOURCE_LIMIT]
    _print_dynamic_section(stream_source)

    print("=" * 100)
    print("Done. See final_experiment_report.md for the full written experiment report.")
    print("=" * 100)


if __name__ == "__main__":
    main()
