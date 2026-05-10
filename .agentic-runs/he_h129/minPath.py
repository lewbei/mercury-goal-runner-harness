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
