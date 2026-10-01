"""Fetch public GitHub stats for the profile card -> data/stats.json.

Needs the GitHub CLI (`gh`) authenticated, or GH_TOKEN set (Actions does this).
Counts only; no private repo names are stored.
"""
import datetime as dt
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(isFork: false, privacy: PUBLIC, first: 100,
                 orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes {
        name stargazerCount pushedAt
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
    }
  }
}
"""


def fetch(login, exclude=(), featured=()):
    res = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={QUERY}", "-F", f"login={login}"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if res.returncode:
        raise SystemExit(f"gh failed: {res.stderr or res.stdout}")
    out = res.stdout
    user = json.loads(out)["data"]["user"]
    repos = [r for r in user["repositories"]["nodes"] if r["name"] not in exclude]
    by_name = {r["name"]: r for r in repos}
    top = [by_name[n] for n in featured if n in by_name]  # medal order = config order
    if not top:
        top = sorted(repos, key=lambda r: r["pushedAt"], reverse=True)
        top.sort(key=lambda r: r["stargazerCount"], reverse=True)  # stable: ties stay newest-first
    c = user["contributionsCollection"]
    return {
        "login": login,
        "fetched_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
        "followers": user["followers"]["totalCount"],
        "repos": len(repos),
        "stars": sum(r["stargazerCount"] for r in repos),
        "commits": c["totalCommitContributions"],
        "prs": c["totalPullRequestContributions"],
        "issues": c["totalIssueContributions"],
        "reviews": c["totalPullRequestReviewContributions"],
        "top_repos": [
            {"name": r["name"], "stars": r["stargazerCount"],
             "languages": [(e["node"]["name"], e["size"]) for e in r["languages"]["edges"]]}
            for r in top[:3]
        ],
    }


if __name__ == "__main__":
    cfg = json.loads((ROOT / "config" / "profile.json").read_text(encoding="utf-8"))
    stats = fetch(cfg["login"], cfg["excludeRepos"], cfg.get("featuredRepos", []))
    (ROOT / "data" / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"ok: {stats['repos']} repos, {stats['stars']} stars, {stats['commits']} commits")
