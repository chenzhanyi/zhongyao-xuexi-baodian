#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从源文本重新抽取数据文件内容，修复 LLM 抽取造成的截断/拼接/碎片问题。
- kuozhan.js      : 备要 src -> 备要完整正文；纲目 src -> 全部【附方】段落（无附方则全文）
- fufang_bencao.js: 纲目【附方】
- benbei.js       : 备要完整正文
保留原 key 顺序与原 o/src/g 字段，仅替换正文(d/c)。
用法: python3 gen_data.py [--apply]   (默认 dry-run, 只报告)
"""
import re, os, sys, json
from opencc import OpenCC

ROOT = os.path.dirname(os.path.abspath(__file__))
T2S = OpenCC('t2s')

# OpenCC 未覆盖的简繁/异体映射
VARIANT_PAIRS = [
    ('痺', '痹'), ('癥', '症'), ('虖', '乎'), ('惪', '德'),
    ('亁', '干'), ('髠', '髡'), ('祕', '秘'), ('姙', '妊'),
    ('輭', '软'), ('媮', '偷'), ('畧', '略'), ('袐', '秘'),
    ('孼', '孽'), ('恡', '吝'), ('舩', '船'), ('臈', '腊'),
]
# 数字化痕迹修正（wikisource 转写问题，繁体阶段做）
FIX_TXT = [
    ('香港腳', '腳氣'),
    ('（ 存性', '（煅存性'),
    ('雷 曰', '雷斅曰'),
    ('寇宗 曰', '寇宗奭曰'),
    ('王 《百一\n花上粉', '王璆《百一選方》）'),  # 通脱木条源文缺字(须在通用条之前)
    ('王 《百一', '王璆《百一'),
    ('常亲养老书》）', '（《奉亲养老书》）'),
    ('常親養老書》）', '（《奉親養老書》）'),
    ('白 石', '白礜石'),          # 源文"白礜石"缺"礜"
    ('痱 ︰', '痱子︰'),
    # 空括号恢复炮制(经全书交叉引用确认)
    ('石膏（ ）', '石膏（煅）'),
    ('寒水石（ ）', '寒水石（煅）'),
    ('牡蠣（ ）', '牡蠣（煅）'),
    ('磁石（ ）', '磁石（煅）'),
    ('爐甘石（ ）', '爐甘石（煅）'),
    ('赤石脂（ ）', '赤石脂（煅）'),
    ('白石脂（ ）', '白石脂（煅）'),
    ('陽起石（ ）', '陽起石（煅）'),
    ('白礬（ ）', '白礬（燒）'),
    ('甘草（ ）', '甘草（炙）'),
    ('龍骨（）', '龍骨（煅）'),
]

# ---------- 源文本解析 ----------
# 纲目分卷有两种格式:
#  A: == 药名 == 为条目, === 節名 === 为小节 (如草之一.txt)
#  B: == 卷标题 == 为卷,  === 药名 === 为条目, 【節名】为小节 (如草之二.txt)
VOL_TITLE = re.compile(r'[種類卷]|[之][一二三四五六七八九十]+$')
SKIP_FILES = {'凡例', '序', '序例上', '序例下', '百病主治藥上', '百病主治藥下', '主治', '名醫別錄'}

def load_gangmu():
    """{药名: [正文块...]}"""
    entries = {}
    d = os.path.join(ROOT, '本草典籍参考', '本草纲目')
    for fn in sorted(os.listdir(d)):
        if not fn.endswith('.txt') or fn[:-4] in SKIP_FILES: continue
        txt = open(os.path.join(d, fn), encoding='utf-8').read()
        # 去 wiki header
        txt = re.sub(r'\{\{[Hh]eader2?\s*\|.*?\}\}', '', txt, flags=re.S)
        l2_names = [m.strip() for m in re.findall(r'^==\s*([^=]+?)\s*==\s*$', txt, re.M)]
        patternA = any(not VOL_TITLE.search(n) for n in l2_names)
        if patternA:
            parts = re.split(r'^==\s*([^=]+?)\s*==\s*$', txt, flags=re.M)
            for i in range(1, len(parts), 2):
                name, body = parts[i].strip(), parts[i+1]
                if VOL_TITLE.search(name): continue  # 卷标题
                entries.setdefault(name, []).append(body)
        else:
            # 条目 = === X ===; ==== 子条目留在父条正文内
            parts = re.split(r'^={3}\s*([^=]+?)\s*={3}\s*$', txt, flags=re.M)
            for i in range(1, len(parts), 2):
                name, body = parts[i].strip(), parts[i+1]
                entries.setdefault(name, []).append(body)
    return entries

def load_bei_yao():
    """{药名: [正文...]}"""
    txt = open(os.path.join(ROOT, '本草典籍参考', '本草备要.txt'), encoding='utf-8').read()
    entries = {}
    for b in re.split(r'<篇名>', txt):
        m = re.match(r'([^\n]+)\n内容：([\s\S]*)', b)
        if m:
            entries.setdefault(m.group(1).strip(), []).append(m.group(2).strip())
    return entries

# ---------- 清洗 ----------
def clean_text(s: str, keep_lines: bool = False) -> str:
    """源文本 -> 干净简体文本
    流水线: 源文补缺 -> wiki标记 -> 实体 -> \\x异名 -> 段落/硬换行还原 -> 繁转简
    keep_lines=True(备要): 换行视为段落(调用方已整理); 否则纲目: 硬折行折叠, 空行/【节】为段落
    """
    # 1) 已知转写缺陷修复(繁体阶段)
    for a, b in FIX_TXT:
        s = s.replace(a, b)
    s = re.sub(r'王璆?《百一\s*\n+\s*花上粉', '王璆《百一選方》）', s)   # 通脱木条缺字
    s = re.sub(r'([。；])(?=《[^》\n]{1,12}》）)', r'\1（', s)   # 补丢失的前括号: 。《x》） -> 。（《x》）
    s = s.replace('（ ）', '').replace('（）', '')              # 无法恢复的空括号 -> 移除
    # 2) wiki 标记
    s = re.sub(r'\{\{\*\|([^}]*)\}\}', r'\1', s)          # {{*|…}} 取内容
    s = re.sub(r'\{\{[A-Za-z\- /]*\}\}', '', s)           # {{PD-old}} 等
    s = s.replace('PD-old', '').replace('Category', '')
    s = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', s)  # [[链接|显示]] -> 显示
    s = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), s)
    # 3) \x…\x 异名标记 -> （…）
    parts = s.split('\\x')
    out = []
    for i, p in enumerate(parts):
        if i % 2 == 1:
            p = p.strip()
            if p:
                out.append('（' + p + '）')
        else:
            out.append(p)
    s = ''.join(out)
    if keep_lines:
        s = s.replace('\\n', ' ')   # 字面 \n 罕见, 视作空格
    else:
        # 4) 字面 \n 段落标记 -> 哨兵
        s = s.replace('\\n', '')
        # 5) 真实换行: 【节】另起段; 空行=段落; 其余硬换行折叠
        s = s.replace('\n【', '【')
        s = re.sub(r'\n{2,}', '', s)
        s = s.replace('\n', '')
        s = s.replace('', '\n').replace('', '\n')
    # 6) 行内空白压缩
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r' *\n *', '\n', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    s = s.strip()
    # 7) 繁转简
    s = T2S.convert(s)
    for a, b in VARIANT_PAIRS:
        s = s.replace(a, b)
    return s

def clean_beiyao(body: str) -> str:
    """备要正文: 功效头行(≤24字)独立成段, 其余硬折行拼接, 再去 <目录> 尾后清洗"""
    body = body.split('<目录>')[0]
    lines = [ln.strip() for ln in body.split('\n') if ln.strip()]
    if not lines:
        return ''
    paras = []
    if len(lines[0]) <= 24:
        paras.append(lines[0])
        rest = lines[1:]
    else:
        rest = lines
    paras.append(''.join(rest))
    return clean_text('\n'.join(paras), keep_lines=True)

# ---------- 纲目附方抽取 ----------
# 附方起点: 【附方】 或 === 附方 === / ====【附方】====
FF_START = re.compile(r'【附方】|^={2,}\s*【?\s*附方\s*】?\s*={2,}\s*$', re.M)
def gangmu_fufang(body: str) -> str:
    """提取条内所有附方段落(兼容A/B两种格式); 无附方则返回全文"""
    segs = []
    for m in FF_START.finditer(body):
        tail = body[m.end():]
        # 到下一个结构边界: ===行 或 【…】节
        b1 = re.search(r'\n={2,}', tail)
        b2 = re.search(r'\n【', tail)
        end = None
        if b1 and b2: end = min(b1.start(), b2.start())
        elif b1: end = b1.start()
        elif b2: end = b2.start()
        seg = tail if end is None else tail[:end]
        seg = clean_text(seg)
        # 源文方文缺失的退化段(如"新一。野狼跋子"仅剩小标题) -> 跳过
        if seg and (len(seg) > 12 or '：' in seg or '︰' in seg):
            segs.append(seg)
    if segs:
        return '\n\n'.join(segs)
    return clean_text(body)

# ---------- 名称查找 ----------
def simp_name(n: str) -> str:
    """简体+异体归一(用于名称匹配)"""
    n = T2S.convert(n)
    for a, b in VARIANT_PAIRS:
        n = n.replace(a, b)
    return n

def name_variants(name, o_names=()):
    """返回用于匹配源条的候选名集合(按优先级: 原名 -> 归一 -> 去括号 -> 去括号+归一)"""
    vs = []
    for n in (name,) + tuple(o_names or ()):
        for v in (n, simp_name(n)):
            if v and v not in vs: vs.append(v)
        n2 = re.sub(r'[（(].*?[)）]', '', n).strip()   # 去括号注释
        for v in (n2, simp_name(n2)):
            if v and v not in vs: vs.append(v)
    return vs

def find_entry(name, o_names, corpus):
    """精确 -> 去括号 -> 双向包含(赤箭⊂赤箭天麻, 术⊂白术)"""
    for v in name_variants(name, o_names):
        if v in corpus:
            return v
    # 双向包含
    best = None
    for v in name_variants(name, o_names):
        if len(v) < 2: continue
        for k in corpus:
            if v in k or k in v:
                if best is None or len(k) > len(best):
                    best = k
    return best

# ---------- JS 数据解析(保留顺序) ----------
def parse_kv_js(path, kind):
    src = open(path, encoding='utf-8').read()
    order, out = [], {}
    if kind in ('kz',):
        for m in re.finditer(r'"([^"]+)":\{o:\[([^\]]*)\],src:\[([^\]]*)\],d:"((?:[^"\\]|\\.)*)"', src):
            n = m.group(1)
            order.append(n)
            out[n] = {
                'o': [x.strip().strip('"') for x in m.group(2).split(',') if x.strip()],
                'src': [x.strip().strip('"') for x in m.group(3).split(',') if x.strip()],
                'd': js_unescape(m.group(4)),
            }
    elif kind == 'fufang':
        for m in re.finditer(r'"([^"]+)":"((?:[^"\\]|\\.)*)"', src):
            n = m.group(1)
            order.append(n)
            out[n] = {'d': js_unescape(m.group(2))}
    elif kind == 'benbei':
        for m in re.finditer(r'"([^"]+)":\{o:"((?:[^"\\]|\\.)*)",c:"((?:[^"\\]|\\.)*)",g:"((?:[^"\\]|\\.)*)"\}', src):
            n = m.group(1)
            order.append(n)
            out[n] = {'o': js_unescape(m.group(2)), 'c': js_unescape(m.group(3)), 'g': js_unescape(m.group(4))}
    return order, out

def js_unescape(s):
    return re.sub(r'\\(.)', lambda m: {'n': '\n', 't': '\t', '"': '"', '\\': '\\'}.get(m.group(1), '\\' + m.group(1)), s)

def js_dump(s):
    return json.dumps(s, ensure_ascii=False, separators=(',', ':'))

# 数据中的垃圾 key(卷标题/部件名被误当药名), 对应内容已由所属药条覆盖
DROP_KEYS = {'根叶', '草之三 芳草类五十六种'}

# ---------- 主流程 ----------
def main():
    apply = '--apply' in sys.argv
    gm = load_gangmu()
    by = load_bei_yao()
    # 简体+异体归一键索引
    gm_s = {simp_name(k): k for k in gm}
    by_s = {simp_name(k): k for k in by}
    print(f'源文本: 纲目 {len(gm)} 条, 备要 {len(by)} 条')

    # ---- kuozhan.js ----
    order, kz = parse_kv_js(os.path.join(ROOT, 'kuozhan.js'), 'kz')
    dropped = [n for n in order if n in DROP_KEYS]
    order = [n for n in order if n not in DROP_KEYS]
    if dropped:
        print(f'[kuozhan] 删除垃圾key: {dropped}')
    fixed = missing = kept = 0
    miss_list = []
    for n in order:
        e = kz[n]
        want_by = any('备要' in s for s in e['src'])
        newd = None
        if want_by:
            k = find_entry(n, e['o'], by_s)
            if k:
                body = by[by_s[k]][0]
                newd = clean_beiyao(body)
        if newd is None:
            k = find_entry(n, e['o'], gm_s)
            if k:
                newd = gangmu_fufang(gm[gm_s[k]][0])
        if newd is not None and newd != e['d']:
            fixed += 1
        elif newd is not None:
            kept += 1
        else:
            missing += 1
            miss_list.append((n, e['src'], e['o'], e['d'][:40]))
        e['d'] = newd if newd is not None else e['d']
    print(f'\n[kuozhan] 总{len(order)}: 修复替换{fixed}, 原文已一致{kept}, 源中找不到{missing}')
    for n, s, o, d in miss_list:
        print(f'  缺: {n} src={s} o={o} 原文={d!r}')

    # ---- fufang_bencao.js ----
    order2, ff = parse_kv_js(os.path.join(ROOT, 'fufang_bencao.js'), 'fufang')
    dropped2 = [n for n in order2 if n in DROP_KEYS]
    order2 = [n for n in order2 if n not in DROP_KEYS]
    if dropped2:
        print(f'[fufang] 删除垃圾key: {dropped2}')
    fixed = missing = kept = 0
    miss2 = []
    for n in order2:
        e = ff[n]
        k = find_entry(n, (), gm_s)
        if k:
            newd = gangmu_fufang(gm[gm_s[k]][0])
            if newd != e['d']: fixed += 1
            else: kept += 1
        else:
            missing += 1
            miss2.append((n, e['d'][:40]))
        e['d'] = newd if newd is not None else e['d']
    print(f'\n[fufang] 总{len(order2)}: 修复替换{fixed}, 原文已一致{kept}, 源中找不到{missing}')
    for n, d in miss2:
        print(f'  缺: {n} 原文={d!r}')

    # ---- benbei.js ----
    order3, bb = parse_kv_js(os.path.join(ROOT, 'benbei.js'), 'benbei')
    fixed = missing = kept = 0
    miss3 = []
    for n in order3:
        e = bb[n]
        k = find_entry(n, (e['o'],), by_s)
        if k:
            newc = clean_beiyao(by[by_s[k]][0])
            if newc != e['c']: fixed += 1
            else: kept += 1
            e['c'] = newc
        else:
            missing += 1
            miss3.append((n, e['o'], e['c'][:40]))
    print(f'\n[benbei] 总{len(order3)}: 修复替换{fixed}, 原文已一致{kept}, 源中找不到{missing}')
    for n, o, c in miss3:
        print(f'  缺: {n} o={o} 原文={c!r}')

    if apply:
        # ---- 写出 ----
        with open(os.path.join(ROOT, 'kuozhan.js'), 'w', encoding='utf-8') as f:
            f.write('// ============================================================\n')
            f.write('// 拓展典籍药 kuozhan.js：本草纲目/本草备要出现、未收录进主库的药材\n')
            f.write('// 结构：KZ[现代名]={o:[原书药名], src:[来源], d:详注}\n')
            f.write('// 2026-08 由 gen_data.py 从《本草纲目》《本草备要》源文本重新校对抽取\n')
            f.write('// ============================================================\n\n')
            f.write('const KZ = {\n')
            f.write(',\n'.join('  %s:{o:[%s],src:[%s],d:%s}' % (
                js_dump(n),
                ', '.join(js_dump(x) for x in kz[n]['o']),
                ', '.join(js_dump(x) for x in kz[n]['src']),
                js_dump(kz[n]['d'])) for n in order))
            f.write('\n};\n')
        with open(os.path.join(ROOT, 'fufang_bencao.js'), 'w', encoding='utf-8') as f:
            f.write('// ============================================================\n')
            f.write('// 本草纲目附方 fufang_bencao.js\n')
            f.write('// 2026-08 由 gen_data.py 从《本草纲目》源文本重新校对抽取\n')
            f.write('// ============================================================\n\n')
            f.write('const FUFANG = {\n')
            f.write(',\n'.join('  %s:%s' % (js_dump(n), js_dump(ff[n]['d'])) for n in order2))
            f.write('\n};\n')
        with open(os.path.join(ROOT, 'benbei.js'), 'w', encoding='utf-8') as f:
            f.write('// ============================================================\n')
            f.write('// 本草备要 benbei.js\n')
            f.write('// 2026-08 由 gen_data.py 从《本草备要》源文本重新校对抽取\n')
            f.write('// ============================================================\n\n')
            f.write('const BEIBAO = {\n')
            f.write(',\n'.join('  %s:{o:%s,c:%s,g:%s}' % (
                js_dump(n), js_dump(bb[n]['o']), js_dump(bb[n]['c']), js_dump(bb[n]['g'])) for n in order3))
            f.write('\n};\n')
        print('\n已写出 kuozhan.js / fufang_bencao.js / benbei.js')
    else:
        print('\n(dry-run, 加 --apply 写出)')

if __name__ == '__main__':
    main()
