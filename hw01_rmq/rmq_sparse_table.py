"""
RMQ with Sparse Table (taught / classic baseline).

Preprocess: O(n log n)
Query:      O(1)
Space:      O(n log n)

Best suited for the *static* baseline of the assignment (immutable array).
For dynamic streams we use the rebuild adapter in rmq_dynamic_adapters.py.
"""

from __future__ import annotations

from typing import List, Sequence

from rmq_common import RMQBase, deep_getsizeof


class SparseTableRMQ(RMQBase):
    name = "Sparse Table"
    preprocess_complexity = "O(n log n)"
    query_complexity = "O(1)"
    space_complexity = "O(n log n)"

    def __init__(self, arr: Sequence[int]) -> None:
        self.arr = arr
        n = len(arr)
        self.n = n
        max_log = max(1, n.bit_length())
        st: List[List[int]] = [[0] * max_log for _ in range(n)]
        for i in range(n):
            st[i][0] = arr[i]
        j = 1
        while (1 << j) <= n:
            half = 1 << (j - 1)
            width = 1 << j
            i = 0
            while i + width - 1 < n:
                st[i][j] = min(st[i][j - 1], st[i + half][j - 1])
                i += 1
            j += 1
        self.st = st

    def query(self, left: int, right: int) -> int:
        length = right - left + 1
        k = length.bit_length() - 1
        return min(self.st[left][k], self.st[right - (1 << k) + 1][k])

    def structure_nbytes_estimate(self) -> int:
        return deep_getsizeof(self.st)

    def describe_extra(self) -> str:
        return f"levels={len(self.st[0])}"
