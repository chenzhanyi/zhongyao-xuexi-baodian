# 中药学习宝典

纯前端、零依赖的中药学习工具（手机 + 桌面双端），含中药速记、经方、配伍禁忌、拓展典籍药、背诵、脉诊速记等模块。双击 HTML 即可运行。

- 仓库：https://github.com/chenzhanyi/zhongyao-xuexi-baodian
- 部署：Cloudflare Worker 托管，**push 到 `main` 即自动部署**（GitHub Pages 未开启）
- 推代码如直连超时，走本机 Clash 代理：`https_proxy=http://127.0.0.1:7897 git push origin main`
- 最后更新：2026-08-24

---

## 一、文件结构

| 文件 | 说明 |
|---|---|
| `index.html` | 入口选择页（手机版 / 桌面版 / 纲目阅读版） |
| `中药学习宝典.html` | **手机版主程序**（单文件，内联全部 JS/CSS） |
| `web.html` | **桌面版**（侧栏布局，纯浏览无背诵/脉诊） |
| `本草纲目-阅读版.html` | 《本草纲目》全文独立阅读版（5.7MB，未纳入数据校对） |
| `tcm-data.js` | 核心数据：305 味中药 `HERBS`、20 首经方 `FORMULAS`、禁忌 `TABOOS`、分类 `CATEGORIES`、沈常用 `SHEN_COMMON`（两版共享） |
| `bencao.js` | `BENCAO`：主库 305 味的本草详注（`sn` 神农本草经 / `gm.{w 气味,z 主治,m,p,j,s,x}`） |
| `benbei.js` | `BEIBAO`：本草备要原文 478 条 `{o:原书药名, c:原文, g:分类}` |
| `fufang_bencao.js` | `FUFANG`：本草纲目附方 518 条（值 = 附方正文字符串） |
| `kuozhan.js` | `KZ`：拓展典籍药 602 条 `{o:[原书药名], src:[来源], d:详注}`（纲目=附方、备要=正文） |
| `aliases.js` | `ALIAS`：305 味别名表（搜索归并用） |
| `gen_data.py` | 数据校对生成器：从源文本重新抽取 kuozhan/fufang/benbei 内容 |
| `audit_collation.py` | 校对审计：把 4 个数据文件与源文本比对（当前 kuozhan 602/602、fufang 518/518、benbei 478/478 全 OK；bencao 的 gm 为人工策展摘要，不参与逐字比对） |
| `fix_bencao.py` | 一次性修复脚本（bencao.js 的 w/z 拆分、悬挂【清理、莪术重写），已执行完毕，留档 |
| `parse_shennong.py` | 神农本草经一次性解析脚本（留档，不参与运行时） |
| `018-本草备要.txt`、`本草典籍参考/` | 源文本语料（纲目分卷 90 个 txt、备要、神农本草经），仅作参考与再生成用，**不进运行时** |
| `第一批/第二批/第三批中药*.xls`、`中药三批合并去重表.xlsx` | 采购原始数据（含单价），被 `.gitignore` 排除，不进仓库 |

## 二、脚本加载顺序（关键约定）

手机版与桌面版均按以下顺序引入数据文件：

```
bencao.js → aliases.js → fufang_bencao.js → benbei.js → kuozhan.js → tcm-data.js
```

`tcm-data.js` 的 `HERBS/FORMULAS` 用 `const` 声明且 UI 立即使用，**必须最后加载**（TDZ 陷阱）；改顺序会导致白屏。

## 三、显示层约定

- 数据内换行用 `\n`；`.ben-note` 等容器已加 `white-space:pre-line`
- 所有数据注入 `innerHTML` 的位置必须经 `esc()` 转义（两个 HTML 都内置 `esc()`；web 另有 `htmlAttr()` 用于属性）
- 折叠面板统一用 `toggleCat(this)`（.cat-card > .cat-head + .cat-body 结构）：打开时 `max-height:none` 动态高度，收起动画归零——**不要**恢复写死 max-height 的做法（曾因此截断 604 条典籍药列表）

## 四、手机版模块地图（中药学习宝典.html）

- **四页签**：中药 / 经方 / 禁忌 / 我的（`switchPage(page)`，页面 `#page-*`，`pulse` 页导航高亮映射到"我的"）
- **搜索**：`doSearch()` 写入 `#srContent`；覆盖主库 + 经方 + 禁忌 + 拓展典籍药（KZ）
- **中药页**：分类手风琴 `#catList`（`toggleCat`）、沈常用筛选、本草详注弹窗 `benModal`（`openBencao`/`bencaooHTML` 拼神农+纲目+附方+相关经方+备要）
- **拓展典籍药**：`renderHerbs()` 内按 `kzList` 分批渲染，每批 60 条由 `kzLoadMore()` 追加（`#kzGrid`/`#kzMore`），避免一次渲染数百卡片
- **经方页**：经典经方 / 纲目附方 / 本草备要 三页签（`fMode`）
- **背诵**：`openRecite`/`buildReciteItems`/`renderReciteCard`，localStorage 记录收藏/已掌握/连续天数
- **回到顶部浮球**：`#toTopBall`（滚动 >300px 显示，`toTop()`）
- **脉诊速记**：见下节

