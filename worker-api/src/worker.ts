import { Hono } from 'hono'
import { MongoClient } from 'mongodb'

const app = new Hono()

// 1. 获取视频列表
app.post('/get_videos', async (c) => {
    const { uri, db } = await c.req.json();
    const client = new MongoClient(uri, {
        autoEncryption: undefined,
        monitorCommands: false,
        connectTimeoutMS: 5000,
    } as any);
    try {
        await client.connect();
        const collection = client.db(db).collection("video_metadata");
        const videos = await collection.find({}).sort({ last_updated: -1 }).limit(100).toArray();
        return c.json({ code: 0, data: videos });
    } catch (e: any) {
        return c.json({ code: 500, msg: e.message });
    } finally {
        await client.close();
    }
});

// 2. 配置界面
app.get('/config', (c) => {
    return c.html(`
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>MongoDB 直连配置</title>
    <style>
      body { font-family: sans-serif; padding: 20px; }
      label { display: block; margin-top: 10px; font-weight: bold; }
      input, select { width: 100%; padding: 8px; margin: 5px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
      .btn { background: #3370ff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; width: 100%; margin-top: 20px; }
      .btn-secondary { background: #f3f3f3; color: #333; margin-top: 5px; }
    </style>
    </head>
    <body>
      <h3>🔌 MongoDB 视频评论选择</h3>
      <label>Connection String (URI)</label>
      <input type="text" id="uri" placeholder="mongodb+srv://..." />
      <label>Database</label>
      <input type="text" id="db" value="bilibili_monitor" />
      
      <div style="margin-top:15px; border-top:1px solid #eee; padding-top:10px;">
          <button class="btn btn-secondary" id="loadVideosBtn">🔄 加载视频列表</button>
          <label>选择视频</label>
          <select id="videoSelect">
            <option value="">请先加载视频列表...</option>
          </select>
      </div>

      <label>Collection (自动填充)</label>
      <input type="text" id="coll" value="comments" readonly />
      
      <button class="btn" id="saveBtn">保存并开始同步</button>

      <script type="module">
        import { bitable } from 'https://esm.sh/@lark-base-open/connector-api';
        
        async function loadVideos() {
            const uri = document.getElementById('uri').value.trim();
            const db = document.getElementById('db').value.trim();
            if(!uri) return alert("请先填写 URI");
            
            // Save to localStorage
            localStorage.setItem('mongo_uri', uri);
            
            const btn = document.getElementById('loadVideosBtn');
            btn.textContent = "加载中...";
            
            try {
                const res = await fetch('/get_videos', {
                    method: 'POST',
                    body: JSON.stringify({ uri, db })
                });
                const json = await res.json();
                if(json.code !== 0) throw new Error(json.msg);
                
                const select = document.getElementById('videoSelect');
                select.innerHTML = '<option value="">-- 请选择视频 --</option>';
                
                // Add "All Comments" option
                const allOpt = document.createElement('option');
                allOpt.value = 'comments';
                allOpt.textContent = '📂 所有评论 (旧数据)';
                select.appendChild(allOpt);
                
                // Add videos
                json.data.forEach(v => {
                    const opt = document.createElement('option');
                    opt.value = v.collection_name || 'comments_' + v.bvid;
                    opt.textContent = \`📺 \${v.title} (\${v.bvid}) - \${v.comment_count || 0}条\`;
                    select.appendChild(opt);
                });
                
                btn.textContent = "✅ 加载成功";
            } catch(e) {
                alert("加载失败: " + e.message);
                btn.textContent = "🔄 重试加载";
            }
        }
        
        // Auto-load URI from localStorage
        const savedUri = localStorage.getItem('mongo_uri');
        if (savedUri) document.getElementById('uri').value = savedUri;
        
        document.getElementById('loadVideosBtn').onclick = loadVideos;
        
        document.getElementById('videoSelect').onchange = (e) => {
            if(e.target.value) {
                document.getElementById('coll').value = e.target.value;
            }
        };

        document.getElementById('saveBtn').onclick = async () => {
          const config = {
            uri: document.getElementById('uri').value.trim(),
            db: document.getElementById('db').value.trim(),
            coll: document.getElementById('coll').value.trim()
          };
          if(!config.coll) return alert("请选择一个视频或填写 Collection");
          await bitable.saveConfigAndGoNext(config);
        }
      </script>
    </body>
    </html>
  `)
})

