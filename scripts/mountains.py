"""Draw the last year of LeetCode submissions as a mountain range (day + night SVGs).

Each week raises a peak whose height follows the square root of that week's submissions, the
back ridge is a 4-week rolling average, and the busiest week gets the summit flag.

Usage:
  python scripts/mountains.py --leetcode user0498vT --out dist
  python scripts/mountains.py --input days.json --out dist     # [{"date": "YYYY-MM-DD", "count": 3}, ...]
"""

import argparse
import json
import math
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

QUERY = """query($u: String!) {
  matchedUser(username: $u) {
    submissionCalendar
    submitStatsGlobal { acSubmissionNum { difficulty count } }
  }
}"""

PALETTES = {
    "night": dict(sky=("#050b18", "#14243d"), far="#1a2a45", mid="#1f3354", near="#2c4870", snow="#e3ecf8",
                  accent="#7dd3fc", warm="#fbbf77", text="#eef3fa", sub="#9fb3c8", halo="#0a1220", ground="#9fb3c8", easy="#22c55e", med="#f59e0b", hard="#f87171"),
    "day": dict(sky=("#8dbde3", "#ffe1b8"), far="#b7c8db", mid="#8ea4bf", near="#566d8a", snow="#ffffff",
                accent="#c2410c", warm="#ea580c", text="#102033", sub="#2f4459", halo="#fff4e6", ground="#f1f5f9", easy="#15803d", med="#b45309", hard="#b91c1c"),
}
W, H = 1280, 320
LEFT, RIGHT, BASE, PEAK_H = 40, 1240, 280, 160
MONO = "'JetBrains Mono','Cascadia Code','Fira Code',Consolas,monospace"
FONT = "'Segoe UI','Inter','Helvetica Neue',Arial,sans-serif"


