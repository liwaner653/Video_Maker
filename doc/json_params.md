# 视频处理 JSON 参数文档

本文档说明视频处理管道（`src/video main.py` / `src/main.py`）的 JSON 输入格式。

## 总体结构

JSON 文件必须是**数组**，每个元素是一个视频任务对象：

```json
[
  { "video_path": "D:/videos/ep01.mkv", "...": "..." },
  { "video_path": "D:/videos/ep02.mkv", "...": "..." }
]
```

### 两个入口的区别

| 入口 | 管道末尾步骤 | 产物 |
|------|------|------|
| `src/video main.py` | VideoTrimStep → VideoMergeStep | 裁剪原视频画面 + 音频 + 烧录字幕（可接额外视频） |
| `src/main.py` | ThumbnailStep → PicVideoMergeStep | 缩略图 + 音频合成静态画面视频（不裁剪原画面） |

`thumbnail` 对象和 `video_parts` 中的 `thumbnail` 字段**仅 `src/main.py` 管道消费**。

## 顶层任务字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:---:|------|------|
| `video_path` | string | ✅ | — | 视频文件完整路径，不存在则整个 JSON 解析失败 |
| `audio` | object | 否 | 见下 | 音频配置 |
| `subtitle` | object | 否 | 见下 | 字幕配置 |
| `thumbnail` | object | 否 | 见下 | 缩略图配置 |
| `final_video` | object | 否 | 见下 | 最终视频配置 |
| `video_parts` | array | 否 | 整段保留 | 分段配置数组 |
| `video_part` | object | 否 | — | 单段简写（与 `video_parts` 二选一） |

`video_parts`、`video_part` 都缺省时，按整段视频处理（start=0，end=视频时长）。

---

## audio 对象

| 字段 | 类型 | 默认值 | 说明 |
|------|------|------|------|
| `audio_stream_index` | int | 0 | 保留字段。**当前实际不按此索引选轨**：AudioStep 会按 `subtitle.subtitle_lang` 的语言标签自动匹配音轨，匹配失败回退到第 0 条音轨 |
| `check_exist` | bool | false | true 时，若 `audio_{lang}/` 目录下已存在同名音频文件（aac/ac3/eac3/mp3/flac/wav/m4a/opus），跳过提取直接复用 |

```json
"audio": { "audio_stream_index": 0, "check_exist": true }
```

## subtitle 对象

| 字段 | 类型 | 默认值 | 说明 |
|------|------|------|------|
| `subtitle_lang` | string | — | 语言代码（`en/de/zh/ja/fr/es/ru/pt`，见 `steps/config.py` 的 LANG_MAP）。**subtitle 对象存在时必填**。同时用于：音轨匹配、内嵌字幕轨匹配、Whisper 生成语言、输出目录后缀 |
| `check_exist` | bool | true | true 时，若最终字幕产物 `subtitles_{lang}/{视频名}.srt` 已存在，跳过提取/生成 |
| `target_titles` | array[string] | `["cc", "sdh", "Dub"]` | 内嵌字幕轨的标题关键字过滤，OR 逻辑（任一匹配即可），不区分大小写 |

字幕获取顺序：
1. 按语言 + `target_titles` 匹配内嵌字幕轨并提取为 SRT（跳过图像类字幕轨）；
2. 未匹配到或提取失败 → 用 Whisper（turbo 模型）从音频生成；
3. 最终合并后的字幕文件 < 20KB 且非 DEBUG 模式时，视为无效，不烧录。

```json
"subtitle": { "subtitle_lang": "de", "check_exist": true, "target_titles": ["cc", "sdh"] }
```

## thumbnail 对象（仅 `src/main.py` 管道）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|------|------|
| `pic_path` | string | `""` | 自定义封面图片路径；非空时校验文件必须存在，且直接使用该图、不再生成缩略图 |
| `blur_sigma` | float | 0.0 | 缩略图高斯模糊强度，0 = 不模糊，负数按 0 处理 |
| `check_exist` | bool | true | true 时，若 `thumbnails_{lang}/` 下已有同名 jpg 则跳过生成 |

