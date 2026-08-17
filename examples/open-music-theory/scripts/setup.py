#!/usr/bin/env python3
"""
omt-daily-push 首次使用引导脚本。

交互式收集必要配置，生成 config.json。
也可以非交互方式通过命令行参数直接生成。

用法：
  python3 scripts/setup.py                    # 交互模式
  python3 scripts/setup.py --kb-name "..."    # 非交互（部分参数）
"""
import json
import os
import sys
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(SKILL_ROOT, 'config.json')

BANNER = r"""
╔══════════════════════════════════════════════════════════════╗
║          🎵 omt-daily-push 首次使用引导                      ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  本 skill 将《Open Music Theory》开源乐理教材拆解为 118 个   ║
║  知识点卡片，每日推送一张中英双语 PDF 到 IMA 知识库。         ║
║                                                              ║
║  执行流程：                                                   ║
║    1. 获取下一张未推送的卡片                                  ║
║    2. 联网核对术语中文译法                                    ║
║    3. AI 实时翻译（核心观点、详解、金句、应用场景）           ║
║    4. 生成卡片式双语 PDF（含教材原文 Example 图片）           ║
║    5. 图片复核（PyMuPDF 自动校验顺序/完整性）                 ║
║    6. 上传 PDF（及相关附件）到 IMA 知识库                     ║
║    7. 记录推送进度                                           ║
║                                                              ║
║  前置要求：                                                   ║
║    • IMA API 凭证已配置于 ~/.config/ima/                      ║
║    • ima-skill 已安装                                         ║
║    • Python 依赖：weasyprint, pymupdf, pillow                 ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""


def check_ima_credentials():
    """检查 IMA 凭证是否已配置。"""
    client_id_path = os.path.expanduser('~/.config/ima/client_id')
    api_key_path = os.path.expanduser('~/.config/ima/api_key')
    has_file = os.path.isfile(client_id_path) and os.path.isfile(api_key_path)
    has_env = bool(os.environ.get('IMA_OPENAPI_CLIENTID') and os.environ.get('IMA_OPENAPI_APIKEY'))
    return has_file or has_env


def find_ima_skill():
    """检查 ima-skill 是否可找到。"""
    candidates = [
        os.environ.get('IMA_SKILL_DIR', ''),
        os.path.join(SKILL_ROOT, '..', 'ima-skill'),
        os.path.expanduser('~/.openclaw/skills/ima-skill'),
        os.path.expanduser('~/.agents/skills/ima-skill'),
    ]
    for d in candidates:
        if d and os.path.isfile(os.path.join(d, 'ima_api.cjs')):
            return os.path.normpath(d)
    return None


def prompt(msg, default=None, required=True):
    """交互式输入。"""
    suffix = f' [{default}]' if default else ''
    while True:
        val = input(f'{msg}{suffix}: ').strip()
        if not val and default:
            return default
        if val or not required:
            return val
        print('  ⚠️ 此项为必填，请输入。')


def main():
    parser = argparse.ArgumentParser(description='omt-daily-push 首次使用引导')
    parser.add_argument('--kb-name', help='IMA 知识库名称')
    parser.add_argument('--folder-name', default='每日一个知识点', help='知识库内目标文件夹名称')
    parser.add_argument('--webhook', default='', help='推送失败通知 webhook URL（可选）')
    parser.add_argument('--non-interactive', action='store_true', help='非交互模式，使用命令行参数')
    args = parser.parse_args()

    print(BANNER)

    # 检查前置条件
    print('📋 前置条件检查：')
    if check_ima_credentials():
        print('  ✅ IMA API 凭证已配置')
    else:
        print('  ❌ IMA API 凭证未配置！')
        print('     请先获取凭证：https://ima.qq.com/agent-interface')
        print('     然后运行：')
        print('       mkdir -p ~/.config/ima')
        print('       echo "<your_client_id>" > ~/.config/ima/client_id')
        print('       printf \'%s\' "<your_api_key>" > ~/.config/ima/api_key')
        print()

    ima_skill = find_ima_skill()
    if ima_skill:
        print(f'  ✅ ima-skill 已找到：{ima_skill}')
    else:
        print('  ⚠️  ima-skill 未找到（上传功能将不可用）')
        print('     下载：https://app-dl.ima.qq.com/skills/ima-skills-1.1.7.zip')
        print('     解压到 ~/.openclaw/skills/ima-skill/')
        print()

    # 检查依赖
    try:
        import weasyprint
        print('  ✅ weasyprint 已安装')
    except ImportError:
        print('  ⚠️  weasyprint 未安装（PDF 生成将不可用）')
        print('     安装：pip3 install weasyprint')

    try:
        import fitz  # PyMuPDF
        print('  ✅ PyMuPDF 已安装')
    except ImportError:
        print('  ⚠️  PyMuPDF 未安装（图片复核将不可用）')
        print('     安装：pip3 install pymupdf')

    print()

    # 收集配置
    if args.non_interactive:
        kb_name = args.kb_name
        folder_name = args.folder_name
        webhook = args.webhook
        if not kb_name:
            print('❌ 非交互模式需要 --kb-name 参数', file=sys.stderr)
            sys.exit(1)
    else:
        print('📝 请提供以下配置信息：')
        print()
        kb_name = prompt('1. IMA 知识库名称（例如：我的乐理知识库）',
                         default=args.kb_name, required=True)
        folder_name = prompt('2. 知识库内目标文件夹名称',
                             default=args.folder_name or '每日一个知识点', required=True)
        webhook = prompt('3. 推送失败通知 webhook URL（可选，飞书/Slack 机器人，直接回车跳过）',
                         default=args.webhook or '', required=False)
        print()

    # 确认
    config = {
        'kbName': kb_name,
        'folderName': folder_name,
    }
    if webhook:
        config['keyExpiredWebhook'] = webhook

    print('📄 生成配置：')
    print(json.dumps(config, ensure_ascii=False, indent=2))
    print()

    if not args.non_interactive:
        confirm = prompt('确认写入 config.json？(y/n)', default='y', required=False)
        if confirm.lower() not in ('y', 'yes', ''):
            print('已取消。')
            sys.exit(0)

    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(f'✅ 配置已写入：{CONFIG_PATH}')
    print()
    print('🚀 一切就绪！可以开始推送了。')
    print('   测试命令：python3 scripts/push_card.py status')
    print('   手动推送：python3 scripts/push_card.py next --force')


if __name__ == '__main__':
    main()
