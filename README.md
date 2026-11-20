# 往事榨汁机 Memory Juicer

把长辈的口述录音，榨成一本可以传下去的书。

访谈 → 语音转写 → 克制润色 → 按主题编排 → 预览成书 → 导出 PDF。全流程在浏览器里完成，长辈不用装 App。

## 技术栈

| 层 | 选型 |
|---|---|
| Web | FastAPI 0.162 + Uvicorn 0.54 |
| 模板 | Jinja2 3.1（服务端渲染，无前端框架） |
| 存储 | SQLite + SQLAlchemy 2.1 |
| 语音转写 | 通义千问 Paraformer（DashScope SDK） |
| 文本润色 / 追问 | 通义千问 qwen-plus |
| 音频转码 | imageio-ffmpeg（免装 ffmpeg） |
| PDF 导出 | Playwright 打印（免装 GTK3） |

## 快速开始

```powershell
# 1. 建虚拟环境（Python 3.13）
python -m venv .venv

# 2. 装依赖
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. 配置（可选，不配也能跑离线演示）
Copy-Item .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY

# 4. 启动
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

打开 http://127.0.0.1:8000

## 离线演示模式

`DASHSCOPE_API_KEY` 为空时自动进入离线模式，**整条产品链路仍可完整走通**：

- 语音：不转写，页面提示「请直接把文字打出来」
- 润色：只做断句与空行整理，一个字都不改（`offline_polish`）
- 追问：按回答里的关键词匹配本地追问模板（`offline_followup`）

这意味着你可以不花一分钱先验证交互、排版和导出。

## 配置项

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DASHSCOPE_API_KEY` | 空 | 留空即离线模式 |
| `LLM_MODEL` | `qwen-plus` | 润色与追问模型 |
| `ASR_MODEL` | `paraformer-realtime-v2` | 语音转写模型 |
| `APP_BASE_URL` | `http://127.0.0.1:8000` | 导出 PDF 时无头浏览器访问的地址 |
| `DATABASE_URL` | `sqlite:///data/memory_juicer.db` | 数据库连接串 |

配置读取优先级：**环境变量 > `.env` 文件 > 代码默认值**。

## 如何查看调用情况

### 1. 先确认配置到底生效了什么

```powershell
.venv\Scripts\python.exe scripts\check_ai.py
```

会打印 Key 长度与前缀、模型名，并真实发一次请求验证 Key 是否有效。

也可以直接查运行时配置：

```powershell
.venv\Scripts\python.exe -c "from app.config import settings; print(settings.ai_enabled, settings.llm_model, settings.asr_model, settings.database_url)"
```

### 2. 看健康检查端点

```powershell
curl http://127.0.0.1:8000/healthz
```

返回 `{"ok": true, "ai_enabled": true, "llm_model": "qwen-plus"}`。
`ai_enabled=false` 说明没读到 Key，此时一切 AI 能力都走兜底。

### 3. 看服务端日志

启动后每次调用都会打一行日志：

```
14:23:05 | INFO    | app.main        | 启动 往事榨汁机 | AI 模式=在线 | 模型=qwen-plus ...
14:23:31 | INFO    | app.services.ai_llm | LLM 请求 model=qwen-plus temperature=0.3 messages=2
14:23:33 | INFO    | app.services.ai_llm | LLM 成功 status=200 input_tokens=210 output_tokens=180 total_tokens=390
14:23:40 | WARNING | app.services.ai_llm | LLM 返回异常 status=401 message=Invalid API-key provided.
```

`LLM 成功` 带 token 用量，可直接估算费用。出现 `WARNING` 就说明回退了兜底逻辑。

### 4. 看数据里存的 provider 字段

每条故事都记录了自己是哪种方式生成的：

```powershell
.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('data/memory_juicer.db'); [print(r) for r in c.execute('select id, topic, provider, length(raw_text), substr(polished_text,1,30) from stories')]"
```

- `provider='offline'` → 走了本地兜底，**没有调用大模型**
- `provider='qwen-plus'` → 真实调用了模型

### 5. 看浏览器端反馈

页面上每次操作都有 toast 提示：成功是「整理好了」，失败会明确写出原因（如「API Key 无效或已过期」）。

## 目录结构

