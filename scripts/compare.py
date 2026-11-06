# -*- coding: utf-8 -*-
"""compare.py —— 两期财报逐行对齐（财报对比片第 1 步）

    python compare.py <工程目录> [--period 2026-09-30] [--quarters 8]

读 <工程>/data/is.csv bs.csv cf.csv（stock-video 的 fetch_data.py 抓的东财长表，A 股一般工商企业）。
写：
  <工程>/data/对比表.md    主控和材料员读：三张表逐行对比、变动最大的行、近 N 季单季走势、交叉检查信号、基数提醒
  <工程>/data/compare.json facts.py 从这里取数（金额单位：元；比率：小数）

口径（细节见 口径.md）：
  - 利润表、现金流量表是"累计数"：一季报 = 1~3 月，半年报 = 1~6 月，三季报 = 1~9 月，年报 = 全年。
    单季 = 本期累计 - 上一期累计（一季度就是一季报本身；四季度 = 年报 - 三季报）。
  - 资产负债表是"时点数"：只能比期末余额（比上季末、比年初、比去年同期末），不能相减求单季。
  - 信号只是"这里要解释"，不是结论；原因去报告里找（季报"主要会计数据发生变动的原因"、附注、管理层原话）。
  - 银行、保险、证券的报表科目不同，本脚本不适用。
"""
import os, sys, json, re
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
YI = 1e8

# ---------- 取数 ----------

def load(path):
    d = pd.read_csv(path, encoding='utf-8-sig')
    d['D'] = d['REPORT_DATE'].astype(str).str[:10]
    if 'NOTICE_DATE' in d: d = d.sort_values('NOTICE_DATE', ascending=False)
    return d.drop_duplicates('D').set_index('D')


def getter(df, date):
    """→ g(列名)：取不到 / 空值返回 None；这一期没有报表行时 g 恒为 None"""
    row = df.loc[date] if date in df.index else None
    def g(col):
        if row is None or col not in row.index: return None
        v = row[col]
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        return None if v != v else v
    g.exists = row is not None
    return g


def add(*xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) if xs else None


def neg(x):
    return None if x is None else -x


def sub(a, b):
    if a is None and b is None: return None
    return (a or 0) - (b or 0)


def first(*xs):
    for x in xs:
        if x is not None: return x
    return None


def div(a, b):
    if a is None or b is None or b == 0: return None
    return a / b


