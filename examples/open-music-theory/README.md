# Open Music Theory 每日双语卡片推送（omt-daily-push）

将 *Open Music Theory* 开源乐理教材拆解为 **118 个知识点卡片**，每日自动生成一张中英双语对照 PDF 并上传到 IMA 知识库。

## ✨ 特性

- 📚 **118 张知识点卡片**：完整覆盖 OMT 教材全部核心内容，内置在 `items.json`
- 🌍 **中英双语对照**：专业术语联网核对权威译法，实时翻译保证准确
- 🖼️ **原文图片支持**：自动从 pressbooks 抓取每个知识点的 Example 图片，精确映射到对应卡片
- 📄 **精美 PDF 排版**：卡片式设计、大字号、Noto CJK 中文字体、术语对照表、相关链接
- ☁️ **IMA 知识库上传**：自动定位知识库和文件夹，支持重名检查，支持附件上传
- 📊 **进度跟踪**：成功上传后才更新进度，失败自动重试，完整日志记录
- 🔔 **密钥失效提醒**：支持 webhook 通知，凭证过期不丢进度

## 🚀 快速开始

### 1. 安装依赖

- Python 3.8+
- Node.js 18+（IMA 上传依赖）
- WeasyPrint + Pango/Cairo（PDF 生成）
- Noto CJK 字体（中文显示）

```bash
# Ubuntu/Debian
sudo apt-get install -y python3-pip libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 fonts-noto-cjk
pip3 install weasyprint

# macOS
brew install python pango cairo gdk-pixbuf libffi
pip3 install weasyprint
brew install --cask font-noto-sans-cjk-sc font-noto-serif-cjk-sc
```

### 2. 安装 ima-skill（必需）

本 skill 依赖官方 ima-skill 进行知识库文件上传，请安装最新版本：

- **下载地址**：https://app-dl.ima.qq.com/skills/ima-skills-1.1.7.zip
- **API Key 获取**：https://ima.qq.com/agent-interface

解压后将 `ima-skill/` 目录放到你的 agent skills 目录下即可。脚本会自动查找：

1. `$IMA_SKILL_DIR` 环境变量
2. 与 `omt-daily-push` 同级目录
3. `~/.openclaw/skills/ima-skill`
4. `~/.agents/skills/ima-skill`

### 3. 配置 IMA 凭证

```bash
mkdir -p ~/.config/ima
echo "<your_client_id>" > ~/.config/ima/client_id
printf '%s' "<your_api_key>" > ~/.config/ima/api_key
```

### 4. 配置目标知识库（可选）

默认上传到知识库「【权威】音乐制作：风格与流派」→「每日一个知识点」文件夹。可通过环境变量自定义：

```bash
export OMT_KB_NAME="你的知识库名称"
export OMT_FOLDER_NAME="目标文件夹名称"
```

## 📖 使用方法

调用 skill 即可自动执行一次完整推送流程：

1. 获取下一张未推送卡片
2. （可选）自动抓取原文图片
3. 联网核对每个术语的权威中文译法
4. 完整翻译所有字段，保持专业准确
5. 生成卡片式双语 PDF
6. 下载相关附件（PDF/DOCX/XLSX 等）
7. 上传 PDF 和附件到 IMA 指定文件夹
8. 更新进度，记录日志

## 🛠️ 辅助命令

```bash
# 查看当前进度
python3 push_card.py status

# 手动触发推送（测试用）
python3 push_card.py next --force

# 批量抓取所有卡片图片（一次性更新 items.json）
python3 scripts/extract_images.py

# 单独测试 PDF 生成
python3 gen_card_pdf.py --payload payload.json --zh zh.json
```

## 📁 文件结构

| 文件 | 说明 |
|------|------|
| `SKILL.md` | 完整使用文档 |
| `push_card.py` | 进度管理 + 卡片载荷生成 |
| `gen_card_pdf.py` | PDF 生成（weasyprint） |
| `upload_ima.py` | IMA 知识库上传 |
| `notify_key_expired.py` | 密钥失效通知 |
| `items.json` | 118 个知识点完整数据 |
| `scripts/extract_images.py` | 图片抓取脚本 |
| `scripts/card_slug_map.py` | 卡片→章节精确映射表 |
| `progress.json` | 推送进度（自动维护） |
| `daily-progress.md` | 每日推送日志 |
| `prompts.md` | 定时任务配置示例 |

## ⚙️ 定时调度

skill 本身不内置定时任务，可以根据你的 agent 平台配置：

- OpenClaw cron
- crontab
- GitHub Actions

示例 crontab：
```cron
30 18 * * * cd /path/to/omt-daily-push && /path/to/your/agent "执行今日乐理卡片推送"
```

## 📝 License

MIT
