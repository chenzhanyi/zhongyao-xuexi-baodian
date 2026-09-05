#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成"中药鉴别"数据文件：jianbie_idx.js / jianbie.js / jianbie_extra.js
数据源：本草典籍参考/开源数据/MedicineRecommendation/app/src/main/assets/herbs_*.json
       （中药世家·开源数据集，Apache-2.0，1000 味，distinguish 字段为鉴别全文）
匹配规则：
  1) 站点药名 = tcm-data.js 的 HERBS 名 ∪ kuozhan.js 的 KZ 键（精确匹配数据集 name）
  2) 匹配到的 → JBI[站点药名] = {o:数据集原药名, d:鉴别全文}（d 为空则跳过）
  3) 未匹配的 → JBI_EXTRA[数据集药名] = {a:别名, s:性味, f:功效, y:用法, d:鉴别全文}
用法：python3 gen_jianbie.py   （在仓库根目录运行）
"""
import json, glob, re, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, '本草典籍参考/开源数据/MedicineRecommendation/app/src/main/assets')
OUT_IDX = os.path.join(ROOT, 'jianbie_idx.js')
OUT_JBI = os.path.join(ROOT, 'jianbie.js')
OUT_EXTRA = os.path.join(ROOT, 'jianbie_extra.js')

def extract_herbs():
    src = open(os.path.join(ROOT, 'tcm-data.js'), encoding='utf-8').read()
    # 仅取 const HERBS = [ ... ]; 之间的数组行
    m = re.search(r'const HERBS\s*=\s*\[(.*?)\n\];', src, re.S)
    names = []
    for line in m.group(1).splitlines():
        mm = re.match(r"^\s*\['([^']+)'", line)
        if mm: names.append(mm.group(1))
    return names

def extract_kz_keys():
    src = open(os.path.join(ROOT, 'kuozhan.js'), encoding='utf-8').read()
    m = re.search(r'const KZ\s*=\s*\{(.*?)\n\};', src, re.S)
    keys = re.findall(r'"([^"]+)"\s*:\s*\{', m.group(1))
    return keys

def clean(s):
    return (s or '').strip()

def main():
    herbs = extract_herbs()
    kz_keys = extract_kz_keys()
    site_names = set(herbs) | set(kz_keys)
    print(f'HERBS 教材药: {len(herbs)}，KZ 拓展药: {len(kz_keys)}，并集: {len(site_names)}')

    files = sorted(glob.glob(os.path.join(ASSETS, 'herbs_*.json')))
    records = []
    for f in files:
        d = json.load(open(f, encoding='utf-8'))
        if isinstance(d, list): records.extend(d)
    print(f'数据集条目: {len(records)}')

    jbi = {}       # 站点标准名 → {o, d}
    extra = {}     # 数据集药名 → {a, s, f, y, d}
    used_ds_names = set()
    for r in records:
        name = clean(r.get('name'))
        if not name: continue
        d = clean(r.get('distinguish'))
        if name in site_names and d:
            # 站点已有药（教材/拓展典籍）：只存鉴别全文 + 数据集原药名
            jbi[name] = {'o': name, 'd': d}
            used_ds_names.add(name)
        elif name not in site_names:
            # 站点未收药：附加分类，存基本信息
            extra[name] = {
                'a': clean(r.get('alias')),
                's': clean(r.get('taste')),
                'f': clean(r.get('function')),
                'y': clean(r.get('usage')),
                'd': d,
            }

    # 断言
    assert set(jbi.keys()) == set(name for name in jbi), 'JBI 键去重失败'
    overlap = set(jbi.keys()) & set(extra.keys())
    assert not overlap, f'JBI 与 JBI_EXTRA 重叠: {overlap}'

    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(',', ':'))

    # 索引文件（键顺序与 JBI 一致，渲染期同步判定按钮显隐）
    idx = {k: 1 for k in jbi}
    with open(OUT_IDX, 'w', encoding='utf-8') as f:
        f.write('// ============================================================\n'
                '// 中药鉴别·索引 jianbie_idx.js：药名→1（该药有鉴别数据）\n'
                '// 键与 jianbie.js 的 JBI 一一对应（键=站点标准名）\n'
                '// 2026-09 由 gen_jianbie.py 从《中药世家·开源数据集》生成（Apache-2.0）\n'
                '// 体积小，随页面同步加载；正文 jianbie.js 点击时才懒加载\n'
                '// ============================================================\n'
                'const JBI_IDX = ' + dump(idx) + ';\n')

    with open(OUT_JBI, 'w', encoding='utf-8') as f:
        f.write('// ============================================================\n'
                '// 中药鉴别·正文 jianbie.js：站点已有药（教材+拓展典籍）的"鉴别"全文\n'
                '// 结构：JBI[站点标准名]={o:数据集原药名, d:鉴别全文}\n'
                '// 出处：中药世家·MedicineRecommendation 开源数据（Apache-2.0），distinguish 字段\n'
                '// 2026-09 由 gen_jianbie.py 生成；体积大，首次点击"鉴别"时懒加载\n'
                '// ============================================================\n'
                'const JBI = ' + dump(jbi) + ';\n')

    with open(OUT_EXTRA, 'w', encoding='utf-8') as f:
        f.write('// ============================================================\n'
                '// 中药鉴别·其他文献附加药 jianbie_extra.js：站点未收药材\n'
                '// 结构：JBI_EXTRA[数据集药名]={a:别名, s:性味, f:功效, y:用法, d:鉴别全文}\n'
                '// 出处：中药世家·MedicineRecommendation 开源数据（Apache-2.0）\n'
                '// 2026-09 由 gen_jianbie.py 生成；体积大，展开附加分类卡时懒加载\n'
                '// ============================================================\n'
                'const JBI_EXTRA = ' + dump(extra) + ';\n')

    for path in (OUT_IDX, OUT_JBI, OUT_EXTRA):
        print(f'{os.path.basename(path)}: {os.path.getsize(path)/1024:.0f} KB')

    print(f'\n★ JBI（站点已有药，含鉴别）: {len(jbi)} 味')
    print(f'  其中 HERBS 教材药: {sum(1 for k in jbi if k in herbs)} 味')
    print(f'  其中 KZ 拓展药: {sum(1 for k in jbi if k in kz_keys)} 味')
    print(f'★ JBI_EXTRA（其他文献附加分类）: {len(extra)} 味')
    print(f'★ 数据集未被收录(既不在JBI也不在EXTRA，多为无鉴别内容): {len(records)-len(jbi)-len(extra)} 条')

if __name__ == '__main__':
    main()
