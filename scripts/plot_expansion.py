"""Standalone scientific figure of observed round means and feasibility."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

from gri_bench.expansion import REPORT


def plot(summary, output):
    rows = [r for r in summary['rows'] if r['split'] == 'sealed']
    assert len(rows) == 9 and summary['new_attempts'] == 216 and summary['combined_strict_profile_attempts'] == 324
    names = summary['display_names']
    colors = {'six_route_expansion': '#087F72', 'earlier_strict_batch': '#65728D'}
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.spines.top': False,
                         'axes.spines.right': False, 'axes.spines.left': False, 'axes.edgecolor': '#C6CDD4',
                         'text.color': '#182C3E', 'axes.labelcolor': '#31495C', 'xtick.color': '#546675',
                         'ytick.color': '#182C3E', 'svg.fonttype': 'none'})
    fig, (quality, feasible) = plt.subplots(1, 2, figsize=(14.4, 8.4), sharey=True,
                                          gridspec_kw={'width_ratios': [3.5, 1.15], 'wspace': .12})
    fig.subplots_adjust(left=.235, right=.95, top=.80, bottom=.24)
    fig.suptitle('Design quality across nine routed models', x=.035, y=.965, ha='left', fontsize=21, fontweight='bold')
    fig.text(.035, .913, 'Same six sealed cases · three repetitions per route · two chronological batches', fontsize=12, color='#546675')
    quality.set_title('Observed round means and overall mean', loc='left', fontsize=12, pad=15)
    feasible.set_title('Safety + submission', loc='left', fontsize=12, pad=15)
    for i, row in enumerate(rows):
        color = colors[row['cohort']]
        quality.axhline(i, color='#E9EDF0', lw=.8, zorder=0)
        quality.hlines(i, min(row['round_means']), max(row['round_means']), color=color, alpha=.6, lw=1.7)
        quality.scatter(row['round_means'], np.array([-.12, 0., .12]) + i, facecolors='white', edgecolors=color, s=30, linewidth=1.1, zorder=3)
        quality.scatter([row['mean_safe_tir']], [i], color=color, s=66, marker='D', zorder=4)
        feasible.barh(i, 18, height=.34, color='#E9EDF0', zorder=0)
        feasible.barh(i, row['feasible_attempts'], height=.34, color=color, zorder=2)
        feasible.text(19, i, f"{row['feasible_attempts']}/18", ha='left', va='center', fontsize=11)
    quality.set_yticks(range(len(rows)), [f"{r['rank']:g}.  {names[r['model']]}" for r in rows])
    quality.tick_params(axis='y', length=0, pad=12)
    feasible.tick_params(axis='y', left=False, labelleft=False)
    quality.set_ylim(8.6, -.6)
    quality.set_xlim(-2, 102)
    quality.set_xticks([0, 20, 40, 60, 80, 100])
    quality.set_xlabel('Safety-gated TIR (%)', labelpad=12)
    feasible.set_xlim(0, 23)
    feasible.set_xticks([0, 6, 12, 18])
    feasible.set_xlabel('Feasible attempts', labelpad=12)
    quality.grid(axis='x', color='#E2E7EB', linewidth=.7)
    quality.set_axisbelow(True)
    handles = [Line2D([0], [0], marker='D', linestyle='', color=colors['six_route_expansion'], markersize=7, label='Six new routes · 216 trials'),
               Line2D([0], [0], marker='D', linestyle='', color=colors['earlier_strict_batch'], markersize=7, label='Earlier three routes · 108 trials')]
    fig.legend(handles=handles, loc='lower left', bbox_to_anchor=(.225, .13), ncol=2, frameon=False, fontsize=10.5, handletextpad=.6, columnspacing=2.)
    fig.text(.035, .090, 'Small circles: individual round means. Diamonds: mean of three rounds. Submission and safety failures score zero.', fontsize=10, color='#546675')
    fig.text(.035, .057, 'Rows rank by feasibility first, then mean TIR. Fixed-case, cross-batch observations; not a population ranking or clinical validation.', fontsize=10, color='#546675')
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / 'comparison.png', dpi=190, facecolor='white')
    fig.savefig(output / 'comparison.svg', facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--summary', type=Path, default=REPORT / 'summary.json')
    parser.add_argument('--output', type=Path, default=REPORT)
    args = parser.parse_args()
    plot(json.loads(args.summary.read_text()), args.output)
    print('Saved', args.output / 'comparison.png')
