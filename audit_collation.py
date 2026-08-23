#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校对审计：把 kuozhan/bencao/fufang_bencao/benbei 四个数据 JS 与源文本比对。
源文本：
  - 本草纲目: 本草典籍参考/本草纲目/*.txt  (以 === 药名 === 分条)
  - 本草备要: 本草典籍参考/本草备要.txt      (以 <篇名>X / 内容：Y 分条)
用法: python3 audit_collation.py [文件...]
"""
import re, os, sys, json
from opencc import OpenCC

ROOT = os.path.dirname(os.path.abspath(__file__))
T2S = OpenCC('t2s')
try:
    from gen_data import FIX_TXT  # 数据修复规则, 审计时同样套用
except ImportError:
    FIX_TXT = []

# ---------- 归一化 ----------
def norm(s: str) -> str:
    """去除一切空白(含字面 \n)、转义残留、wiki标记、HTML实体 -> 繁转简 -> 便于比对
    注: （…）括号内容两侧同规则去除(数据侧把反斜杠x异名反斜杠x 转成了（异名）)
    备要源文尾部的 <目录> 导航行同样去除"""
    s = s.split('<目录>')[0]
    for a, b in FIX_TXT:
        s = s.replace(a, b)
    s = re.sub(r'王璆?《百一\s*\n+\s*花上粉', '王璆《百一選方》）', s)   # 通脱木条缺字
    s = s.replace('\\n', '').replace('\\x', '').replace('\\\\x', '')
    s = re.sub(r'\{\{\*\|[^}]*\}\}', '', s)          # {{*|…}}
    s = re.sub(r'\{\{[A-Za-z\-]*\}\}', '', s)        # {{PD-old}} 等
    s = re.sub(r'&#\d+;', lambda m: chr(int(m.group(0)[2:-1])), s)
    s = re.sub(r'\s+', '', s)
    s = re.sub(r'（([^（）]{1,60})）', r'\1', s)       # 括号对等去除(先除空白再剥, 内容含硬换行也能剥)
    s = re.sub(r'\(([^()]{1,60})\)', r'\1', s)
    s = s.replace('（）', '').replace('()', '')        # 空白已去除后遗留的空括号
    # 全角/半角标点差异
    s = s.replace('︰', '：').replace('∶', '：').replace('﹕', '：')
    s = s.replace('〜', '～')
    s = T2S.convert(s)  # 数据文件是简体, 源文本是繁体 -> 统一成简体
    # OpenCC 漏掉的简化字总表映射(异体/生僻)
    for a, b in VARIANT_PAIRS:
        s = s.replace(a, b)
    return s

# 简化字总表/异体字中 OpenCC t2s 未覆盖的映射(源文繁体 -> 数据简体)
VARIANT_PAIRS = [
    ('痺', '痹'), ('癥', '症'), ('虖', '乎'), ('惪', '德'),
    ('亁', '干'), ('髠', '髡'), ('祕', '秘'), ('姙', '妊'),
    ('輭', '软'), ('媮', '偷'), ('畧', '略'), ('袐', '秘'),
]

# ---------- 加载源文本(与 gen_data.py 共用同一解析) ----------
from gen_data import load_gangmu, load_bei_yao

# ---------- 解析 JS 数据文件 ----------
def unescape_js(s: str) -> str:
    """只还原 JS 字符串转义（\\n \\t \\" \\\\ 等），不动中文"""
    return re.sub(r'\\(.)', lambda m: {'n': '\n', 't': '\t', '"': '"',
        '\\': '\\', "'": "'", '/': '/'}.get(m.group(1), '\\' + m.group(1)), s)

def parse_js(path, kind):
    src = open(path, encoding='utf-8').read()
    out = {}
    if kind == 'kz':
        for m in re.finditer(r'"([^"]+)":\{o:\[([^\]]*)\],src:\[([^\]]*)\],d:"((?:[^"\\]|\\.)*)"', src):
            name, o, s, d = m.group(1), m.group(2), m.group(3), m.group(4)
            d = unescape_js(d)
            out[name] = {'o': [x.strip().strip('"') for x in o.split(',') if x.strip()],
                         'src': [x.strip().strip('"') for x in s.split(',') if x.strip()],
                         'd': d}
    elif kind == 'bencao':
        # "药名":{sn:"...",gm:{w:"...",z:"..."}} 或 {gm:{...}}
        for m in re.finditer(r'"([^"]+)":\{((?:[^{}]|\{[^{}]*\})*)\}', src):
            name, body = m.group(1), m.group(2)
            sn = re.search(r'sn\s*:\s*"((?:[^"\\]|\\.)*)"', body)
            w = re.search(r'["\']?w["\']?\s*:\s*"((?:[^"\\]|\\.)*)"', body)
            z = re.search(r'["\']?z["\']?\s*:\s*"((?:[^"\\]|\\.)*)"', body)
            out[name] = {
                'sn': unescape_js(sn.group(1)) if sn else None,
                'w': unescape_js(w.group(1)) if w else None,
                'z': unescape_js(z.group(1)) if z else None,
            }
    elif kind == 'fufang':
        for m in re.finditer(r'"([^"]+)":"((?:[^"\\]|\\.)*)"', src):
            out[m.group(1)] = {'d': m.group(2)}
    elif kind == 'benbei':
        for m in re.finditer(r'"([^"]+)":\{o:"((?:[^"\\]|\\.)*)",c:"((?:[^"\\]|\\.)*)",g:"((?:[^"\\]|\\.)*)"\}', src):
            out[m.group(1)] = {'o': m.group(2), 'c': m.group(3), 'g': m.group(4)}
    return out

# ---------- 分类 ----------
def seg_similarity(seg: str, pool) -> float:
    """段落被语料覆盖的比例(≥12字匹配块累计/段长)。
    提取会跳过子条目标题(柳耳【主治】等), 用累计覆盖率而不是最长连续块。"""
    import difflib
    dn = norm(seg)
    if not dn:
        return 0.0
    if len(dn) < 30:
        # 短文本直接查子串
        return 1.0 if any(dn in cn for cn in pool) else 0.0
    best = 0.0
    for cn in pool:
        sm = difflib.SequenceMatcher(None, cn, dn, autojunk=False)
        matched = sum(b.size for b in sm.get_matching_blocks() if b.size >= 12)
        cov = matched / len(dn)
        if cov > best:
            best = cov
        if best >= 0.93:
            break
    return best

def classify(d_text, corpus_norm):
    """返回 (状态, 说明)。corpus_norm 可为空列表 -> 全库搜索"""
    dn = norm(d_text)
    # 1) 整体匹配(先于长度判断, 源文本身极短的条目如备要"银:功用略同。"也算OK)
    for cn in corpus_norm:
        if dn in cn:
            return 'OK', ''
    if len(dn) < 8:
        return 'FRAGMENT', f'内容过短({len(dn)}字)'
    # 2) 前缀截断：d 是源文某段的前缀
    for cn in corpus_norm:
        if cn.startswith(dn) and len(cn) > len(dn):
            return 'TRUNC-END', f'源文{len(cn)}字, d只有{len(dn)}字, 结尾截断'
    # 3) 后缀截断：d 是源文某段的后缀
    for cn in corpus_norm:
        if cn.endswith(dn) and len(cn) > len(dn):
            return 'TRUNC-START', f'开头截断, 丢失{len(cn)-len(dn)}字'
    # 4) 双向截断：d 是源文子串但两端都短
    for cn in corpus_norm:
        i = cn.find(dn)
        if i >= 0:
            return 'TRUNC-BOTH', f'中段摘取(前丢{i}字,后丢{len(cn)-i-len(dn)}字)'
    return 'NO-MATCH', '源文中找不到'

def candidates(name, o_names, norm_index):
    """按名称（繁简互转）找候选源条目正文。norm_index: {简体名: [norm正文...]}"""
    keys = [name] + (o_names or [])
    got = []
    for k in keys:
        for kk in (T2S.convert(k), k):
            if kk in norm_index:
                got += norm_index[kk]
    return got

def main():
    only = sys.argv[1:] or ['kz', 'bencao', 'fufang', 'benbei']
    gm = load_gangmu(); gm_norm = {T2S.convert(k): [norm(b) for b in v] for k, v in gm.items()}
    by = load_bei_yao(); by_norm = {T2S.convert(k): [norm(b) for b in v] for k, v in by.items()}
    # 全库正文（兜底全局搜索）
    gm_all = [c for v in gm_norm.values() for c in v]
    by_all = [c for v in by_norm.values() for c in v]
    print(f'源文本: 纲目 {len(gm)} 条, 备要 {len(by)} 条\n')

    if 'kz' in only:
        kz = parse_js(os.path.join(ROOT, 'kuozhan.js'), 'kz')
        stats = {}
        for name, e in kz.items():
            want_by = any('备要' in s for s in e['src'])
            corps = candidates(name, e['o'], by_norm if want_by else gm_norm)
            if not corps and want_by:
                corps = candidates(name, e['o'], gm_norm)  # 标备要但在纲目
            # 附方类数据按段(空行分隔)逐段做相似度校验——源文缺字/损伤允许小幅差异
            segs = [s for s in re.split(r'\n{2,}', e['d']) if s.strip()]
            bad = []
            for sg in segs:
                r = seg_similarity(sg, corps or gm_all + by_all)
                if r < 0.93:
                    bad.append((sg[:24], r))
            if not bad:
                st, note = 'OK', ''
            else:
                st, note = 'LOW-SIM', f'{len(bad)}/{len(segs)}段相似度不足: {bad[0]}'
            stats[st] = stats.get(st, 0) + 1
            if st != 'OK':
                print(f"[kuozhan] {st:12s} {name:12s} src={e['src']} o={e['o']} | {note} | d={e['d'][:45]!r}")
        print(f'\n[kuozhan] 统计: {stats}')

    if 'bencao' in only:
        bc = parse_js(os.path.join(ROOT, 'bencao.js'), 'bencao')
        stats = {}
        for name, e in bc.items():
            gm_bodies = gm_norm.get(name, [])
            for field, val in (('w', e['w']), ('z', e['z'])):
                if not val: continue
                st, note = classify(val, gm_bodies)
                stats.setdefault(st, 0)
                stats[st] += 1
                if st != 'OK':
                    print(f"[bencao] {st:12s} {name}.{field} | {note} | v={val[:45]!r}")
            if e['sn']:
                # sn 与神农本草经比对（简略：检查是否能在任何卷里找到）
                pass
        print(f'\n[bencao] 统计: {stats}')

    if 'fufang' in only:
        ff = parse_js(os.path.join(ROOT, 'fufang_bencao.js'), 'fufang')
        stats = {}
        for name, e in ff.items():
            corps = candidates(name, (), gm_norm)
            segs = [s for s in re.split(r'\n{2,}', e['d']) if s.strip()]
            bad = []
            for sg in segs:
                r = seg_similarity(sg, corps or gm_all)
                if r < 0.93:
                    bad.append((sg[:24], r))
            if not bad:
                st, note = 'OK', ''
            else:
                st, note = 'LOW-SIM', f'{len(bad)}/{len(segs)}段相似度不足: {bad[0]}'
            stats[st] = stats.get(st, 0) + 1
            if st != 'OK':
                print(f"[fufang] {st:12s} {name:12s} | {note} | d={e['d'][:45]!r}")
        print(f'\n[fufang] 统计: {stats}')

    if 'benbei' in only:
        bb = parse_js(os.path.join(ROOT, 'benbei.js'), 'benbei')
        stats = {}
        for name, e in bb.items():
            corps = [by_norm.get(k, []) for k in (e['o'], name) if k]
            flat = [c for cc in corps for c in cc if cc]
            st, note = classify(e['c'], flat)
            stats[st] = stats.get(st, 0) + 1
            if st != 'OK':
                print(f"[benbei] {st:12s} {name:12s} o={e['o']} | {note} | c={e['c'][:45]!r}")
        print(f'\n[benbei] 统计: {stats}')

if __name__ == '__main__':
    main()
