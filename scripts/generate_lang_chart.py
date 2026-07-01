#!/usr/bin/env python3
"""Generate stats card and language donut chart as clean SVGs from GitHub API."""

import os
import sys
import math
from collections import defaultdict
from datetime import datetime, timedelta

from github import Github, RateLimitExceededException


# ── Configuration ──────────────────────────────────────────────────────────

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
USERNAME = 'licette32'
STATS_OUTPUT = 'assets/stats-card.svg'
LANG_OUTPUT  = 'assets/lang-chart.svg'

EXCLUDED_LANGS = {'Jupyter Notebook', 'HTML', 'CSS', 'Makefile', 'Shell'}

COLORS = [
    '#38bdf8',  # sky blue
    '#34d399',  # emerald
    '#a78bfa',  # violet
    '#fbbf24',  # amber
    '#f87171',  # red
    '#2dd4bf',  # teal
    '#fb923c',  # orange
    '#e879f9',  # fuchsia
]


# ── Helpers ────────────────────────────────────────────────────────────────

def format_number(n):
    if n >= 1_000:
        return f'{n / 1000:.1f}k'
    return str(n)


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ── GitHub data ────────────────────────────────────────────────────────────

def compute_stats(g):
    result = {}
    try:
        user = g.get_user(USERNAME)
        repos = [r for r in user.get_repos(type='owner') if not r.fork and not r.archived]
        result['stars'] = format_number(sum(r.stargazers_count for r in repos))
        result['repos'] = format_number(len(repos))
    except Exception as e:
        print(f'::warning ::repos/stars: {e}')
        result['stars'] = result['repos'] = '—'

    try:
        raw_prs = g.search_issues(f'author:{USERNAME} type:pr').totalCount
        result['prs'] = format_number(raw_prs)
        result['raw_prs'] = raw_prs
    except Exception as e:
        print(f'::warning ::prs: {e}')
        result['prs'] = '—'

    try:
        raw_issues = g.search_issues(f'author:{USERNAME} type:issue').totalCount
        result['issues'] = format_number(raw_issues)
        result['raw_issues'] = raw_issues
    except Exception as e:
        print(f'::warning ::issues: {e}')
        result['issues'] = '—'

    try:
        since = (datetime.utcnow() - timedelta(days=365)).strftime('%Y-%m-%d')
        raw_commits = g.search_commits(f'author:{USERNAME} committer-date:>={since}').totalCount
        result['commits'] = format_number(raw_commits)
        result['raw_commits'] = raw_commits
    except Exception as e:
        print(f'::warning ::commits: {e}')
        result['commits'] = '—'

    try:
        result['contributed'] = format_number(
            g.search_repositories(f'contributor:{USERNAME} fork:false').totalCount
        )
    except Exception as e:
        print(f'::warning ::contributed: {e}')
        result['contributed'] = '—'

    result['year'] = datetime.utcnow().year
    result['updated'] = datetime.utcnow().strftime('%Y-%m-%d')
    return result


def compute_languages(g):
    lang_bytes = defaultdict(int)
    total_repos = 0
    for repo in g.get_user(USERNAME).get_repos(type='owner'):
        if repo.fork or repo.archived:
            continue
        total_repos += 1
        try:
            for lang, count in repo.get_languages().items():
                if lang not in EXCLUDED_LANGS:
                    lang_bytes[lang] += count
        except Exception:
            continue
    return dict(lang_bytes), total_repos


def prune_languages(lang_bytes, max_items=7):
    total = sum(lang_bytes.values())
    if not total:
        return {}
    sorted_langs = sorted(lang_bytes.items(), key=lambda x: -x[1])
    main = {}
    other = 0
    for i, (lang, count) in enumerate(sorted_langs):
        if i < max_items:
            main[lang] = count
        else:
            other += count
    if other:
        main['Other'] = other
    return main


# ── SVG: Stats card ────────────────────────────────────────────────────────

