import asyncio
import datetime
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from bilibili_api import video, comment, Credential

app = FastAPI()

# ==================== State & Models ====================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass 

manager = ConnectionManager()

class MonitorState:
    def __init__(self):
        self.running = False
        self.target_bvid = ""
        self.sessdata = ""
        self.buvid3 = ""
        self.bili_jct = ""
        self.task: Optional[asyncio.Task] = None
        self.last_rpid = 0
        self.oid = 0
        self.title = ""

monitor_state = MonitorState()

class ConfigRequest(BaseModel):
    bvid: str
    sessdata: str
    buvid3: str = ""
    bili_jct: str = ""

# ==================== Logic ====================

async def fetch_task():
    """Background task to fetch comments loops"""
    print("Monitor task started")
    credential = Credential(
        sessdata=monitor_state.sessdata, 
        buvid3=monitor_state.buvid3,
        bili_jct=monitor_state.bili_jct
    )
    
    # Init video info
    try:
        v = video.Video(bvid=monitor_state.target_bvid, credential=credential)
        info = await v.get_info()
        monitor_state.oid = info['aid']
        monitor_state.title = info['title']
        
        await manager.broadcast({
            "type": "status", 
            "msg": f"已连接视频: {monitor_state.title}",
            "level": "success"
        })
        
        # Init last_rpid
        init_data = await comment.get_comments(
            oid=monitor_state.oid, 
            type_=comment.CommentResourceType.VIDEO, 
            order=comment.OrderType.TIME, 
            page_index=1,
            credential=credential
        )
        if init_data['replies']:
            monitor_state.last_rpid = init_data['replies'][0]['rpid']
        else:
            monitor_state.last_rpid = 0
            
    except Exception as e:
        await manager.broadcast({"type": "status", "msg": f"初始化失败: {str(e)}", "level": "error"})
        monitor_state.running = False
        return

    while monitor_state.running:
        try:
            data = await comment.get_comments(
                oid=monitor_state.oid, 
                type_=comment.CommentResourceType.VIDEO, 
                order=comment.OrderType.TIME, 
                page_index=1,
                credential=credential
            )
            replies = data.get('replies', [])
            
            new_comments = []
            if replies:
                for r in replies:
                    current_rpid = r['rpid']
                    if current_rpid > monitor_state.last_rpid:
                        info = {
                            'rpid': r['rpid'],
                            'user': r['member']['uname'],
                            'mid': r['member']['mid'],
                            'avatar': r['member']['avatar'],
                            'content': r['content']['message'],
                            'time': datetime.datetime.fromtimestamp(r['ctime']).strftime('%H:%M:%S'),
                            'level': r['member']['level_info']['current_level']
                        }
                        new_comments.append(info)
                    else:
                        break
            
            if new_comments:
                # Update last_rpid
                max_id = max([c['rpid'] for c in new_comments])
                monitor_state.last_rpid = max(monitor_state.last_rpid, max_id)
                
                # Send to frontend (reversed to match chronological order usually preferred in logs, 
                # but frontend can handle prepending. Let's send list and let frontend handle)
                await manager.broadcast({
                    "type": "new_comments", 
                    "data": new_comments
                })
                
        except Exception as e:
            await manager.broadcast({"type": "status", "msg": f"API请求错误: {str(e)}", "level": "warning"})
            
        await asyncio.sleep(5)

# ==================== Endpoints ====================

@app.post("/api/start")
async def start_monitor(req: ConfigRequest):
    if monitor_state.running:
        return {"status": "already_running"}
    
    monitor_state.target_bvid = req.bvid
    monitor_state.sessdata = req.sessdata
    monitor_state.buvid3 = req.buvid3
    monitor_state.bili_jct = req.bili_jct
    monitor_state.running = True
    monitor_state.task = asyncio.create_task(fetch_task())
    return {"status": "started"}

@app.post("/api/stop")
async def stop_monitor():
    if not monitor_state.running:
        return {"status": "not_running"}
    
    monitor_state.running = False
    if monitor_state.task:
        monitor_state.task.cancel()
        try:
            await monitor_state.task
        except asyncio.CancelledError:
            pass
        monitor_state.task = None
        
    await manager.broadcast({"type": "status", "msg": "监控已停止", "level": "info"})
    return {"status": "stopped"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send current status on connect
        status_msg = "监控进行中" if monitor_state.running else "等待开始..."
        await websocket.send_json({
            "type": "init", 
            "running": monitor_state.running,
            "title": monitor_state.title,
            "status": status_msg
        })
        while True:
            # Keep connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Mount static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
