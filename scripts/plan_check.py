# -*- coding: utf-8 -*-
"""plan_check.py（财报对比片）—— 文字方案交出去之前跑

    python plan_check.py <工程目录>     读 <工程>/文字方案.md、facts.json、data/compare.json，结果写 <工程>/plan_check.txt

沿用 stock-video 的 plan_check（触发词、7 秒间隔、红线、未经审计、数字对账、重复念的数、强推断词、推算前提），
把"公司一句话 / 生意那一拍"两条换成对比片自己的：
  必须改：
    - 总览没填"一句话定性"或"成绩单"（改善 / 恶化 / 不对劲各几条）
    - 三张表有一张在旁白里一个相关词都没有（对比片三张表都要讲变化）
    - data/compare.json 的交叉检查信号，有一条没出现在文字方案"信号处理表"里（讲 / 不讲都要写理由）
    - 本期是季报 / 半年报，旁白没说"未经审计"，总览也没写"审计：已审计"
  要核：
    - 开场章没出现"同比 / 环比 / 比去年 / 比上一季 / 比年初"这类对比口径
    - 本期不是一季报，旁白里没出现"单季 / 这一季 / X季度"（累计数会把这一季的变化盖住）
    - compare.json 有基数提醒，旁白里却没出现"环比 / 上一季"
    - 结尾章没有"下一份 / 下个季度 / 年报 / 接下来看"
"""
import os, re, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sv, importlib.util
_spec = importlib.util.spec_from_file_location('sv_plan_check', os.path.join(sv.use(), 'scripts', 'plan_check.py'))
P = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(P)   # stock-video 的 plan_check（同名，按路径载入）

WORDS = {
    '利润表': r'收入|营收|毛利|利润|费用|亏损|赚',
    '资产负债表': r'负债|存货|应收|资产|借款|货币资金|账上|合同负债|预收',
    '现金流量表': r'现金流|经营现金|回款|收现|资本开支|筹资|投资活动',
}
CMP = r'同比|环比|比去年|去年同期|比上一?季|上个季度|比年初|年初'
QTR = r'单季|这一季|这个季度|(?<![前后])[一二三四]季度|第[一二三四]季'
NEXT = r'下一份|下个季度|下一季|年报|半年报|接下来看|下次看|盯'


def rules(md, chs, lines):
    """替换 stock-video 的 business()：→ (必须改, 要核, 给作者看的)"""
    must, check, show = [], [], []
    root = os.path.abspath(sys.argv[1])
    allv = ' '.join(s for rows in lines for s in rows)

    def field(name):
        m = re.search(rf'^-\s*{name}[^：:\n]*[：:][ \t]*(.*)$', md, re.M)
        v = m.group(1).strip() if m else ''
        return '' if not v or '<' in v or '__' in v else v

    one, card = field('一句话定性'), field('成绩单')
    if not one: must.append('总览的"一句话定性"没填：这份报告和之前比，一句话是变好、变坏，还是好坏参半')
    else: show.append(f'- 一句话定性：{one}')
    if not card or not re.search(r'改善.*\d|恶化.*\d|不对劲.*\d', card):
        must.append('总览的"成绩单"没填：写"改善 N 条 / 恶化 N 条 / 不对劲 N 条"，每条在 故事.md 第一节有证据')
    else: show.append(f'- 成绩单：{card}')

    for k, pat in WORDS.items():
        if not re.search(pat, allv): must.append(f'旁白里没讲到{k}（一个相关词都没有）：对比片三张表的变化都要讲')

    cj = {}
    p = os.path.join(root, 'data', 'compare.json')
    if os.path.exists(p): cj = json.load(open(p, encoding='utf-8'))
    else: check.append('没找到 data/compare.json：先跑 compare.py')
    sec = re.search(r'信号处理表(.*?)(\n## |\Z)', md, re.S)
    sec = sec.group(1) if sec else ''
    for s in cj.get('信号', []):
        if s['信号'] not in sec:
            must.append(f'信号「{s["信号"]}」（{s["数据"]}）没写进"信号处理表"：讲就写在哪一章，不讲写理由')

    kind = cj.get('类型', '')
    if kind and kind != '年报' and '未经审计' not in allv and not re.search(r'^-\s*审计[：:]\s*已审计', md, re.M):
        must.append(f'本期是{kind}，旁白没说"未经审计"（经过审计就在总览写"- 审计：已审计"）')

    if lines and not re.search(CMP, ''.join(lines[0])):
        check.append('开场章没出现对比口径（同比 / 环比 / 比年初…）：观众知道是在和什么比吗？')
    if kind and kind != '一季报' and not re.search(QTR, allv):
        check.append(f'本期是{kind}（累计数），旁白没讲单季：累计数会把最近这一季的变化盖住，要不要拆出单季？')
    if cj.get('基数提醒') and not re.search(r'环比|上一?季|上个季度', allv):
        check.append('compare.json 有基数提醒（' + '；'.join(cj['基数提醒']) + '），旁白没给环比')
    if lines and not re.search(NEXT, ''.join(lines[-1])):
        check.append('结尾章没说"下一份报告看什么"（哪几个数、什么时候公布）')
    if cj: show.append(f'- 本期：{cj.get("本期")} {kind}；信号 {len(cj.get("信号", []))} 条；基数提醒 {len(cj.get("基数提醒", []))} 条')
    return must, check, show


P.business = rules


def main():
    rc = P.main()
    out = os.path.join(os.path.abspath(sys.argv[1]), 'plan_check.txt') if len(sys.argv) > 1 else None
    if out and os.path.exists(out):
        t = open(out, encoding='utf-8').read()
        t = t.replace('## 公司做什么（作者对着看：外行听完知道它卖什么、给谁、怎么收钱吗）',
                      '## 对比片：定性、成绩单、本期（作者对着看）')
        open(out, 'w', encoding='utf-8').write(t)
    return rc


if __name__ == '__main__':
    sys.exit(main())