def make_stats_card(stats):
    rank = calculate_rank(stats)
    grade = rank['level']
    percentile = rank['percentile']
    grade_color = GRADE_COLORS.get(grade, '#60a5fa')
    # Circle: circumference = 2*pi*50 ≈ 314.16
    # fill = (100 - percentile) / 100 * 314.16
    circ = 314.16
    fill_len = round((100 - percentile) / 100 * circ, 1)
    gap_len  = round(circ - fill_len, 1)
    W, H = 420, 200
    BG   = '#0b1120'
    BLUE = '#60a5fa'
    MUTED = '#94a3b8'
    TEXT  = '#e2e8f0'

    year = stats['year']

    rows = [
        ('☆', f'Total Stars:',         stats['stars']),
        ('⊙', f'{year} Commits:',      stats['commits']),
        ('⇅', 'Total PRs:',            stats['prs']),
        ('⊗', 'Total Issues:',         stats['issues']),
        ('▣', 'Contributed to:',       stats['contributed']),
    ]

    # Row y positions — evenly spaced between y=52 and y=168
    y_start = 60
    y_end   = 168
    step    = (y_end - y_start) / (len(rows) - 1)

    row_svgs = []
    for i, (icon, label, value) in enumerate(rows):
        y = round(y_start + i * step)
        row_svgs.append(f'''
    <text x="22"  y="{y}" font-family="monospace" font-size="13" fill="{MUTED}" dominant-baseline="middle">{esc(icon)}</text>
    <text x="42"  y="{y}" font-family="monospace" font-size="12" fill="{TEXT}"  dominant-baseline="middle">{esc(label)}</text>
    <text x="240" y="{y}" font-family="monospace" font-size="12" fill="{BLUE}" font-weight="bold" dominant-baseline="middle">{esc(value)}</text>''')

    svg = f'''<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{W}" height="{H}" fill="{BG}" rx="10"/>

  <!-- Title -->
  <text x="22" y="30" font-family="monospace" font-size="18" font-weight="bold" fill="{BLUE}">Stats</text>

  <!-- Separator -->
  <line x1="22" y1="44" x2="{W-22}" y2="44" stroke="{BLUE}" stroke-width="0.5" opacity="0.3"/>

  <!-- Metric rows -->
  {''.join(row_svgs)}

  <!-- Grade circle -->
  <circle cx="370" cy="100" r="50" fill="none" stroke="#1e293b" stroke-width="6"/>
  <circle cx="370" cy="100" r="50" fill="none" stroke="{grade_color}" stroke-width="6"
          stroke-dasharray="{fill_len} {gap_len}"
          stroke-dashoffset="78.5"
          stroke-linecap="round"/>
  <text x="370" y="95" font-family="monospace" font-size="20" font-weight="bold" fill="{grade_color}" text-anchor="middle" dominant-baseline="middle">{grade}</text>
  <text x="370" y="118" font-family="monospace" font-size="9" fill="{MUTED}" text-anchor="middle">grade</text>

  <!-- Footer -->
  <text x="{W-16}" y="{H-10}" font-family="monospace" font-size="9" fill="{MUTED}" text-anchor="end">Updated {esc(stats["updated"])}</text>
</svg>'''

    os.makedirs(os.path.dirname(STATS_OUTPUT) or '.', exist_ok=True)
    with open(STATS_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f'::notice ::Stats card saved → {STATS_OUTPUT}')


# ── SVG: Language donut chart ──────────────────────────────────────────────

