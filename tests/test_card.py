import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_card as b

CFG = {
    "login": "x", "name": "X", "role": "R", "school": "S",
    "stack": ["Python", "Git"], "caps": {"stars": 50, "commits": 1000, "prs": 100, "followers": 100},
}
STATS = {
    "fetched_at": "2026-01-01", "followers": 0, "repos": 0, "stars": 0, "commits": 0, "prs": 0,
    "top_repos": [],
}


def test_level_monotonic_and_progress_in_range():
    prev = 0
    for xp in range(0, 5000, 7):
        lv, prog = b.level(xp)
        assert lv >= prev and 0 <= prog < 1
        prev = lv


def test_bar_fill_bounds():
    assert b.bar_fill(0, 50) == 0
    assert b.bar_fill(10**9, 50) == 1


def test_render_empty_account_and_non_ascii():
    stats = dict(STATS, top_repos=[{"name": "ไทย-repo", "stars": 0, "languages": []},
                                  {"name": "r2", "stars": 0, "languages": [["Python", 90], ["Zig", 9], ["Go", 1]]}])
    frames = b.render(stats, CFG)
    assert len(frames) > 1
    assert all(f.width == b.W * b.SCALE and f.height > 0 for f, _ in frames)


def test_static_node_matches_api_shape():
    import fetch_stats as f
    n = f.static_node("p", {"Python": 3, "CSS": 1})
    assert n["stargazerCount"] == 0
    assert [(e["node"]["name"], e["size"]) for e in n["languages"]["edges"]] == [("Python", 3), ("CSS", 1)]
