"""
Dynamic data-stream scenario generator for RMQ experiments.

The assignment asks for creative stream planning on top of rmq_data.csv:
  - diverse arrival time windows
  - insert / delete frequencies
  - multiple load patterns

Events are replayed against any DynamicRMQBase implementation.  A parallel
Python list is maintained as ground truth so query accuracy can be checked.
"""

from __future__ import annotations

import random
import time
import tracemalloc
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Iterable, List, Sequence

from rmq_common import DynamicRMQBase, DynamicRunStats, naive_rmq


class Op(Enum):
    APPEND = auto()
    INSERT = auto()
    DELETE = auto()
    QUERY = auto()


@dataclass(frozen=True)
class Event:
    op: Op
    # APPEND: value
    # INSERT: index, value
    # DELETE: index
    # QUERY: left, right
    a: int = 0
    b: int = 0


def _qi(rng: random.Random, n: int) -> tuple[int, int]:
    """Random valid closed query on a sequence of length n."""
    left = rng.randint(0, n - 1)
    right = rng.randint(left, n - 1)
    return left, right


def scenario_burst_arrival(source: Sequence[int], rng: random.Random) -> List[Event]:
    """
    Wave 1: rapid appends (dense arrivals).
    Wave 2: query-only burst on the stabilized prefix.
    """
    events: List[Event] = []
    take = min(len(source), 4000)
    for v in source[:take]:
        events.append(Event(Op.APPEND, v))
    for _ in range(800):
        l, r = _qi(rng, take)
        events.append(Event(Op.QUERY, l, r))
    return events


def scenario_update_heavy(source: Sequence[int], rng: random.Random) -> List[Event]:
    """
    Warm-start with a moderate prefix, then many inserts/deletes and few queries.
    Models a high update/query ratio.
    """
    events: List[Event] = []
    warm = min(len(source), 1500)
    for v in source[:warm]:
        events.append(Event(Op.APPEND, v))
    cursor = warm
    live = warm
    for i in range(2000):
        roll = rng.random()
        if roll < 0.45 and cursor < len(source):
            idx = rng.randint(0, live)
            events.append(Event(Op.INSERT, idx, source[cursor]))
            cursor += 1
            live += 1
        elif roll < 0.85 and live > 10:
            idx = rng.randint(0, live - 1)
            events.append(Event(Op.DELETE, idx))
            live -= 1
        elif live > 0:
            l, r = _qi(rng, live)
            events.append(Event(Op.QUERY, l, r))
    return events


def scenario_query_heavy(source: Sequence[int], rng: random.Random) -> List[Event]:
    """
    Fill a window, then mostly queries with rare mutations.
    Models a low update/query ratio (static-like stream).
    """
    events: List[Event] = []
    warm = min(len(source), 3000)
    for v in source[:warm]:
        events.append(Event(Op.APPEND, v))
    cursor = warm
    live = warm
    for i in range(2500):
        roll = rng.random()
        if roll < 0.05 and cursor < len(source):
            events.append(Event(Op.APPEND, source[cursor]))
            cursor += 1
            live += 1
        elif roll < 0.08 and live > 10:
            idx = rng.randint(0, live - 1)
            events.append(Event(Op.DELETE, idx))
            live -= 1
        else:
            l, r = _qi(rng, live)
            events.append(Event(Op.QUERY, l, r))
    return events


def scenario_mixed_waves(source: Sequence[int], rng: random.Random) -> List[Event]:
    """
    Alternating temporal windows:
      arrive-heavy → query-heavy → churn → query-heavy.
    """
    events: List[Event] = []
    cursor = 0
    live = 0

    def arrive(k: int) -> None:
        nonlocal cursor, live
        for _ in range(k):
            if cursor >= len(source):
                return
            events.append(Event(Op.APPEND, source[cursor]))
            cursor += 1
            live += 1

    def queries(k: int) -> None:
        for _ in range(k):
            if live <= 0:
                return
            l, r = _qi(rng, live)
            events.append(Event(Op.QUERY, l, r))

    def churn(k: int) -> None:
        nonlocal cursor, live
        for _ in range(k):
            if live <= 5:
                break
            if rng.random() < 0.5 and cursor < len(source):
                idx = rng.randint(0, live)
                events.append(Event(Op.INSERT, idx, source[cursor]))
                cursor += 1
                live += 1
            else:
                idx = rng.randint(0, live - 1)
                events.append(Event(Op.DELETE, idx))
                live -= 1

    arrive(1200)
    queries(400)
    churn(600)
    queries(500)
    arrive(800)
    queries(400)
    return events


