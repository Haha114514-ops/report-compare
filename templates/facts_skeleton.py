# -*- coding: utf-8 -*-
"""<公司>(<代码>) <本期> 财报对比 —— facts.py 骨架。复制到 <工程>/facts.py 后改，跑一遍生成 facts.json。

全片每个数从这里来：先跑 compare.py 生成 data/compare.json，这里用 cmp() 取数，说法（对象 / 时间窗 / 口径）自动带上；
报告原文里查到的数（非经常性损益逐项、管理层给的目标、公司自己报的经营指标）用 put() 手写，说法里写出处。
旁白和画面只照 facts.json 的 labels 念。
"""
import os, re, sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def _find(name):
    """找 skill 目录：环境变量 → <skill> → 往上找工作区技能目录（.claude/skills、.opencode/skill 等）里的 <name> 及其入口指向的正本"""
    env = os.environ.get({'stock-video': 'STOCK_VIDEO_SKILL', 'report-compare': 'REPORT_COMPARE_SKILL'}[name])
    cands = [env, r'<skill>' if name == 'report-compare' else None]
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        for sd in (('.claude', 'skills'), ('.opencode', 'skill'), ('.opencode', 'skills')):   # 各平台放技能的目录
            e = os.path.join(d, *sd, name)
            cands.append(e)
            try:   # 工作区入口 SKILL.md 里写着"规约正本：`<路径>\SKILL.md`"
                m = re.search(r'规约正本：`([^`]+?)[\\/]SKILL\.md`', open(os.path.join(e, 'SKILL.md'), encoding='utf-8').read())
                if m: cands.append(m.group(1))
            except OSError:
                pass
        if os.path.dirname(d) == d: break
        d = os.path.dirname(d)
    for c in cands:
        if c and os.path.isfile(os.path.join(c, 'scripts', 'compare.py' if name == 'report-compare' else 'motion.py')): return c
    sys.exit(f'找不到 {name}：设环境变量 REPORT_COMPARE_SKILL / STOCK_VIDEO_SKILL，或把本文件的 <skill> 换成 report-compare 目录')


RC = _find('report-compare')
sys.path.insert(0, os.path.join(RC, 'scripts'))
import sv; sv.use()
from components import put       # stock-video：put(FX, 键, 值, 说法, quote=原文)

ROOT = os.path.dirname(os.path.abspath(__file__))
CJ = json.load(open(os.path.join(ROOT, 'data', 'compare.json'), encoding='utf-8'))
FX = {}
P, KIND, QN = CJ['本期'], CJ['类型'], CJ['单季名']
UNAUD = '' if KIND == '年报' else '，未经审计'     # 半年报经过审计的，这里改成 ''
MONTHS = {'03-31': '1~3 月', '06-30': '1~6 月', '09-30': '1~9 月', '12-31': '全年'}
QM = {'03-31': '1~3 月', '06-30': '4~6 月', '09-30': '7~9 月', '12-31': '10~12 月'}


def _when(field):
    y, ly = P[:4], CJ['去年同期'][:4]
    pq = CJ['上一期']
    return {
        '累计': f'{y} 年 {MONTHS[P[5:]]}累计', '去年同期累计': f'{ly} 年 {MONTHS[P[5:]]}累计',
        '单季': f'{y} 年{QN}单季（{QM[P[5:]]}，累计相减）', '去年同季': f'{ly} 年{QN}单季（累计相减）',
        '上一季': f'{pq[:4]} 年 {QM[pq[5:]]}单季（累计相减）',
        '同比': f'{y} 年 {MONTHS[P[5:]]}累计 vs {ly} 年同期', '单季同比': f'{y} 年{QN}单季 vs {ly} 年{QN}',
        '单季环比': f'{y} 年{QN}单季 vs 上一季',
        '期末': f'{P} 期末余额', '上季末': f'{pq} 期末余额', '年初': f'{CJ["年初"]} 期末余额（年初）',
        '去年同期末': f'{CJ["去年同期"]} 期末余额',
    }[field]


