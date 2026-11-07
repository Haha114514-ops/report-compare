# -*- coding: utf-8 -*-
"""fetch_reports.py —— 下载对比要用的三份定期报告原文（巨潮），并用 stock-video 的 report_cut.py 切段

    python fetch_reports.py <代码> <工程>/data [--period 2026-09-30] [--notes=科目,…]

下哪三份（年报 / 半年报 / 一季报 / 三季报都认）：
  本期       --period 指定的那一期；不指定就是最新一份
  上一期     本期之前最近的一份（三季报 → 半年报；年报 → 三季报；一季报 → 上年年报）
  去年同期   去年同一期
  另加：最近一份年报（本期不是年报时）——管理层的全年目标、"下一年计划"在年报里，用来对照"说过的兑现了没"

产出：<工程>/data/reports/<标题>.pdf + 切好的段（见 stock-video report_cut.py）、reports_log.json
季报没有附注，切出来主要是"主要会计数据、财务指标发生变动的情况及原因"和非经常性损益表——这是季报里公司自己解释变化的地方，先读。
"""
import contextlib, io, json, os, re, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import warnings; warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv
sv.use()
import report_cut          # stock-video/scripts
import q_cut
import akshare as ak, requests

PERIOD = {'第一季度': '03-31', '一季度': '03-31', '半年度': '06-30', '第三季度': '09-30', '三季度': '09-30', '年度': '12-31'}
KIND = {'03-31': '一季报', '06-30': '半年报', '09-30': '三季报', '12-31': '年报'}


def period_of(title):
    m = re.search(r'(\d{4})\s*年\s*(第一季度|一季度|半年度|第三季度|三季度|年度)报告', title)
    return f'{m.group(1)}-{PERIOD[m.group(2)]}' if m else None


def listing(code):
    y = time.localtime().tm_year
    rows = []
    for cat in ('年报', '半年报', '一季报', '三季报'):
        for i in range(3):
            try:
                with contextlib.redirect_stderr(io.StringIO()):   # akshare 的 tqdm 进度条每类一行，收掉
                    d = ak.stock_zh_a_disclosure_report_cninfo(symbol=code, market='沪深京', category=cat,
                                                               start_date=f'{y - 3}0101', end_date=time.strftime('%Y%m%d'))
                break
            except Exception as e:
                print('retry', cat, i, repr(e)[:120]); time.sleep(2 + 2 * i); d = None
        if d is None: continue
        for _, r in d.iterrows():
            t = str(r['公告标题'])
            if re.search(r'摘要|英文|English|已取消|取消', t): continue
            p = period_of(t)
            if p: rows.append({'期': p, '标题': t, '时间': str(r['公告时间'])[:10], '链接': r['公告链接']})
    # 同一期多份（更正后的版本）取最新公告
    best = {}
    for r in sorted(rows, key=lambda r: r['时间']):
        best[r['期']] = r
    return dict(sorted(best.items()))


def download(r, rdir, notes):
    title = re.sub(r'[\\/:*?"<>|\s]', '', r['标题'])
    aid = re.search(r'announcementId=(\d+)', r['链接']).group(1)
    pdf = os.path.join(rdir, title + '.pdf')
    if not os.path.exists(pdf):
        for ext in ('PDF', 'pdf'):   # 巨潮有的文件是小写 .pdf
            url = f'https://static.cninfo.com.cn/finalpage/{r["时间"]}/{aid}.{ext}'
            resp = requests.get(url, timeout=60, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code != 404: break
        resp.raise_for_status()
        if not resp.content.startswith(b'%PDF'): raise ValueError('不是 PDF: ' + url)
        with open(pdf, 'wb') as fp: fp.write(resp.content)
    res = report_cut.cut(pdf, rdir, title, notes)
    full = os.path.join(rdir, title + '_全文.txt')
    if r['期'][5:] in ('03-31', '09-30') and os.path.exists(full):   # 季报没有附注，按季报固定几节切
        # report_cut 按年报附注清单切，季报会列出 30 多项"没切到"——不是缺材料，只留全文字数，换成季报切段的结果
        res = res.split(' / ')[0] + '；' + q_cut.cut(full)
    return res


def main():
    period, args, skip = None, [], False
    for i, a in enumerate(sys.argv[1:], 1):   # "--period 2026-09-30" 和 "--period=2026-09-30" 都认，值不当位置参数
        if skip: skip = False; continue
        if a == '--period' and i + 1 < len(sys.argv): period, skip = sys.argv[i + 1], True
        elif a.startswith('--period='): period = a.split('=', 1)[1]
        elif not a.startswith('--'): args.append(a)
    if len(args) != 2 or not re.fullmatch(r'\d{6}', args[0]): sys.exit(__doc__)
    code, out = args
    notes = [k for a in sys.argv[1:] if a.startswith('--notes=') for k in a[8:].split(',') if k]
    rdir = os.path.join(out, 'reports'); os.makedirs(rdir, exist_ok=True)

    lst = listing(code)
    if not lst: sys.exit('巨潮上没查到定期报告')
    ps = list(lst)
    P = period or ps[-1]
    if P not in lst: sys.exit(f'巨潮上没有 {P} 这一期；有：{ps[-6:]}')
    i = ps.index(P)
    want = {'本期': P}
    if i > 0: want['上一期'] = ps[i - 1]
    ly = f'{int(P[:4]) - 1}{P[4:]}'
    if ly in lst: want['去年同期'] = ly
    if P[5:] != '12-31':
        fy = [p for p in ps[:i] if p.endswith('12-31')]
        if fy and fy[-1] not in want.values(): want['最近年报'] = fy[-1]

    log = {'清单': {p: r['标题'] + '（' + r['时间'] + '）' for p, r in lst.items()}}
    for role, p in want.items():
        r = lst[p]
        try:
            res = download(r, rdir, notes)
            log[role] = f'{p} {KIND[p[5:]]}：{r["标题"]}（{r["时间"]}）→ {res}'
            print('ok', role, log[role] if len(log[role]) <= 220 else log[role][:220] + '…（全文见 reports_log.json）')
        except Exception as e:
            log[role] = f'FAIL {p}: ' + repr(e)[:200]; print('fail', role, repr(e)[:200])
    json.dump(log, open(os.path.join(out, 'reports_log.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    fails = [k for k, v in log.items() if str(v).startswith('FAIL')]
    if fails: print('失败项（详见 reports_log.json）：', '、'.join(fails))


if __name__ == '__main__':
    main()
