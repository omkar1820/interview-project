"""Built-in coding problems. Expected outputs are produced by the reference solutions below, so test cases
can never drift from the statement. Tests are stdin -> stdout. The first two inputs are visible samples."""
from collections import Counter, OrderedDict, deque
from typing import Callable, Dict, List, Optional

LANGUAGES = ("python", "javascript")
STARTERS = {
    "python": ("import sys\n\n\ndef main():\n    data = sys.stdin.read().split()\n"
               "    # TODO: solve and print the answer\n\n\nmain()\n"),
    "javascript": ("const data = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean);\n"
                   "// TODO: solve and console.log the answer\n"),
}


def _ints(s: str) -> List[int]:
    return [int(x) for x in s.split()]


def _sum_evens(s):
    a = _ints(s)
    return str(sum(x for x in a[1:1 + a[0]] if x % 2 == 0))


def _reverse_words(s):
    return " ".join(s.split()[::-1])


def _brackets(s):
    pairs, st = {")": "(", "]": "[", "}": "{"}, []
    for ch in s.strip():
        if ch in "([{":
            st.append(ch)
        elif not st or st.pop() != pairs[ch]:
            return "NO"
    return "NO" if st else "YES"


def _two_sum(s):
    a = _ints(s)
    n, arr, target = a[0], a[1:1 + a[0]], a[1 + a[0]]
    for i in range(n):
        for j in range(i + 1, n):
            if arr[i] + arr[j] == target:
                return f"{i} {j}"
    return "-1 -1"