# ---------- 科目（名称, 取法）；取法拿到 g(列名) ----------
IS = [
    ('营业总收入', lambda g: g('TOTAL_OPERATE_INCOME')),
    ('营业收入', lambda g: g('OPERATE_INCOME')),
    ('营业成本', lambda g: g('OPERATE_COST')),
    ('毛利', lambda g: sub(g('OPERATE_INCOME'), g('OPERATE_COST')) if g('OPERATE_INCOME') is not None else None),
    ('税金及附加', lambda g: g('OPERATE_TAX_ADD')),
    ('销售费用', lambda g: g('SALE_EXPENSE')),
    ('管理费用', lambda g: g('MANAGE_EXPENSE')),
    ('研发费用', lambda g: g('RESEARCH_EXPENSE')),
    ('财务费用', lambda g: g('FINANCE_EXPENSE')),
    ('其中：利息费用', lambda g: g('FE_INTEREST_EXPENSE')),
    ('其他收益', lambda g: g('OTHER_INCOME')),
    ('投资收益', lambda g: g('INVEST_INCOME')),
    ('公允价值变动收益', lambda g: g('FAIRVALUE_CHANGE_INCOME')),
    ('信用减值（负数=损失）', lambda g: first(g('CREDIT_IMPAIRMENT_INCOME'), neg(g('CREDIT_IMPAIRMENT_LOSS')))),
    ('资产减值（负数=损失）', lambda g: first(g('ASSET_IMPAIRMENT_INCOME'), neg(g('ASSET_IMPAIRMENT_LOSS')))),
    ('资产处置收益', lambda g: g('ASSET_DISPOSAL_INCOME')),
    ('营业利润', lambda g: g('OPERATE_PROFIT')),
    ('营业外收支净额', lambda g: sub(g('NONBUSINESS_INCOME'), g('NONBUSINESS_EXPENSE'))),
    ('利润总额', lambda g: g('TOTAL_PROFIT')),
    ('所得税', lambda g: g('INCOME_TAX')),
    ('净利润', lambda g: g('NETPROFIT')),
    ('少数股东损益', lambda g: g('MINORITY_INTEREST')),
    ('归母净利润', lambda g: g('PARENT_NETPROFIT')),
    ('扣非归母净利润', lambda g: g('DEDUCT_PARENT_NETPROFIT')),
]
BS = [
    ('货币资金', lambda g: g('MONETARYFUNDS')),
    ('交易性金融资产', lambda g: first(g('TRADE_FINASSET_NOTFVTPL'), g('TRADE_FINASSET'))),
    ('应收票据及账款', lambda g: first(g('NOTE_ACCOUNTS_RECE'), add(g('NOTE_RECE'), g('ACCOUNTS_RECE')))),
    ('其中：应收账款', lambda g: g('ACCOUNTS_RECE')),
    ('预付款项', lambda g: g('PREPAYMENT')),
    ('其他应收款', lambda g: first(g('TOTAL_OTHER_RECE'), g('OTHER_RECE'))),
    ('存货', lambda g: g('INVENTORY')),
    ('合同资产', lambda g: g('CONTRACT_ASSET')),
    ('长期股权投资', lambda g: g('LONG_EQUITY_INVEST')),
    ('投资性房地产', lambda g: g('INVEST_REALESTATE')),
    ('固定资产', lambda g: g('FIXED_ASSET')),
    ('在建工程', lambda g: g('CIP')),
    ('使用权资产', lambda g: g('USERIGHT_ASSET')),
    ('无形资产', lambda g: g('INTANGIBLE_ASSET')),
    ('商誉', lambda g: g('GOODWILL')),
    ('资产总计', lambda g: g('TOTAL_ASSETS')),
    ('短期借款', lambda g: g('SHORT_LOAN')),
    ('应付票据及账款', lambda g: first(g('NOTE_ACCOUNTS_PAYABLE'), add(g('NOTE_PAYABLE'), g('ACCOUNTS_PAYABLE')))),
    ('预收款项+合同负债', lambda g: add(g('ADVANCE_RECEIVABLES'), g('CONTRACT_LIAB'))),
    ('其他应付款', lambda g: first(g('TOTAL_OTHER_PAYABLE'), g('OTHER_PAYABLE'))),
    ('一年内到期的非流动负债', lambda g: g('NONCURRENT_LIAB_1YEAR')),
    ('长期借款', lambda g: g('LONG_LOAN')),
    ('应付债券', lambda g: g('BOND_PAYABLE')),
    ('租赁负债', lambda g: g('LEASE_LIAB')),
    ('负债合计', lambda g: g('TOTAL_LIABILITIES')),
    ('有息负债（含租赁）', lambda g: add(g('SHORT_LOAN'), g('SHORT_BOND_PAYABLE'), g('NONCURRENT_LIAB_1YEAR'),
                                    g('LONG_LOAN'), g('BOND_PAYABLE'), g('LEASE_LIAB'))),
    ('短期有息负债', lambda g: add(g('SHORT_LOAN'), g('SHORT_BOND_PAYABLE'), g('NONCURRENT_LIAB_1YEAR'))),
    ('净有息负债', lambda g: sub(add(g('SHORT_LOAN'), g('SHORT_BOND_PAYABLE'), g('NONCURRENT_LIAB_1YEAR'),
                                g('LONG_LOAN'), g('BOND_PAYABLE'), g('LEASE_LIAB')),
                            add(g('MONETARYFUNDS'), first(g('TRADE_FINASSET_NOTFVTPL'), g('TRADE_FINASSET'))))),
    ('少数股东权益', lambda g: g('MINORITY_EQUITY')),
    ('归母所有者权益', lambda g: g('TOTAL_PARENT_EQUITY')),
]
CF = [
    ('销售商品、提供劳务收到的现金', lambda g: g('SALES_SERVICES')),
    ('购买商品、接受劳务支付的现金', lambda g: g('BUY_SERVICES')),
    ('支付给职工的现金', lambda g: g('PAY_STAFF_CASH')),
    ('支付的各项税费', lambda g: g('PAY_ALL_TAX')),
    ('经营活动现金流净额', lambda g: g('NETCASH_OPERATE')),
    ('购建长期资产（资本开支）', lambda g: g('CONSTRUCT_LONG_ASSET')),
    ('投资支付的现金', lambda g: g('INVEST_PAY_CASH')),
    ('收回投资收到的现金', lambda g: g('WITHDRAW_INVEST')),
    ('投资活动现金流净额', lambda g: g('NETCASH_INVEST')),
    ('吸收投资收到的现金', lambda g: g('ACCEPT_INVEST_CASH')),
    ('取得借款收到的现金', lambda g: g('RECEIVE_LOAN_CASH')),
    ('偿还债务支付的现金', lambda g: g('PAY_DEBT_CASH')),
    ('分配股利、利润或偿付利息（分红付息）', lambda g: g('ASSIGN_DIVIDEND_PORFIT')),
    ('筹资活动现金流净额', lambda g: g('NETCASH_FINANCE')),
    ('现金净增加额', lambda g: g('CCE_ADD')),
    ('经营现金流 - 资本开支', lambda g: sub(g('NETCASH_OPERATE'), g('CONSTRUCT_LONG_ASSET')) if g('NETCASH_OPERATE') is not None else None),
]
TOTALS = {'营业总收入', '营业收入', '营业利润', '利润总额', '净利润', '归母净利润', '扣非归母净利润', '毛利',
          '资产总计', '负债合计', '有息负债（含租赁）', '短期有息负债', '净有息负债', '归母所有者权益',
          '经营活动现金流净额', '投资活动现金流净额', '筹资活动现金流净额', '现金净增加额', '经营现金流 - 资本开支'}
