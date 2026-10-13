import html
import json
import math
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

USER = os.environ["GH_USER"]
TOKEN = os.environ["GH_TOKEN"]
UTC_OFFSET = -3
OUT = "profile-cards"

BG, WHITE, GRAY = "#0d1117", "#ffffff", "#8b949e"
RED, LIGHT, WINE = "#C1121F", "#E5989B", "#8B1A2B"
PALETTE = [RED, LIGHT, GRAY, WINE, "#F1F1F1"]


def request(url, body=None):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-cards",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    data = request("https://api.github.com/graphql", body)
    if "errors" in data:
        raise SystemExit(f"Erro GraphQL: {data['errors']}")
    return data["data"]


# ---------- dados ----------
base = gql(
    """
query($login:String!){
  user(login:$login){
    createdAt
    pullRequests{totalCount}
    issues{totalCount}
    repositoriesContributedTo(first:1, contributionTypes:[COMMIT,ISSUE,PULL_REQUEST,REPOSITORY]){totalCount}
    repositories(ownerAffiliations:OWNER, first:100, isFork:false){nodes{stargazerCount}}
  }
}""",
    {"login": USER},
)["user"]

stars = sum(n["stargazerCount"] for n in base["repositories"]["nodes"])
prs = base["pullRequests"]["totalCount"]
issues = base["issues"]["totalCount"]
contributed = base["repositoriesContributedTo"]["totalCount"]

year_query = """
query($login:String!,$from:DateTime!,$to:DateTime!){
  user(login:$login){
    contributionsCollection(from:$from,to:$to){
      totalCommitContributions
      commitContributionsByRepository(maxRepositories:100){
        repository{nameWithOwner primaryLanguage{name}}
        contributions{totalCount}
      }
    }
  }
}"""

first_year = int(base["createdAt"][:4])
this_year = datetime.now(timezone.utc).year
commits = 0
repo_counts = {}
lang_counts = {}

for year in range(first_year, this_year + 1):
    col = gql(
        year_query,
        {"login": USER, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"},
    )["user"]["contributionsCollection"]
    commits += col["totalCommitContributions"]
    for item in col["commitContributionsByRepository"]:
        n = item["contributions"]["totalCount"]
        name = item["repository"]["nameWithOwner"]
        repo_counts[name] = repo_counts.get(name, 0) + n
        lang = item["repository"]["primaryLanguage"]
        if lang:
            lang_counts[lang["name"]] = lang_counts.get(lang["name"], 0) + n

# commits por hora (usa os 30 repositórios com mais commits)
hours = [0] * 24
top_repos = sorted(repo_counts, key=repo_counts.get, reverse=True)[:30]
for repo in top_repos:
    for page in range(1, 6):
        try:
            items = request(
                f"https://api.github.com/repos/{repo}/commits?author={USER}&per_page=100&page={page}"
            )
        except urllib.error.HTTPError:
            break
        for item in items:
            raw = item["commit"]["author"]["date"].replace("Z", "+00:00")
            dt = datetime.fromisoformat(raw) + timedelta(hours=UTC_OFFSET)
            hours[dt.hour] += 1
        if len(items) < 100:
            break


# ---------- svg ----------
def card(title, body):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195">'
        '<style>text{font-family:"Segoe UI",Ubuntu,Arial,sans-serif}</style>'
        f'<rect width="495" height="195" rx="4.5" fill="{BG}"/>'
        f'<text x="30" y="38" font-size="20" font-weight="600" fill="{RED}">{html.escape(title)}</text>'
        f"{body}</svg>"
    )


def stats_card():
    rows = [
        ("Total Stars", stars),
        ("Total Commits", commits),
        ("Total PRs", prs),
        ("Total Issues", issues),
        ("Contributed to", contributed),
    ]
    body = []
    for i, (label, value) in enumerate(rows):
        y = 75 + i * 25
        body.append(f'<rect x="30" y="{y - 10}" width="8" height="8" rx="1" fill="{RED}"/>')
        body.append(f'<text x="46" y="{y}" font-size="14" fill="{GRAY}">{label}</text>')
        body.append(f'<text x="200" y="{y}" font-size="14" font-weight="600" fill="{WHITE}">{value}</text>')
    body.append(f'<circle cx="385" cy="110" r="48" fill="none" stroke="{RED}" stroke-width="6"/>')
    body.append(f'<text x="385" y="115" font-size="24" font-weight="700" fill="{WHITE}" text-anchor="middle">{commits}</text>')
    body.append(f'<text x="385" y="133" font-size="11" fill="{GRAY}" text-anchor="middle">commits</text>')
    return card("Stats", "".join(body))


def hours_card():
    peak = max(hours) or 1
    body = []
    base_y, max_h = 160, 85
    for h, n in enumerate(hours):
        height = max(2, n / peak * max_h) if n else 0
        x = 30 + h * (435 / 24)
        color = LIGHT if n == peak else RED
        body.append(
            f'<rect x="{x:.1f}" y="{base_y - height:.1f}" width="14" height="{height:.1f}" rx="2" fill="{color}"/>'
        )
    body.append(f'<line x1="30" y1="{base_y}" x2="465" y2="{base_y}" stroke="{GRAY}" stroke-width="1"/>')
    for h in (0, 6, 12, 18, 23):
        x = 30 + h * (435 / 24) + 7
        body.append(f'<text x="{x:.1f}" y="178" font-size="10" fill="{GRAY}" text-anchor="middle">{h}h</text>')
    return card(f"Commits by hour (UTC{UTC_OFFSET:+d})", "".join(body))


def langs_card():
    top = sorted(lang_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    total = sum(n for _, n in top)
    if not total:
        return card("Top Languages by Commit", f'<text x="30" y="90" font-size="14" fill="{GRAY}">Sem dados</text>')
    body = []
    radius = 48
    circ = 2 * math.pi * radius
    offset = 0
    for i, (name, n) in enumerate(top):
        color = PALETTE[i]
        y = 75 + i * 25
        pct = n / total * 100
        body.append(f'<rect x="30" y="{y - 11}" width="12" height="12" rx="2" fill="{color}"/>')
        body.append(f'<text x="50" y="{y}" font-size="14" fill="{WHITE}">{html.escape(name)}</text>')
        body.append(f'<text x="180" y="{y}" font-size="12" fill="{GRAY}">{pct:.0f}%</text>')
        seg = circ * n / total
        body.append(
            f'<circle cx="370" cy="110" r="{radius}" fill="none" stroke="{color}" stroke-width="22" '
            f'stroke-dasharray="{seg:.2f} {circ - seg:.2f}" stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 370 110)"/>'
        )
        offset += seg
    return card("Top Languages by Commit", "".join(body))


os.makedirs(OUT, exist_ok=True)
for name, svg in (("stats", stats_card()), ("commit-hours", hours_card()), ("top-langs", langs_card())):
    with open(f"{OUT}/{name}.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"{OUT}/{name}.svg gerado")

print(f"commits={commits} stars={stars} prs={prs} issues={issues} contributed={contributed} langs={len(lang_counts)} horas={sum(hours)}")