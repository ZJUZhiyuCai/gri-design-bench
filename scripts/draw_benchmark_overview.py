"""Draw the bilingual README schematic as self-contained SVG and PNG.

Run with a Python environment containing Matplotlib and a Chinese font, e.g.
Source Han Sans SC or Noto Sans CJK SC. SVG text is outlined for portable display.
This schematic illustrates the frozen protocol; it contains no measured curves.
"""
import argparse
from pathlib import Path
import warnings
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Circle
from matplotlib.path import Path as MplPath


ROOT = Path(__file__).resolve().parents[1]
W, H = 1200, 1260
INK = '#172F3E'
MUTED = '#526674'
TEAL = '#117C72'
BLUE = '#3569A7'
AMBER = '#A16716'
RED = '#B24C49'

COPY = {
    'en': {
        'title': 'How GRI Design Bench works',
        's1': 'The formulation responds to glucose',
        's1_sub': 'The parameters stay fixed; the release rate changes over time.',
        'glucose': 'Patient glucose',
        'glucose_body': 'Meals change\nglucose levels',
        'formulation': 'Fixed formulation',
        'formulation_body': 'Finite insulin supply\nStops when empty',
        'release': 'Insulin release',
        'release_body': 'More at high glucose\nLess at low glucose',
        'signal': 'Tissue\nglucose',
        'response': 'Leakage\n+ delay',
        'feedback': 'Absorption and insulin action lower blood glucose',
        's2': 'The agent searches within a fixed budget',
        'inputs': 'Inputs: known patients, parameter bounds and training meal scenarios',
        'propose': 'Propose', 'propose_body': 'Choose candidate\nparameters',
        'simulate': 'Simulate', 'simulate_body': 'Test patients\non training meals',
        'compare': 'Compare', 'compare_body': 'Inspect glucose\nand safety',
        'submit': 'Submit', 'submit_body': 'One fixed design\ndesign.json',
        'iterate': 'Use the results to revise parameters and try again',
        'budget': '30 CPU seconds  ·  up to 12 model calls  ·  18,000 completion tokens',
        's3': 'Independent evaluation: safety first, then quality',
        's3_sub': 'Re-simulate the submitted design on fresh meal scenarios.',
        'evaluation': 'New meal scenarios',
        'evaluation_body': '3 patients × 2 fresh seeds\n× 3 meal variants\n= 18 three-day traces',
        'gate': 'Every trajectory must pass',
        'thresholds': 'Time below 70: ≤ 4%\nTime below 54: ≤ 1%\nMinimum glucose: ≥ 40',
        'warmup': 'The minimum includes warmup.',
        'pass': 'All pass', 'pass_score': 'Score = mean TIR',
        'fail': 'Any failure', 'fail_score': 'Score = 0',
        'invalid': 'Invalid output or failed simulation also scores zero.',
        'timing': 'Glucose: mg/dL. Time-based metrics use days 2–3.',
        'tir': 'TIR = % of time at 70–180 mg/dL',
        'rank': 'Model ranking: feasible attempts first, then mean score.',
        'desc': 'A fixed formulation senses tissue glucose and changes insulin release, '
                'subject to leakage, delay and a finite reservoir. The agent iterates '
                'over candidate parameters using training simulations, then submits '
                'one fixed design. Independent evaluation uses 18 three-day '
                'trajectories on new meal scenarios. Every trajectory must satisfy '
                'the safety thresholds for the design to receive its mean time in '
                'range; any failure scores zero. Models rank by feasible attempts '
                'first and mean score second.',
    },
    'zh-CN': {
        'title': '从响应配方到最终得分',
        's1': '配方如何响应葡萄糖',
        's1_sub': '固定的是配方参数，释放速率仍会随时间变化。',
        'glucose': '患者血糖', 'glucose_body': '进餐会改变\n葡萄糖水平',
        'formulation': '固定配方', 'formulation_body': '储库内的胰岛素有限\n用尽后停止释放',
        'release': '胰岛素释放', 'release_body': '高糖时释放更多\n低糖时释放更少',
        'signal': '组织液\n葡萄糖信号', 'response': '基础泄漏\n与响应延迟',
        'feedback': '胰岛素经过吸收与作用，使血糖降低',
        's2': 'Agent 如何在预算内搜索方案',
        'inputs': '输入：已知患者、参数边界，以及训练用的进餐情景',
        'propose': '提出候选', 'propose_body': '选择一组\n配方参数',
        'simulate': '运行模拟', 'simulate_body': '测试患者在\n训练情景下的表现',
        'compare': '比较结果', 'compare_body': '检查血糖轨迹\n与安全指标',
        'submit': '提交设计', 'submit_body': '选定一套固定参数\ndesign.json',
        'iterate': '根据结果修正参数，在预算内继续试验',
        'budget': '30 CPU 秒  ·  最多 12 次模型调用  ·  18,000 个输出 token',
        's3': '独立评分：先检查安全，再计算效果',
        's3_sub': '读取已提交的设计，用新的进餐情景独立重算。',
        'evaluation': '新进餐情景',
        'evaluation_body': '3 名患者 × 2 个新种子\n× 3 种进餐变体\n= 18 条三天血糖轨迹',
        'gate': '每条轨迹都要通过',
        'thresholds': '低于 70 的时间比例 ≤ 4%\n低于 54 的时间比例 ≤ 1%\n最低血糖 ≥ 40',
        'warmup': '最低血糖检查包含首日预热期。',
        'pass': '全部通过', 'pass_score': '得分 = 平均 TIR',
        'fail': '任一失败', 'fail_score': '得分 = 0',
        'invalid': '提交无效或模拟失败，同样计零分。',
        'timing': '血糖单位为 mg/dL；时间比例按第 2–3 天计算。',
        'tir': 'TIR = 血糖处于 70–180 的时间比例',
        'rank': '模型排名先比较可行次数，再比较平均得分。',
        'desc': '固定配方感知组织液葡萄糖，并在基础泄漏、响应延迟和有限储库的约束下'
                '调节胰岛素释放。Agent 利用训练模拟反复修改候选参数，最后提交一套'
                '固定设计。独立评测用新进餐情景生成 18 条三天轨迹；每条轨迹均满足'
                '安全阈值时，得分为平均血糖达标时间比例，否则为零。模型排名先比较'
                '可行次数，再比较平均得分。',
    },
}


