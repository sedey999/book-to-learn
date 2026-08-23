---
name: omt-daily-push
description: |
  Open Music Theory（开放乐理）每日双语知识点卡片推送。
  当用户提到"推送乐理卡片"、"今日乐理卡片"、"omt 推送"、"音乐理论每日卡片"、
  "open music theory push"，或在定时任务中需要执行每日乐理知识点推送时，使用此 skill。
  每次调用推送一张卡片：取下一张 → 联网核对术语 → 实时翻译 → 生成卡片式 PDF →
  上传到 IMA 知识库指定文件夹 → 记录进度。
  遇 IMA 密钥失效时，打印清晰的凭证更新指引（可选 webhook 通知），且本次不计入进度。
homepage: https://viva.pressbooks.pub/openmusictheory
metadata:
  openclaw:
    emoji: 🎵
    requires:
      env:
        - IMA_OPENAPI_CLIENTID
        - IMA_OPENAPI_APIKEY
    primaryEnv: IMA_OPENAPI_CLIENTID
  security:
    credentials_usage: |
      本 skill 调用 IMA OpenAPI（ima.qq.com）上传 PDF 到知识库。
      IMA 凭证（Client ID / API Key）由用户首次运行时提供，存储于 ~/.config/ima/，
      仅作为 HTTP 头发送给 ima.qq.com。
      COS 上传使用 IMA 返回的临时凭证，发送给 *.myqcloud.com。
      密钥失效时向 stderr 打印通知并以退出码 2 返回，由调用方决定通知渠道
      （可选：设置 IMA_KEY_EXPIRED_WEBHOOK 环境变量启用 webhook 通知）。
      不向其他任何目的地发送凭证。
    allowed_domains:
      - ima.qq.com
      - '*.myqcloud.com'
      - viva.pressbooks.pub
---

# omt-daily-push — 开放乐理每日双语卡片推送

将《Open Music Theory》教材拆解为 118 个知识点卡片，每日推送一张中英双语 PDF 到 IMA 知识库。

## ⛔ 核心规则 — 执行前必读

1. **推送时间不由 skill 决定**：skill 仅在被调用时执行一次推送。何时调用由外部定时任务控制。
2. **进度仅在推送成功后记录**：术语核对、翻译、PDF 生成、IMA 上传任一环节失败，都不更新 progress.json，下次重推同一张卡片。
3. **密钥失效处理**：IMA API 返回认证失败时，调用 notify_key_expired.py 打印指引并以退出码 2 通知调用方，本次不计入进度，退出。
4. **翻译实时完成**：术语核对必须联网查询权威译法，不得凭记忆；翻译在每次推送时现做。
5. **PDF 文件名必须含当天日期**，统一格式 `OMT_YYYY-MM-DD_<card_id>.pdf`。

## 🚀 首次使用引导（必须在首次推送前完成）

当首次使用本 skill 时，**必须先向用户说明本 skill 的功能，并收集以下配置信息**：

### 向用户说明的内容

> 🎵 **omt-daily-push** 将《Open Music Theory》开源乐理教材拆解为 **118 个知识点卡片**，每次调用自动完成：
>
> 1. 获取下一张未推送的卡片
> 2. 联网核对每个音乐术语的权威中文译法
> 3. AI 实时翻译（核心观点、详解、金句、应用场景）
> 4. 生成精美的中英双语对照 PDF（含教材原文乐谱图片）
> 5. 图片完整性自动复核
> 6. 上传 PDF 及相关附件到你的 IMA 知识库
> 7. 记录进度（失败不计入，下次自动重推）
>
> 需要你提供两项信息即可开始：

### 需要向用户收集的信息

| # | 信息 | 是否必填 | 说明 |
|---|------|---------|------|
| 1 | **IMA 知识库名称** | ✅ 必填 | 你在 IMA 中创建的知识库名称，例如「我的乐理笔记」 |
| 2 | **目标文件夹名称** | ✅ 必填 | 知识库内存放每日卡片的文件夹，默认「每日一个知识点」 |
| 3 | **推送失败 Webhook URL** | ❌ 可选 | 飞书/Slack/企业微信机器人 webhook，凭证失效或附件失败时通知你。不提供则仅在日志中提示 |

