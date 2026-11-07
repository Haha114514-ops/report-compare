# -*- coding: utf-8 -*-
"""找 stock-video 的目录：财报对比片的画面、配音、渲染、切报告都直接调用 stock-video 的脚本，不复制。

顺序：环境变量 STOCK_VIDEO_SKILL → 本 skill 旁边的 ../stock-video → 从当前目录往上找工作区技能目录里的 stock-video
      → 用户目录下的技能目录。技能目录各平台不同（SKILL_DIRS），认 scripts/motion.py 在不在。
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIRS = [('.claude', 'skills'), ('.opencode', 'skill'), ('.opencode', 'skills')]   # 工作区里放技能的目录，各平台不同


def find():
    cands = [os.environ.get('STOCK_VIDEO_SKILL'), os.path.join(os.path.dirname(HERE), '..', 'stock-video')]
    d = os.getcwd()
    while True:
        cands += [os.path.join(d, *sd, 'stock-video') for sd in SKILL_DIRS]
        if os.path.dirname(d) == d: break
        d = os.path.dirname(d)
    home = os.path.expanduser('~')
    cands += [os.path.join(home, *sd, 'stock-video') for sd in SKILL_DIRS]
    cands.append(os.path.join(home, '.config', 'opencode', 'skill', 'stock-video'))
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
