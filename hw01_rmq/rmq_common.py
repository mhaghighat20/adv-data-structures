"""
Shared utilities and base interfaces for static and dynamic RMQ.

This module holds everything reused across:
  - classic static structures (Sparse Table, Block Decomposition, Fischer-Heun)
  - the proposed dynamic stream structure
  - stream scenario generation and benchmarking
"""

from __future__ import annotations

import abc
import random
import sys
import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

# Path to the one-million-element CSV supplied with the assignment.
DATA_PATH = Path(__file__).resolve().parent / "rmq_data.csv"


class RMQBase(abc.ABC):
    """
    Common interface for *static* RMQ structures.

    Contract:
      - constructed once from a fixed array
      - query(left, right) returns min on the closed interval [left, right]
    """

    name: str
    preprocess_complexity: str
    query_complexity: str
    space_complexity: str

    @abc.abstractmethod
    def query(self, left: int, right: int) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def structure_nbytes_estimate(self) -> int:
        raise NotImplementedError

    def describe_extra(self) -> str:
        """Optional method-specific details for benchmark logs."""
        return ""


class DynamicRMQBase(abc.ABC):
    """
    Interface for *dynamic* RMQ over a mutable sequence (data stream).

    Positions are 0-based indices in the *current* live sequence.
    insert(i, v) inserts v so that it becomes the element at index i.
    delete(i) removes the element currently at index i.
    """

    name: str
    preprocess_complexity: str
    insert_complexity: str
    delete_complexity: str
    query_complexity: str
    space_complexity: str

    @abc.abstractmethod
    def __len__(self) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def insert(self, index: int, value: int) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def delete(self, index: int) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def append(self, value: int) -> None:
        """Stream-friendly arrival at the end (may be specialized)."""
        raise NotImplementedError

    @abc.abstractmethod
    def query(self, left: int, right: int) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def to_list(self) -> List[int]:
        """Materialize the current sequence (for verification / naive checks)."""
        raise NotImplementedError

    @abc.abstractmethod
    def structure_nbytes_estimate(self) -> int:
        raise NotImplementedError

    def describe_extra(self) -> str:
        return ""


def load_array(path: Path = DATA_PATH) -> List[int]:
    """Load a flat comma-separated numeric array from CSV."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Empty data file: {path}")
    return [int(token) for token in text.split(",") if token.strip()]


def naive_rmq(arr: Sequence[int], left: int, right: int) -> int:
    """Brute-force RMQ for verification (ground truth)."""
    if left > right:
        raise ValueError("left must be <= right")
    return min(arr[left : right + 1])


def deep_getsizeof(obj: object, seen: set[int] | None = None) -> int:
    """Approximate deep memory size of nested Python containers."""
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)
    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        size += sum(deep_getsizeof(k, seen) + deep_getsizeof(v, seen) for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set, frozenset)):
        size += sum(deep_getsizeof(x, seen) for x in obj)
    return size


def format_bytes(num: float) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(num)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{num:.2f} B"


@dataclass
class BuildStats:
    name: str
    build_seconds: float
    peak_memory_bytes: int
    structure_bytes: int
    preprocess_complexity: str
    query_complexity: str
    space_complexity: str
    extra: str
    insert_complexity: str = "-"
    delete_complexity: str = "-"


@dataclass
class DynamicRunStats:
    """Aggregated costs while replaying one stream scenario."""

    name: str
    scenario: str
    n_events: int
    n_insert: int = 0
    n_delete: int = 0
    n_append: int = 0
    n_query: int = 0
    time_insert: float = 0.0
    time_delete: float = 0.0
    time_append: float = 0.0
    time_query: float = 0.0
    time_total: float = 0.0
    peak_memory_bytes: int = 0
    structure_bytes: int = 0
    correct_queries: int = 0
    failed_queries: int = 0
    final_length: int = 0
    notes: str = ""
    extras: dict = field(default_factory=dict)


def build_with_metrics(
    factory: Callable[[Sequence[int]], RMQBase],
    arr: Sequence[int],
) -> Tuple[RMQBase, BuildStats]:
    """Build a static RMQ and measure wall time + peak traced memory."""
    tracemalloc.start()
    t0 = time.perf_counter()
    structure = factory(arr)
    build_seconds = time.perf_counter() - t0
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    stats = BuildStats(
        name=structure.name,
        build_seconds=build_seconds,
        peak_memory_bytes=peak,
        structure_bytes=structure.structure_nbytes_estimate(),
        preprocess_complexity=structure.preprocess_complexity,
        query_complexity=structure.query_complexity,
        space_complexity=structure.space_complexity,
        extra=structure.describe_extra(),
    )
    return structure, stats


def timed_queries(
    query_fn: Callable[[int, int], int],
    queries: Sequence[Tuple[int, int]],
    rounds: int = 5,
) -> Tuple[float, List[int]]:
    """Average time of replaying a fixed query batch."""
    for left, right in queries:
        query_fn(left, right)
    t0 = time.perf_counter()
    last: List[int] = []
    for _ in range(rounds):
        last = [query_fn(left, right) for left, right in queries]
    elapsed = time.perf_counter() - t0
    return elapsed / rounds, last


def make_queries(n: int, count: int = 12, seed: int = 42) -> List[Tuple[int, int]]:
    """Deterministic mixed short/long range queries for static evaluation."""
    if n <= 0:
        return []
    fixed = [
        (0, min(9, n - 1)),
        (0, n - 1),
        (n // 10, n // 4),
        (n // 2, n // 2),
        ((3 * n) // 4, n - 1),
        (0, n // 2),
        (n // 3, (2 * n) // 3),
        (max(0, n - 100), n - 1),
    ]
    rng = random.Random(seed)
    random_q: List[Tuple[int, int]] = []
    while len(fixed) + len(random_q) < count:
        left = rng.randint(0, n - 1)
        right = rng.randint(left, n - 1)
        random_q.append((left, right))
    return fixed + random_q


def clamp_index(index: int, n: int) -> int:
    """Clamp an insert index into [0, n] (n means append)."""
    if n <= 0:
        return 0
    return max(0, min(index, n))