// 2. 数据处理：使用 MongoClient 直连
app.post('/records', async (c) => {
    const reqBody = await c.req.json();
    const params = JSON.parse(reqBody.params);
    const config = typeof params.datasourceConfig === 'string' ? JSON.parse(params.datasourceConfig) : params.datasourceConfig;

    const client = new MongoClient(config.uri, {
        autoEncryption: undefined,
        monitorCommands: false,
        connectTimeoutMS: 10000,
    } as any);
    try {
        await client.connect();
        const collection = client.db(config.db).collection(config.coll);

        // 一次性拉取所有数据（不分页），按评论时间升序（最旧在前）
        const docs = await collection.find({})
            .sort({ ctime: 1 })  // 按评论时间升序
            .limit(5000)
            .toArray();

        const records = docs.map(doc => ({
            primaryID: String(doc._id),
            data: {
                id: String(doc._id),
                user: doc.user || "",
                mid: doc.mid ? String(doc.mid) : "",
                sex: doc.sex || "保密",
                location: doc.location || "",
                content: doc.content || "",
                time: doc.ctime ? new Date(doc.ctime * 1000).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) : "",
                level: doc.level ? String(doc.level) : "0",
                likes: doc.likes ? String(doc.likes) : "0",
                rcount: doc.rcount ? String(doc.rcount) : "0",
                fans_medal: doc.fans_medal || ""
            }
        }));

        // 不分页，直接返回全部
        return c.json({
            code: 0,
            msg: "success",
            data: {
                hasMore: false,
                pageToken: "",
                records
            }
        });
    } catch (err: any) {
        return c.json({ code: 500, msg: "连接失败: " + err.message });
    } finally {
        await client.close();
    }
})

// 3. 表结构定义 - 需要从请求中获取配置来确定表名
app.post('/table_meta', async (c) => {
    const reqBody = await c.req.json();
    const params = JSON.parse(reqBody.params);
    const config = typeof params.datasourceConfig === 'string' ? JSON.parse(params.datasourceConfig) : params.datasourceConfig;

    // 尝试从 video_metadata 获取视频标题
    let tableName = "B站评论数据";
    if (config.uri && config.db && config.coll && config.coll.startsWith('comments_')) {
        const client = new MongoClient(config.uri, {
            autoEncryption: undefined,
            monitorCommands: false,
            connectTimeoutMS: 5000,
        } as any);
        try {
            await client.connect();
            const bvid = config.coll.replace('comments_', '');
            const metadata = await client.db(config.db).collection('video_metadata').findOne({ bvid });
            if (metadata && metadata.title) {
                tableName = metadata.title;
            }
        } catch (e) {
            // Fallback to default name
        } finally {
            await client.close();
        }
    }

    return c.json({
        code: 0, msg: "success",
        data: {
            tableName,
            fields: [
                { fieldID: "id", fieldName: "文档ID", fieldType: 1, isPrimary: true },
                { fieldID: "user", fieldName: "用户名", fieldType: 1 },
                { fieldID: "mid", fieldName: "用户UID", fieldType: 1 },
                { fieldID: "sex", fieldName: "性别", fieldType: 1 },
                { fieldID: "location", fieldName: "IP属地", fieldType: 1 },
                { fieldID: "content", fieldName: "评论内容", fieldType: 1 },
                { fieldID: "time", fieldName: "发布时间", fieldType: 1 },
                { fieldID: "level", fieldName: "等级", fieldType: 1 },
                { fieldID: "likes", fieldName: "点赞数", fieldType: 1 },
                { fieldID: "rcount", fieldName: "回复数", fieldType: 1 },
                { fieldID: "fans_medal", fieldName: "粉丝勋章", fieldType: 1 }
            ]
        }
    })
})

// 4. 元数据
app.get('/meta.json', (c) => {
    const origin = new URL(c.req.url).origin;
    return c.json({
        schemaVersion: 1, type: "data_connector",
        extraData: { dataSourceConfigUiUri: `${origin}/config` },
        protocol: {
            type: "http", httpProtocol: {
                uris: [
                    { type: "tableMeta", uri: "/table_meta" },
                    { type: "records", uri: "/records" }
                ]
            }
        }
    })
})

export default app