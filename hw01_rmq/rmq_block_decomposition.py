"""
RMQ with Block Decomposition / sqrt decomposition (taught baseline).

Preprocess: O(n)
Query:      O(√n)
Space:      O(n)

Cheap to rebuild compared with Sparse Table, but queries are not O(1).
Used both as a static baseline and via rebuild-on-update in the stream study.
"""

from __future__ import annotations

import math
from typing import List, Sequence

from rmq_common import RMQBase, deep_getsizeof


class BlockDecompositionRMQ(RMQBase):
    name = "Block Decomposition"
    preprocess_complexity = "O(n)"
    query_complexity = "O(√n)"
    space_complexity = "O(n)"

    def __init__(self, arr: Sequence[int]) -> None:
        self.arr = arr
        n = len(arr)
        self.n = n
        self.block_size = max(1, int(math.isqrt(n)))
        num_blocks = (n + self.block_size - 1) // self.block_size
        block_min: List[int] = [0] * num_blocks
        for b in range(num_blocks):
            lo = b * self.block_size
            hi = min(n, lo + self.block_size)
            block_min[b] = min(arr[lo:hi])
        self.block_min = block_min

    def query(self, left: int, right: int) -> int:
        arr = self.arr
        bs = self.block_size
        best = arr[left]

        while left <= right and left % bs != 0:
            if arr[left] < best:
                best = arr[left]
            left += 1

        while left + bs - 1 <= right:
            b = left // bs
            if self.block_min[b] < best:
                best = self.block_min[b]
            left += bs

        while left <= right:
            if arr[left] < best:
                best = arr[left]
            left += 1
        return best

    def structure_nbytes_estimate(self) -> int:
        return deep_getsizeof(self.block_min)

    def describe_extra(self) -> str:
        return f"block_size={self.block_size}, blocks={len(self.block_min)}"
