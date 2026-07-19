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

## 安装（首次使用前）

### 1. 必备依赖

- **Python 3.8+**
- **Node.js 18+**（ima-skill 上传时使用）
- **WeasyPrint**（PDF 生成）
- **Noto Sans/Serif CJK 字体**（PDF 中文字体）

#### macOS

```bash
brew install python pango cairo gdk-pixbuf libffi
pip3 install weasyprint
# 字体
brew install --cask font-noto-sans-cjk-sc font-noto-serif-cjk-sc
```

#### Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install -y python3-pip libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 \
    fonts-noto-cjk
pip3 install weasyprint
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
export OMT_KB_NAME="【权威】音乐制作：风格与流派"   # 你在 IMA 中的知识库名称
export OMT_FOLDER_NAME="每日一个知识点"              # 知识库内的目标文件夹
```

未配置时，默认使用上述示例名称（你也可以在 IMA 中创建同名知识库/文件夹，或修改 `upload_ima.py` 顶部的 `DEFAULT_KB_NAME` / `DEFAULT_FOLDER_NAME`）。

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
cd $SD && python3 scripts/push_card.py next --force > /tmp/omt_payload.json
```

解析输出 JSON。若含 `"skip": true`：
- `all_done` → 全部 118 张已推送完毕，告知用户并结束
- 其他（如 `weekend`/`already_pushed_today`）→ 结束本次

从载荷提取 `nextId`、`terminology` 数组、`coreIdeaEn`、`explanationEn`、`quoteEn`、`applicationScenarios`、`relatedLinks`（对象数组，含 href 与 text 原文标题）、`images`（Example 图片数组，可能为空）。

> **数据来源说明**：卡片英文内容直接来自 `items.json`（已内置 118 张卡片的全部字段），无需额外的 `cards/` HTML 目录。如果你的安装中存在 `cards/` 目录（可选，包含原始 HTML 卡片），脚本会优先使用 HTML；否则自动回退到 items.json。

### Step 1b（可选）：提取卡片原文中的 Example 图片

如果希望 PDF 包含教材原文的 Example 图（且 `items.json` 中尚无 `images` 字段），运行抓取：

```bash
cd $SD && python3 scripts/extract_images.py --card <nextId>   # 单张
cd $SD && python3 scripts/extract_images.py                    # 批量全部
```

这会从 pressbooks 页面抓取所有 figure 图片并缓存为 base64，批量模式输出到 `items_new.json`，确认无误后替换 `items.json`。

### Step 2：联网核对术语中文译法

对 `terminology` 数组中每个英文术语，使用 **web search 工具**（agent 内置的联网搜索能力，如 `web_search` 工具）查询其在**音乐理论领域**的权威中文译法。检索词示例：

- `music theory <term> 中文 译名`
- `<term> 乐理 术语`
- `<term> music theory translation Chinese`

> **搜索工具选择**：直接使用 agent 内置的 web search 工具即可，不依赖任何特定搜索 skill（如 searxng/byted），保持跨平台通用性。

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

PDF 规格：A4、卡片式设计、大字号（中文正文 18px、英文 15px、标题 25px）、中英对照、术语表、Noto CJK 字体。
输出路径默认为 `/tmp/OMT_YYYY-MM-DD_<card_id>_<topicZh>.pdf`（如 `OMT_2026-06-29_ch01-01_西方音乐记谱法简介.pdf`）。
**不要加 `--out` 参数**，让脚本自动从 `topicZh` 生成文件名。

**多图支持（重要！图片插入到中文对应位置）：**

`gen_card_pdf.py` 会自动处理 `payload.images` 数组中的图片，按以下逻辑渲染：

1. **解析 `explanationZh` 中的 `__IMAGE_X__` 标记**：每个标记对应第 X 张 Example 图片。标记由 Step 3 翻译时在中文段落末尾添加。
   - 示例：`示例 3 展示了正确的符头写法...__IMAGE_3__`
2. **匹配图片到标记**：遍历 `images` 数组，通过每张图片的 `caption` 字段（如 "Example 3. Correct noteheads..."）提取 Example 编号，找到对应的 `__IMAGE_X__` 标记位置
3. **插入图片**：将图片 HTML（含 caption）替换到标记位置
4. **未匹配的图片**：如果有图片的 Example 编号在中文文本中没有对应的 `__IMAGE_X__` 标记，**放在 explanation 区域最上方**
5. **向后兼容**：如果 payload 中无 `images` 数组，显示旧的单图字段（`payload.image`）

**英文原文保留**：PDF 保持中英对照格式，中文 explanation 下方显示对应的英文原文。

**图片样式**：每张图限制最大宽度 100%，圆角边框显示。图片标题（caption）居中显示在图片上方。

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

主 PDF 上传成功后，检查 payload 的 `relatedLinks` 数组中真正的文件类型链接：

1. **遍历 relatedLinks**，识别 href 以以下文件扩展名**结尾**的链接：`.pdf` / `.docx` / `.xlsx` / `.doc` / `.pptx`
   - ⚠️ **只匹配上述后缀**，不要匹配网页链接（如 `.com/`、`.html`、无后缀的 URL 等）
   - ⚠️ 不要将 `hellomusictheory.com/learn/duplets/` 这样的网页链接误识别为文件
2. **下载附件**：使用 `curl -sL -A "Mozilla/5.0"` 下载（带 User-Agent，避免 403）
3. **验证文件类型**：下载后执行 `file <路径>` 检查是否为真正的 PDF/DOCX/XLSX 等格式
   - 如果是 `HTML document`（即被重定向到网页），说明链接失效或不是文件，**跳过并记录**
4. **重命名**：统一格式为 `OMT_YYYY-MM-DD_<card_id>_<原文件名>`
   - 例：`OMT_2026-07-04_ch01-01_WK-Introduction-to-Western-Musical-Notation.pdf`
5. **逐个上传**：对每个真正的文件附件执行 `python3 scripts/upload_ima.py --file <附件路径>`
6. **记录**：在 daily-progress.md 中标注附件数量和文件名

附件上传失败不影响主推送进度，仅记录失败信息。

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
| `scripts/notify_key_expired.py` | 密钥失效通知（stderr + 可选 $IMA_KEY_EXPIRED_WEBHOOK） |
| `scripts/extract_images.py` | 从 pressbooks 抓取 Example 图片并缓存到 items.json |
| `scripts/card_slug_map.py` | 卡片 ID → pressbooks 章节精确映射表 |
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
