# music-library-cleanup

一个用于**安全整理音乐文件夹**的 skill（技能），帮助你把乱七八糟的音乐库整理得干净、规范、每首歌都能找到。

> 面向场景：NAS（群晖 / 威联通 / 飞牛等）、本地硬盘上成百上千首歌曲乱成一片：重复一堆、目录错乱、歌手歌名缺失、想清理又怕误删。

## 它做什么

- 🧹 **去重复**：按「歌名 + 歌手」找出重复的歌，自动保留音质最好的一份（DSD > FLAC > WAV > APE > MP3）
- 📂 **归类**：把歌曲统一成 `歌手 / 专辑名 / 歌手 - 歌名.格式` 的规范目录结构
- 🧽 **清理**：清掉空文件夹、只剩封面的"空壳"目录，腾出空间
- 🛡️ **绝不误删**：全程「只移动、不删除」，删任何文件都需你亲自确认，每步可回退

## 核心设计：三条底线

1. **只移动，不删除** —— 删除必须你确认，且删除前有完整清单可回溯
2. **拿不准就留** —— 判断不了的一律标"待确认"，绝不猜着删
3. **先做计划再动手** —— 批量改动前先产出 before→after 清单给你审

## 目录结构

```
music-library-cleanup/
├── SKILL.md                          # skill 主指令（通俗版六步流程 + 十条坑）
└── scripts/                          # 5 个参数化脚本，按序使用
    ├── build_index.py                # 扫描所有歌基本信息
    ├── enrich.py                     # 补齐/清洗歌手歌名专辑
    ├── dedup.py                      # 找重复、留最优音质
    ├── build_rename_plan.py          # 生成改名/归类计划
    └── apply_album_mapping.py        # 按清单把歌搬进专辑目录
```

## 怎么安装这个 skill

这是为 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（DSH）设计的 skill。安装方法：

```bash
# 1. 克隆到你的 DSH 用户 skill 目录
mkdir -p ~/.dsh/skills
git clone https://github.com/<你的用户名>/music-library-cleanup.git ~/.dsh/skills/music-library-cleanup
```

或者手动：把整个文件夹放到 `<项目目录>/.dsh/skills/` 或 `~/.dsh/skills/` 下即可。

安装后，在 DSH 会话里说「帮我整理音乐库」，它就会自动加载这个 skill，按六步流程指导你安全地整理。

## 怎么直接用脚本（不通过 DSH）

脚本是标准的 Python 3，需要 `ffprobe`（ffmpeg 自带）。按顺序运行：

```bash
python3 scripts/build_index.py        你的音乐目录 ./   # 扫描
python3 scripts/enrich.py              你的音乐目录 ./   # 补信息
python3 scripts/dedup.py               ./               # 找重复
python3 scripts/build_rename_plan.py   ./               # 生成计划
python3 scripts/apply_album_mapping.py 你的音乐目录 映射.json  # 执行归类
```

每一步都是"只移动/只生成计划"，不会直接删除任何音乐。

## 适用与不适用

- ✅ 适用：本地或 NAS 上的音乐文件（flac / ape / mp3 / wav / dsf / dff / m4a / wma）
- ⚠️ 注意：翻唱合辑、群星精选这类"没有单一歌手标准专辑"的，会自动归为"待确认"，不会乱归

## License

MIT
