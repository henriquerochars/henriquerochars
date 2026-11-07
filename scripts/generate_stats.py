"""Generate the profile's annual stats card from GitHub's contribution calendar."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape


QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { totalContributions }
      restrictedContributionsCount
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalRepositoryContributions
    }
  }
}
"""


def format_number(value):
    return f"{value:,}".replace(",", ".")


def main():
    token = os.environ["GITHUB_TOKEN"]
    login = os.environ.get("GITHUB_USER", "henriquerochars")
    year = int(os.environ.get("STATS_YEAR", datetime.now(timezone.utc).year))
    payload = json.dumps({
        "query": QUERY,
        "variables": {
            "login": login,
            "from": f"{year}-01-01T00:00:00Z",
            "to": f"{year + 1}-01-01T00:00:00Z",
        },
    }).encode()
    request = Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "henriquerochars-profile-stats",
        },
    )
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get("errors") or not result.get("data", {}).get("user"):
        raise RuntimeError(f"GitHub contribution query failed: {result.get('errors')}")

    stats = result["data"]["user"]["contributionsCollection"]
    values = {
        "total": stats["contributionCalendar"]["totalContributions"],
        "private": stats["restrictedContributionsCount"],
        "commits": stats["totalCommitContributions"],
        "prs": stats["totalPullRequestContributions"],
        "issues": stats["totalIssueContributions"],
        "repositories": stats["totalRepositoryContributions"],
    }
    if any(not isinstance(value, int) or value < 0 for value in values.values()):
        raise ValueError("GitHub returned an invalid contribution count")

    rows = [
        (f"Total contributions ({year})", values["total"], 75, "total"),
        ("Private contributions", values["private"], 103, "private"),
        ("Public commits", values["commits"], 146, "public"),
        ("Public PRs", values["prs"], 173, "public"),
        ("Public issues", values["issues"], 200, "public"),
        ("Public repositories created", values["repositories"], 227, "public"),
    ]
    row_svg = "\n".join(
        f'<text class="label {kind}" x="25" y="{y}">{escape(label)}</text>'
        f'<text class="value {kind}" x="442" y="{y}" text-anchor="end">'
        f'{format_number(value)}</text>'
        for label, value, y, kind in rows
    )
    description = escape(
        f"{year}: {values['total']} total contributions, including "
        f"{values['private']} private. Public: {values['commits']} commits, "
        f"{values['prs']} pull requests, {values['issues']} issues and "
        f"{values['repositories']} repositories created."
    )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="467" height="250" viewBox="0 0 467 250" role="img" aria-labelledby="title desc">
  <title id="title">Henrique Rocha Serrano's GitHub Stats</title>
  <desc id="desc">{description}</desc>
  <style>
    .title {{ fill: #70a5fd; font: 600 19px 'Segoe UI', Ubuntu, sans-serif; }}
    .label {{ fill: #38bdae; font: 600 14px 'Segoe UI', Ubuntu, sans-serif; }}
    .value {{ fill: #38bdae; font: 700 15px 'Segoe UI', Ubuntu, sans-serif; }}
    .total {{ fill: #70a5fd; }}
    .private {{ fill: #bb9af7; }}
  </style>
  <rect width="467" height="250" rx="6" fill="#1a1b27" />
  <text class="title" x="25" y="37">Henrique Rocha Serrano's GitHub Stats</text>
  <line x1="25" y1="119" x2="442" y2="119" stroke="#303858" />
{row_svg}
</svg>
'''
    output = Path(__file__).resolve().parents[1] / "profile" / "stats.svg"
    output.write_text(svg, encoding="utf-8")
    print(f"Wrote {output} for {year}: {values}")


if __name__ == "__main__":
    main()
