"""Generate annual stats and streak cards from GitHub's contribution calendar."""

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape


QUERY = """
query($login: String!, $from: DateTime!, $streakFrom: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { totalContributions }
      restrictedContributionsCount
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalRepositoryContributions
    }
    streak: contributionsCollection(from: $streakFrom, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
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
    year_start = date(year, 1, 1)
    first_sunday = year_start - timedelta(days=(year_start.weekday() + 1) % 7)
    today = min(datetime.now(timezone.utc).date(), date(year, 12, 31))
    payload = json.dumps({
        "query": QUERY,
        "variables": {
            "login": login,
            "from": f"{year}-01-01T00:00:00Z",
            "streakFrom": f"{first_sunday.isoformat()}T00:00:00Z",
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

    calendar = result["data"]["user"]["streak"]["contributionCalendar"]
    daily = {
        date.fromisoformat(day["date"]): day["contributionCount"]
        for week in calendar["weeks"]
        for day in week["contributionDays"]
    }
    if today < year_start:
        raise ValueError("Cannot generate a streak card for a future year")
    longest = active = run = 0
    day = year_start
    while day <= today:
        if day not in daily or not isinstance(daily[day], int) or daily[day] < 0:
            raise ValueError(f"GitHub returned invalid contribution data for {day}")
        if daily[day]:
            active += 1
            run += 1
            longest = max(longest, run)
        else:
            run = 0
        day += timedelta(days=1)
    current_day = today if daily[today] else today - timedelta(days=1)
    current = 0
    while current_day >= year_start and daily[current_day]:
        current += 1
        current_day -= timedelta(days=1)

    streak_description = escape(
        f"{year}: current contribution streak {current} days, "
        f"longest streak {longest} days, active on {active} days."
    )
    streak_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="467" height="195" viewBox="0 0 467 195" role="img" aria-labelledby="title desc">
  <title id="title">Henrique's GitHub Contribution Streak</title>
  <desc id="desc">{streak_description}</desc>
  <style>
    .title {{ fill: #70a5fd; font: 600 18px 'Segoe UI', Ubuntu, sans-serif; }}
    .number {{ fill: #38bdae; font: 700 31px 'Segoe UI', Ubuntu, sans-serif; }}
    .label {{ fill: #a9b1d6; font: 600 12px 'Segoe UI', Ubuntu, sans-serif; }}
    .footer {{ fill: #8f9bb3; font: 11px 'Segoe UI', Ubuntu, sans-serif; }}
  </style>
  <rect width="467" height="195" rx="6" fill="#1a1b27" />
  <text class="title" x="25" y="37">Henrique's GitHub Contribution Streak</text>
  <line x1="25" y1="55" x2="442" y2="55" stroke="#303858" />
  <line x1="156" y1="76" x2="156" y2="154" stroke="#303858" />
  <line x1="311" y1="76" x2="311" y2="154" stroke="#303858" />
  <text class="number" x="78" y="116" text-anchor="middle">{current}</text>
  <text class="label" x="78" y="140" text-anchor="middle">Current streak</text>
  <text class="number" x="234" y="116" text-anchor="middle">{longest}</text>
  <text class="label" x="234" y="140" text-anchor="middle">Longest streak</text>
  <text class="number" x="389" y="116" text-anchor="middle">{active}</text>
  <text class="label" x="389" y="140" text-anchor="middle">Active days</text>
  <text class="footer" x="234" y="177" text-anchor="middle">{year} · GitHub contribution calendar</text>
</svg>
'''
    streak_output = output.parent / "streak.svg"
    streak_output.write_text(streak_svg, encoding="utf-8")
    print(f"Wrote {streak_output} for {year}: current={current}, longest={longest}, active={active}")


if __name__ == "__main__":
    main()
