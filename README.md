# Bilibili Comment Monitor

实时监控 Bilibili 视频评论，并将数据同步至 MongoDB 和飞书多维表格。

## 功能

- **实时评论监控**：WebSocket 推送新评论
- **历史评论获取**：支持分页拉取全部评论（含楼中楼回复）
- **MongoDB 存储**：按视频 BV 号分表存储
- **飞书连接器**：Cloudflare Worker 实现，可同步至飞书多维表格

## 快速开始

### 1. Python 后端

```bash
# 安装依赖
uv sync

# 启动服务
uv run uvicorn server:app --reload
```

访问 `http://127.0.0.1:8000`，输入 BV 号和 Cookie 开始监控。

### 2. 飞书连接器（Cloudflare Worker）

```bash
cd worker-api
npm install
npx wrangler deploy
```

部署后获取 Worker URL，在飞书多维表格添加自定义数据连接器：
- Manifest URL: `https://your-worker.workers.dev/meta.json`

## 项目结构

```
├── server.py          # FastAPI 后端主程序
├── static/            # 前端页面
│   ├── index.html
│   ├── app.js
│   └── style.css
├── worker-api/        # Cloudflare Worker (飞书连接器)
│   └── src/worker.ts
├── monitor_comments.py # 独立命令行监控脚本
└── pyproject.toml     # Python 依赖配置
```

## 环境变量

MongoDB 连接字符串在 `server.py` 中配置：
```python
MONGO_URI = "mongodb+srv://..."
```

## License

MIT
