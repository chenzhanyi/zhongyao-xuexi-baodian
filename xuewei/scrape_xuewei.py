#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
采集 zhzyw.com 针灸穴位大全（列表页 https://m.zhzyw.com/zt/xwdq/）
- 列表页按十四经分组（十二正经 + 督脉 + 任脉）
- 内页正文在 <article id="content">，字段以【定位】【解剖】【主治】【操作】【配伍】【附注】分段
输出：xuewei.js  const XUEWEI = { 穴名: {m:经脉,py:拼音,src:出处,dw,jp,zz,cz,pw,bz,img} }
用法：python3 scrape_xuewei.py [--apply]
  无 --apply：仅统计 + 试抓前几条打印，不写文件
  --apply：全量抓取并写 xuewei.js（带 raw 缓存，可中断续抓）
"""
import os, re, sys, json, time, urllib.request, subprocess

BASE = 'https://m.zhzyw.com/zt/xwdq/'
CACHE = 'xuewei_raw.json'   # 已抓内页缓存 {url: text}
PROXY = 'http://127.0.0.1:7897'
LIST_CACHE = 'xuewei_list.html'
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'

def http_get(url):
    for attempt in range(3):
        try:
            handlers = [urllib.request.ProxyHandler({'http': PROXY, 'https': PROXY})]
            opener = urllib.request.build_opener(*handlers)
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with opener.open(req, timeout=40) as r:
                return r.read()
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2)

def get_list():
    if os.path.exists(LIST_CACHE):
        raw = open(LIST_CACHE, 'rb').read()
    else:
        raw = http_get(BASE)
        open(LIST_CACHE, 'wb').write(raw)
    return raw.decode('gb18030', errors='replace')

def parse_list(h):
    # 经脉分组：<h2 ...>一、手太阴肺经</h2> / <h2>督脉</h2>
    heads = [(m.group(1).strip(), m.start()) for m in
             re.finditer(r'<h[23][^>]*>\s*(?:[一二三四五六七八九十]+[、.．])?\s*((?:手|足|督|任)[^<]{0,12}?)\s*</h', h, re.I)]
    groups = []
    for i, (name, pos) in enumerate(heads):
        end = heads[i+1][1] if i+1 < len(heads) else len(h)
        seg = h[pos:end]
        pts = re.findall(r'href="(https://m\.zhzyw\.com/zyts/zyzj/jl/[^"]+)"[^>]*>([^<]+)</a>', seg)
        seen = []
        for u, n in pts:
            n = n.strip()
            if n and not any(x[1] == n for x in seen):
                seen.append((u, n))
        groups.append((name, seen))
    return groups

def strip_tags(s):
    s = re.sub(r'<br\s*/?>', '\n', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = (s.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<')
           .replace('&gt;', '>').replace('&quot;', '"'))
    return re.sub(r'[ \t]+', ' ', s).strip()

def parse_detail(html):
    m = re.search(r'<article[^>]*id="content"[^>]*>(.*?)</article>', html, re.S)
    body = m.group(1) if m else html
    body = re.sub(r'<mip-showmore[^>]*>', '', body)
    body = body.replace('</mip-showmore>', '')
    body = re.sub(r'<div[^>]*class="mip-showmore-btn"[^>]*>.*?</div>', '', body, flags=re.S)
    # 图片
    img = ''
    im = re.search(r'<img[^>]+src="(https?://img\.zhzyw\.com/[^"]+)"', body)
    if im:
        img = im.group(1)
    # 图注：X-体表图 / X-体表示意图（点击放大）
    cap = ''
    cm = re.search(r'>\s*([^<]*[-–][^<]*(?:体表图|体表示意图|示意图)[^<]*)<', body)
    if cm:
        cap = strip_tags(cm.group(1)).replace('（点击放大）', '').replace('(点击放大)', '').strip()
    # 首段：穴名 拼音《出处》
    first = re.search(r'<p[^>]*>(.*?)</p>', body, re.S)
    py = src = ''
    if first:
        ft = strip_tags(first.group(1))
        pym = re.search(r'([A-Za-zà-ǜ][A-Za-zà-ǜ\s]{1,20})', ft)
        if pym:
            py = pym.group(1).strip()
        sm = re.search(r'《([^》]+)》', ft)
        if sm:
            src = sm.group(1)
    # 字段：同时支持 【定位】 和 [定位] 两种标记
    fields = {}
    for fm in re.finditer(r'[【\[]([^】\]]+)[】\]](.*?)(?=[【\[][^】\]]+[】\]]|$)', body, re.S):
        key = fm.group(1).strip()
        val = strip_tags(fm.group(2))
        val = re.sub(r'咨询电话[:：]?[\d\-—\s]*', '', val)  # 删电话
        val = val.replace('↓展开全部内容', '').replace('↑收起全部内容', '')
        val = re.sub(r'\s+', ' ', val).strip(' 。；;')
        if val:
            fields[key] = val
    return {'py': py, 'src': src, 'img': img, 'cap': cap, 'f': fields}

FIELD_MAP = {'定位': 'dw', '解剖': 'jp', '主治': 'zz', '操作': 'cz', '配伍': 'pw',
             '配伍举例': 'pw', '附注': 'bz', '备注': 'bz', '刺灸法': 'cz', '解剖部位': 'jp'}

def main():
    apply = '--apply' in sys.argv
    h = get_list()
    groups = parse_list(h)
    total = sum(len(pts) for _, pts in groups)
    print(f'经脉 {len(groups)} 组，穴位 {total} 个')
    for name, pts in groups:
        print(f'  {name}: {len(pts)}')

    cache = {}
    if os.path.exists(CACHE):
        cache = json.load(open(CACHE, encoding='utf-8'))

    items = []
    for gname, pts in groups:
        for url, name in pts:
            items.append((gname, name, url))

    if not apply:
        # 试抓 3 条
        for gname, name, url in items[:3]:
            raw = http_get(url).decode('gb18030', errors='replace')
            d = parse_detail(raw)
            print('\n====', name, f'[{gname}]')
            print('  拼音:', d['py'], '| 出处:', d['src'], '| 图:', d['img'][:50])
            for k, v in d['f'].items():
                print(f'  【{k}】{v[:60]}')
        return

    # 全量
    done = 0
    out = []
    for i, (gname, name, url) in enumerate(items):
        if url in cache:
            raw = cache[url]
        else:
            raw = http_get(url).decode('gb18030', errors='replace')
            cache[url] = raw
            if i % 10 == 0:
                json.dump(cache, open(CACHE, 'w', encoding='utf-8'))
            time.sleep(0.8)
        d = parse_detail(raw)
        rec = {'n': name, 'm': gname, 'py': d['py'], 'src': d['src'], 'img': d['img'], 'cap': d.get('cap', '')}
        for k, v in d['f'].items():
            key = FIELD_MAP.get(k)
            if key and v:
                rec[key] = v
        out.append(rec)
        done += 1
        if done % 30 == 0:
            print(f'  已抓 {done}/{total}')
    json.dump(cache, open(CACHE, 'w', encoding='utf-8'))

    # 生成 xuewei.js
    def js_str(s):
        return s.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
    lines = ['// 针灸穴位库 · 采集自 m.zhzyw.com（手机中医中药网）十四经穴位，字段：定位/解剖/主治/操作/配伍/附注',
             'const XUEWEI = [']
    for r in out:
        parts = [f"n:'{js_str(r['n'])}'", f"m:'{js_str(r['m'])}'"]
        if r.get('py'): parts.append(f"py:'{js_str(r['py'])}'")
        if r.get('src'): parts.append(f"src:'{js_str(r['src'])}'")
        # img 改写为本地路径（xuewei/img/xxx.gif），不依赖对方图床
        if r.get('img'):
            local = 'xuewei/img/' + r['img'].split('/')[-1]
            parts.append(f"img:'{js_str(local)}'")
        if r.get('cap'): parts.append(f"cap:'{js_str(r['cap'])}'")
        for k in ('dw', 'jp', 'zz', 'cz', 'pw', 'bz'):
            if r.get(k):
                parts.append(f"{k}:'{js_str(r[k])}'")
        lines.append('  {' + ','.join(parts) + '},')
    lines.append('];')
    open('xuewei.js', 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print(f'\n完成：{len(out)} 穴 → xuewei.js')

if __name__ == '__main__':
    main()