TYPE = {3: '一季报', 6: '半年报', 9: '三季报', 12: '年报'}
QNAME = {3: '一季度', 6: '二季度', 9: '三季度', 12: '四季度'}


# ---------- 期别 ----------

def qend(y, m):
    return f'{y}-{m:02d}-{31 if m in (3, 12) else 30}'


def prev_q(date):
    y, m = int(date[:4]), int(date[5:7])
    return qend(y - 1, 12) if m == 3 else qend(y, m - 3)


def last_year(date):
    return qend(int(date[:4]) - 1, int(date[5:7]))


def year_start(date):
    return qend(int(date[:4]) - 1, 12)


# ---------- 累计、单季、时点 ----------

def cum(df, items, date):
    g = getter(df, date)
    return {n: (f(g) if g.exists else None) for n, f in items}


def single(df, items, date):
    """单季 = 本期累计 - 同年上一期累计；一季度就是累计本身。缺一边就是 None"""
    if int(date[5:7]) == 3: return cum(df, items, date)
    a, b = getter(df, date), getter(df, prev_q(date))
    if not (a.exists and b.exists): return {n: None for n, _ in items}
    out = {}
    for n, f in items:
        x, y = f(a), f(b)
        out[n] = None if x is None and y is None else (x or 0) - (y or 0)
    return out


def ratios(i, c=None):
    """一组利润表数（累计或单季）→ 比率"""
    rev = i.get('营业收入') or i.get('营业总收入')
    r = {
        '毛利率': div(i.get('毛利'), i.get('营业收入')),
        '销售费用率': div(i.get('销售费用'), rev),
        '管理费用率': div(i.get('管理费用'), rev),
        '研发费用率': div(i.get('研发费用'), rev),
        '财务费用率': div(i.get('财务费用'), rev),
        '归母净利率': div(i.get('归母净利润'), i.get('营业总收入')),
        '有效税率（所得税/利润总额）': div(i.get('所得税'), i.get('利润总额')) if (i.get('利润总额') or 0) > 0 else None,
        '扣非 / 归母': div(i.get('扣非归母净利润'), i.get('归母净利润')) if (i.get('归母净利润') or 0) > 0 else None,
        '少数股东损益 / 净利润': div(i.get('少数股东损益'), i.get('净利润')) if (i.get('净利润') or 0) > 0 else None,
    }
    if c is not None:
        r['经营现金流 / 净利润'] = div(c.get('经营活动现金流净额'), i.get('净利润')) if (i.get('净利润') or 0) > 0 else None
        r['收现比（销售收现/营业收入）'] = div(c.get('销售商品、提供劳务收到的现金'), i.get('营业收入'))
    return r


def bs_ratios(b):
    return {
        '资产负债率': div(b.get('负债合计'), b.get('资产总计')),
        '短期有息负债 / 货币资金': div(b.get('短期有息负债'), b.get('货币资金')),
        '有息负债 / 总资产': div(b.get('有息负债（含租赁）'), b.get('资产总计')),
    }


# ---------- 格式 ----------

def yi(x):
    return '—' if x is None else f'{x / YI:,.2f}'


def neg_word(n):
    """负数叫什么：现金流是"净流出"，减值是"损失"，利润类才是"亏损"（旁白照 facts 说法念，叫错会念错）"""
    n = n or ''
    if '现金' in n or n.startswith('经营现金流 -'): return '净流出'
    if '减值' in n: return '损失'
    return '亏损'


