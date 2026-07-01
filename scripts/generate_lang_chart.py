#!/usr/bin/env python3
"""Fetch GitHub language stats and generate a dark-theme donut chart SVG."""

import os
import sys
from collections import defaultdict

from github import Github
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ── Configuration ──────────────────────────────────────────────────────────
GITHUB_TOKEN = os.environ.get('INPUT_GITHUB_TOKEN') or os.environ.get('GITHUB_TOKEN')
USERNAME = os.environ.get('INPUT_USERNAME', 'licette32')
OUTPUT_PATH = os.environ.get('OUTPUT_PATH', 'assets/lang-chart.svg')
EXCLUDED_REPOS = [r.strip() for r in os.environ.get('EXCLUDED_REPOS', '').split(',') if r.strip()]

# ── Dracula / Aura Dark palette ────────────────────────────────────────────
BG_COLOR = '#0b1120'
TEXT_COLOR = '#e2e8f0'
ACCENT_COLOR = '#60a5fa'
COLORS_CYCLE = [
    '#ff79c6', '#50fa7b', '#8be9fd', '#bd93f9',
    '#ffb86c', '#f1fa8c', '#ff5555', '#6272a4',
    '#69ff94', '#ff92d0', '#a4ffff', '#cba6f7',
]

# ── Helpers ─────────────────────────────────────────────────────────────────

def compute_language_data(g, username):
    """Aggregate bytes of code per language across all non‑fork, non‑archived repos."""
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
    """Group languages below threshold into 'Other'."""
    total = sum(lang_bytes.values())
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


def make_donut_chart(lang_bytes, total_repos):
    """Render a horizontal donut chart with legend and save as SVG."""
    data = prune_small(lang_bytes)
    labels = list(data.keys())
    sizes = list(data.values())
    total_bytes = sum(sizes)
    colors = COLORS_CYCLE[:len(labels)]

    # ── Figure ──────────────────────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(
        1, 2,
        figsize=(8, 2.8),
        gridspec_kw={'width_ratios': [1, 1.1]},
    )
    fig.patch.set_facecolor(BG_COLOR)

    # ── Donut ───────────────────────────────────────────────────────────────
    wedges, _ = ax1.pie(
        sizes,
        labels=None,
        startangle=90,
        counterclock=False,
        colors=colors,
        wedgeprops={
            'linewidth': 1.5,
            'edgecolor': BG_COLOR,
        },
        radius=1,
    )

    centre = plt.Circle((0, 0), 0.60, fc=BG_COLOR, ec=BG_COLOR, lw=2)
    ax1.add_artist(centre)

    ax1.text(
        0, 0, 'Languages',
        ha='center', va='center',
        fontfamily='Courier New, monospace',
        fontsize=9,
        fontweight='bold',
        color=TEXT_COLOR,
        transform=ax1.transData,
    )

    ax1.set_facecolor(BG_COLOR)
    ax1.set_xlim(-1.3, 1.3)

    # ── Legend ──────────────────────────────────────────────────────────────
    ax2.axis('off')
    ax2.set_facecolor(BG_COLOR)

    y_start = 0.92
    row_h = 0.12
    max_items = 12
    items = list(zip(labels, sizes, colors))[:max_items]

    for i, (lang, count, color) in enumerate(items):
        y = y_start - i * row_h
        pct = count / total_bytes * 100

        ax2.scatter(0.05, y, s=180, c=color, edgecolors='none', transform=ax2.transData, zorder=5)
        ax2.text(
            0.14, y, lang,
            fontfamily='Courier New, monospace',
            fontsize=8,
            color=TEXT_COLOR,
            va='center',
            transform=ax2.transData,
        )
        ax2.text(
            0.85, y, f'{pct:.1f}%',
            fontfamily='Courier New, monospace',
            fontsize=8,
            fontweight='bold',
            color=ACCENT_COLOR,
            ha='right', va='center',
            transform=ax2.transData,
        )

    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)
    ax2.text(
        0.5, 1.0, f'based on {total_repos} repos',
        fontfamily='Courier New, monospace',
        fontsize=7,
        color='#64748b',
        ha='center', va='bottom',
        transform=ax2.transData,
    )

    # ── Tight layout & save ─────────────────────────────────────────────────
    plt.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.08, wspace=0.15)
    fig.savefig(
        OUTPUT_PATH,
        format='svg',
        dpi=150,
        facecolor=BG_COLOR,
        edgecolor='none',
        bbox_inches='tight',
        pad_inches=0.1,
    )
    plt.close(fig)


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    if not GITHUB_TOKEN:
        print('::error ::GITHUB_TOKEN is required', file=sys.stderr)
        sys.exit(1)

    g = Github(GITHUB_TOKEN)
    lang_bytes, total_repos = compute_language_data(g, USERNAME)

    if not lang_bytes:
        print('::warning ::No language data found. Skipping chart generation.')
        return

    os.makedirs(os.path.dirname(OUTPUT_PATH) or '.', exist_ok=True)
    make_donut_chart(lang_bytes, total_repos)
    print(f'::notice ::Language chart saved to {OUTPUT_PATH}')


if __name__ == '__main__':
    main()