def scenario_sliding_churn(source: Sequence[int], rng: random.Random) -> List[Event]:
    """
    Sliding-window style: append to the right, delete from the left, with
    intermittent range-min queries on the active window.
    """
    events: List[Event] = []
    window = 1000
    for v in source[:window]:
        events.append(Event(Op.APPEND, v))
    live = window
    for v in source[window : window + 2500]:
        events.append(Event(Op.APPEND, v))
        live += 1
        events.append(Event(Op.DELETE, 0))  # drop oldest
        live -= 1
        if rng.random() < 0.25 and live > 0:
            l, r = _qi(rng, live)
            events.append(Event(Op.QUERY, l, r))
    return events


SCENARIO_BUILDERS: dict[str, Callable[[Sequence[int], random.Random], List[Event]]] = {
    "burst_arrival": scenario_burst_arrival,
    "update_heavy": scenario_update_heavy,
    "query_heavy": scenario_query_heavy,
    "mixed_waves": scenario_mixed_waves,
    "sliding_churn": scenario_sliding_churn,
}


def build_scenario(name: str, source: Sequence[int], seed: int = 7) -> List[Event]:
    if name not in SCENARIO_BUILDERS:
        raise KeyError(f"Unknown scenario: {name}")
    return SCENARIO_BUILDERS[name](source, random.Random(seed))


def replay_stream(
    factory: Callable[[], DynamicRMQBase],
    events: Sequence[Event],
    scenario_name: str,
    verify_every_query: bool = True,
) -> DynamicRunStats:
    """
    Replay events on a fresh structure.  Optionally verify each query against
    a parallel ground-truth list (accuracy / stability metric).
    """
    structure = factory()
    truth: List[int] = []
    stats = DynamicRunStats(name=structure.name, scenario=scenario_name, n_events=len(events))

    tracemalloc.start()
    t_all = time.perf_counter()

    for ev in events:
        if ev.op is Op.APPEND:
            t0 = time.perf_counter()
            structure.append(ev.a)
            stats.time_append += time.perf_counter() - t0
            truth.append(ev.a)
            stats.n_append += 1
        elif ev.op is Op.INSERT:
            t0 = time.perf_counter()
            structure.insert(ev.a, ev.b)
            stats.time_insert += time.perf_counter() - t0
            truth.insert(ev.a, ev.b)
            stats.n_insert += 1
        elif ev.op is Op.DELETE:
            t0 = time.perf_counter()
            structure.delete(ev.a)
            stats.time_delete += time.perf_counter() - t0
            del truth[ev.a]
            stats.n_delete += 1
        elif ev.op is Op.QUERY:
            t0 = time.perf_counter()
            ans = structure.query(ev.a, ev.b)
            stats.time_query += time.perf_counter() - t0
            stats.n_query += 1
            if verify_every_query:
                expected = naive_rmq(truth, ev.a, ev.b)
                if ans == expected:
                    stats.correct_queries += 1
                else:
                    stats.failed_queries += 1
        else:
            raise RuntimeError(f"Unhandled op {ev.op}")

    stats.time_total = time.perf_counter() - t_all
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    stats.peak_memory_bytes = peak
    stats.structure_bytes = structure.structure_nbytes_estimate()
    stats.final_length = len(structure)
    stats.notes = structure.describe_extra()
    # Stability proxy: fraction of verified queries that matched ground truth.
    stats.extras = {
        "accuracy": (
            stats.correct_queries / stats.n_query if stats.n_query else 1.0
        ),
        "update_query_ratio": (
            (stats.n_insert + stats.n_delete + stats.n_append) / max(1, stats.n_query)
        ),
    }
    return stats


def all_scenario_names() -> Iterable[str]:
    return SCENARIO_BUILDERS.keys()