def chg(a, b, n=None):
    """变化：(差额, 百分比或说明)；n = 科目名，决定负数的叫法"""
    if a is None or b is None: return None, '—'
    d = a - b
    if b == 0: return d, '基数为 0'
    if b < 0 and a >= 0: return d, '由负转正'
    if b > 0 and a < 0: return d, '由正转负'
    if b < 0:
        w = neg_word(n)
        if a > b: return d, f'{w}收窄 {abs(d / b) * 100:.1f}%' if w != '损失' else f'损失减少 {abs(d / b) * 100:.1f}%'
        return d, f'{w}扩大 {abs(d / b) * 100:.1f}%' if w != '损失' else f'损失增加 {abs(d / b) * 100:.1f}%'
    return d, f'{d / b * 100:+.1f}%'


def chg_txt(a, b, n=None):
    d, p = chg(a, b, n)
    return '—' if d is None else f'{d / YI:+,.2f}（{p}）'


def pct(x):
    return '—' if x is None else f'{x * 100:.1f}%'


def pp(a, b):
    return '—' if a is None or b is None else f'{(a - b) * 100:+.1f} 个百分点'


# ---------- 信号（只是"要解释"，阈值见 口径.md §3） ----------

def signals(P, LY, PQ, YS, ci, ci_ly, cc, cc_ly, b, b_ly, b_ys, r, r_ly, qs):
    out = []
    def S(name, text, where):
        out.append({'信号': name, '数据': text, '去哪找原因': where})
    def gr(a, c):  # 增速
        return None if a is None or c is None or c <= 0 else a / c - 1

    rev_g = gr(ci.get('营业收入'), ci_ly.get('营业收入'))
    rec_g = gr(b.get('应收票据及账款'), b_ly.get('应收票据及账款'))
    if rev_g is not None and rec_g is not None and rec_g - rev_g > 0.15 and (b.get('应收票据及账款') or 0) > 0.03 * (b.get('资产总计') or 1e30):
        S('应收涨得比收入快', f'应收票据及账款比去年同期末 {rec_g * 100:+.1f}%，营业收入同比 {rev_g * 100:+.1f}%',
          '季报变动原因表 / 附注应收账款账龄、前五名客户；问：放宽了账期，还是收入确认提前？')
    cost_g = gr(ci.get('营业成本'), ci_ly.get('营业成本'))
    inv_g = gr(b.get('存货'), b_ly.get('存货'))
    if cost_g is not None and inv_g is not None and inv_g - cost_g > 0.15 and (b.get('存货') or 0) > 0.05 * (b.get('资产总计') or 1e30):
        S('存货涨得比成本快', f'存货比去年同期末 {inv_g * 100:+.1f}%，营业成本同比 {cost_g * 100:+.1f}%',
          '附注存货构成（原材料 / 在产品 / 库存商品）、跌价准备；管理层是否说过备货')
    ocf, npf = cc.get('经营活动现金流净额'), ci.get('净利润')
    if npf is not None and ocf is not None and npf > 0 and ocf < 0.5 * npf:
        S('利润没变成现金', f'累计净利润 {yi(npf)} 亿，经营现金流 {yi(ocf)} 亿（{"负" if ocf < 0 else f"只有 {ocf / npf * 100:.0f}%"}）。{bridge()}',
          '现金流量表直接法：销售收现 vs 购买商品付现；资产负债表应收、存货、预付、合同负债各变了多少')
    def bridge():   # 净利润 → 经营现金流：加回不走经营现金流的项目，剩下的才是营运资金（大悦城 2026Q3 口径审员推出来的桥）
        fin, imp_a = ci.get('财务费用') or 0, -(ci.get('资产减值（负数=损失）') or 0) - (ci.get('信用减值（负数=损失）') or 0)
        inv, gain = ci.get('投资收益') or 0, (ci.get('资产处置收益') or 0) + (ci.get('公允价值变动收益') or 0)
        est = npf + fin + imp_a - inv - gain
        return (f'推算桥：净利润 {yi(npf)} + 财务费用 {yi(fin)}（付息在筹资）+ 减值 {yi(imp_a)}（不花钱）'
                f' {("+ 投资亏损 " + yi(-inv)) if inv < 0 else ("- 投资收益 " + yi(inv))} {("+ 处置/公允亏损 " + yi(-gain)) if gain < 0 else ("- 处置/公允 " + yi(gain))}（钱在投资活动）≈ {yi(est)} 亿，和经营现金流差 {yi(ocf - est)} 亿是营运资金变动'
                f'（存货 / 预收 / 应收 / 应付，看资产负债表比年初）')
    if npf is not None and ocf is not None and npf < 0 and ocf > 0:
        S('亏损但经营现金为正', f'累计净利润 {yi(npf)} 亿，经营现金流 {yi(ocf)} 亿。{bridge()}',
          '先看推算桥；剩下的营运资金按资产负债表比年初拆。别拿"付款比去年少"解释——那只解释同比，解释不了亏损时为什么是正的')
    gm, gm_ly = r.get('毛利率'), r_ly.get('毛利率')
    if gm is not None and gm_ly is not None and abs(gm - gm_ly) > 0.03:
        S('毛利率变化大', f'累计毛利率 {pct(gm)}，去年同期 {pct(gm_ly)}（{pp(gm, gm_ly)}）',
          '主营构成（zygc.csv 按产品 / 行业）的结构变化 vs 单价、成本变化；管理层原话')
    imp = add(ci.get('信用减值（负数=损失）'), ci.get('资产减值（负数=损失）'))
    imp_ly = add(ci_ly.get('信用减值（负数=损失）'), ci_ly.get('资产减值（负数=损失）'))
    tp = ci.get('利润总额')
    if imp is not None and tp is not None and (abs(imp - (imp_ly or 0)) > 0.2 * abs(tp) and abs(imp - (imp_ly or 0)) > 0.02 * abs(ci.get('营业收入') or 0)):
        S('减值变化大', f'累计减值合计 {yi(imp)} 亿，去年同期 {yi(imp_ly)} 亿；利润总额 {yi(tp)} 亿',
          '附注减值明细（哪类资产、哪个项目）；是不是集中在四季度计提的惯例')
    oth = add(ci.get('投资收益'), ci.get('公允价值变动收益'), ci.get('资产处置收益'), ci.get('营业外收支净额'))
    if oth is not None and tp is not None and tp > 0 and abs(oth) > 0.3 * tp:
        S('利润靠主业以外', f'投资收益 + 公允价值 + 资产处置 + 营业外合计 {yi(oth)} 亿，占利润总额 {oth / tp * 100:.0f}%',
          '非经常性损益明细；投资收益附注（卖了什么、联营企业赚了多少）')
    pn, dn = ci.get('归母净利润'), ci.get('扣非归母净利润')
    if pn is not None and dn is not None and abs(pn - dn) > 0.2 * max(abs(pn), abs(dn), 1):
        S('归母和扣非差得多', f'归母 {yi(pn)} 亿，扣非 {yi(dn)} 亿，差 {yi(pn - dn)} 亿',
          '季报"非经常性损益项目和金额"表，逐项抄')
    st, cash = b.get('短期有息负债'), b.get('货币资金')
    if st is not None and cash is not None and st > cash:
        S('短债超过现金', f'短期有息负债 {yi(st)} 亿 > 货币资金 {yi(cash)} 亿（期末）',
          '附注受限资金、一年内到期的债务明细、未用授信；期后有没有发债 / 续贷公告')
    if b_ys.get('货币资金') and cash is not None and cash < 0.7 * b_ys['货币资金']:
        S('现金比年初少了三成以上', f'货币资金 {yi(cash)} 亿，年初 {yi(b_ys["货币资金"])} 亿',
          '现金流量表三块各进出多少：是经营流出、投资花掉，还是还债 / 分红')
    o, o_ly = b.get('其他应收款'), b_ly.get('其他应收款')
    if o is not None and o_ly and o > 1.5 * o_ly and o > 0.02 * (b.get('资产总计') or 1e30):
        S('其他应收款冒出来', f'其他应收款 {yi(o)} 亿，去年同期末 {yi(o_ly)} 亿',
          '附注其他应收款按性质（往来款 / 押金 / 关联方）和前五名；关联交易公告')
    t, t_ly = r.get('有效税率（所得税/利润总额）'), r_ly.get('有效税率（所得税/利润总额）')
    if t is not None and t_ly is not None and abs(t - t_ly) > 0.10:
        S('税率变化大', f'有效税率 {pct(t)}，去年同期 {pct(t_ly)}',
          '年报附注"会计利润与所得税费用调整过程"；季报一般不拆，写"季报没拆原因"')
    cl, cl_ly = b.get('预收款项+合同负债'), b_ly.get('预收款项+合同负债')
    if cl is not None and cl_ly and abs(cl / cl_ly - 1) > 0.25 and cl > 0.03 * (b.get('资产总计') or 1e30):
        S('预收款变化大', f'预收款项 + 合同负债 {yi(cl)} 亿，去年同期末 {yi(cl_ly)} 亿（{(cl / cl_ly - 1) * 100:+.1f}%）',
          '预收是还没确认的收入：它在缩，后面几个季度的收入可能跟着缩（推测，要看订单 / 销售数据）')
    m, m_ly = r.get('少数股东损益 / 净利润'), r_ly.get('少数股东损益 / 净利润')
    if m is not None and m_ly is not None and 0 <= m <= 1 and 0 <= m_ly <= 1 and abs(m - m_ly) > 0.15:   # 超过 100%（归母在亏）时比例没意义
        S('少数股东分走的比例变了', f'少数股东损益占净利润 {pct(m)}，去年同期 {pct(m_ly)}',
          '哪家非全资子公司赚得多了 / 少了；合并范围有没有变')
    me, me_ly = b.get('少数股东权益'), b_ly.get('少数股东权益')
    if me is not None and me_ly and abs(me / me_ly - 1) > 0.15 and abs(me - me_ly) > 0.02 * (b.get('资产总计') or 1e30):
        S('少数股东权益变化大', f'少数股东权益 {yi(me)} 亿，去年同期末 {yi(me_ly)} 亿（{(me / me_ly - 1) * 100:+.1f}%）',
          '收购少数股权 / 子公司私有化 / 合作方退出：归母和少数股东分利润的比例变了，归母的同比要加一句"两年分法不同"（年报、半年报"在子公司中的权益"）')
    mi, pn = ci.get('少数股东损益'), ci.get('归母净利润')
    if mi is not None and pn is not None and pn < 0 < mi and mi > 0.2 * abs(pn):   # 上一条在归母亏损时算不了比例，这条补上
        S('归母亏损但少数股东在赚', f'归母净利润 {yi(pn)} 亿，少数股东损益 {yi(mi)} 亿（去年同期 {yi(ci_ly.get("归母净利润"))} / {yi(ci_ly.get("少数股东损益"))} 亿）',
          '赚钱的是合作项目 / 非全资子公司，亏钱的在全资部分：年报附注"重要非全资子公司"、管理层讨论')
    return out