def chinese_font(path=None):
    if path:
        fm.fontManager.addfont(str(path))
        return fm.FontProperties(fname=str(path)).get_name()
    available = {font.name for font in fm.fontManager.ttflist}
    for family in ('Source Han Sans SC', 'Noto Sans CJK SC', 'Microsoft YaHei',
                   'PingFang SC', 'Heiti SC', 'Arial Unicode MS'):
        if family in available:
            return family
    raise RuntimeError('Install a Chinese font or pass --chinese-font FONT_FILE.')


def draw(language, output, zh_font):
    c = COPY[language]
    family = zh_font if language == 'zh-CN' else 'DejaVu Sans'
    plt.rcParams.update({'font.family': family, 'svg.fonttype': 'path',
                         'svg.hashsalt': 'gri-benchmark-overview-v1',
                         'axes.unicode_minus': False})
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor='white')
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0, W), ylim=(H, 0))
    ax.axis('off')
    labels = []

    def text(x, y, value, size=22, color=INK, bold=False, align='left', width=None):
        item = ax.text(x, y, value, fontsize=size * .72, color=color,
                       fontweight='bold' if bold else 'normal', ha=align, va='center',
                       linespacing=1.2, zorder=5)
        labels.append((item, width))
        return item

    def box(x, y, w, h, fill='white', stroke='#D7E2E6', radius=14, lw=1.2):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                     boxstyle=f'round,pad=0,rounding_size={radius}',
                     facecolor=fill, edgecolor=stroke, linewidth=lw * .72, zorder=1))

    def arrow(points, color, lw=2.2, head=14):
        path = MplPath(points, [MplPath.MOVETO] + [MplPath.LINETO] * (len(points)-1))
        ax.add_patch(FancyArrowPatch(path=path, arrowstyle='-|>', mutation_scale=head,
                                    linewidth=lw * .72, color=color, zorder=3,
                                    capstyle='round', joinstyle='round'))

    def section(y, h, number, title, subtitle, color, fill):
        box(35, y, 1130, h, fill, '#DDE6E9', 19)
        ax.add_patch(Circle((78, y+35), 20, color=color, zorder=2))
        text(78, y+35, number, 20, 'white', True, 'center', 35)
        text(112, y+35, title, 27, INK, True, width=1000)
        text(70, y+73, subtitle, 21, MUTED, width=1060)

    text(60, 30, 'GRI DESIGN BENCH', 16, TEAL, True, width=1080)
    text(60, 73, c['title'], 36, INK, True, width=1080)

    # 1. The physiological feedback loop operates for each tested candidate.
    section(110, 295, '01', c['s1'], c['s1_sub'], TEAL, '#F1F8F6')
    for x, title, body, fill in (
            (70, c['glucose'], c['glucose_body'], 'white'),
            (460, c['formulation'], c['formulation_body'], '#DFF1EC'),
            (850, c['release'], c['release_body'], 'white')):
        box(x, 210, 280, 106, fill, '#BDD8D2')
        text(x+140, 239, title, 23, TEAL, True, 'center', 250)
        text(x+140, 282, body, 20, INK, align='center', width=250)
    arrow([(355, 267), (455, 267)], TEAL)
    arrow([(745, 267), (845, 267)], TEAL)
    text(405, 234, c['signal'], 17, TEAL, align='center', width=100)
    text(795, 234, c['response'], 17, TEAL, align='center', width=100)
    arrow([(990, 321), (990, 351), (210, 351), (210, 321)], TEAL, head=12)
    text(600, 377, c['feedback'], 21, TEAL, align='center', width=1060)

    # 2. The agent revises parameters only while searching on training scenarios.
    section(425, 355, '02', c['s2'], c['inputs'], BLUE, '#F3F6FB')
    xs = (70, 355, 640, 925)
    keys = ('propose', 'simulate', 'compare', 'submit')
    for x, key in zip(xs, keys):
        box(x, 530, 205, 112, '#E7EFFA' if key == 'submit' else 'white', '#C7D5E9')
        text(x+102.5, 558, c[key], 25, BLUE, True, 'center', 181)
        text(x+102.5, 603, c[key+'_body'], 20, INK, align='center', width=181)
    for x in xs[:-1]:
        arrow([(x+210, 587), (x+280, 587)], BLUE)
    arrow([(742.5, 647), (742.5, 682), (172.5, 682), (172.5, 647)], BLUE, head=12)
    text(457.5, 707, c['iterate'], 21, BLUE, align='center', width=760)
    box(70, 733, 1060, 30, '#E7EFFA', '#E7EFFA', 8)
    text(600, 748, c['budget'], 20, BLUE, align='center', width=1030)

    # 3. Only the submitted design proceeds to independent native resimulation.
    section(800, 415, '03', c['s3'], c['s3_sub'], AMBER, '#FCF8F1')
    box(70, 901, 300, 200, 'white', '#DFD5C5')
    text(220, 933, c['evaluation'], 24, INK, True, 'center', 270)
    text(220, 1001, c['evaluation_body'], 20, INK, align='center', width=270)
    text(220, 1073, 'simglucose / dopri5', 18, MUTED, align='center', width=270)
    arrow([(375, 1001), (405, 1001)], AMBER, head=12)

    box(410, 901, 390, 200, '#FBF0DB', '#D5BE91')
    text(605, 933, c['gate'], 24, AMBER, True, 'center', 360)
    text(605, 996, c['thresholds'], 21, INK, align='center', width=360)
    text(605, 1073, c['warmup'], 18, MUTED, align='center', width=360)

    box(850, 901, 280, 86, '#E4F3EC', '#A7CEBA')
    text(990, 925, c['pass'], 19, TEAL, True, 'center', 250)
    text(990, 958, c['pass_score'], 25, TEAL, True, 'center', 250)
    box(850, 1015, 280, 86, '#F9EAE8', '#D9B3AF')
    text(990, 1039, c['fail'], 19, RED, True, 'center', 250)
    text(990, 1072, c['fail_score'], 25, RED, True, 'center', 250)
    arrow([(805, 944), (845, 944)], TEAL, head=12)
    arrow([(805, 1058), (845, 1058)], RED, head=12)

    text(70, 1128, c['timing'], 18, MUTED, width=1060)
    text(70, 1157, c['invalid'], 18, MUTED, width=1060)
    text(1130, 1128, c['tir'], 18, TEAL, align='right', width=470)
    text(600, 1192, c['rank'], 23, INK, True, 'center', 1060)

    # Measure actual font extents before exporting either language.
    with warnings.catch_warnings():
        warnings.filterwarnings('error', message=r'Glyph .* missing from font')
        fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    errors = []
    for item, allowed in labels:
        bounds = item.get_window_extent(renderer)
        if allowed is not None and bounds.width > allowed + .5:
            errors.append(f'text exceeds {allowed}px: {item.get_text()!r}')
        if bounds.x0 < 30 or bounds.x1 > W-30 or bounds.y0 < 20 or bounds.y1 > H-15:
            errors.append(f'text outside canvas: {item.get_text()!r}')
    # Check text-to-text collisions as well as individual width constraints.
    boxes = [(item, item.get_window_extent(renderer)) for item, _ in labels]
    for i, (left, a) in enumerate(boxes):
        for right, b in boxes[i+1:]:
            if a.overlaps(b):
                errors.append(f'labels overlap: {left.get_text()!r} / {right.get_text()!r}')
    if errors:
        raise ValueError(language + ': ' + '; '.join(errors))

    output.mkdir(parents=True, exist_ok=True)
    stem = output / f'benchmark-overview-{language}'
    fig.savefig(stem.with_suffix('.svg'), facecolor='white',
                metadata={'Date': None, 'Creator': 'GRI Design Bench'})
    fig.savefig(stem.with_suffix('.png'), dpi=180, facecolor='white',
                metadata={'Software': 'GRI Design Bench'})
    plt.close(fig)

    # Accessible text remains available even though the visible glyphs are paths.
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    tree = ET.parse(stem.with_suffix('.svg'))
    svg = tree.getroot()
    svg.set('role', 'img')
    svg.set('aria-labelledby', 'overview-title overview-description')
    title = ET.Element('{http://www.w3.org/2000/svg}title', id='overview-title')
    title.text = c['title']
    desc = ET.Element('{http://www.w3.org/2000/svg}desc', id='overview-description')
    desc.text = c['desc']
    svg.insert(0, title)
    svg.insert(1, desc)
    tree.write(stem.with_suffix('.svg'), encoding='utf-8', xml_declaration=True)
    svg_path = stem.with_suffix('.svg')
    svg_path.write_text('\n'.join(line.rstrip() for line in svg_path.read_text().splitlines()) + '\n')
    print(f'Saved {stem.name}.svg and .png; {len(labels)} labels checked.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'docs'/'assets')
    parser.add_argument('--chinese-font', type=Path)
    args = parser.parse_args()
    font = chinese_font(args.chinese_font)
    for language in ('en', 'zh-CN'):
        draw(language, args.output, font)
