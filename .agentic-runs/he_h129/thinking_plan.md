# Thinking Plan: Implement minPath

## Architecture
We will implement the solution in a single Python file `minPath.py`. The file will contain the public function `minPath(grid, k)` that fulfills the contract, plus a small private helper `_get_min_neighbor` to encapsulate neighbor selection logic. All reasoning, design decisions, and validation steps are documented in this plan, so the implementer can directly copy the provided template without any missing pieces.

## Design decisions
| Decision | Options | Chosen | Why |
|---|---|---|---|
| Algorithmic approach for lexicographically minimal path | 1. Greedy neighbor selection (choose smallest neighbor at each step) 2. Full DP / BFS exploring all length‑k paths 3. Dijkstra‑like search with lexicographic ordering | Greedy neighbor selection | Greedy is optimal because lexicographic ordering cares about the earliest differing element. Picking the smallest possible next value at each step yields the globally minimal path. It also runs in O(k) after an O(N²) scan, which is far cheaper than exponential DP. |
| Error handling for invalid inputs | 1. Raise `ValueError` with descriptive message 2. Return empty list 3. Silent ignore | Raise `ValueError` | The contract expects a well‑formed grid and a positive `k`. Raising an exception makes misuse explicit and aids debugging. |
| Neighbor enumeration order | 1. Fixed order (up, down, left, right) 2. Sort neighbors by value before picking 3. Random | Sort neighbors by value (effectively picking the minimum) | Sorting ensures we always pick the smallest neighbor regardless of positional order, guaranteeing correctness. |

---

## Step 1: minPath.py

### Why
The contract specifies a single output artifact `minPath.py`. Implementing the function here satisfies the `final_outputs` requirement and provides a self‑contained solution that can be imported and tested directly.

### Design
* **Input validation** – Verify `grid` is a non‑empty square matrix and `k` is a positive integer.
* **Locate start cell** – Because the grid contains each integer `1..N*N` exactly once, the lexicographically minimal path must start at the cell containing `1`.
* **Greedy walk** – For each subsequent step, examine the four orthogonal neighbors, filter out‑‑of‑bounds cells, and move to the neighbor with the smallest value. Record that value.
* **Helper `_get_min_neighbor`** – Encapsulates neighbor collection and minimum selection, returning the coordinates of the best neighbor.
* **Complexity** – O(N²) to locate the start cell, then O(k) for the walk. Memory usage is O(1) besides the output list.
* **Edge cases** – `k == 1` returns `[1]`. If `k` exceeds any reasonable limit, the algorithm still works because we can revisit cells indefinitely.

### Template
```python
# minPath.py

def minPath(grid, k):
    """Return the lexicographically minimal path of length ``k`` in ``grid``.

    The grid is a square list‑of‑lists containing each integer from 1 to N*N
    exactly once. A path visits exactly ``k`` cells (the start cell counts as the
    first visit) and may revisit cells. Moves are allowed only to orthogonal
    neighbours (up, down, left, right) staying inside the grid.

    The function implements a greedy algorithm: start at the cell containing
    ``1`` (the smallest possible first value) and repeatedly move to the neighbour
    with the smallest value. This yields the lexicographically minimal path
    because the earliest differing element determines the ordering.

    Parameters
    ----------
    grid : List[List[int]]
        Square matrix of size N×N (N >= 2) with unique values 1..N*N.
    k : int
        Desired path length (k >= 1).

    Returns
    -------
    List[int]
        Ordered list of the values on the cells visited by the minimal path.

    Raises
    ------
    ValueError
        If ``grid`` is not square, empty, or if ``k`` is not a positive integer.
    """
    # ----- Input validation -------------------------------------------------
    if not isinstance(grid, list) or not grid:
        raise ValueError("grid must be a non‑empty list of lists")
    n = len(grid)
    for row in grid:
        if not isinstance(row, list) or len(row) != n:
            raise ValueError("grid must be a square matrix (N x N)")
    if not isinstance(k, int) or k <= 0:
        raise ValueError("k must be a positive integer")

    # ----- Locate the start cell (value 1) -----------------------------------
    start_r = start_c = None
    for r in range(n):
        for c in range(n):
            if grid[r][c] == 1:
                start_r, start_c = r, c
                break
        if start_r is not None:
            break
    if start_r is None:
        # This should never happen because the contract guarantees values 1..N*N
        raise ValueError("grid does not contain the value 1")

    # ----- Greedy walk -------------------------------------------------------
    path = [1]
    cur_r, cur_c = start_r, start_c
    for _ in range(1, k):
        # Determine the neighbour with the smallest value
        best_r, best_c = _get_min_neighbor(grid, cur_r, cur_c)
        cur_r, cur_c = best_r, best_c
        path.append(grid[cur_r][cur_c])
    return path


def _get_min_neighbor(grid, r, c):
    """Return the coordinates (row, col) of the orthogonal neighbour of ``(r,c)``
    that has the smallest value.

    The function assumes that at least one neighbour exists (the grid size is
    >= 2). It does **not** modify the grid.
    """
    n = len(grid)
    # Candidate positions: up, down, left, right
    candidates = []
    if r - 1 >= 0:
        candidates.append((r - 1, c))
    if r + 1 < n:
        candidates.append((r + 1, c))
    if c - 1 >= 0:
        candidates.append((r, c - 1))
    if c + 1 < n:
        candidates.append((r, c + 1))

    # Find the neighbour with the minimum value
    min_val = None
    min_pos = None
    for nr, nc in candidates:
        val = grid[nr][nc]
        if (min_val is None) or (val < min_val):
            min_val = val
            min_pos = (nr, nc)
    # ``min_pos`` will always be set because the grid is at least 2×2
    return min_pos
```

### Validation
To verify the implementation, run the following commands in a Python interpreter:

```bash
python - <<'PY'
from minPath import minPath

# Example 1
grid1 = [[1,2,3],[4,5,6],[7,8,9]]
print(minPath(grid1, 3))  # Expected: [1, 2, 1]

# Example 2
grid2 = [[5,9,3],[4,1,6],[7,8,2]]
print(minPath(grid2, 1))  # Expected: [1]

# Additional sanity check
grid3 = [[8,7],[6,5]]
print(minPath(grid3, 4))  # Path should start at 5 (the smallest), then 6,5,6 ...
PY
```
The output should match the expected results shown in the comments. If any `ValueError` is raised, check that the input conforms to the contract.

---