def _top_word(s):
    w, c = sorted(Counter(s.split()).items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return f"{w} {c}"


def _merge(s):
    a = _ints(s)
    iv = sorted((a[1 + 2 * i], a[2 + 2 * i]) for i in range(a[0]))
    out: List[List[int]] = []
    for lo, hi in iv:
        if out and lo <= out[-1][1]:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return "\n".join(f"{lo} {hi}" for lo, hi in out)


def _coins(s):
    a = _ints(s)
    amount, coins = a[0], a[2:2 + a[1]]
    best = [0] + [10 ** 9] * amount
    for v in range(1, amount + 1):
        for c in coins:
            if c <= v:
                best[v] = min(best[v], best[v - c] + 1)
    return str(best[amount] if best[amount] < 10 ** 9 else -1)


def _lru(s):
    lines = s.strip().splitlines()
    cap, cache, out = int(lines[0]), OrderedDict(), []
    for ln in lines[2:2 + int(lines[1])]:
        p = ln.split()
        if p[0] == "put":
            cache[p[1]] = p[2]
            cache.move_to_end(p[1])
            if len(cache) > cap:
                cache.popitem(last=False)
        elif p[1] in cache:
            cache.move_to_end(p[1])
            out.append(cache[p[1]])
        else:
            out.append("-1")
    return "\n".join(out)


def _grid(s):
    lines = s.strip().splitlines()
    r, c = map(int, lines[0].split())
    g = lines[1:1 + r]
    if g[0][0] == "#" or g[r - 1][c - 1] == "#":
        return "-1"
    dist, q = {(0, 0): 0}, deque([(0, 0)])
    while q:
        y, x = q.popleft()
        if (y, x) == (r - 1, c - 1):
            return str(dist[(y, x)])
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < r and 0 <= nx < c and g[ny][nx] == "." and (ny, nx) not in dist:
                dist[(ny, nx)] = dist[(y, x)] + 1
                q.append((ny, nx))
    return "-1"


def _p(pid: str, title: str, level: str, tags: List[str], statement: str, ref: Callable[[str], str],
       inputs: List[str]) -> dict:
    return {"id": pid, "title": title, "difficulty": level, "tags": tags, "statement": statement,
            "tests": [{"input": i, "expected": ref(i)} for i in inputs]}


PROBLEMS: List[dict] = [
    _p("sum-evens", "Sum of even numbers", "easy", ["general", "data"],
       "First line: n. Second line: n integers. Print the sum of the even numbers (0 if there are none).",
       _sum_evens, ["5\n1 2 3 4 5\n", "3\n1 3 5\n", "4\n-2 10 7 8\n", "1\n0\n", "6\n100 200 300 1 1 1\n"]),
    _p("reverse-words", "Reverse the words", "easy", ["general", "frontend"],
       "Read one line of words separated by spaces. Print the words in reverse order, separated by single spaces.",
       _reverse_words, ["hello world\n", "one\n", "the quick brown fox jumps\n", "  a   b  c \n", "x y\n"]),
    _p("balanced-brackets", "Balanced brackets", "easy", ["general", "backend"],
       "Read one line containing only the characters ()[]{}. Print YES if the brackets are balanced, otherwise NO.",
       _brackets, ["()[]{}\n", "(]\n", "{[()]}\n", "((()\n", "]\n", "([{}])()\n"]),
    _p("two-sum", "Two sum", "medium", ["general", "backend"],
       "First line: n. Second line: n integers. Third line: a target. Exactly one pair i < j has a[i] + a[j] equal "
       "to the target. Print i and j (0-based) separated by a space.",
       _two_sum, ["4\n2 7 11 15\n9\n", "3\n3 2 4\n6\n", "2\n3 3\n6\n", "5\n10 -2 5 8 1\n3\n",
                  "6\n1 5 9 14 20 3\n34\n"]),
    _p("top-word", "Most frequent word", "medium", ["data", "backend"],
       "Read one line of lowercase words. Print the most frequent word and its count separated by a space. "
       "If several words tie, print the alphabetically smallest.",
       _top_word, ["a b a c b a\n", "x y z\n", "to be or not to be\n", "go go go\n", "b a b a\n"]),
    _p("merge-intervals", "Merge intervals", "medium", ["data", "backend"],
       "First line: n. Then n lines, each 'start end'. Merge overlapping intervals (touching ones such as 1-3 and "
       "3-5 also merge). Print the merged intervals sorted by start, one 'start end' per line.",
       _merge, ["4\n1 3\n2 6\n8 10\n15 18\n", "2\n1 4\n4 5\n", "3\n5 6\n1 2\n3 4\n", "3\n1 10\n2 3\n4 5\n", "1\n7 7\n"]),
    _p("min-coins", "Minimum coins", "hard", ["general", "backend"],
       "Line 1: the amount. Line 2: k, the number of coin types. Line 3: the k coin values (each can be used any "
       "number of times). Print the minimum number of coins that make the amount, or -1 if it is impossible.",
       _coins, ["11\n3\n1 2 5\n", "3\n1\n2\n", "0\n2\n1 2\n", "100\n4\n1 5 10 25\n", "27\n3\n9 6 5\n", "7\n2\n2 4\n"]),
    _p("lru-cache", "LRU cache", "hard", ["backend"],
       "Line 1: capacity. Line 2: m operations. Then m lines, each 'put key value' or 'get key'. Implement a least "
       "recently used cache: put and a successful get make the key most recently used; a put beyond capacity "
       "evicts the least recently used key. For every get print its value, or -1 if the key is missing.",
       _lru, ["2\n7\nput 1 1\nput 2 2\nget 1\nput 3 3\nget 2\nput 4 4\nget 1\n",
              "1\n3\nput 5 9\nget 5\nget 6\n",
              "2\n6\nput 1 1\nput 2 2\nput 1 10\nput 3 3\nget 1\nget 2\n",
              "3\n8\nput 1 a\nput 2 b\nput 3 c\nget 1\nput 4 d\nget 2\nget 3\nget 4\n"]),
    _p("grid-path", "Shortest path in a grid", "hard", ["general", "backend"],
       "Line 1: R and C. Then R lines of C characters: '.' is open, '#' is a wall. Move up, down, left or right "
       "from the top-left to the bottom-right cell. Print the minimum number of steps, or -1 if there is no path "
       "(also -1 if the start or end is a wall).",
       _grid, ["3 3\n...\n.#.\n...\n", "2 2\n.#\n#.\n", "1 1\n.\n", "4 4\n....\n.##.\n.#..\n....\n",
               "3 4\n.#..\n.#.#\n....\n"]),
]
BY_ID: Dict[str, dict] = {p["id"]: p for p in PROBLEMS}
TRACKS = {"frontend": ("frontend", "front-end", "ui", "ux", "web", "react", "angular"),
          "data": ("data", "analyst", "scientist", "ml", "machine", "ai", "bi"),
          "backend": ("backend", "api", "server", "devops", "cloud", "java", "python", "engineer", "developer")}
VISIBLE = 2


def track_for(role: str) -> str:
    words = role.lower().replace("-", " ").split()
    for track, keys in TRACKS.items():
        if any(k in words or (len(k) > 3 and k in role.lower()) for k in keys):
            return track
    return "general"


def pick_problem(role: str, level: str, seed: int) -> dict:
    pool = [p for p in PROBLEMS if p["difficulty"] == level]
    tagged = [p for p in pool if track_for(role) in p["tags"]]
    pool = tagged or pool
    return pool[seed % len(pool)]


def get(problem_id: str) -> Optional[dict]:
    return BY_ID.get(problem_id)


def public_view(p: dict) -> dict:
    return {"id": p["id"], "title": p["title"], "difficulty": p["difficulty"], "statement": p["statement"],
            "samples": [{"input": t["input"], "output": t["expected"]} for t in p["tests"][:VISIBLE]],
            "starters": STARTERS, "languages": list(LANGUAGES)}
