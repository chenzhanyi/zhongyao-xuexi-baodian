#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 xuewei.js 里的 img 路径批量改成图床地址。
用法：
  python3 set_img_base.py https://img.9yzs.cn/xuewei
会把  img:'xuewei/img/xxx.gif'  改成  img:'https://img.9yzs.cn/xuewei/xxx.gif'
"""
import re, sys, os

JS = os.path.join(os.path.dirname(__file__), 'xuewei.js')

def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    base = sys.argv[1].rstrip('/')
    s = open(JS, encoding='utf-8').read()
    # 匹配 img:'..../文件名.gif' 或 img:'<base>/文件名.gif'，统一替换为 base/文件名
    def repl(m):
        fn = m.group(1).split('/')[-1]
        return "img:'%s/%s'" % (base, fn)
    s2, n = re.subn(r"img:'(?:[^']*?)/?([0-9A-Za-z_]+\.gif)'", repl, s)
    open(JS, 'w', encoding='utf-8').write(s2)
    print('已替换 %d 处图片地址 → %s/<文件名>.gif' % (n, base))

if __name__ == '__main__':
    main()