## final_video 对象（仅 `src/video main.py` 管道）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|------|------|
| `check_exist` | bool | false | true 时，若 `final_videos_{lang}/{视频名}.mkv` 已存在，跳过画面裁剪和音视频合并 |
| `additional_video_path` | string | 见说明 | 额外 mkv 文件路径，合并到最终视频**末尾**。非空时校验文件必须存在（否则 JSON 解析报错）；显式传 `""` 则不合并。⚠️ 未在 JSON 中配置时，代码内置默认值为 `C:\Users\12864\Desktop\2\1.mkv`，该文件不存在则合并步骤自动跳过 |

```json
"final_video": { "check_exist": false, "additional_video_path": "D:/videos/ending.mkv" }
```

---

## video_parts 分段配置

每个分段对象字段：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|------|------|
| `name` | string | `""` | 分段名称，仅作标识 |
| `cut_front_seconds` | float | 无 | 开始时间（秒），支持小数 |
| `start_chapter_name` | string | `""` | 从指定章节名开始（仅 mkv 有章节；章节不存在则警告并回退默认） |
| `last_seconds` | float | 无 | 持续秒数，>0 时结束时间 = 开始 + 该值 |
| `end_chapter_name` | string | 无 | 结束于指定章节名的结束时间 |
| `cut_back_seconds` | float | 无 | 结束时间 = 视频时长 − 该值 |
| `thumbnail` | bool | true | 该段是否参与缩略图生成（仅 `src/main.py`） |
| `srt` | bool | true | 该段是否生成/保留字幕 |
| `audio` | bool | true | **该段是否进入最终视频**（见下方重要说明） |
| `audio_offset_chapter_start_time` | string | `""` | 音频偏移章节名：剪辑音频、生成片段字幕时，时间会减去该章节的 start_time（用于音频与画面章节不对齐的场景） |

### 开始/结束时间的生效顺序

- **开始时间**：`cut_front_seconds` > `start_chapter_name` > 上一段的结束时间（首段默认为 0）
- **结束时间**：`last_seconds` > `end_chapter_name` > `cut_back_seconds` > 下一段的开始时间（最后一段默认为视频时长）

### 重要：`audio=false` 的分段不会出现在最终视频中

画面裁剪（VideoTrimStep）和音频修剪（AudioTrimStep）都只处理 `audio=true` 的分段并拼接；`audio=false` 的段仅作为时间占位被跳过。例如"剪掉中间一段"的写法是把中间段设为 `audio: false`：

```json
"video_parts": [
  { "cut_front_seconds": 0,   "cut_back_seconds": 600 },
  { "name": "广告段", "audio": false },
  { "cut_front_seconds": 600 }
]
```

（第 2 段未指定开始时间 → 默认接第 1 段结束；未指定结束 → 默认到第 3 段开始，即 600s。）

---

## 输出目录结构

以视频所在目录为根（`{lang}` 为 `subtitle_lang`）：

```
{视频目录}/
├── thumbnails_{lang}/        # 缩略图（仅 main.py 管道）
├── audio_{lang}/             # 提取的音频（后处理时删除）
├── subtitles_{lang}/         # 字幕（后处理时移动至 git 仓库）
└── final_videos_{lang}/
    └── {视频名}.mkv          # 最终产物
```

后处理步骤（`config.DEBUG = False` 时才执行）：删除 `audio_{lang}/`，将 `subtitles_{lang}/` 移动到 `steps/config.py` 中 `GIT_REPO_PATH` 指向的仓库并自动 commit。

## 完整示例

```json
[
  {
    "video_path": "D:/videos/ep01.mkv",
    "audio": { "check_exist": true },
    "subtitle": {
      "subtitle_lang": "de",
      "check_exist": true,
      "target_titles": ["cc", "sdh", "Dub"]
    },
    "final_video": {
      "check_exist": false,
      "additional_video_path": "D:/videos/ending.mkv"
    },
    "video_parts": [
      { "start_chapter_name": "Chapter 2", "last_seconds": 1200 },
      { "name": "跳过的片尾", "audio": false, "srt": false }
    ]
  },
  {
    "video_path": "D:/videos/ep02.mkv",
    "subtitle": { "subtitle_lang": "en" }
  }
]
```

第 2 个任务为最小配置：整段处理，提取/生成英文字幕，输出到 `final_videos_en/ep02.mkv`。