```
app/
  main.py              FastAPI 入口，挂载静态资源与路由
  config.py            配置中心，自动创建 data/ uploads/ exports/
  logging_setup.py     统一日志格式
  db.py                会话管理与建表
  models.py            Project / Story / Photo
  question_bank.py     5 大主题 30 个问题，破冰→追问→情感钩子
  routers/
    pages.py           首页 / 编辑台 / 访谈 / 成书预览 / PDF
    api.py             提问、录音上传、润色、追问、照片
  services/
    ai_asr.py          语音转写 + ffmpeg 自动转码
    ai_llm.py          润色与追问，含离线兜底
    book_service.py    把故事编排成书
    pdf_service.py     Playwright 打印 PDF
  templates/           Jinja2 模板
  static/              手写 CSS 与原生 JS
scripts/
  check_ai.py          Key 与链路自检
  smoke.py             端到端冒烟脚本
tests/                 pytest 用例
```

## 路线图

项目仍在持续更新中，以下按优先级排列。

### 已完成

- [x] 建项目 → 分享链接 → 访谈录音/打字 → 转写 → 润色 → 编辑 → 成书 → PDF 全链路
- [x] 5 大主题 30 个问题，破冰 / 追问 / 情感钩子分层推进
- [x] 透明润色 Diff：逐字高亮 AI 改动，并给出原话保真度百分比
- [x] 原声播放条（编辑台与成书页均可听原话）
- [x] 记忆温度进度环：已录段数、估算时长、主题覆盖度
- [x] 离线演示模式：无 API Key 时润色只断句、追问走本地模板，全流程仍可走通
- [x] PDF 导出优先复用本机 Chrome / Edge

### 中期

- [ ] Alembic 数据库迁移（当前 `create_all` 不会给旧表加列，加字段会导致老库缺列）
- [ ] 题库在线管理与自定义（按方言区、年代、职业替换问题集）
- [ ] 生命刻度尺：按故事发生年份排成 0→80 岁横向刻度，空白即"还没讲完"
- [ ] 金句墙：从全部故事中挑出"最像本人说话"的句子
- [ ] 声音明信片：带二维码的分享图，扫码听一段原声
- [ ] 成书页脚二维码，扫码听章节原声（实体书场景）

### 长期

- [ ] 多视角对照：让不同家人讲同一件事，成书时并排展示，不做统一
- [ ] 记忆地图：只打点老人明确说出的地名，模糊位置用区域圆圈
- [ ] 时代同框：本地人工校对年表查表，禁止模型生成历史事件
- [ ] 人物卡片 + 手动连线（AI 抽取仅作建议，需人工确认）
- [ ] 主题点亮 / 记忆盲盒等轻量玩法

### 明确不做

| 不做 | 原因 |
|---|---|
| AI 生成场景配图 | 直接违反"不得添加原文不存在的细节"，画出来的房子不是他家那栋 |
| 声音克隆 / 数字永生 | 伦理风险极高，且真实原声比克隆声音动人 |
| 重度游戏化（积分 / 榜单 / 打卡） | 与产品调性冲突，会把讲人生故事变得廉价 |
| 自动家族树 | 抽取准确率不足，错误在家族场景里是冒犯性错误 |
| 在线地图 API | 老人的村子多半没有标注，接了反而显示一片空白 |

## 接口一览

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/healthz` | 健康检查 + AI 开关状态 |
| GET | `/api/topics` | 主题列表 |
| GET | `/api/projects/{token}/question` | 取下一个问题 |
| POST | `/api/projects/{token}/stories` | 提交口述（转写 + 润色） |
| PATCH | `/api/stories/{id}` | 手动编辑文本 |
| POST | `/api/stories/{id}/repolish` | 重新润色（可切换更生动） |
| POST | `/api/stories/{id}/followup` | 生成追问建议 |
| DELETE | `/api/stories/{id}` | 删除故事 |
| POST | `/api/projects/{token}/photos` | 上传老照片 |
| DELETE | `/api/photos/{id}` | 删除照片 |
| GET | `/book/{token}/pdf` | 导出 PDF |

## 测试

```powershell
.venv\Scripts\python.exe -m pytest -q
```

## PDF 导出说明

默认优先用**本机已装的 Chrome / Edge**（`channel="chrome"` → `"msedge"` → 自带 chromium），所以通常不需要下载 200MB 的浏览器内核。若三者都不可用，执行：

```powershell
.venv\Scripts\python.exe -m playwright install chromium
```

## 产品底线

AI 润色必须克制。保留原话语气与方言词汇，只修正病句和标点，**绝不添加原文不存在的细节**。否则成品读起来不像本人，情感价值直接归零。