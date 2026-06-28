# 📖 Book-to-Learn

**把任意一本书分解成日常学习任务，每日推送一张知识点卡片。**

支持中英文书籍（PDF / DOCX / HTML / EPUB / TXT），拆解为知识点后每日推送一张卡片到 IMA 知识库（PDF）或飞书（卡片消息）。英文书自动联网核对术语并实时翻译；中文书无翻译环节。

## ✨ 特性

- **多格式输入**：PDF、DOCX、HTML、EPUB、TXT、RTF，自动选择提取器并带回退链
- **中英文自适应**：英文书联网核对术语 + 实时翻译；中文书跳过翻译
- **两阶段架构**：拆书（一次性生成知识点数据）+ 推送（每次调用复用）
- **两种推送方案**：IMA 知识库 PDF（默认）/ 飞书卡片消息（备选）
- **卡片式设计**：大字号、中英对照、术语表、配图内嵌、移动端友好
- **进度自维护**：推送成功才记录进度，失败自动重推同一张
- **失败通知**：任何环节失败通过 webhook 通知，且不计进度
- **通用化**：参数化配置，支持多本书，首次使用引导配置

## 🙏 致谢与参考

本项目在**多格式文本提取**的方法论上参考了 [book-to-skill](https://github.com/virgiliojr94/book-to-skill) 项目（by [virgiliojr94](https://github.com/virgiliojr94)）。book-to-skill 将书籍转换为 AI agent 可检索的静态参考库；本项目在此基础上发展出**主动推送**模式——把书拆解为知识点后每日定时推送，变被动检索为主动学习。

两者的核心差异：

| 维度 | book-to-skill | book-to-learn |
|------|---------------|---------------|
| 目标 | 静态参考库，AI 按需检索 | 主动推送，每日一张卡片 |
| 输出 | SKILL.md + chapters + glossary | items.json + cards + 每日推送 |
| 语言 | 仅英文 | 中英文自适应 |
| 推送 | 无 | IMA PDF / 飞书卡片 |

## 📦 安装

```bash
# 克隆
git clone https://github.com/sedey999/book-to-learn.git
cd book-to-learn

# 安装 Python 依赖
sudo pip3 install weasyprint python-docx beautifulsoup4 ebooklib pypdf pdfminer.six
```

如需推送到 IMA 知识库，还需安装 [IMA skill](https://ima.qq.com/agent-interface)：

```bash
cd /tmp && curl -sL -o ima-skills.zip "https://app-dl.ima.qq.com/skills/ima-skills-1.1.7.zip"
mkdir -p ima-skills-extracted && unzip -o ima-skills.zip -d ima-skills-extracted >/dev/null 2>&1
cp -r ima-skills-extracted/ima-skill ~/.codebuddy/skills/ima-skill

# 配置 IMA 凭证
mkdir -p ~/.config/ima
echo "<your_client_id>" > ~/.config/ima/client_id
printf '%s' "<your_api_key>" > ~/.config/ima/api_key
```

## 🚀 使用

### 阶段一：拆书（每本书执行一次）

```bash
SKILL_DIR=~/.codebuddy/skills/book-to-learn

# 1. 提取文本
python3 $SKILL_DIR/extract_text.py your-book.pdf --out full_text.txt

# 2. 初始化配置（AI 引导填写 IMA 目标 / 通知 webhook / 语言等）
python3 $SKILL_DIR/book_setup.py init <book-slug> --title "书名" --lang en

# 3. AI 分析结构，生成知识点大纲（需确认）
# 4. 确认后生成完整 items.json
# 5. 生成卡片和索引
python3 $SKILL_DIR/book_setup.py gen-cards <book-slug>
python3 $SKILL_DIR/book_setup.py gen-index <book-slug>

# 6. 下载内嵌配图
python3 $SKILL_DIR/book_setup.py download-imgs <book-slug>

# 7. 输出定时任务提示词
python3 $SKILL_DIR/book_setup.py prompt <book-slug>
```

### 阶段二：每日推送（定时任务调用）

将 Step 7 输出的提示词配置到定时任务软件（如 CodeBuddy 的定时任务），设定触发时间即可。每次调用自动：取下一张 → [英文书联网核对术语+翻译] → 生成卡片式 PDF → 推送 → 记录进度。

## 📚 示例案例：Open Music Theory

`examples/open-music-theory/` 目录包含一个完整的拆书案例，基于开放乐理教材：

- **资料来源**：[Open Music Theory](https://viva.pressbooks.pub/openmusictheory)（viva.pressbooks.pub，开放教育资源）
- **拆解结果**：118 个知识点卡片，覆盖 10 个主题部分（基础、对位、曲式、和声、半音主义、爵士、流行音乐、20 世纪技法、十二音音乐、配器）
- **配图**：61 张原书配图已下载并以 base64 内嵌，离线可见
- **推送周期**：每工作日 1 张，约 24 周

案例展示了从 WXR 导出文件拆解、配图内嵌、双语翻译、IMA 上传的完整流程。详见 `examples/open-music-theory/SKILL.md`。

## 🔧 推送方案

| 方案 | 优势 | 适用场景 |
|------|------|----------|
| **IMA PDF（默认）** | 知识库可检索、PDF 卡片式美观、配图内嵌离线可读 | 知识库积累、长期学习 |
| **飞书卡片（备选）** | 即时通知、交互式卡片、主动触达 | 即时学习提醒、团队共学 |

首次配置时选择推送方案。飞书卡片方案的图片通过免费图床（catbox.moe）上传获取 URL 后嵌入。

## 📁 项目结构

```
book-to-learn/
├── SKILL.md                # 主指令（拆书+推送两阶段、首次配置流程）
├── extract_text.py         # 多格式文本提取（PDF/DOCX/HTML/EPUB/TXT/RTF）
├── book_setup.py           # 拆书编排
├── push_card.py            # 推送进度管理（--book 参数化，支持多本书）
├── gen_card_pdf.py         # 卡片式 PDF 生成（中英文自适应）
├── upload_ima.py           # IMA 知识库上传（密钥失效检测）
├── send_feishu.py          # 飞书卡片推送（图床上传）
├── notify_failure.py       # 通用失败通知
└── examples/
    └── open-music-theory/  # 示例案例
        ├── SKILL.md
        ├── items.json      # 118 个知识点
        ├── cards/          # 118 张 HTML 卡片
        └── ...
```

## 🔒 安全

- 所有凭证（IMA Client ID / API Key、飞书 webhook）存储于本地配置文件，**不硬编码于脚本**
- 凭证仅发送给对应官方域名（ima.qq.com / open.feishu.cn），不发送给任何第三方
- 推送失败通知的 webhook 在首次配置时由用户填写

## 📄 License

MIT
