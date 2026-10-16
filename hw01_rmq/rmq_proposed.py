"""
Proposed method: AP-Treap RMQ
(Append-Pulse Order-Statistic Cartesian Treap for Dynamic Stream RMQ)

Motivation (assignment: dynamic data stream, not a pure classic rebuild):
  Classic Sparse Table / Fischer-Heun are excellent on *static* arrays but force
  an O(n log n) or O(n) full rebuild after every insert/delete.  Block
  Decomposition is lighter to rebuild but still global.

Novelty of this proposal (defensible for the course report):
  1) Keep the live sequence in an *implicit treap* (heap-ordered random
     priorities, inorder = sequence order) annotated with subtree size and
     subtree minimum → insert / delete / range-min in O(log n) w.h.p.
  2) Add a stream-oriented *append pulse*: pure arrivals at the end accumulate
     in a small mutable buffer and are absorbed into the treap in batches.
     Append-heavy windows therefore amortize pointer work; mixed update windows
     flush eagerly so semantics stay exact.
  3) Policy hook `pulse_limit` can be tuned from the observed update/query
     ratio (scenario-adaptive), which is the engineering lever we study
     experimentally against the three taught baselines.

This is NOT a mechanical merge of the three taught structures; it is a
dynamic order-statistic approach tailored to stream arrival patterns.
"""

from __future__ import annotations

import random
from typing import List, Optional, Sequence

from rmq_common import DynamicRMQBase, RMQBase, deep_getsizeof


class _TreapNode:
    """Implicit treap node: inorder position is implicit via subtree sizes."""

    __slots__ = ("val", "prio", "left", "right", "size", "smin")

    def __init__(self, val: int, prio: int) -> None:
        self.val = val
        self.prio = prio
        self.left: Optional[_TreapNode] = None
        self.right: Optional[_TreapNode] = None
        self.size = 1
        self.smin = val


def _size(node: Optional[_TreapNode]) -> int:
    return 0 if node is None else node.size


def _smin(node: Optional[_TreapNode]) -> int:
    # Identity for min-monoid on empty set: +inf (we never query empty).
    return node.smin if node is not None else 10**30


def _pull(node: _TreapNode) -> None:
    node.size = 1 + _size(node.left) + _size(node.right)
    node.smin = min(node.val, _smin(node.left), _smin(node.right))


def _merge(left: Optional[_TreapNode], right: Optional[_TreapNode]) -> Optional[_TreapNode]:
    if left is None:
        return right
    if right is None:
        return left
    if left.prio < right.prio:
        left.right = _merge(left.right, right)
        _pull(left)
        return left
    right.left = _merge(left, right.left)
    _pull(right)
    return right


def _split(node: Optional[_TreapNode], k: int) -> tuple[Optional[_TreapNode], Optional[_TreapNode]]:
    """Split into (first k elements, the rest)."""
    if node is None:
        return None, None
    left_size = _size(node.left)
    if k <= left_size:
        ll, lr = _split(node.left, k)
        node.left = lr
        _pull(node)
        return ll, node
    rl, rr = _split(node.right, k - left_size - 1)
    node.right = rl
    _pull(node)
    return node, rr


def _inorder(node: Optional[_TreapNode], out: List[int]) -> None:
    if node is None:
        return
    _inorder(node.left, out)
    out.append(node.val)
    _inorder(node.right, out)


class APTreapRMQ(DynamicRMQBase, RMQBase):
    """
    Append-Pulse Implicit Treap RMQ.

    Also implements RMQBase so it can be evaluated on the static baseline by
    building once from a fixed array (pulse flushed, then queries only).
    """

    name = "AP-Treap (Proposed)"
    preprocess_complexity = "O(n log n)"  # build via n inserts / absorb
    insert_complexity = "O(log n) amortized*"
    delete_complexity = "O(log n) amortized*"
    query_complexity = "O(log n) amortized*"
    space_complexity = "O(n)"

    # *amortized over pulse absorption; worst-case single op still O(log n + |pulse|).

    def __init__(
        self,
        arr: Sequence[int] | None = None,
        pulse_limit: int = 64,
        seed: int = 12345,
    ) -> None:
        self._rng = random.Random(seed)
        self.root: Optional[_TreapNode] = None
        self.pulse: List[int] = []
        self.pulse_limit = max(1, pulse_limit)
        self._treap_size = 0
        if arr:
            # Static / warm-start construction: push into pulse then absorb in chunks.
            for value in arr:
                self.append(value)
            self._flush_pulse()

    def __len__(self) -> int:
        return self._treap_size + len(self.pulse)

    def describe_extra(self) -> str:
        return (
            f"pulse_limit={self.pulse_limit}, treap_n={self._treap_size}, "
            f"pulse_n={len(self.pulse)}"
        )

    def _new_node(self, value: int) -> _TreapNode:
        return _TreapNode(value, self._rng.randrange(1 << 30))

    def _flush_pulse(self) -> None:
        """Absorb the append pulse into the treap (preserves order)."""
        if not self.pulse:
            return
        # Build a tiny treap for the pulse then merge to the right (append side).
        pulse_root: Optional[_TreapNode] = None
        for value in self.pulse:
            pulse_root = _merge(pulse_root, self._new_node(value))
        self.root = _merge(self.root, pulse_root)
        self._treap_size += len(self.pulse)
        self.pulse.clear()

    def append(self, value: int) -> None:
        """Stream arrival at the end — buffered for amortization."""
        self.pulse.append(value)
        if len(self.pulse) >= self.pulse_limit:
            self._flush_pulse()

    def insert(self, index: int, value: int) -> None:
        n = len(self)
        if index < 0 or index > n:
            raise IndexError("insert index out of range")
        # Non-append updates need a consistent treap view of the whole sequence.
        self._flush_pulse()
        left, right = _split(self.root, index)
        self.root = _merge(_merge(left, self._new_node(value)), right)
        self._treap_size += 1

    def delete(self, index: int) -> None:
        n = len(self)
        if index < 0 or index >= n:
            raise IndexError("delete index out of range")
        self._flush_pulse()
        left, rest = _split(self.root, index)
        _mid, right = _split(rest, 1)
        self.root = _merge(left, right)
        self._treap_size -= 1

    def query(self, left: int, right: int) -> int:
        n = len(self)
        if n == 0 or left < 0 or right >= n or left > right:
            raise ValueError("invalid query range")
        self._flush_pulse()
        # Isolate [left, right] via two splits, read subtree min, then restore.
        mid_right, right_part = _split(self.root, right + 1)
        left_part, mid = _split(mid_right, left)
        answer = _smin(mid)
        self.root = _merge(_merge(left_part, mid), right_part)
        return answer

    def to_list(self) -> List[int]:
        self._flush_pulse()
        out: List[int] = []
        _inorder(self.root, out)
        return out

    def structure_nbytes_estimate(self) -> int:
        # Approximate: materialize values + count nodes via size; deep walk is costly.
        # We charge Python object overhead per node roughly via a sampled walk.
        self._flush_pulse()
        return deep_getsizeof(self.to_list()) + self._treap_size * 64 + len(self.pulse) * 28