### 自动配置

收集信息后，运行引导脚本自动生成配置：

```bash
cd <skill_dir>
python3 scripts/setup.py
```

脚本会：
- 展示本 skill 功能说明
- 检查 IMA 凭证、ima-skill、Python 依赖是否就绪
- 交互式收集知识库名称、文件夹名称、webhook URL
- 生成 `config.json`

也可以通过参数非交互配置：

```bash
python3 scripts/setup.py --non-interactive \
  --kb-name "你的知识库名称" \
  --folder-name "每日一个知识点" \
  --webhook "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
```

### 前置条件检查清单

首次运行前确认以下条件：
- [ ] IMA API 凭证已配置（`~/.config/ima/client_id` 和 `api_key`）
- [ ] ima-skill 已安装
- [ ] Python 依赖已安装（`pip install -r requirements.txt`）
- [ ] `config.json` 已通过 setup.py 生成
- [ ] 目标知识库和文件夹已在 IMA 中创建

运行 `python3 scripts/push_card.py status` 验证安装。

## 安装（首次使用前）

### 1. 必备依赖

- **Python 3.8+**
- **Node.js 18+**（ima-skill 上传时使用）
- **WeasyPrint**（PDF 生成）
- **Noto Sans/Serif CJK 字体**（PDF 中文字体）

#### macOS

```bash
brew install python pango cairo gdk-pixbuf libffi
pip3 install weasyprint pymupdf
# 字体
brew install --cask font-noto-sans-cjk-sc font-noto-serif-cjk-sc
```

#### Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install -y python3-pip libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 \
    fonts-noto-cjk
