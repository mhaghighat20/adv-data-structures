"""
RMQ with Fischer–Heun structure (taught baseline).

Preprocess: O(n)
Query:      O(1)
Space:      O(n)

Strong static tradeoff (linear space, constant query).  Like Sparse Table, it
is immutable after construction; dynamic use goes through rebuild adapters.
"""

from __future__ import annotations

from typing import List, Sequence

from rmq_common import RMQBase, deep_getsizeof


class FischerHeunRMQ(RMQBase):
    """
    Classic Fischer–Heun RMQ:
      - split into blocks of size b ≈ log2(n)/2
      - Sparse Table over block minima (covers whole blocks)
      - Cartesian-tree type + precomputed in-block RMQ tables
    """

    name = "Fischer-Heun"
    preprocess_complexity = "O(n)"
    query_complexity = "O(1)"
    space_complexity = "O(n)"

    def __init__(self, arr: Sequence[int]) -> None:
        self.arr = arr
        n = len(arr)
        self.n = n
        if n == 0:
            raise ValueError("Array is empty")

        self.b = max(1, (n.bit_length() - 1) // 2)
        self.m = (n + self.b - 1) // self.b

        block_min: List[int] = []
        block_argmin: List[int] = []
        types: List[int] = []
        type_table: dict[int, List[List[int]]] = {}

        for bi in range(self.m):
            lo = bi * self.b
            hi = min(n, lo + self.b)
            idx = lo
            for j in range(lo + 1, hi):
                if arr[j] < arr[idx]:
                    idx = j
            block_min.append(arr[idx])
            block_argmin.append(idx)

            t = self._cartesian_type(arr, lo, hi)
            types.append(t)
            if t not in type_table:
                type_table[t] = self._precompute_inblock(arr, lo, hi)

        self.block_min = block_min
        self.block_argmin = block_argmin
        self.types = types
        self.type_table = type_table

        max_log = max(1, self.m.bit_length())
        st_val = [[0] * max_log for _ in range(self.m)]
        st_arg = [[0] * max_log for _ in range(self.m)]
        for i in range(self.m):
            st_val[i][0] = block_min[i]
            st_arg[i][0] = block_argmin[i]
        j = 1
        while (1 << j) <= self.m:
            half = 1 << (j - 1)
            width = 1 << j
            i = 0
            while i + width - 1 < self.m:
                left_i, right_i = i, i + half
                if st_val[left_i][j - 1] <= st_val[right_i][j - 1]:
                    st_val[i][j] = st_val[left_i][j - 1]
                    st_arg[i][j] = st_arg[left_i][j - 1]
                else:
                    st_val[i][j] = st_val[right_i][j - 1]
                    st_arg[i][j] = st_arg[right_i][j - 1]
                i += 1
            j += 1
        self.st_val = st_val
        self.st_arg = st_arg

    @staticmethod
    def _cartesian_type(arr: Sequence[int], lo: int, hi: int) -> int:
        stack: List[int] = []
        mask = 0
        bit = 0
        for i in range(lo, hi):
            while stack and arr[stack[-1]] > arr[i]:
                stack.pop()
                mask |= 1 << bit
                bit += 1
            stack.append(i)
            bit += 1
        while stack:
            stack.pop()
            mask |= 1 << bit
            bit += 1
        return (mask << 8) | (hi - lo)

    @staticmethod
    def _precompute_inblock(arr: Sequence[int], lo: int, hi: int) -> List[List[int]]:
        s = hi - lo
        relative = [[0] * s for _ in range(s)]
        for i in range(s):
            best = 0
            relative[i][i] = 0
            best_val = arr[lo + i]
            for j in range(i + 1, s):
                if arr[lo + j] < best_val:
                    best_val = arr[lo + j]
                    best = j - i
                relative[i][j] = best

        out = [[0] * s for _ in range(s)]
        for i in range(s):
            for j in range(i, s):
                out[i][j] = i + relative[i][j]
        return out

    def _query_block_range(self, bl: int, br: int) -> int:
        length = br - bl + 1
        k = length.bit_length() - 1
        left_v = self.st_val[bl][k]
        right_v = self.st_val[br - (1 << k) + 1][k]
        return left_v if left_v <= right_v else right_v

    def _inblock_min(self, block_id: int, left: int, right: int) -> int:
        base = block_id * self.b
        i = left - base
        j = right - base
        rel = self.type_table[self.types[block_id]][i][j]
        return self.arr[base + rel]

    def query(self, left: int, right: int) -> int:
        if left == right:
            return self.arr[left]
        b = self.b
        bl = left // b
        br = right // b
        if bl == br:
            return self._inblock_min(bl, left, right)

        left_end = min(self.n - 1, (bl + 1) * b - 1)
        right_start = br * b
        best = self._inblock_min(bl, left, left_end)
        right_best = self._inblock_min(br, right_start, right)
        if right_best < best:
            best = right_best
        if bl + 1 <= br - 1:
            mid = self._query_block_range(bl + 1, br - 1)
            if mid < best:
                best = mid
        return best

    def structure_nbytes_estimate(self) -> int:
        return (
            deep_getsizeof(self.block_min)
            + deep_getsizeof(self.block_argmin)
            + deep_getsizeof(self.types)
            + deep_getsizeof(self.type_table)
            + deep_getsizeof(self.st_val)
            + deep_getsizeof(self.st_arg)
        )

    def describe_extra(self) -> str:
        return (
            f"block_size={self.b}, blocks={self.m}, "
            f"unique_types={len(self.type_table)}"
        )
