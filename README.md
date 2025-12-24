# Bilibili Comment Monitor

实时监控 Bilibili 视频评论，并将数据同步至 MongoDB 和飞书多维表格。

## 架构

```
┌─────────────────────────────────────────────────────┐
│                  GitHub Actions                      │
│            (每 20 分钟定时运行爬虫)                   │
│                      │                               │
│                      ▼                               │
│              ┌───────────────┐                       │
│              │  crawler.py   │                       │
│              │   Python 爬虫  │                       │
│              └───────┬───────┘                       │
└──────────────────────┼──────────────────────────────┘
                       │
                       ▼
              ┌───────────────┐
              │   MongoDB     │
              │  云端数据库    │
              └───────┬───────┘
                       │
        ┌──────────────┴──────────────┐
        │                              │
        ▼                              ▼
┌───────────────┐            ┌───────────────┐
│ Cloudflare    │            │   飞书        │
│ Worker        │            │  多维表格     │
│ (WebUI + API) │            │   连接器      │
└───────────────┘            └───────────────┘
```

## 功能

- **定时评论抓取**：GitHub Actions 每 20 分钟自动运行
- **历史评论获取**：支持分页拉取全部评论（含楼中楼回复）
- **MongoDB 存储**：按视频 BV 号分表存储
- **Web 监控面板**：Cloudflare Worker 提供实时查看界面
- **飞书连接器**：可同步至飞书多维表格

---

## 部署方式

### 方式 1：GitHub Actions + Cloudflare Worker（推荐）

#### 1.1 配置 GitHub Secrets

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 说明 | 示例 |
|-------------|------|------|
| `BVID` | 要监控的视频 BV 号 | `BV1xx411x7xx` |
| `COOKIES_JSON` | Cookie 配置 JSON | `[{"sessdata":"xxx","buvid3":"yyy"}]` |
| `MONGO_URI` | MongoDB 连接字符串 | `mongodb+srv://user:pass@...` |

#### 1.2 推送代码

```bash
git add .
git commit -m "Deploy crawler"
git push
```

推送后 GitHub Actions 会自动每 20 分钟运行爬虫。也可手动触发：
- 打开仓库 → Actions → 定时抓取 Bilibili 评论 → Run workflow

#### 1.3 部署 Cloudflare Worker

```bash
cd worker-api

# 安装依赖
npm install

# 配置 MongoDB URI（会提示输入）
npx wrangler secret put MONGO_URI

# 部署
npx wrangler deploy
```

部署后会显示 Worker URL，访问即可看到监控面板。

---

### 方式 2：本地运行（开发测试）

```bash
# 安装 Python 依赖
uv sync

# 设置环境变量
export BVID="BVxxxxxx"
export COOKIES_JSON='[{"sessdata":"your_sessdata"}]'
export MONGO_URI="mongodb+srv://..."

# 运行爬虫
uv run python crawler.py

# 或启动完整后端（含 WebSocket 实时监控）
uv run uvicorn server:app --reload
```

---

## 项目结构

```
├── crawler.py              # 定时爬虫脚本 (GitHub Actions 使用)
├── server.py               # FastAPI 后端 (本地开发用)
├── static/                 # 本地前端页面
│   ├── index.html
│   ├── app.js
│   └── style.css
├── worker-api/             # Cloudflare Worker
│   ├── src/worker.ts       # API + WebUI
│   ├── wrangler.toml       # Worker 配置
│   └── package.json
├── .github/
│   └── workflows/
│       └── crawl.yml       # GitHub Actions 定时任务
├── pyproject.toml          # Python 依赖
└── README.md
```

---

## API 接口

Cloudflare Worker 提供以下 API：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 监控面板 WebUI |
| GET | `/api/videos` | 获取已监控的视频列表 |
| GET | `/api/comments/:bvid` | 获取指定视频的评论 |
| GET | `/api/video/:bvid` | 获取视频详情和最新评论 |
| GET | `/meta.json` | 飞书数据连接器 manifest |
| GET | `/config` | 飞书连接器配置页面 |

---

## Cookie 获取方法

1. 登录 Bilibili 网页版
2. 按 F12 打开开发者工具 → Application → Cookies
3. 复制 `SESSDATA`、`buvid3`、`bili_jct` 的值
4. 格式化为 JSON：

```json
[
  {
    "sessdata": "你的 SESSDATA",
    "buvid3": "你的 buvid3",
    "bili_jct": "你的 bili_jct"
  }
]
```

支持多账号轮询，只需在数组中添加更多账号配置。

---

## License

MIT
