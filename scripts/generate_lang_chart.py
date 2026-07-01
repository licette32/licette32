#!/usr/bin/env python3
"""Generate language donut chart and stats card SVGs from GitHub API."""

import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

from github import Github, RateLimitExceededException
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


# ── Configuration ──────────────────────────────────────────────────────────

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
USERNAME = 'licette32'
LANG_OUTPUT = 'assets/lang-chart.svg'
STATS_OUTPUT = 'assets/stats-card.svg'

# Palette (Aura Dark / Dracula inspired)
BG_COLOR = '#0b1120'
CARD_BG = '#121826'
TEXT_MAIN = '#e2e8f0'
TEXT_MUTED = '#94a3b8'
ACCENT_BLUE = '#60a5fa'
ACCENT_GOLD = '#fbbf24'

COLORS_CYCLE = [
    '#ff79c6', '#38bdf8', '#34d399', '#fbbf24',
    '#a78bfa', '#f87171', '#2dd4bf', '#a1a1aa',
]

FONT = 'monospace'


# ── Helpers ─────────────────────────────────────────────────────────────────

def format_axis(ax):
    ax.set_facecolor(CARD_BG)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)


def format_number(n):
    if n >= 100_000:
        return f'{n / 1000:.0f}k'
    if n >= 1_000:
        return f'{n / 1000:.1f}k'
    return str(n)


# ── Language data ──────────────────────────────────────────────────────────

def compute_language_data(g):
    lang_bytes = defaultdict(int)
    total_repos = 0

    for repo in g.get_user(USERNAME).get_repos(type='owner'):
        if repo.fork or repo.archived:
            continue
        total_repos += 1
        try:
            for lang, count in repo.get_languages().items():
                lang_bytes[lang] += count
        except Exception:
            continue

    return dict(lang_bytes), total_repos


def prune_languages(lang_bytes, threshold=0.03, max_items=8):
    total = sum(lang_bytes.values())
    if total == 0:
        return {}
    sorted_langs = sorted(lang_bytes.items(), key=lambda x: -x[1])
    main = {}
    other = 0
    kept = 0
    for lang, count in sorted_langs:
        if kept < max_items and count / total >= threshold:
            main[lang] = count
            kept += 1
        else:
            other += count
    if other > 0:
        main['Other'] = other
    return main


# ── Stats data ─────────────────────────────────────────────────────────────

