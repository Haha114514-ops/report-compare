# -*- coding: utf-8 -*-
"""q_cut.py —— 季报（一季报 / 三季报）切段。季报没有附注，stock-video 的 report_cut.py 切不出东西；
这里按季报固定的几节切：

    python q_cut.py <报告_全文.txt>      （fetch_reports.py 下载季报后会自动调用）

产出（和全文放在一起）：
  <标题>_季报_主要会计数据.txt   本期 / 年初至今 / 同比，公司自己算的
  <标题>_季报_非经常性损益.txt   逐项金额——"归母和扣非差在哪"从这里抄
  <标题>_季报_变动原因.txt       "主要会计数据和财务指标发生变动的情况及原因"：公司自己对每个大幅变动科目的解释，**先读这个**
  <标题>_季报_其他重要事项.txt   回购、增减持、重大合同等
并在 <标题>_目录索引.md 末尾追加这几段的页码和字数。
"""
import os, re, sys

SECS = [  # (文件名后缀, 起点关键词, 终点关键词列表)
    ('主要会计数据', r'主要会计数据和财务指标(?!发生变动)', [r'非经常性损益项目和金额']),
    ('非经常性损益', r'非经常性损益项目和金额', [r'主要会计数据和财务指标发生变动', r'股东信息']),
    ('变动原因', r'主要会计数据和财务指标发生变动的情况及原因', [r'股东信息', r'其他重要事项', r'季度财务报表']),
    ('其他重要事项', r'其他重要事项', [r'季度财务报表', r'财务报表']),
]


def page_at(text, pos):
    pages = re.findall(r'=====PDF第(\d+)页=====', text[:pos])
    return int(pages[-1]) if pages else 1


def cut(full_txt):
    text = open(full_txt, encoding='utf-8').read()
    base = full_txt[:-len('_全文.txt')] if full_txt.endswith('_全文.txt') else os.path.splitext(full_txt)[0]
    out = []
    for name, start, ends in SECS:
        m = re.search(start, text)
        if not m:
            out.append(f'- {name}：没找到（在全文里搜"{start}"）'); continue
        a = m.start()
        b = min([e.start() for pat in ends for e in [re.search(pat, text[m.end():])] if e] or [len(text) - m.end()]) + m.end()
        seg = text[a:b].strip()
        p = os.path.basename(base) + f'_季报_{name}.txt'
        open(os.path.join(os.path.dirname(full_txt), p), 'w', encoding='utf-8').write(seg + '\n')
        out.append(f'- {name}：`{p}`（PDF 第 {page_at(text, a)}~{page_at(text, b)} 页，{len(seg)} 字）')
    idx = base + '_目录索引.md'
    with open(idx, 'a', encoding='utf-8') as fp:
        fp.write('\n\n## 季报切段（q_cut.py）\n\n' + '\n'.join(out) + '\n')
    return '季报切段：' + '；'.join(x.split('：')[0][2:] + ('×' if '没找到' in x else '✓') for x in out)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) < 2: sys.exit(__doc__)
    print(cut(sys.argv[1]))
