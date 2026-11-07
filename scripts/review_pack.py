# -*- coding: utf-8 -*-
"""review_pack.py（财报对比片）—— 成片后跑，代替直接跑 stock-video 的 review_pack

    python review_pack.py <工程目录>

先跑 stock-video 的 review_pack（抽帧拼图、念到的数画面上有没有、静止段、红线、数字对账、说法对照、推断句、推算句、重复），
再把文末"自查问题 / 口径复核"换成对比片的：stock-video 那套问的是"为什么便宜、估值几问"，对比片不讲估值，问错了作者就会跳过不答。
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sv, importlib.util
_spec = importlib.util.spec_from_file_location('sv_review_pack', os.path.join(sv.use(), 'scripts', 'review_pack.py'))
R = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(R)   # stock-video 的 review_pack（同名，按路径载入）

SELF = '''## 自查问题（作者对着本目录回答；对比片版）

1. 只凭这部片写出：这家公司卖什么、卖给谁（开场那半句）；这份报告和去年同期、上一季比，一句话是变好还是变坏；成绩单每一条（改善 / 恶化 / 不对劲）的数、和什么比、为什么。哪条写不出来或写得含糊？
2. 每个变化，画面图角都写了和什么比（累计 vs 去年同期 / 单季，累计相减 / 比年初）吗？有没有一屏里累计和单季混着画？
3. 画面上出现的每个数，facts.json 里都有吗？画面员为了"算平"补出来的柱子（"其他""报告没说"），标签说的原因有没有超出报告和推算？（旁白数字对账只查念出来的数，画面上的数要人看）
4. "改善"背后有没有一次性收益、少提减值、去年基数低、持股比例变化撑着？片子说了没有？同比和环比是不是同一把尺子？
5. 公司的解释照念的地方，报表核得上吗？解释覆盖的时间（半年报只管上半年）和旁白说的时间一致吗？
6. 结尾"下一份看什么"：每个数有门槛、有公布时间吗？门槛和盯的东西是同一个科目吗（盯减值就给减值的门槛）？
7. 哪一章在凑数？哪几处画面空、挤、静止太久？哪些术语没给半句白话？

## 口径复核（只核口径审片之后改过的句子；没改过就跳过。交回文字方案阶段的同一个口径审员）

1. 上面"旁白数字 ↔ facts 说法"逐行看：改过的句子，累计 / 单季、和什么比、时间窗，和 facts 说法一致吗？季报的数说了"未经审计"吗？
2. 推测念了"可能 / 推测"吗？推算的前提念全了吗，和画面角注是同一句吗？
3. 有没有说过头：单一归因、"恶化"说成"危机"、"改善"说成"反转"、像买卖建议？
'''


def main():
    a = sys.argv[1:]
    root = os.path.abspath(a[0]) if a else None   # 先算：stock-video 的 review_pack 会切工作目录
    out = os.path.abspath(a[a.index('--out') + 1]) if '--out' in a else (os.path.join(root, 'review') if root else None)
    rc = R.main()
    p = os.path.join(out, '审片包.md') if out else None
    if p and os.path.exists(p):
        t = open(p, encoding='utf-8').read()
        i = t.find('## 自查问题')
        if i >= 0:
            open(p, 'w', encoding='utf-8').write(t[:i] + SELF)
        else:
            print('审片包里没找到"## 自查问题"：stock-video review_pack 的小标题改了，自查问题没换成对比片版')
    return rc


if __name__ == '__main__':
    sys.exit(main())