def base_warn(qs, P):
    """去年同季是近 N 季单季的最高 / 最低 → 提醒同时给环比"""
    out = []
    ly = last_year(P)
    for k in ('营业收入', '归母净利润', '扣非归母净利润', '经营活动现金流净额'):
        ser = [(d, v) for d, v in qs.get(k, []) if v is not None]
        if len(ser) < 5: continue
        vals = dict(ser)
        if ly in vals:
            others = [v for d, v in ser if d != ly]
            if vals[ly] >= max(others): out.append(f'{k}：去年同季（{ly}）是近 {len(ser)} 季单季最高，同比会显得差，要同时给环比')
            elif vals[ly] <= min(others): out.append(f'{k}：去年同季（{ly}）是近 {len(ser)} 季单季最低，同比会显得好，要同时给环比')
    return out


# ---------- 主程序 ----------

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args: print(__doc__); return 2
    root = os.path.abspath(args[0]); data = os.path.join(root, 'data')
    opt = {a.split('=')[0]: a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--') and '=' in a}
    for i, a in enumerate(sys.argv):
        if a in ('--period', '--quarters') and i + 1 < len(sys.argv): opt[a] = sys.argv[i + 1]
    try:
        dis, dbs, dcf = (load(os.path.join(data, f'{n}.csv')) for n in ('is', 'bs', 'cf'))
    except FileNotFoundError as e:
        print('缺数据：', e, '\n先跑 stock-video 的 fetch_data.py <代码> <工程>/data --no-reports'); return 2

    dates = sorted(set(dis.index), reverse=True)
    P = opt.get('--period') or dates[0]
    if P not in dis.index: print('没有这一期：', P, '；有：', dates[:8]); return 2
    NQ = int(opt.get('--quarters', 8))
    m = int(P[5:7]); kind = TYPE[m]
    LY, PQ, YS = last_year(P), prev_q(P), year_start(P)
    PQ_LY = prev_q(LY)

    ci, ci_ly = cum(dis, IS, P), cum(dis, IS, LY)
    cc, cc_ly = cum(dcf, CF, P), cum(dcf, CF, LY)
    qi, qi_ly, qi_pq = single(dis, IS, P), single(dis, IS, LY), single(dis, IS, PQ)
    qc, qc_ly, qc_pq = single(dcf, CF, P), single(dcf, CF, LY), single(dcf, CF, PQ)
    b, b_pq, b_ys, b_ly = (cum(dbs, BS, d) for d in (P, PQ, YS, LY))
    r, r_ly = ratios(ci, cc), ratios(ci_ly, cc_ly)
    rq, rq_ly, rq_pq = ratios(qi, qc), ratios(qi_ly, qc_ly), ratios(qi_pq, qc_pq)
    rb, rb_pq, rb_ys, rb_ly = bs_ratios(b), bs_ratios(b_pq), bs_ratios(b_ys), bs_ratios(b_ly)

    # 近 N 季单季走势（利润 / 现金流）和季末余额（资产负债表）
    qdates = []
    d = P
    while len(qdates) < NQ and d in dis.index:
        qdates.append(d); d = prev_q(d)
    qdates = qdates[::-1]
    keys_i = ['营业收入', '毛利', '归母净利润', '扣非归母净利润', '资产减值（负数=损失）']   # 减值：四季度常集中计提，"下一份看什么"的门槛要用
    keys_c = ['经营活动现金流净额', '购建长期资产（资本开支）']
    keys_b = ['货币资金', '有息负债（含租赁）', '应收票据及账款', '存货', '预收款项+合同负债']
    qs = {k: [] for k in keys_i + ['毛利率'] + keys_c + keys_b}
    for d in qdates:
        si, sc, sb = single(dis, IS, d), single(dcf, CF, d), cum(dbs, BS, d)
        for k in keys_i: qs[k].append((d, si[k]))
        qs['毛利率'].append((d, ratios(si)['毛利率']))
        for k in keys_c: qs[k].append((d, sc[k]))
        for k in keys_b: qs[k].append((d, sb[k]))

    sig = signals(P, LY, PQ, YS, ci, ci_ly, cc, cc_ly, b, b_ly, b_ys, r, r_ly, qs)
    warn = base_warn(qs, P)
    name = str(dis.loc[P].get('SECURITY_NAME_ABBR', '')) if P in dis.index else ''
    notice = str(dis.loc[P].get('NOTICE_DATE', ''))[:10] if 'NOTICE_DATE' in dis.columns else ''
    qn = QNAME[m]

    # ---------- 对比表.md ----------
    L = [f'# {name} {P[:4]} {kind} 对比表（compare.py 生成，别手改）', '',
         f'- 本期：{P}（{kind}，公告 {notice}）；去年同期：{LY}；上一期：{PQ}；年初：{YS}',
         f'- 利润表、现金流量表："累计" = 年初到期末；"单季" = 本期累计 - 上一期累计（{qn}）。资产负债表是期末余额，只比余额。',
         '- 金额单位：亿元（原始值算增速，表里只是显示四舍五入）。',
         '- 季报、半年报一般未经审计（以报告首页"是否经审计"为准）。', '']
    L += ['## 一、交叉检查信号（只是"要解释"，不是结论；每条在 故事.md 第三节写讲 / 不讲和理由）', '']
    L += [f'{i + 1}. **{s["信号"]}**：{s["数据"]}。去哪找原因：{s["去哪找原因"]}' for i, s in enumerate(sig)] or ['- 无']
    L += ['', '## 二、基数提醒', ''] + ([f'- {w}' for w in warn] or ['- 无'])

    def flow_table(title, items, c, c_ly, q, q_ly, q_pq, rr, rr_ly, rrq, rrq_ly, rrq_pq):
        T = ['', f'## {title}', '']
        has_q = m != 3
        head = '| 项目 | 本期累计 | 去年同期累计 | 同比变化 |'
        if has_q: head += f' 本季单季（{qn}） | 去年同季 | 单季同比 | 上一季单季 | 单季环比 |'
        T += [head, '|' + '---|' * (head.count('|') - 1)]
        for n, _ in items:
            row = f'| {"**" + n + "**" if n in TOTALS else n} | {yi(c[n])} | {yi(c_ly[n])} | {chg_txt(c[n], c_ly[n], n)} |'
            if has_q: row += f' {yi(q[n])} | {yi(q_ly[n])} | {chg_txt(q[n], q_ly[n], n)} | {yi(q_pq[n])} | {chg_txt(q[n], q_pq[n], n)} |'
            T.append(row)
        if rr is not None:
            for k in rr:
                row = f'| {k} | {pct(rr[k])} | {pct(rr_ly.get(k))} | {pp(rr[k], rr_ly.get(k))} |'
                if has_q: row += f' {pct(rrq.get(k))} | {pct(rrq_ly.get(k))} | {pp(rrq.get(k), rrq_ly.get(k))} | {pct(rrq_pq.get(k))} | {pp(rrq.get(k), rrq_pq.get(k))} |'
                T.append(row)
        return T

    L += flow_table('三、利润表', IS, ci, ci_ly, qi, qi_ly, qi_pq, r, r_ly, rq, rq_ly, rq_pq)
    L += flow_table('四、现金流量表', CF, cc, cc_ly, qc, qc_ly, qc_pq, None, None, None, None, None)
    L += ['', '## 五、资产负债表（期末余额）', '',
          '| 项目 | 本期末 | 上季末 | 比上季末 | 年初 | 比年初 | 去年同期末 | 比去年同期末 | 占总资产 |',
          '|---|---|---|---|---|---|---|---|---|']
    ta = b.get('资产总计')
    for n, _ in BS:
        L.append(f'| {"**" + n + "**" if n in TOTALS else n} | {yi(b[n])} | {yi(b_pq[n])} | {chg_txt(b[n], b_pq[n])} | {yi(b_ys[n])} | '
                 f'{chg_txt(b[n], b_ys[n])} | {yi(b_ly[n])} | {chg_txt(b[n], b_ly[n])} | {pct(div(b[n], ta))} |')
    for k in rb:
        L.append(f'| {k} | {pct(rb[k])} | {pct(rb_pq[k])} | {pp(rb[k], rb_pq[k])} | {pct(rb_ys[k])} | {pp(rb[k], rb_ys[k])} | '
                 f'{pct(rb_ly[k])} | {pp(rb[k], rb_ly[k])} | |')

    # 变动最大的行（不含合计行）：利润表 / 现金流按同比差额，资产负债表按比年初差额
    def movers(items, now, base, k=6):
        rows = [(n, now[n] - base[n]) for n, _ in items if n not in TOTALS and now[n] is not None and base[n] is not None]
        return sorted(rows, key=lambda x: -abs(x[1]))[:k]
    L += ['', '## 六、变动最大的行（不含合计行，按差额绝对值排；深挖从这里挑）', '']
    for title, items, now, base, basis in (('利润表（累计同比）', IS, ci, ci_ly, ci.get('营业收入')),
                                           ('现金流量表（累计同比）', CF, cc, cc_ly, ci.get('营业收入')),
                                           ('资产负债表（比年初）', BS, b, b_ys, ta)):
        unit = '占本期营业收入' if '资产' not in title else '占总资产'
        L.append(f'- {title}：' + '；'.join(f'{n} {d / YI:+,.2f} 亿（{unit} {pct(div(abs(d), basis))}）' for n, d in movers(items, now, base)))

    L += ['', f'## 七、近 {len(qdates)} 季走势（利润、现金流为单季；资产负债表为季末余额）', '',
          '| 项目 | ' + ' | '.join(d[:7] for d in qdates) + ' |', '|---|' + '---|' * len(qdates)]
    for k, ser in qs.items():
        f = pct if k == '毛利率' else yi
        L.append(f'| {k} | ' + ' | '.join(f(v) for _, v in ser) + ' |')
    if len(qdates) < 8:
        L.append(f'\n- 只有 {len(qdates)} 季数据：季节性判断不了，旁白别说"往年同季都这样"。')
    open(os.path.join(data, '对比表.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')

    # ---------- compare.json ----------
    def pack_flow(c, c_ly, q, q_ly, q_pq):
        return {n: {'累计': c[n], '去年同期累计': c_ly[n], '同比': chg(c[n], c_ly[n], n)[1],
                    '单季': q[n], '去年同季': q_ly[n], '单季同比': chg(q[n], q_ly[n], n)[1],
                    '上一季': q_pq[n], '单季环比': chg(q[n], q_pq[n], n)[1]} for n in c}
    J = {'公司': name, '本期': P, '类型': kind, '公告日': notice, '去年同期': LY, '上一期': PQ, '年初': YS,
         '单季名': qn, '单位': '元；比率为小数',
         '利润表': pack_flow(ci, ci_ly, qi, qi_ly, qi_pq),
         '现金流量表': pack_flow(cc, cc_ly, qc, qc_ly, qc_pq),
         '资产负债表': {n: {'期末': b[n], '上季末': b_pq[n], '年初': b_ys[n], '去年同期末': b_ly[n]} for n in b},
         '比率': {'累计': r, '去年同期累计': r_ly, '单季': rq, '去年同季': rq_ly, '上一季': rq_pq,
                '期末': rb, '上季末': rb_pq, '年初': rb_ys, '去年同期末': rb_ly},
         '季度走势': {k: [[d, v] for d, v in ser] for k, ser in qs.items()},
         '信号': sig, '基数提醒': warn}
    json.dump(J, open(os.path.join(data, 'compare.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{name} {P} {kind}：信号 {len(sig)} 条，基数提醒 {len(warn)} 条 → data/对比表.md、data/compare.json')
    for s in sig: print('  [信号] ' + s['信号'] + '：' + s['数据'])
    for w in warn: print('  [基数] ' + w)
    return 0


if __name__ == '__main__':
    sys.exit(main())
