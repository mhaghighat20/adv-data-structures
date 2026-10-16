"""
Dynamic adapters for the three taught *static* RMQ methods.

Taught structures do not support insert/delete natively.  We keep a live list
and use a *lazy rebuild-on-query* policy:

  - append / insert / delete only mutate the list (O(1) / O(n) list splice)
  - the static RMQ is reconstructed on the next query if the list is dirty

Theoretical eager-rebuild costs (rebuild after every mutation) are documented
in README.md for the assignment's complexity table.  Lazy rebuild is the
measured engineering policy so stream experiments finish in reasonable time
while still charging classic methods a full static preprocess whenever the
sequence changed before a query.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Type

from rmq_block_decomposition import BlockDecompositionRMQ
from rmq_common import DynamicRMQBase, RMQBase, deep_getsizeof
from rmq_fischer_heun import FischerHeunRMQ
from rmq_proposed import APTreapRMQ
from rmq_sparse_table import SparseTableRMQ


class RebuildDynamicRMQ(DynamicRMQBase):
    """Live list + lazy full rebuild of a static RMQ before queries."""

    def __init__(
        self,
        static_cls: Type[RMQBase],
        name: str,
        preprocess_complexity: str,
        insert_complexity: str,
        delete_complexity: str,
        query_complexity: str,
        space_complexity: str,
        arr: Sequence[int] | None = None,
    ) -> None:
        self._static_cls = static_cls
        self.name = name
        self.preprocess_complexity = preprocess_complexity
        # Documented *eager* complexities (assignment table); runtime uses lazy rebuild.
        self.insert_complexity = insert_complexity
        self.delete_complexity = delete_complexity
        self.query_complexity = query_complexity
        self.space_complexity = space_complexity
        self.data: List[int] = list(arr) if arr is not None else []
        self._rmq: Optional[RMQBase] = None
        self._dirty = True
        if self.data:
            self._ensure_rmq()

    def _ensure_rmq(self) -> None:
        if not self._dirty and self._rmq is not None:
            return
        if not self.data:
            self._rmq = None
            self._dirty = False
            return
        self._rmq = self._static_cls(self.data)
        self._dirty = False

    def __len__(self) -> int:
        return len(self.data)

    def append(self, value: int) -> None:
        self.data.append(value)
        self._dirty = True

    def insert(self, index: int, value: int) -> None:
        if index < 0 or index > len(self.data):
            raise IndexError("insert index out of range")
        self.data.insert(index, value)
        self._dirty = True

    def delete(self, index: int) -> None:
        if index < 0 or index >= len(self.data):
            raise IndexError("delete index out of range")
        del self.data[index]
        self._dirty = True

    def query(self, left: int, right: int) -> int:
        self._ensure_rmq()
        if self._rmq is None:
            raise ValueError("empty structure")
        return self._rmq.query(left, right)

    def to_list(self) -> List[int]:
        return list(self.data)

    def structure_nbytes_estimate(self) -> int:
        base = deep_getsizeof(self.data)
        self._ensure_rmq()
        if self._rmq is None:
            return base
        return base + self._rmq.structure_nbytes_estimate()

    def describe_extra(self) -> str:
        extra = self._rmq.describe_extra() if self._rmq is not None else "empty"
        return f"policy=lazy-rebuild-on-query, dirty={self._dirty}, n={len(self.data)}, {extra}"


def make_rebuild_sparse(arr: Sequence[int] | None = None) -> RebuildDynamicRMQ:
    return RebuildDynamicRMQ(
        SparseTableRMQ,
        name="Sparse Table (rebuild)",
        preprocess_complexity="O(n log n)",
        insert_complexity="O(n log n) eager / O(1) lazy mutate",
        delete_complexity="O(n log n) eager / O(n) list lazy",
        query_complexity="O(1) + rebuild if dirty",
        space_complexity="O(n log n)",
        arr=arr,
    )


def make_rebuild_block(arr: Sequence[int] | None = None) -> RebuildDynamicRMQ:
    return RebuildDynamicRMQ(
        BlockDecompositionRMQ,
        name="Block Decomposition (rebuild)",
        preprocess_complexity="O(n)",
        insert_complexity="O(n) eager / O(n) list lazy",
        delete_complexity="O(n) eager / O(n) list lazy",
        query_complexity="O(√n) + rebuild if dirty",
        space_complexity="O(n)",
        arr=arr,
    )


def make_rebuild_fischer(arr: Sequence[int] | None = None) -> RebuildDynamicRMQ:
    return RebuildDynamicRMQ(
        FischerHeunRMQ,
        name="Fischer-Heun (rebuild)",
        preprocess_complexity="O(n)",
        insert_complexity="O(n) eager / O(n) list lazy",
        delete_complexity="O(n) eager / O(n) list lazy",
        query_complexity="O(1) + rebuild if dirty",
        space_complexity="O(n)",
        arr=arr,
    )


def make_proposed(arr: Sequence[int] | None = None) -> APTreapRMQ:
    return APTreapRMQ(arr, pulse_limit=64, seed=12345)


DYNAMIC_EMPTY_FACTORIES: dict[str, Callable[[], DynamicRMQBase]] = {
    "AP-Treap (Proposed)": lambda: make_proposed(None),
    "Sparse Table (rebuild)": lambda: make_rebuild_sparse(None),
    "Block Decomposition (rebuild)": lambda: make_rebuild_block(None),
    "Fischer-Heun (rebuild)": lambda: make_rebuild_fischer(None),
}