def make_donut_chart(lang_bytes, total_repos):
    data = prune_languages(lang_bytes)
    if not data:
        print('::warning ::No language data after pruning.')
        return

    W, H   = 480, 250
    BG     = '#0b1120'
    BLUE   = '#60a5fa'
    MUTED  = '#94a3b8'
    TEXT   = '#e2e8f0'

    cx, cy = 115, 148   # donut center (lower to make room for title)
    R_out  = 85
    R_in   = 47

    labels = list(data.keys())
    sizes  = list(data.values())
    total  = sum(sizes)
    colors = COLORS[:len(labels)]

    def polar(angle, r):
        rad = math.radians(angle - 90)
        return cx + r * math.cos(rad), cy + r * math.sin(rad)

    wedge_svgs = []
    angle = 0
    for i, size in enumerate(sizes):
        sweep = size / total * 360
        large = 1 if sweep > 180 else 0
        a1, a2 = angle, angle + sweep
        x1o, y1o = polar(a1, R_out)
        x2o, y2o = polar(a2, R_out)
        x1i, y1i = polar(a2, R_in)
        x2i, y2i = polar(a1, R_in)
        d = (f'M {x1o:.2f} {y1o:.2f} '
             f'A {R_out} {R_out} 0 {large} 1 {x2o:.2f} {y2o:.2f} '
             f'L {x1i:.2f} {y1i:.2f} '
             f'A {R_in} {R_in} 0 {large} 0 {x2i:.2f} {y2i:.2f} Z')
        wedge_svgs.append(f'  <path d="{d}" fill="{colors[i]}" stroke="{BG}" stroke-width="2"/>')
        angle += sweep

    legend_svgs = []
    lx = 220
    ly_start = 58
    row_h = (H - 78) / max(len(labels), 1)

    for i, (lang, count) in enumerate(data.items()):
        ly = ly_start + i * row_h
        pct = count / total * 100
        legend_svgs.append(
            f'  <circle cx="{lx + 6}" cy="{ly + 6}" r="5" fill="{colors[i]}"/>\n'
            f'  <text x="{lx + 16}" y="{ly + 6}" font-family="monospace" font-size="11" fill="{TEXT}" dominant-baseline="middle">{esc(lang)}</text>\n'
            f'  <text x="{W - 16}" y="{ly + 6}" font-family="monospace" font-size="11" fill="{BLUE}" font-weight="bold" text-anchor="end" dominant-baseline="middle">{pct:.1f}%</text>'
        )

    wedge_block  = '\n'.join(wedge_svgs)
    legend_block = '\n'.join(legend_svgs)

    svg = (
        f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <rect width="{W}" height="{H}" fill="{BG}" rx="10"/>\n'
        f'  <text x="22" y="28" font-family="monospace" font-size="13" font-weight="bold" fill="{BLUE}">Top Languages by Repo</text>\n'
        f'  <line x1="22" y1="40" x2="{W-22}" y2="40" stroke="{BLUE}" stroke-width="0.5" opacity="0.25"/>\n'
        f'{wedge_block}\n'
        f'  <circle cx="{cx}" cy="{cy}" r="{R_in - 2}" fill="{BG}"/>\n'
        f'  <line x1="205" y1="48" x2="205" y2="{H - 16}" stroke="{MUTED}" stroke-width="0.4" opacity="0.3"/>\n'
        f'{legend_block}\n'
        f'</svg>'
    )

    os.makedirs(os.path.dirname(LANG_OUTPUT) or '.', exist_ok=True)
    with open(LANG_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f'::notice ::Language chart saved → {LANG_OUTPUT}')


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    if not GITHUB_TOKEN:
        print('::error ::GITHUB_TOKEN is required', file=sys.stderr)
        sys.exit(1)

    try:
        g = Github(GITHUB_TOKEN)

        try:
            stats = compute_stats(g)
            make_stats_card(stats)
        except Exception as e:
            print(f'::error ::Stats card failed: {e}', file=sys.stderr)

        try:
            lang_bytes, total_repos = compute_languages(g)
            if lang_bytes:
                make_donut_chart(lang_bytes, total_repos)
            else:
                print('::warning ::No language data found.')
        except Exception as e:
            print(f'::error ::Language chart failed: {e}', file=sys.stderr)

    except RateLimitExceededException:
        print('::error ::GitHub rate limit exceeded', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()