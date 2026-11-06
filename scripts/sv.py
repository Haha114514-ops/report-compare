# -*- coding: utf-8 -*-
"""找 stock-video 的目录：财报对比片的画面、配音、渲染、切报告都直接调用 stock-video 的脚本，不复制。

顺序：环境变量 STOCK_VIDEO_SKILL → 本 skill 旁边的 ../stock-video → 从当前目录往上找 .claude/skills/stock-video
      → ~/.claude/skills/stock-video。认 scripts/motion.py 在不在。
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def find():
    cands = [os.environ.get('STOCK_VIDEO_SKILL'), os.path.join(os.path.dirname(HERE), '..', 'stock-video')]
    d = os.getcwd()
    while True:
        cands.append(os.path.join(d, '.claude', 'skills', 'stock-video'))
        if os.path.dirname(d) == d: break
        d = os.path.dirname(d)
    cands.append(os.path.join(os.path.expanduser('~'), '.claude', 'skills', 'stock-video'))
    for c in cands:
        if c and os.path.isfile(os.path.join(c, 'scripts', 'motion.py')): return os.path.abspath(c)
    sys.exit('找不到 stock-video 的 scripts/motion.py：设环境变量 STOCK_VIDEO_SKILL=<stock-video 目录>')


def use():
    """把 stock-video/scripts 放进 import 路径，返回 stock-video 目录"""
    d = find()
    p = os.path.join(d, 'scripts')
    if p not in sys.path: sys.path.insert(0, p)
    return d


if __name__ == '__main__':
    print(find())
