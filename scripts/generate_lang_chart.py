#!/usr/bin/env python3
"""Generate language donut chart and stats card SVGs from GitHub API."""

import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

from github import Github
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


# ── Configuration ──────────────────────────────────────────────────────────

GITHUB_TOKEN = os.environ.get('INPUT_GITHUB_TOKEN') or os.environ.get('GITHUB_TOKEN')
USERNAME = os.environ.get('INPUT_USERNAME', 'licette32')
LANG_CHART_PATH = os.environ.get('LANG_CHART_PATH', 'assets/lang-chart.svg')
STATS_CARD_PATH = os.environ.get('STATS_CARD_PATH', 'assets/stats-card.svg')
EXCLUDED_REPOS = [r.strip() for r in os.environ.get('EXCLUDED_REPOS', '').split(',') if r.strip()]


# ── Palette (Dracula / Aura Dark) ─────────────────────────────────────────

BG_COLOR = '#0b1120'
TEXT_COLOR = '#e2e8f0'
ACCENT_BLUE = '#60a5fa'
ACCENT_GOLD = '#fbbf24'
LABEL_COLOR = '#94a3b8'
FOOTER_COLOR = '#64748b'

COLORS_CYCLE = [
    '#ff79c6', '#50fa7b', '#8be9fd', '#bd93f9',
    '#ffb86c', '#f1fa8c', '#ff5555', '#6272a4',
    '#69ff94', '#ff92d0', '#a4ffff', '#cba6f7',
]

FONT = 'monospace'


# ── Language data ──────────────────────────────────────────────────────────

def compute_language_data(g, username):
    """Aggregate bytes of code per language across non-fork repos."""
    user = g.get_user(username)
    lang_bytes = defaultdict(int)
    total_repos = 0

    for repo in user.get_repos(type='owner', sort='updated', direction='desc'):
        if repo.fork or repo.archived:
            continue
        if repo.name in EXCLUDED_REPOS:
            continue
        try:
            langs = repo.get_languages()
            for lang, count in langs.items():
                lang_bytes[lang] += count
            total_repos += 1
        except Exception:
            continue

    return dict(lang_bytes), total_repos


def prune_small(lang_bytes, threshold=0.015):
    """Group languages below *threshold* into 'Other'."""
    total = sum(lang_bytes.values())
    if total == 0:
        return {}
    main = {}
    other = 0
    for lang, count in sorted(lang_bytes.items(), key=lambda x: -x[1]):
        if count / total >= threshold:
            main[lang] = count
        else:
            other += count
    if other > 0:
        main['Other'] = other
    return main


# ── Donut chart (unchanged logic, cleaned params) ─────────────────────────

def make_donut_chart(lang_bytes, total_repos):
    """Render a horizontal donut chart with legend → lang-chart.svg."""
    data = prune_small(lang_bytes)
    if not data:
        print('::warning ::Pruned language data is empty, skipping chart.')
        return

    labels = list(data.keys())
    sizes = list(data.values())
    total = sum(sizes)
    colors = COLORS_CYCLE[:len(labels)]

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(8, 2.8),
        gridspec_kw={'width_ratios': [1, 1.1]},
    )
    fig.patch.set_facecolor(BG_COLOR)

    ax1.pie(
        sizes, labels=None,
        startangle=90, counterclock=False,
        colors=colors,
        wedgeprops={'linewidth': 1.5, 'edgecolor': BG_COLOR},
        radius=1,
    )
    centre = plt.Circle((0, 0), 0.60, fc=BG_COLOR, ec=BG_COLOR, lw=2)
    ax1.add_artist(centre)
    ax1.text(0, 0, 'Languages',
             ha='center', va='center', fontfamily=FONT,
             fontsize=9, fontweight='bold', color=TEXT_COLOR)
    ax1.set_facecolor(BG_COLOR)
    ax1.set_xlim(-1.3, 1.3)

    # ── Legend ─────────────────────────────────────────────────────────────
    ax2.axis('off')
    ax2.set_facecolor(BG_COLOR)

    n = len(items) if (items := list(zip(labels, sizes, colors))) else 0
    max_visible = 7
    display_items = items[:max_visible]
    extra = n - max_visible

    y_start = 0.92
    row_h = 0.12

    for i, (lang, count, color) in enumerate(display_items):
        y = y_start - i * row_h
        pct = count / total * 100
        ax2.scatter(0.05, y, s=180, c=color, edgecolors='none',
                    transform=ax2.transData, zorder=5)
        ax2.text(0.14, y, lang, fontfamily=FONT, fontsize=8,
                 color=TEXT_COLOR, va='center', transform=ax2.transData)
        ax2.text(0.85, y, f'{pct:.1f}%', fontfamily=FONT, fontsize=8,
                 fontweight='bold', color=ACCENT_BLUE,
                 ha='right', va='center', transform=ax2.transData)

    if extra > 0:
        y_extra = y_start - max_visible * row_h
        ax2.text(0.14, y_extra, f'+ {extra} more',
                 fontfamily=FONT, fontsize=7, fontstyle='italic',
                 color=FOOTER_COLOR, va='center', transform=ax2.transData)

    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)
    ax2.text(0.5, 1.02, f'based on {total_repos} repos',
             fontfamily=FONT, fontsize=7, color=FOOTER_COLOR,
             ha='center', va='bottom', transform=ax2.transData)

    os.makedirs(os.path.dirname(LANG_CHART_PATH) or '.', exist_ok=True)
    fig.savefig(LANG_CHART_PATH, format='svg',
                facecolor=BG_COLOR, edgecolor='none',
                bbox_inches='tight', pad_inches=0.15)
    plt.close(fig)
    print(f'::notice ::Language chart saved to {LANG_CHART_PATH}')