def compute_stats_data(g):
    result = {}

    try:
        user = g.get_user(USERNAME)
        repos = list(user.get_repos(type='owner'))
        non_fork = [r for r in repos if not r.fork and not r.archived]
        result['repos'] = format_number(len(non_fork))
        result['stars'] = format_number(sum(r.stargazers_count for r in non_fork))
    except Exception as exc:
        print(f'::warning ::Failed to fetch repos: {exc}')
        result['repos'] = result['stars'] = '—'

    try:
        pr_result = g.search_issues(f'author:{USERNAME} type:pr')
        result['prs'] = format_number(pr_result.totalCount)
    except Exception as exc:
        print(f'::warning ::Failed to search PRs: {exc}')
        result['prs'] = '—'

    try:
        issue_result = g.search_issues(f'author:{USERNAME} type:issue')
        result['issues'] = format_number(issue_result.totalCount)
    except Exception as exc:
        print(f'::warning ::Failed to search Issues: {exc}')
        result['issues'] = '—'

    try:
        since = (datetime.utcnow() - timedelta(days=365)).strftime('%Y-%m-%d')
        commit_result = g.search_commits(f'author:{USERNAME} committer-date:>={since}')
        result['commits'] = format_number(commit_result.totalCount)
    except Exception as exc:
        print(f'::warning ::Failed to search commits: {exc}')
        result['commits'] = '—'

    try:
        contrib_result = g.search_repositories(f'contributor:{USERNAME} fork:false')
        result['contributed'] = format_number(contrib_result.totalCount)
    except Exception as exc:
        print(f'::warning ::Failed to search contributed repos: {exc}')
        result['contributed'] = '—'

    result['updated'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    return result


# ── Render 1: Stats card (classic GitHub card style) ──────────────────────

def make_stats_card(stats):
    fig, ax = plt.subplots(figsize=(8, 2.8))
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.axis('off')
    ax.set_xlim(0, 8)
    ax.set_ylim(0, 2.8)

    # Left accent bar (3px visual width)
    ax.add_patch(plt.Rectangle(
        (0.05, 0), 0.06, 2.8,
        facecolor=ACCENT_BLUE, edgecolor='none',
    ))

    # Title
    ax.text(0.30, 2.48, "Beverly's GitHub Stats",
            fontfamily=FONT, fontsize=10, fontweight='bold',
            color=ACCENT_BLUE, va='center')

    # Divider
    ax.axhline(y=2.20, xmin=0.04, xmax=0.96,
               color=ACCENT_BLUE, linewidth=0.5, alpha=0.30)

    # Row 1: Stars | Commits | Repos  (y=1.80 value, y=1.45 label)
    r1 = [
        (stats['stars'], 1.8, 'Total Stars'),
        (stats['commits'], 4.0, 'Commits (1y)'),
        (stats['repos'], 6.2, 'Repos'),
    ]
    for val, x, label in r1:
        ax.text(x, 1.80, val,
                fontfamily=FONT, fontsize=18, fontweight='bold',
                color=ACCENT_GOLD, ha='center', va='center')
        ax.text(x, 1.45, label,
                fontfamily=FONT, fontsize=8,
                color=TEXT_MUTED, ha='center', va='center')

    # Row 2: PRs | Issues | username  (y=0.95 value, y=0.60 label)
    r2 = [
        (stats['prs'], 1.8, 'Pull Requests'),
        (stats['issues'], 4.0, 'Issues'),
        ('', 6.2, USERNAME),
    ]
    for val, x, label in r2:
        ax.text(x, 0.95, val,
                fontfamily=FONT, fontsize=18, fontweight='bold',
                color=ACCENT_GOLD, ha='center', va='center')
        ax.text(x, 0.60, label,
                fontfamily=FONT, fontsize=8,
                color=TEXT_MUTED, ha='center', va='center')

    # Footer
    ax.text(7.60, 0.18, f'Updated {stats["updated"]}',
            fontfamily=FONT, fontsize=6, color=TEXT_MUTED,
            ha='right', va='center')

    os.makedirs(os.path.dirname(STATS_OUTPUT) or '.', exist_ok=True)
    fig.savefig(STATS_OUTPUT, format='svg',
                facecolor=BG_COLOR, edgecolor='none',
                bbox_inches='tight', pad_inches=0.10)
    plt.close(fig)
    print(f'::notice ::Stats card saved to {STATS_OUTPUT}')


# ── Render 2: Language donut chart ────────────────────────────────────────

def make_donut_chart(lang_bytes, total_repos):
    data = prune_languages(lang_bytes)
    if not data:
        print('::warning ::Pruned language data is empty, skipping chart.')
        return

    labels = list(data.keys())
    sizes = list(data.values())
    total = sum(sizes) or 1
    colors = COLORS_CYCLE[:len(labels)]

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(6, 4),
        gridspec_kw={'width_ratios': [1, 1.15]},
    )
    fig.patch.set_facecolor(BG_COLOR)
    format_axis(ax1)
    format_axis(ax2)

    ax1.fill_between([-1.4, 1.4], -1.4, 1.4, color=CARD_BG)
    ax2.fill_between([0, 1], 0, 1, color=CARD_BG)

    # Donut with hole ratio 0.55 -> width = 1 - 0.55 = 0.45
    ax1.pie(sizes, startangle=90, counterclock=False, colors=colors,
            wedgeprops={'linewidth': 2, 'edgecolor': BG_COLOR, 'width': 0.45},
            radius=1)

    # Center text: repo count in two lines
    ax1.text(0, 0.08, str(total_repos),
             ha='center', va='center',
             fontfamily=FONT, fontsize=18, fontweight='bold',
             color=ACCENT_BLUE)
    ax1.text(0, -0.12, 'repos',
             ha='center', va='center',
             fontfamily=FONT, fontsize=8,
             color=TEXT_MUTED)

    # Legend on right side
    num_items = len(data)
    max_legend = 8
    display_items = list(data.items())[:max_legend]
    extra = num_items - max_legend

    y_top = 0.88
    y_bot = 0.12
    n = len(display_items)
    step = (y_top - y_bot) / max(n, 1)

    for i, (lang, count) in enumerate(display_items):
        y = y_top - i * step
        pct = count / total * 100
        ax2.scatter(0.10, y, s=45, c=colors[i], edgecolors='none')
        ax2.text(0.20, y, lang,
                 fontfamily=FONT, fontsize=8,
                 color=TEXT_MAIN, va='center')
        ax2.text(0.90, y, f'{pct:.1f}%',
                 fontfamily=FONT, fontsize=8, fontweight='bold',
                 color=ACCENT_BLUE, ha='right', va='center')

    if extra > 0:
        ax2.text(0.20, y_bot, f'+ {extra} more',
                 fontfamily=FONT, fontsize=7, fontstyle='italic',
                 color=TEXT_MUTED, va='center')

    ax1.set_xlim(-1.3, 1.3)
    ax1.set_ylim(-1.3, 1.3)
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)

    os.makedirs(os.path.dirname(LANG_OUTPUT) or '.', exist_ok=True)
    fig.savefig(LANG_OUTPUT, format='svg',
                facecolor=BG_COLOR, edgecolor='none',
                bbox_inches='tight', pad_inches=0.10)
    plt.close(fig)
    print(f'::notice ::Language chart saved to {LANG_OUTPUT}')


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    if not GITHUB_TOKEN:
        print('::error ::GITHUB_TOKEN is required', file=sys.stderr)
        sys.exit(1)

    try:
        g = Github(GITHUB_TOKEN)

        # 1. Stats card
        try:
            stats = compute_stats_data(g)
            make_stats_card(stats)
        except Exception as exc:
            print(f'::error ::Stats card failed: {exc}', file=sys.stderr)

        # 2. Language chart
        try:
            lang_bytes, total_repos = compute_language_data(g)
            if lang_bytes:
                make_donut_chart(lang_bytes, total_repos)
            else:
                print('::warning ::No language data, skipping donut chart.')
        except Exception as exc:
            print(f'::error ::Language chart failed: {exc}', file=sys.stderr)

    except RateLimitExceededException:
        print('::error ::GitHub API Rate Limit Exceeded', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