def fetch(username: str) -> tuple[list[tuple[date, int]], dict[str, int]]:
    """Public LeetCode profile data: daily submission counts and solved problems by difficulty."""
    req = urllib.request.Request(
        "https://leetcode.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"u": username}}).encode(),
        headers={"Content-Type": "application/json", "Referer": "https://leetcode.com", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        user = json.load(resp)["data"]["matchedUser"]
    if not user:
        raise SystemExit(f"LeetCode user {username!r} not found")
    days = [(datetime.fromtimestamp(int(ts), UTC).date(), n) for ts, n in json.loads(user["submissionCalendar"]).items()]
    solved = {s["difficulty"]: s["count"] for s in user["submitStatsGlobal"]["acSubmissionNum"]}
    return days, solved


def weekly(days: list[tuple[date, int]], today: date) -> list[tuple[date, int]]:
    """Sunday-starting weeks covering the last 52 weeks, oldest first; empty weeks count 0."""
    first = today - timedelta(days=364)
    first -= timedelta(days=(first.weekday() + 1) % 7)
    buckets = {first + timedelta(weeks=i): 0 for i in range((today - first).days // 7 + 1)}
    for d, c in days:
        if first <= d <= today:
            buckets[d - timedelta(days=(d.weekday() + 1) % 7)] += c
    return sorted(buckets.items())


def foothill(x: float) -> float:
    """Low decorative rolling ground so empty weeks still read as terrain."""
    return 7 + 4 * math.sin(x / 37) + 3 * math.sin(x / 13 + 1)


def terrain(values: list[float], top: float, spread: float) -> tuple[list[tuple[float, float]], list[float]]:
    """Each week raises a peak at its x position (height ~ sqrt(count)), with slopes whose
    width grows with height. Overlapping peaks merge by taking the highest slope, like a
    real range. Returns the sampled ridge and each week's x position."""
    n = len(values)
    step = (RIGHT - LEFT) / max(n - 1, 1)
    xs_week = [LEFT + i * step for i in range(n)]
    heights = [0.0 if top <= 0 or v <= 0 else math.sqrt(v / top) * PEAK_H for v in values]
    xs = sorted(set([float(x) for x in range(LEFT - 40, RIGHT + 41, 5)] + xs_week))
    pts = []
    for x in xs:
        e = foothill(x)
        for xi, h in zip(xs_week, heights):
            if h:
                e = max(e, h * (1 - abs(x - xi) / (18 + h * spread)))
        rough = math.sin(x * 12.9898) * 43758.5453 % 1 - 0.5  # deterministic rock texture
        if x not in xs_week:
            e += rough * 5 * min(e / PEAK_H, 1)
        pts.append((x, BASE - e))
    return pts, xs_week


def path_of(pts: list[tuple[float, float]], close: bool) -> str:
    d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    return f"M{LEFT - 40} {BASE} L" + d[1:] + f" L{RIGHT + 40} {BASE} V{H} H{LEFT - 40}Z" if close else d


def render(weeks: list[tuple[date, int]], total: int, solved: dict[str, int], mode: str, updated: str) -> str:
    p = PALETTES[mode]
    counts = [c for _, c in weeks]
    top = max(counts, default=0)
    rolling = [sum(counts[max(0, i - 3): i + 1]) / len(counts[max(0, i - 3): i + 1]) for i in range(len(counts))]
    front, xs_week = terrain(counts, top, 0.5)
    back, _ = terrain(rolling, top, 0.9)
    back = [(x, y - 16) for x, y in back]  # the 4-week average sits behind the weekly ridge
    ridge_y = dict(front)
    far = "M0 280 L70 214 L150 246 L240 196 L330 238 L420 204 L520 244 L610 186 L700 230 L790 200 L880 240 L980 192 L1070 228 L1160 198 L1280 236 V320 H0Z"

    months, seen = [], set()
    for i, (start, _) in enumerate(weeks):
        key = (start + timedelta(days=6)).strftime("%b")
        if (start + timedelta(days=6)).day <= 7 and key not in seen and 0 < i < len(weeks) - 1:
            seen.add(key)
            months.append(f'<text x="{xs_week[i]:.0f}" y="302" text-anchor="middle" font-family="{MONO}" font-size="11" fill="{p["ground"]}">{key}</text>')

    summit = ""
    if top > 0:
        i = max(range(len(counts)), key=lambda k: (counts[k], k))
        x = xs_week[i]
        y = ridge_y[x]
        anchor, tx = ("end", x - 10) if x > 1000 else ("start", x + 10)
        label = f"busiest week · {top} submission{'s' if top != 1 else ''} · week of {weeks[i][0].strftime('%d %b %Y')}"
        summit = (
            f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y - 30:.1f}" stroke="{p["text"]}" stroke-width="1.8"/>'
            f'<path class="flag" style="transform-origin:{x:.1f}px {y - 29:.1f}px" d="M{x + 1:.1f} {y - 30:.1f} l24 5 l-24 6Z" fill="{p["warm"]}"/>'
            f'<text x="{tx:.1f}" y="{y - 36:.1f}" text-anchor="{anchor}" class="lbl" font-family="{MONO}" font-size="12" font-weight="700" fill="{p["accent"]}">{label}</text>'
        )
    else:
        summit = f'<text x="640" y="230" text-anchor="middle" font-family="{MONO}" font-size="14" fill="{p["sub"]}">fresh snow: no submissions in this window yet</text>'

    front_d = path_of(front, close=False)
    snow_stop = 0.22
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
  <title id="t">LeetCode range</title>
  <desc id="d">{total} LeetCode submissions in the last year drawn as a mountain range; {solved.get('All', 0)} problems solved. The highest peak is the busiest week ({top}).</desc>
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{p['sky'][0]}"/><stop offset="1" stop-color="{p['sky'][1]}"/></linearGradient>
    <linearGradient id="rock" gradientUnits="userSpaceOnUse" x1="0" y1="{BASE - PEAK_H}" x2="0" y2="{BASE}">
      <stop offset="0" stop-color="{p['snow']}"/><stop offset="{snow_stop}" stop-color="{p['snow']}"/>
      <stop offset="{snow_stop + .08}" stop-color="{p['near']}"/><stop offset="1" stop-color="{p['near']}"/>
    </linearGradient>
    <clipPath id="rise"><rect class="rise" x="0" y="0" width="0" height="{H}"/></clipPath>
    <style>
      .rise{{animation:rise 2.8s cubic-bezier(.3,.7,.2,1) .2s forwards}}
      @keyframes rise{{to{{width:{W}px}}}}
      .lbl{{paint-order:stroke;stroke:{p['halo']};stroke-width:4px;stroke-linejoin:round}}
      .flag{{animation:wave 1.6s ease-in-out infinite alternate}}
      @keyframes wave{{from{{transform:skewY(-6deg) scaleX(.9)}}to{{transform:skewY(5deg)}}}}
      .glow{{animation:glow 2.4s ease-in-out infinite}}@keyframes glow{{50%{{opacity:.3}}}}
      @media (prefers-reduced-motion:reduce){{*{{animation:none!important}}.rise{{width:{W}px}}}}
    </style>
  </defs>
  <rect width="{W}" height="{H}" fill="url(#sky)"/>
  <path d="{far}" fill="{p['far']}" opacity=".55"/>
  <g clip-path="url(#rise)">
    <path d="{path_of(back, close=True)}" fill="{p['mid']}" opacity=".85"/>
    <path d="{path_of(front, close=True)}" fill="url(#rock)"/>
    <path d="{front_d}" fill="none" stroke="{p['halo']}" stroke-opacity=".35" stroke-width="1"/>
    {''.join(months)}
    {summit}
  </g>
  <g>
    <circle r="8" fill="{p['warm']}" opacity=".35" class="glow"/>
    <circle r="3.6" fill="{p['warm']}" stroke="{p['halo']}" stroke-width="1.2"/>
    <animateMotion dur="24s" begin="3s" repeatCount="indefinite" path="{front_d}"/>
  </g>
  <text x="40" y="38" font-family="{MONO}" font-size="12" letter-spacing="3" font-weight="700" fill="{p['accent']}">LEETCODE · LAST 12 MONTHS</text>
  <text x="40" y="70" font-family="{FONT}" font-size="26" font-weight="800" fill="{p['text']}">{total:,} submissions</text>
  <text x="1240" y="44" text-anchor="end" font-family="{FONT}" font-size="20" font-weight="800" fill="{p['text']}">{solved.get('All', 0)} solved</text>
  <text x="1240" y="66" text-anchor="end" font-family="{MONO}" font-size="12" fill="{p['sub']}"><tspan fill="{p['easy']}">easy {solved.get('Easy', 0)}</tspan>  ·  <tspan fill="{p['med']}">medium {solved.get('Medium', 0)}</tspan>  ·  <tspan fill="{p['hard']}">hard {solved.get('Hard', 0)}</tspan></text>
  <text x="40" y="92" font-family="{MONO}" font-size="11" fill="{p['sub']}">one peak per week · updated {updated}</text>
</svg>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leetcode")
    ap.add_argument("--input")
    ap.add_argument("--out", default="dist")
    a = ap.parse_args()
    if a.input:
        days = [(date.fromisoformat(d["date"]), int(d["count"])) for d in json.loads(Path(a.input).read_text())]
        solved: dict[str, int] = {}
    else:
        days, solved = fetch(a.leetcode)
    today = datetime.now(UTC).date()
    weeks = weekly(days, today)
    total = sum(c for _, c in weeks)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    updated = today.strftime("%d %b %Y")
    for mode in PALETTES:
        (out / f"leetcode-range-{mode}.svg").write_text(render(weeks, total, solved, mode, updated), encoding="utf-8")
    print(f"{len(weeks)} weeks, {total} submissions, busiest week {max((c for _, c in weeks), default=0)}, solved {solved}")


if __name__ == "__main__":
    main()