## 五、脉诊速记模块（手机版"我的 → 学习工具 → 脉诊速记"）

页面 `#page-pulse`，核心数据结构与函数：

- `PULSE_PARTS` 六部（左寸心/左关肝/左尺肾/右寸肺/右关脾/右尺命门）× `PULSE_LAYERS` 三层（浮/中/沉）
- **每层选脉**：弹出底部面板 `#pulsePickPanel`
  - `PULSE_BASE` 17 个基础脉 chip（可多选组合成相兼脉，如弦+滑）
  - `PULSE_COMP` 10 个复合脉 chip（点选**自动勾选** `compBases` 基础脉并带出 `compForce` 力度，如洪→浮+大+有力）
  - `PULSE_FORCES` 力度三 chip（有力/中等/无力，单选互斥）
- **十问歌**：`WEN_ITEMS`（8 组 chips，头身带引经药注释、胸腹带痞满注释）+ `WEN_ITEMS_EXT`（妇女·月经/带下/胎产、小儿·惊风/积食/疫苗，两组为折叠卡）；`WEN_TEXT`（旧病/起因）+ `WEN_TEXT_EXT`（孕产史/小儿发育文本）；"对象"（男/女/小儿，联动展开妇女/小儿折叠组，小儿附一指定三关提示）与"年龄"（儿童<14/青少年14-18/成年18-59/老年≥60，选儿童或青少年附剂量折算提示）、"左右脉力"（左手强/右手强/两手相当）
- **报告**：`genPulseReport()` 生成 `pulseReportText`——六部（未记录层不显示）+ 对象/年龄/左右脉力 + `—— 十问 ——`（只列已记录项）+ 备注 + 免责声明；`copyPulseReport()` 一键复制
- **复位**：`resetPulseAll()` 清空全部（含十问、对象、年龄、脉力、本地存储）
- 选脉/力度/十问均即时写入 localStorage（key 见下节）

## 六、localStorage Key 清单

| Key | 内容 |
|---|---|
| `tcm_learning_progress` | 学习进度（收藏/已掌握/设置/连续天数，`STORE_KEY`） |
| `tcm_pulse_sel` | 六部×三层选脉，`{部:{层:[脉名,...]}}`（数组，支持相兼脉） |
| `tcm_pulse_force` | 每层力度 `{部:{层:'有力'}}` |
| `tcm_pulse_note` | 脉诊备注 |
| `tcm_pulse_side` | 左右脉力（左手强/右手强/两手相当） |
| `tcm_wen_sel` | 十问 chips 选择 `{组:[选项,...]}` |
| `tcm_wen_text` | 旧病/起因/孕产史/小儿发育文本 |
| `tcm_wen_person` | 对象（男/女/小儿） |
| `tcm_wen_age` | 年龄（儿童/青少年/成年/老年） |

## 七、数据校对工具链（gen_data.py / audit_collation.py）

背景：kuozhan/fufang/benbei 三库原为 AI 抽取，存在截断/碎片/拼接错误，2026-08 已改为从本地源文本重新抽取。

- 源文本格式（两种标记并存，`load_gangmu()` 自动识别）：
  - 格式 A（如草之一）：`== 药名 ==` 为条目、`=== 節名 ===` 为小节
  - 格式 B（如草之二）：`== 卷标题 ==`、`=== 药名 ===` 为条目、【節名】为小节
  - 备要：`<篇名>X` + `内容：Y` 分条；`\x…\x` 为异名标记；硬换行为折行
- `gen_data.py`：`clean_text()` 流水线 = 源文补缺（`FIX_TXT`，繁体阶段）→ wiki 标记清洗 → 实体解码 → 异名转（…）→ 段落/硬折行还原 → OpenCC 繁转简 + `VARIANT_PAIRS` 补充映射；`gangmu_fufang()` 抽取条内全部【附方】段；用法 `python3 gen_data.py [--apply]`
- `audit_collation.py`：与 `gen_data.py` 共用解析与 FIX 规则，逐段相似度校验；用法 `python3 audit_collation.py [kz|bencao|fufang|benbei]`
- Python 依赖：`opencc-python-reimplemented`（仅工具用，网页零依赖）
- 已知遗留：`本草典籍参考/` 源 txt 本身仍有零星数字化缺字（抽取时由 `FIX_TXT` 修正，源文件未回写）；`本草纲目-阅读版.html` 未纳入校对；bencao.js 的 `gm` 字段是人工策展的现代摘要（非原文）

## 八、开发注意事项

- 数据文件都是纯数据（`const XXX = {...};`），无辅助函数；工具函数在各自 HTML 内联脚本里
- 修改数据后建议跑：各 JS `node --check`、两 HTML 内联脚本语法校验、`python3 audit_collation.py`（如重抽了数据）
- 手机版页面都放在 `.app` 容器**内部**（曾有把 page 插到容器外导致整屏留白的事故）
- 提交信息用中文描述；仓库历史均以功能为单位小步提交
