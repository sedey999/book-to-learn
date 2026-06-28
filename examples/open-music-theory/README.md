# 示例案例：Open Music Theory

本目录是 book-to-learn skill 的完整拆书案例。

## 资料来源

**[Open Music Theory](https://viva.pressbooks.pub/openmusictheory)** — 一本开放的乐理教材，由 Bryn Hughes、Chelsey Hamm、Megan Lavengood、Brian Jarvis、Mark Gotham、John Peterson、Kyle Gullings 等作者编写，托管于 viva.pressbooks.pub。

> ⚠️ 本案例的所有知识点内容均提炼自上述开放教材。配图来自原书。遵循原书的开放许可使用。

## 案例内容

| 文件 | 说明 |
|------|------|
| `SKILL.md` | 该案例的推送流程指令 |
| `items.json` | 118 个知识点（含 base64 内嵌配图） |
| `index.json` | 推送顺序索引 |
| `progress.json` | 推送进度（初始状态） |
| `cards/` | 118 张纯英文 HTML 卡片 |
| `images/` | 61 张原书配图 |
| `push_card.py` | 进度管理脚本 |
| `gen_card_pdf.py` | 卡片式 PDF 生成 |
| `upload_ima.py` | IMA 知识库上传 |
| `notify_key_expired.py` | 密钥失效通知 |

## 知识点分布

| Part | 主题 | 章节数 |
|------|------|--------|
| I | Fundamentals 基础 | 26 |
| II | Counterpoint and Galant Schemas 对位与加兰特范式 | 13 |
| III | Form 曲式 | 9 |
| IV | Diatonic Harmony 自然音和声 | 15 |
| V | Chromaticism 半音主义 | 15 |
| VI | Jazz 爵士 | 9 |
| VII | Popular Music 流行音乐 | 14 |
| VIII | 20th- and 21st-Century Techniques 20–21 世纪技法 | 8 |
| IX | Twelve-Tone Music 十二音音乐 | 6 |
| X | Orchestration 配器 | 3 |

每工作日推送 1 张，约 24 周完成全部 118 个知识点。

## 使用

```bash
# 查看进度
python3 push_card.py status

# 手动推送下一张（测试）
python3 push_card.py next --force
```

> **注意**：使用前需将 `notify_key_expired.py` 中的 `YOUR_WEBHOOK_TOKEN` 替换为你自己的飞书 webhook，并配置 IMA 凭证。
