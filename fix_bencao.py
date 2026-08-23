#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bencao.js 校对修复(精确字符串手术):
1. w 字段混入主治(「；主...」且 z 为空) -> 拆回 w=性味 / z=主治
2. z 尾部残留截断的「【」(来源引用被切) -> 移除悬挂的【
3. 莪术整体误复制白术 -> 按《本草纲目·蓬莪荗》修正
"""
import re, json

PATH = 'bencao.js'
src = open(PATH, encoding='utf-8').read()

# ---- 1) 拆分混入主治的 w ----
# 抓取: "KEY":{...gm:{"w": "...", "z": ""}(z为空)
pat = re.compile(r'"([^"]+)":(\{(?:sn:[^,]+?,)?gm:\{)"w": ("(?:\\.|[^"\\])*"), "z": ""')
def split_w(m):
    key = m.group(1)
    w_serial = m.group(3)          # 含引号的序列化形式
    w_raw = json.loads(w_serial)   # 解出真实字符串
    if '；主' not in w_raw:
        return m.group(0)
    i = w_raw.index('；主')
    w, z = w_raw[:i], w_raw[i+2:]
    if z.startswith('主'):
        z = z[1:]
    old = '"w": %s, "z": ""' % w_serial
    new = '"w": %s, "z": %s' % (json.dumps(w, ensure_ascii=False), json.dumps(z, ensure_ascii=False))
    return m.group(0).replace(old, new)

src2, n_split = pat.subn(split_w, src)
print(f'拆分 w 字段: {n_split} 条')

# ---- 2) z 尾部悬挂的【 ----
n_strip = len(re.findall(r'【(?=")', src2))
src2 = re.sub(r'【(?=")', '', src2)
print(f'移除悬挂【: {n_strip} 处')

# ---- 3) 莪术修正 ----
ezhu_old = re.search(r'"莪术":\{gm:\{"w": "[^"]*", "z": "[^"]*"\}\}', src2)
if ezhu_old:
    ezhu_new = '"莪术":{gm:{"w": "苦、辛，温，无毒", "z": "心腹痛、中恶疰忤鬼气、霍乱冷气、吐酸水、解毒、食饮不消（《开宝》），破痃癖冷气、以酒醋磨服，治一切气、开胃消食、通月经、消瘀血、止扑损痛。"}}'
    src2 = src2.replace(ezhu_old.group(0), ezhu_new, 1)
    print('莪术条已修正')
else:
    print('莪术条未找到')

open(PATH, 'w', encoding='utf-8').write(src2)
print('done')
