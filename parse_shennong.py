# -*- coding: utf-8 -*-
# 解析《神农本草经》→ 药名+性味表；与 app 当前数据交叉核对
import re, json, os

def norm_flavor(s):
    """把'味甘微寒無毒'规范化成'甘，微寒'等"""
    s = s.replace('味','').replace('無毒','').replace('有毒','')
    wei = re.findall(r'[甘苦酸辛咸淡澀]', s)
    xing = []
    for m in re.findall(r'(微?[寒温凉][熱]?|平)', s):
        xing.append(m)
    xing = list(dict.fromkeys(xing))  # 去重保序
    return ('、'.join(xing) if xing else '') + ('，' if wei and xing else '') + '、'.join(wei) if (wei or xing) else ''

# 已下载的神农本草经
txt = open('本草典籍参考/神农本草经.txt',encoding='utf-8').read()
entries = []
for m in re.finditer(r"'''([^']+)'''\s*[　 ]*(味[^。]+)。", txt):
    name = m.group(1).strip()
    flav = m.group(2).strip()
    entries.append((name, flav, norm_flavor(flav)))
print("神农本草经解析药条数:", len(entries))
open('本草典籍参考/神农本草经-性味表.tsv','w',encoding='utf-8').write(
    "药名\t原文字句\t规范化性味\n" + "\n".join(f"{a}\t{b}\t{c}" for a,b,c in entries)
)

# 与现代别名映射
ALIAS = {'丹砂':'朱砂','消石':'芒硝','朴消':'芒硝','滑石':'滑石','禹余糧':'禹余粮','太一禹余糧':'禹余粮',
 '天門冬':'天冬','麥門冬':'麦冬','朮':'白术','委萎':'玉竹','黃耆':'黄芪','黃芪':'黄芪','當歸':'当归','芍藥':'白芍',
 '麻黃':'麻黄','桂':'桂枝','黃連':'黄连','黃芩':'黄芩','大黃':'大黄','甘草':'甘草','人參':'人参','乾地黃':'生地黄',
 '五味子':'五味子','菖蒲':'石菖蒲','茯苓':'茯苓','澤瀉':'泽泻','豬苓':'猪苓','薯蕷':'山药','牛膝':'牛膝',
 '山茱萸':'山茱萸','杜仲':'杜仲','桑上寄生':'桑寄生','牡丹':'牡丹皮','麥冬':'麦冬','防風':'防风','白芷':'白芷',
 '蒼耳實':'苍耳子','獨活':'独活','細辛':'细辛','柴胡':'柴胡','升麻':'升麻','葛根':'葛根','知母':'知母',
 '貝母':'川贝母','瓜蔞':'瓜蒌','桔梗':'桔梗','半夏':'半夏','款冬花':'款冬花','紫菀':'紫菀','杏仁':'苦杏仁',
 '桃核仁':'桃仁','杏核仁':'苦杏仁','茵陳蒿':'茵陈','菊花':'菊花','決明子':'决明子','車前子':'车前子','牛蒡':'牛蒡子',
 '蛇床子':'蛇床子','地膚子':'地肤子','蜻蛉':'','烏賊魚骨':'海螵蛸','牡蠣':'牡蛎','龜甲':'龟甲','沙參':'北沙参',
 '丹參':'丹参','玄參':'玄参','苦參':'苦参','紫草':'紫草','知母':'知母','黃柏':'黄柏','厚朴':'厚朴','枳實':'枳实',
 '陳橘皮':'陈皮','吳茱萸':'吴茱萸','蜀椒':'花椒','乾薑':'干姜','附子':'附子','烏頭':'川乌','秦艽':'秦艽',
 '木香':'木香','川芎':'川芎','牡丹':'牡丹皮','犀角':'','羚羊角':'', '水蛭':'水蛭','蜚虻':'虻虫','鼈甲':'鳖甲',
 '石韋':'石韦','萹蓄':'萹蓄','瞿麥':'瞿麦','海藻':'海藻','澤蘭':'泽兰','益母':'益母草','紫參':'','白及':'白及',
 '桑根白皮':'桑白皮','枇杷葉':'枇杷叶','茅根':'白茅根','艾葉':'艾叶','地榆':'地榆','槐實':'槐花','血餘':'',
 '木蘭':'','杜若':'','旋覆花':'旋覆花','蜀漆':'','白前':'白前','丁香':'丁香','枳殼':'枳壳','當歸':'当归','阿膠':'阿胶'}

our = {}
data = open('tcm-data.js',encoding='utf-8').read()
# 简单提取 herb 数组药名（按 '名','py' 形式）
for m in re.finditer(r"\['([^']+)','[^']+','([^']+)','([^']+)'", data):
    if m.group(1) not in our and len(m.group(2))>1:
        our[m.group(1)] = (m.group(2), m.group(3))

rows = []
for sname, raw, sf in entries:
    target = ALIAS.get(sname)
    if not target or target not in our: continue
    our_nat, our_mer = our[target]
    match = (sf and our_nat.replace('；','，') in (sf, sf+'') and sf.split('，')[0] in our_nat) or (sf and our_nat.startswith(sf.split('，')[0]))
    rows.append((sname, target, sf, our_nat, '≈' if (sf and (sf.split('，')[0] in our_nat)) else '≠'))
print(f"神农本草经条目中可匹配到 app 数据的药: {len(rows)}")
print(f"{'神农名':<8}{'app名':<6}{'神农药性':<12}{'app(现代)':<14}对比")
flag=0
for s,t,sf,on,c in rows:
    mark='' if c=='≈' else ' ★差异'
    if c!='≈': flag+=1
    print(f"{s:<8}{t:<6}{sf:<12}{on:<14}{c}{mark}")
print(f"其中性味首味一致≈{len(rows)-flag} / 有差异{flag}（古典vs现代口径差异，以现代药典为准）")
open('本草典籍参考/神农本草经-与app交叉核对.tsv','w',encoding='utf-8').write(
    "神农本草经药名\tapp药名\t神农药性(古典)\tapp性味(现代)\t对比\n" +
    "\n".join(f"{s}\t{t}\t{sf}\t{on}\t{c}" for s,t,sf,on,c in rows))