# ── Stats data ─────────────────────────────────────────────────────────────

def format_number(n):
    if n >= 100_000:
        return f'{n / 1000:.0f}k'
    if n >= 1_000:
        return f'{n / 1000:.1f}k'
    return str(n)


def compute_stats_data(g, username):
    """Fetch profile-wide counts via search + repository iteration.

    Returns a dict with keys: repos, stars, commits, prs, issues, updated.
    Every value is guaranteed to be a safe string (never raises).
    """
    result = {}

    # ── Repo count & stars (iterates once, reused from language data) ──────
    try:
        user = g.get_user(username)
        repos = list(user.get_repos(type='owner', sort='updated', direction='desc'))
        non_fork = [r for r in repos if not r.fork and not r.archived]
        result['repos'] = format_number(len(non_fork))
        result['stars'] = format_number(sum(r.stargazers_count for r in non_fork))
    except Exception as exc:
        print(f'::warning ::Failed to fetch repo list: {exc}')
        result['repos'] = '—'
        result['stars'] = '—'

    # ── PRs & Issues via search API ────────────────────────────────────────
    try:
        pr_result = g.search_issues(f'author:{username} type:pr')
        result['prs'] = format_number(pr_result.totalCount)
    except Exception as exc:
        print(f'::warning ::Failed to search PRs: {exc}')
        result['prs'] = '—'

    try:
        issue_result = g.search_issues(f'author:{username} type:issue')
        result['issues'] = format_number(issue_result.totalCount)
    except Exception as exc:
        print(f'::warning ::Failed to search Issues: {exc}')
        result['issues'] = '—'

    # ── Commits last 365 days via commit-search API ────────────────────────
    try:
        since = (datetime.utcnow() - timedelta(days=365)).strftime('%Y-%m-%d')
        commit_result = g.search_commits(
            f'author:{username} committer-date:>={since}'
        )
        result['commits'] = format_number(commit_result.totalCount)
    except Exception as exc:
        print(f'::warning ::Failed to search commits: {exc}')
        result['commits'] = '—'

    result['updated'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    return result


# ── Stats card render ──────────────────────────────────────────────────────

def make_stats_card(stats):
    """Render a clean metrics card SVG (figsize matches donut chart height)."""
    fig, ax = plt.subplots(figsize=(8, 2.8))
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.axis('off')
    ax.set_xlim(0, 8)
    ax.set_ylim(0, 2.8)

    # Accent bar
    ax.add_patch(plt.Rectangle((0.05, 0), 0.06, 2.8,
                                facecolor=ACCENT_BLUE, edgecolor='none'))

    # Title
    ax.text(0.4, 2.48, 'GITHUB STATISTICS',
            fontfamily=FONT, fontsize=10, fontweight='bold',
            color=ACCENT_BLUE, va='center')

    # Divider
    ax.axhline(y=2.20, xmin=0.05, xmax=0.95,
               color=ACCENT_BLUE, linewidth=0.5, alpha=0.35)

    # Row 1 — 3 cols: Stars / Commits / Repos  (y=1.75 value, y=1.40 label)
    metrics_r1 = [
        (stats['stars'], 1.6, 'Stars'),
        (stats['commits'], 4.0, 'Commits (1y)'),
        (stats['repos'], 6.4, 'Repos'),
    ]
    for val, x, label in metrics_r1:
        ax.text(x, 1.75, val, fontfamily=FONT, fontsize=16,
                fontweight='bold', color=ACCENT_GOLD,
                ha='center', va='center')
        ax.text(x, 1.36, label, fontfamily=FONT, fontsize=8,
                color=LABEL_COLOR, ha='center', va='center')

    # Row 2 — 2 cols: PRs / Issues  (y=0.90 value, y=0.58 label)
    metrics_r2 = [
        (stats['prs'], 1.6, 'Pull Requests'),
        (stats['issues'], 4.0, 'Issues'),
    ]
    for val, x, label in metrics_r2:
        ax.text(x, 0.90, val, fontfamily=FONT, fontsize=16,
                fontweight='bold', color=ACCENT_GOLD,
                ha='center', va='center')
        ax.text(x, 0.58, label, fontfamily=FONT, fontsize=8,
                color=LABEL_COLOR, ha='center', va='center')

    # Footer
    ax.text(7.55, 0.20, f'Updated {stats["updated"]}',
            fontfamily=FONT, fontsize=6, color=FOOTER_COLOR,
            ha='right', va='center')

    os.makedirs(os.path.dirname(STATS_CARD_PATH) or '.', exist_ok=True)
    fig.savefig(STATS_CARD_PATH, format='svg',
                facecolor=BG_COLOR, edgecolor='none',
                bbox_inches='tight', pad_inches=0.15)
    plt.close(fig)
    print(f'::notice ::Stats card saved to {STATS_CARD_PATH}')


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    if not GITHUB_TOKEN:
        print('::error ::GITHUB_TOKEN is required', file=sys.stderr)
        sys.exit(1)

    g = Github(GITHUB_TOKEN)

    # ── 1. Language donut chart ──────────────────────────────────────────
    try:
        lang_bytes, total_repos = compute_language_data(g, USERNAME)
        if lang_bytes:
            make_donut_chart(lang_bytes, total_repos)
        else:
            print('::warning ::No language data, skipping donut chart.')
    except Exception as exc:
        print(f'::error ::Language chart failed: {exc}', file=sys.stderr)

    # ── 2. Stats card ─────────────────────────────────────────────────────
    try:
        stats = compute_stats_data(g, USERNAME)
        make_stats_card(stats)
    except Exception as exc:
        print(f'::error ::Stats card failed: {exc}', file=sys.stderr)


if __name__ == '__main__':
    main()