def cmp(key, table, item, field, unit=1e8, nd=2, label_extra=''):
    """从 compare.json 取一个数冻结进 facts.json。
    table: 利润表 / 现金流量表 / 资产负债表 / 比率；field 见 _when()。金额默认换成亿元（unit=1e8）；
    同比、环比字段是 compare.py 写好的文字（如 '+12.3%'、'亏损收窄 40.8%'），原样存。"""
    if table == '比率':
        v = CJ['比率'][field][item]
        val = None if v is None else round(v * 100, 1)
        lab = f'{_when(field)}，{item}（%）{UNAUD if field in ("累计", "单季", "期末", "上一季", "上季末") else ""}'
    else:
        v = CJ[table][item][field]
        tail = UNAUD if field not in ("去年同期累计", "去年同季", "年初", "去年同期末") else ""
        if isinstance(v, str):   # 同比 / 环比：compare.py 写的 '+1.0%'、'亏损收窄 40.8%'、'由正转负'
            m = re.search(r'([+-]?\d+(?:\.\d+)?)%', v)
            val = float(m.group(1)) if m else v
            word = re.sub(r'\s*[+-]?\d+(?:\.\d+)?%', '', v).strip()
            lab = f'{_when(field)}，{item}{"，" + word if word else ""}{"（%）" if m else ""}{tail}'
        else:
            val = None if v is None else round(v / unit, nd)
            lab = f'{_when(field)}，{item}{"（亿元）" if unit == 1e8 else ""}{tail}'
    return put(FX, key, val, lab + (('；' + label_extra) if label_extra else ''))


def diff(key, table, item, a, b, label=None):
    """推算的差额（a - b，亿元），如"9 月底比年初多了多少""比 6 月底少了多少"。旁白念差额时用它，别在脑子里减。
    a / b 是 compare.json 的字段名（期末 / 上季末 / 年初 / 去年同期末 / 累计 / 去年同期累计 / 单季 / 上一季 / 去年同季）"""
    row = CJ[table][item]
    v = None if row.get(a) is None or row.get(b) is None else round((row[a] - row[b]) / 1e8, 2)
    return put(FX, key, v, label or f'推算：{item}，{_when(a)} 减 {_when(b)}（亿元）{UNAUD}')


def seg(key, date, name, field='gm', kind='按行业分类'):
    """主营构成（stock-video fetch_data 的 zygc.csv，来自半年报 / 年报）：field = rev（收入，亿元）/ gm（毛利率，%）。
    季报没有分业务数据，用半年报的，说法里写"半年报 1~6 月"。name 要和 zygc.csv 的"主营构成"一字不差。"""
    import pandas as pd
    z = pd.read_csv(os.path.join(ROOT, 'data', 'zygc.csv'))
    r = z[(z['报告日期'] == date) & (z['分类类型'] == kind) & (z['主营构成'] == name)]
    if r.empty: sys.exit(f'zygc.csv 里没有 {date} {kind} {name}；有：{sorted(z[z["报告日期"] == date]["主营构成"].unique())}')
    v = round(r.iloc[0]['主营收入'] / 1e8, 2) if field == 'rev' else round(r.iloc[0]['毛利率'] * 100, 1)
    win = {'06-30': '1~6 月', '12-31': '全年'}.get(date[5:], date)
    return put(FX, key, v, f'{date[:4]} 年 {win}，{name}{"收入（亿元）" if field == "rev" else "毛利率（%）"}，{"半年报" if date[5:] == "06-30" else "年报"}分业务{"，未经审计" if date[5:] == "06-30" else ""}')


# ---------- 这一期用到的数（按 故事.md 成绩单和三张表逐张填） ----------
put(FX, 'meta.period', P, f'本期：{P}（{KIND}）')
cmp('is.rev_cum', '利润表', '营业收入', '累计')
cmp('is.rev_yoy', '利润表', '营业收入', '同比')
cmp('is.np_q', '利润表', '归母净利润', '单季')
cmp('is.np_qoq', '利润表', '归母净利润', '单季环比')
cmp('r.gm_cum', '比率', '毛利率', '累计')
cmp('bs.cash', '资产负债表', '货币资金', '期末')
cmp('cf.ocf_cum', '现金流量表', '经营活动现金流净额', '累计')
diff('bs.cash_chg_ys', '资产负债表', '货币资金', '期末', '年初')
seg('seg.main_gm', '2026-06-30', '<zygc.csv 里的业务名>')   # 用之前改业务名，不用就删
# 报告原文里的数：put(FX, 'nr.gov_sub', 0.85, '2026 年 1~9 月政府补助，计入非经常性损益，三季报第 2 页', quote='原文……')

json.dump(FX, open(os.path.join(ROOT, 'facts.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('facts.json：', len(FX.get('labels', {})), '个数')