pip3 install weasyprint pymupdf
```

#### Windows

```powershell
pip install weasyprint
# 安装 GTK3 runtime: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
# 字体：下载 Noto Sans CJK SC 并安装
```

### 2. 安装 ima-skill（必需）

本 skill 依赖 **ima-skill** 进行知识库文件上传，请安装官方最新版本：

- **下载地址**：https://app-dl.ima.qq.com/skills/ima-skills-1.1.7.zip
- **API Key 获取**：https://ima.qq.com/agent-interface

解压后将 `ima-skill/` 目录放到你的 agent skills 目录下（例如 OpenClaw 用户目录 `~/.openclaw/skills/ima-skill`）。

脚本会自动按以下顺序查找 ima-skill：

1. 环境变量 `IMA_SKILL_DIR`（显式指定路径）
2. 与 `omt-daily-push` 同级的 `ima-skill/` 目录
3. OpenClaw 常见路径：`~/.openclaw/skills/ima-skill`
4. `~/.agents/skills/ima-skill`

### 3. 首次使用：配置 IMA 知识库凭证

**首次运行时必须完成凭证配置**，否则上传会失败。

1. 打开 https://ima.qq.com/agent-interface 获取 **Client ID** 和 **API Key**
2. 运行一次凭证配置：

```bash
mkdir -p ~/.config/ima
echo "<your_client_id>" > ~/.config/ima/client_id
printf '%s' "<your_api_key>" > ~/.config/ima/api_key
```

或使用环境变量（不写入文件）：

```bash
export IMA_OPENAPI_CLIENTID="<your_client_id>"
export IMA_OPENAPI_APIKEY="***"
```

### 4. 配置目标知识库与文件夹

编辑 `push_card.py` 同目录下的 `config.json`（首次运行会自动生成模板），或通过环境变量传入：

```bash
export OMT_KB_NAME="我的乐理笔记"                   # 你在 IMA 中的知识库名称（示例）
export OMT_FOLDER_NAME="每日一个知识点"              # 知识库内的目标文件夹
```

未配置时使用 `upload_ima.py` 中的默认示例名称。建议在 IMA 中创建自己的知识库/文件夹后按上述方式配置。

### 5. （可选）密钥失效 webhook 通知

如果希望密钥失效时主动收到通知（例如飞书/Slack/企业微信机器人），设置环境变量：

```bash
export IMA_KEY_EXPIRED_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/<your-hook-id>"
```

未设置时，`notify_key_expired.py` 仅向 stderr 打印通知文本并以退出码 1 退出，由调用方处理。

### 6. Node.js 环境注意

某些沙箱环境中 `node` 可能被 bun shim 劫持（NODE_OPTIONS 指向不存在的模块）。
`upload_ima.py` 已内置处理：优先使用 `/usr/bin/node` 并在子进程中清除 `NODE_OPTIONS`，无需手动设置。

## 推送流程（每次调用执行一次）

`SKILL_DIR` 为本 skill 所在目录（脚本自动通过 `__file__` 定位，不依赖绝对路径）。
下面用 `$SD` 代表 SKILL_DIR。

### Step 1：获取下一张卡片载荷

```bash
cd $SD && python3 scripts/push_card.py next > /tmp/omt_payload.json
```

解析输出 JSON。若含 `"skip": true`：
- `all_done` → 全部 118 张已推送完毕，告知用户并结束
- 其他（如 `weekend`/`already_pushed_today`）→ 结束本次

从载荷提取 `nextId`、`terminology` 数组、`coreIdeaEn`、`explanationEn`、`quoteEn`、`applicationScenarios`、`relatedLinks`（对象数组，含 href 与 text 原文标题）、`images`（Example 图片数组，可能为空）。

> **数据来源说明**：卡片英文内容直接来自 `items.json`（已内置 118 张卡片的全部字段），无需额外的 `cards/` HTML 目录。如果你的安装中存在 `cards/` 目录（可选，包含原始 HTML 卡片），脚本会优先使用 HTML；否则自动回退到 items.json。

### Step 1b（必须）：自动补全卡片原文和 Example 图片

> **⚠️ 此步骤为强制步骤，不可跳过。** items.json 中的 explanationEn 存在被截断在 6000 字符的历史问题，且 images 数组可能不完整。每次推送前必须运行以下命令，从官网补全当前卡片的完整文本和所有 Example 图片：

```bash
cd $SD && python3 scripts/extract_images.py --card <nextId> --force
```

此脚本会：
1. 从 pressbooks 官网抓取该章节的完整 HTML
2. 提取所有静态图片（`<img>` / `<figure>`）并转为 base64
3. 自动通过 Wayback Machine 缓存获取 MuseScore 交互式乐谱的 SVG 并转为 PNG
4. 输出到 `items_new.json`

**脚本执行完成后，必须检查输出：**
- 如果 `items_new.json` 中该卡片的 explanationEn 比 items.json 更长，或 images 数量更多，则用 items_new.json 替换 items.json：
  ```bash
  cp items_new.json items.json
  ```
- 替换后**重新运行 Step 1a**（`push_card.py next --force`，此时需 --force 跳过当日已推判断以获取更新后的载荷）获取更新后的 payload
- 如果脚本报告有 MuseScore 乐谱截图失败（`captured=false`），在 PDF 中以链接卡片形式呈现（与 ch01-14 处理方式相同），不要中止推送

**图片类型说明：**

教材中的 Example 有三种形式，`extract_images.py` 处理能力不同：

1. **静态图片（`<img>` / `<figure>`）**：自动抓取为 base64 内嵌到 PDF。这是最常见的形式。WordPress 缩略图会自动升级为原图。
2. **MuseScore 交互式乐谱（`<iframe>` 来自 musescore.com）**：浏览器中是可交互/播放的乐谱。`extract_images.py` 会自动通过 web archive 缓存获取 SVG 矢量乐谱并转为 PNG。若截图失败，以链接卡片形式呈现。
3. **YouTube/Spotify 嵌入（`<iframe>`）**：没有静态图片，无法嵌入 PDF，会被跳过。

**翻译时如何区分：** payload 中 `images` 数组里有对应 Example 编号的图片才能加 `__IMAGE_X__` 标记。如果原文提到 "Example X" 但 payload.images 中没有该编号，说明这是视频或交互内容，**不要加标记**。

### Step 2：联网核对术语中文译法

对 `terminology` 数组中每个英文术语，按以下优先级使用联网查询其在**音乐理论领域**的权威中文译法：

1. **首选：searxng skill** — `~/.openclaw/workspace/skills/searxng/`
2. **备选：byted-web-search skill** — `~/.openclaw/workspace/skills/byted-web-search/`
3. **备选：agent 内置 web search 工具**

检索词示例：`music theory <term> 中文 译名` 或 `<term> 乐理 术语`。
汇总为 `terminologyZh` 对象 `{"英文术语": "中文译法"}`。**必须核对，不可凭记忆。**

### Step 3：实时翻译

将 coreIdeaEn / explanationEn / quoteEn / applicationScenarios 翻译为准确流畅的简体中文：
- explanationEn 按 `\n` 分段翻译，保持段落一一对应
- 专业术语首次出现采用「中文（英文）」格式
- 译文准确专业，符合乐理表达习惯
- **中文标点规范（重要！）**：
  - 中文部分必须使用**中文引号**「」，**禁止使用英文直引号 " "**
  - 中文逗号、句号、冒号、分号等也必须使用中文标点
  - 英文术语、代码片段、URL 等保持英文标点不变
- **explanationEn / applicationScenarios 中可能含 markdown 链接 `[text](url)`**：翻译时**保留 `[...](url)` 结构和 url 不变**，仅将方括号内的 text 翻译为中文（如 `["How was Musical Notation Invented?"](https://...)` → `[「音乐记谱法是如何发明的？」](https://...)`）；文件格式名 `pdf`/`docx` 等不翻译
- **翻译 relatedLinks 的标题**：对载荷 `relatedLinks` 数组中每个链接的 `text`（英文原文标题）翻译为中文，生成 `relatedLinksZh` 数组
- **翻译 topic（知识点主题）**：将载荷中的 `topic` 翻译为准确的中文，用于 PDF 文件名
- **⚠️ 图片位置标记**：翻译 explanation 时，检查原文中提及 "Example X." 的位置，**在对应的中文段落末尾添加图片插入标记**，格式为 `__IMAGE_X__`（X 为 Example 编号）。
  - 例如：原文 "Example 3 shows correct noteheads..." → 中文 "示例 3 展示了正确的符头写法...__IMAGE_3__"
  - 这样 Step 6 生成 PDF 时，`gen_card_pdf.py` 会解析标记，将 `images` 数组中对应编号的 Example 图片插入到这个位置
  - 注意：只对 explanation（详细解释）段落添加标记，coreIdea / quote / application 不需要
  - **⚠️ 标记顺序必须严格按 Example 编号升序排列**：`__IMAGE_1__` 必须出现在 `__IMAGE_2__` 之前，依此类推。Step 6 会强制校验顺序，乱序直接报错退出。
  - **⚠️ 只能标记 payload 中实际存在的 Example 图片**：标记之前先确认 `payload.images` 中存在该 Example 编号的图片；如果原文只是文字引用但 payload 里没有对应图片（可能是 YouTube 视频或 MuseScore 交互内容），**不要加标记**。
  - **⚠️ 如何确认图片是否存在**：查看 payload 中每张图片的 `caption` 字段（如 "Example 3. ..."），只有 caption 里有的 Example 编号才可以标记。如果 caption 里没有 "Example 3" 但原文提到了 Example 3，那通常是视频嵌入，无静态图。
  - **⚠️ 同一段落多个标记**：如果同一个段落引用了两张相邻的图，可以写 `__IMAGE_6____IMAGE_7__`（两个标记紧挨着）。

### Step 4：翻译质量全面检查 ✨

**在写入 JSON 前，逐项检查：**

1. **中文标点**：无英文直引号，标点全部中文
2. **核心翻译准确性**：语义准确、流畅、术语一致
3. **格式一致性**：markdown 链接结构完整，段落对应，首次术语「中文（英文）」
4. **PDF 文件名**：`OMT_YYYY-MM-DD_<card_id>_<topicZh>.pdf`

### Step 5：写翻译 JSON

将翻译结果写入 `/tmp/omt_zh.json`：

```json
{
  "coreIdeaZh": "...",
  "explanationZh": "...(用\n分段,保留[text](url)链接结构)...",
  "quoteZh": "...",
  "applicationZh": "...(保留[text](url)链接结构)...",
  "terminologyZh": {"英文": "中文", ...},
  "relatedLinksZh": [
    {"href": "https://...", "textEn": "English Title", "textZh": "中文标题"}
  ],
  "topicZh": "中文主题名（用于PDF文件名）",
  "note": "术语核对要点说明"
}
```

### Step 6：生成卡片式 PDF

```bash
cd $SD && python3 scripts/gen_card_pdf.py --payload /tmp/omt_payload.json --zh /tmp/omt_zh.json
```

**⚠️ 严格校验（会阻止错误 PDF 生成）：**

`gen_card_pdf.py` 在生成 PDF 前会自动执行以下校验，**任何一项失败都会以退出码 3 报错并中止，不会产出 PDF**：

1. **标记合法性**：所有 `__IMAGE_X__` 标记引用的 Example 编号必须在 `payload.images` 中存在（防止翻译幻觉标记不存在的图）
2. **图片全覆盖**：`payload.images` 中所有 Example 图片都必须有对应的 `__IMAGE_X__` 标记（防止漏标）
3. **顺序正确性**：标记出现顺序必须严格按 Example 编号升序（防止 "示例20跑到示例15前面" 之类的乱序）
4. **位置合理性**：标记所在段落的中文文字必须提到对应「示例 X」或 "Example X"（warning 级别）

如果报错退出，根据错误信息修正翻译 JSON（调整标记位置/删除错误标记/补充遗漏标记）后重新运行。

PDF 规格：A4、卡片式设计、大字号（中文正文 18px、英文 15px、标题 25px）、中英对照、术语表、Noto CJK 字体。
输出路径默认为 `/tmp/OMT_YYYY-MM-DD_<card_id>_<topicZh>.pdf`（如 `OMT_2026-06-29_ch01-01_西方音乐记谱法简介.pdf`）。
**不要加 `--out` 参数**，让脚本自动从 `topicZh` 生成文件名。

**多图支持（图片插入到中文对应位置）：**

`gen_card_pdf.py` 处理 `payload.images` 数组的逻辑：

1. **解析 `explanationZh` 中的 `__IMAGE_X__` 标记**：每个标记对应第 X 张 Example 图片
2. **严格校验**（见上方）：标记全部合法、顺序正确、覆盖所有图片后才继续
3. **插入图片**：将图片 HTML（含 caption 和 `data-example` 属性）替换到标记位置。同一段落支持多个标记（`__IMAGE_6____IMAGE_7__`）
4. **向后兼容**：如果 payload 中无 `images` 数组，显示旧的单图字段（`payload.image`）

**英文原文保留**：PDF 保持中英对照格式，中文 explanation 下方显示对应的英文原文。

**图片样式**：每张图限制最大宽度 100%，圆角边框显示。图片标题（caption）居中显示在图片上方。

### Step 6.5：图片复核（强制环节，未通过禁止上传 IMA）🔍

> ⚠️ **此步骤必须执行，不得跳过！** 这是防止错误 PDF 上传到 IMA 的最后一道防线。

PDF 生成成功后，必须用 `scripts/review_pdf_images.py` 复核图片顺序和位置：

```bash
cd $SD && python3 scripts/review_pdf_images.py \
  --pdf "/tmp/OMT_<date>_<card_id>_<topicZh>.pdf" \
  --payload /tmp/omt_payload.json \
  --zh /tmp/omt_zh.json
```

**复核脚本会用 PyMuPDF 解析 PDF，检查三项：**

1. **图片顺序**：PDF 中实际出现的 Example 图片是否严格按编号升序排列（防止顺序错乱）
2. **图片完整性**：payload 中所有 Example 图片都必须出现在 PDF 中，不能遗漏
3. **图片位置**：每张 Example 图片附近的正文文字是否提到对应「示例 X」/"Example X"（防止图片插入到错误段落）

**退出码含义：**
- `0` = ✅ 全部通过，可以上传
- `4` = ❌ 复核失败（图片顺序/完整性/位置错误），**禁止上传 IMA**，必须修正翻译后重新生成 PDF

**如果复核失败：**
- 根据输出的错误信息定位问题
- 回到 Step 3 修正翻译中的 `__IMAGE_X__` 标记位置
- 重新执行 Step 6 和 Step 6.5，直到复核通过
- 同时在日志中记录失败原因，方便后续排查

**依赖：** 复核脚本需要 PyMuPDF（`pip3 install pymupdf`）。

### Step 7：上传主 PDF 和相关附件到 IMA 知识库

#### 7a. 上传主 PDF

```bash
cd $SD && python3 scripts/upload_ima.py --file "/tmp/OMT_<date>_<nextId>.pdf"
```

脚本自动：动态定位 ima-skill → 定位知识库（默认名称见安装步骤 4）→ 定位目标文件夹 →
preflight 检查 → 重名检查 → create_media → COS 上传 → add_knowledge。

**退出码含义**：
- `0` → 上传成功
- `1` → 其他错误（已输出错误详情）
- `2` → **IMA 密钥失效**（已打印通知/触发 webhook，本次不计入进度，结束）

**若返回码 2（密钥失效）**：提示用户更新凭证（见安装步骤 3），**不要执行后续步骤**。

#### 7b. 上传相关附件

主 PDF 上传成功后，调用自动处理脚本下载并处理所有文件附件：

```bash
cd $SD && python3 scripts/process_attachments.py \
  --payload /tmp/omt_payload.json \
  --date <YYYY-MM-DD 推送日期> \
  --card-id <nextId> \
  --out-dir /tmp/omt_attachments
```

脚本自动完成以下工作：
1. **识别文件链接**：自动筛选 `relatedLinks` 中以 `.pdf/.docx/.xlsx/.doc/.pptx/.png/.jpg/.jpeg/.gif/.webp` 结尾的真实文件链接，跳过网页链接
2. **去重检查**：自动跳过已在 `payload.images` 中作为 base64 内嵌到 PDF 的图片，避免重复上传
3. **下载文件**：带浏览器 User-Agent/Accept/Referer 下载，自动识别并跳过 403/404 错误页
4. **PNG 自动转 JPG**：所有下载的 PNG 文件自动转换为高质量 JPG（quality=95），透明背景填充白色，转换后删除原 PNG
5. **统一命名**：按 `OMT_YYYY-MM-DD_<card_id>_<原文件名（扩展名已更新为jpg）>` 格式重命名

脚本运行完成后，读取 `/tmp/omt_attachments/attachments.json` 获取处理结果，对 `processed` 数组中的每个文件执行上传：
```bash
cd $SD && python3 scripts/upload_ima.py --file "<local_path>"
```

上传完成后在 daily-progress.md 中标注附件数量和文件名，注明哪些是 PNG 转换而来。

**附件上传失败**：不影响主推送进度，但必须通过 `scripts/notify_attachment_failed.py` 通知（webhook URL 从 config.json 读取）。

手动处理方式（不推荐，仅作参考）：
1. **遍历 relatedLinks**，识别 href 以以下文件扩展名**结尾**的链接：`.pdf` / `.docx` / `.xlsx` / `.doc` / `.pptx`
   - ⚠️ **只匹配上述后缀**，不要匹配网页链接（如 `.com/`、`.html`、无后缀的 URL 等）
2. **下载附件**：使用 `curl -sL -A "Mozilla/5.0"` 下载（带 User-Agent，避免 403）
3. **验证文件类型**：下载后执行 `file <路径>` 检查是否为真正的 PDF/DOCX/XLSX 等格式
4. **重命名并上传**：统一格式为 `OMT_YYYY-MM-DD_<card_id>_<原文件名>`，逐个上传

### Step 8：记录推送进度（仅主 PDF 上传成功后）

```bash
cd $SD && python3 scripts/push_card.py mark <nextId> success
```

### Step 9：更新 daily-progress.md 进度文件

在 `$SD/daily-progress.md` 中追加当天的执行记录：

```markdown
| 日期 | 卡片 ID | 主题 | 状态 | 完成时间 | 备注 |
|------|---------|------|------|----------|------|
| YYYY-MM-DD | <nextId> | <topic> | ✅ 完成 | HH:MM | 简要备注 |
```

同时在「执行日志」部分追加详细执行记录（含术语搜索所用工具、PDF 大小、附件数量等）。失败时也需记录失败原因。

### Step 10：汇报

简短汇报：今日推送第 X/118 张、卡片主题、术语核对要点、PDF 已上传至 IMA 知识库。

## 辅助命令

- 查看进度：`cd $SD && python3 scripts/push_card.py status`
- 手动重推某张：`python3 scripts/push_card.py next --force`
- 重置进度：编辑 progress.json，lastPushedId/lastPushDate 置 null，清空 pushHistory
- 单独测试 PDF 生成：`python3 scripts/gen_card_pdf.py --payload <payload.json> --zh <zh.json> --out test.pdf`
- 单独测试上传：`python3 scripts/upload_ima.py --file <xxx.pdf>`
- （可选，需 cards/ 目录）渲染双语 HTML：`python3 scripts/push_card.py render <id> --zh <zh.json>`

## 文件说明

| 文件 | 作用 |
|------|------|
| `SKILL.md` | 本指令文件 |
| `items.json` | 118 个知识点知识库（中英文字段 + 可选图片 base64 缓存） |
| `index.json` | 卡片推送顺序索引 |
| `progress.json` | 推送进度（自动维护，默认为 0） |
| `daily-progress.md` | 每日执行进度记录文件 |
| `prompts.md` | 定时任务配置建议（通用示例） |
| `scripts/push_card.py` | 进度管理 + 卡片载荷提取（status/next/render/mark/weekday） |
| `scripts/gen_card_pdf.py` | 生成卡片式双语 PDF（weasyprint） |
| `scripts/upload_ima.py` | 上传 PDF/附件到 IMA 知识库文件夹（含密钥失效检测、动态 ima-skill 路径查找） |
| `scripts/notify_key_expired.py` | 密钥失效通知（stderr + webhook 从 config.json 或 $IMA_KEY_EXPIRED_WEBHOOK 读取） |
| `scripts/extract_images.py` | 从 pressbooks 抓取 Example 图片并缓存到 items.json（支持 WordPress 原图 + MuseScore iframe 乐谱转静态图） |
| `scripts/review_pdf_images.py` | **PDF 生成后强制复核**：用 PyMuPDF 检查图片顺序/完整性/位置，未通过则阻止上传 |
| `scripts/card_slug_map.py` | 卡片 ID → pressbooks 章节精确映射表 |
| `scripts/process_attachments.py` | 自动下载/转换/重命名 relatedLinks 中的文件附件（PNG→JPG） |
| `scripts/notify_attachment_failed.py` | 附件下载/上传失败时发送 webhook 通知 |
| `config.json` | 本地配置：知识库名称、文件夹、webhook URL（不提交到公开仓库） |
| `scripts/setup.py` | 首次使用引导脚本（交互式检查环境 + 生成 config.json） |
| `cards/`（可选）| 118 张纯英文 HTML 卡片源，若存在则优先使用；不存在则直接读取 items.json |

## 定时任务配置

skill 本身不内置定时任务。可通过你的 agent 运行时（如 OpenClaw cron、crontab、GitHub Actions 等）调度：

- **主推送**：每天 1 次，调用 skill 执行 Step 1~10
- **监督/重试（可选）**：间隔 1 小时后检查 progress.json，未成功则重试

示例 crontab（每天 18:30 调用）：

```cron
30 18 * * * cd /path/to/skills/omt-daily-push && /path/to/your/agent-runner "执行 omt-daily-push 推送今日乐理卡片"
```

更多示例见 `prompts.md`。

## 注意事项

- 进度是唯一凭证，勿手动误改 progress.json
- 失败的推送绝不计进度，确保下次重推同一张
- PDF 文件名日期格式统一 `YYYY-MM-DD`
- 翻译质量优先：术语必须联网核对，宁可慢不可错
- 所有路径通过 `__file__` 动态解析，可放置于任意 skills 目录
