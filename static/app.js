const bvidInput = document.getElementById('bvid');
const sessdataInput = document.getElementById('sessdata');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusText = document.getElementById('statusText');
const targetTitle = document.getElementById('targetTitle');
const monitorBadge = document.getElementById('monitorBadge');
const commentList = document.getElementById('commentList');

let ws = null;
let isRunning = false;

// Initialize WebSocket
function initWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws`);

    ws.onopen = () => {
        console.log("Connected to WS");
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    };

    ws.onclose = () => {
        statusText.textContent = "连接断开，尝试重连...";
        setTimeout(initWebSocket, 3000);
    };
}

function handleMessage(msg) {
    switch (msg.type) {
        case 'init':
            updateRunningState(msg.running);
            if (msg.title) targetTitle.textContent = msg.title;
            break;
        case 'status':
            statusText.textContent = msg.msg;
            if (msg.level === 'error') {
                statusText.style.color = '#ff4757';
                updateRunningState(false);
            } else if (msg.level === 'success') {
                statusText.style.color = '#2ecc71';
            } else {
                statusText.style.color = '#9499a0';
            }
            break;
        case 'new_comments':
            renderComments(msg.data);
            break;
    }
}

function updateRunningState(running) {
    isRunning = running;
    if (running) {
        startBtn.disabled = true;
        stopBtn.disabled = false;
        bvidInput.disabled = true;
        sessdataInput.disabled = true;
        monitorBadge.textContent = "MONITORING";
        monitorBadge.classList.add('active');
        // Clear empty state if it exists
        if (document.querySelector('.empty-state')) {
            commentList.innerHTML = '';
        }
    } else {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        bvidInput.disabled = false;
        sessdataInput.disabled = false;
        monitorBadge.textContent = "OFFLINE";
        monitorBadge.classList.remove('active');
    }
}

function renderComments(comments) {
    // Reverse to show newest on top if prepending
    // Data comes in chronological (oldest -> newest), we want to prepend newest first.
    // So we iterate the list as is and prepend each one, effectively reversing them in the UI stack.
    comments.forEach(c => {
        const card = document.createElement('div');
        card.className = 'comment-card';
        card.innerHTML = `
            <img src="${c.avatar}" class="avatar" loading="lazy">
            <div class="content-wrapper">
                <div class="header">
                    <span class="username">${escapeHtml(c.user)}</span>
                    <span class="level">LV${c.level}</span>
                    <span class="time">${c.time}</span>
                </div>
                <div class="message">${escapeHtml(c.content)}</div>
            </div>
        `;
        commentList.prepend(card);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Cookie Handling
const uploadBtn = document.getElementById('uploadBtn');
const cookieFile = document.getElementById('cookieFile');
const cookieStatus = document.getElementById('cookieStatus');

uploadBtn.addEventListener('click', () => cookieFile.click());

cookieFile.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
        try {
            const content = event.target.result;
            const json = JSON.parse(content);
            let cookies = {};

            // Handle EditThisCookie array format
            if (Array.isArray(json)) {
                json.forEach(c => cookies[c.name] = c.value);
            } else {
                cookies = json;
            }

            if (cookies.SESSDATA) {
                // Fill hidden inputs
                document.getElementById('sessdata').value = cookies.SESSDATA;
                document.getElementById('buvid3').value = cookies.buvid3 || "";
                document.getElementById('bili_jct').value = cookies.bili_jct || "";

                cookieStatus.style.display = 'block';
                cookieStatus.textContent = `✓ 已解析: SESSDATA, ${cookies.bili_jct ? 'bili_jct' : ''}`;
                uploadBtn.textContent = "✅ 已加载 " + file.name;
                uploadBtn.style.background = "#2ecc71";
            } else {
                alert("错误: JSON 中未找到 SESSDATA 字段");
            }
        } catch (err) {
            alert("JSON 解析失败: " + err);
        }
    };
    reader.readAsText(file);
});

// API Calls
startBtn.addEventListener('click', async () => {
    const sessdata = document.getElementById('sessdata').value;
    const buvid3 = document.getElementById('buvid3').value;
    const bili_jct = document.getElementById('bili_jct').value;

    if (!sessdata) {
        alert("请先导入包含 SESSDATA 的 Cookie JSON 文件！");
        return;
    }

    statusText.textContent = "正在启动...";
    try {
        const res = await fetch('/api/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                bvid: bvidInput.value,
                sessdata: sessdata,
                buvid3: buvid3,
                bili_jct: bili_jct
            })
        });
        const data = await res.json();
        if (data.status === 'started') {
            updateRunningState(true);
        } else if (data.status === 'already_running') {
            alert("监控已在运行中");
        }
    } catch (e) {
        statusText.textContent = "启动失败: " + e;
    }
});

stopBtn.addEventListener('click', async () => {
    try {
        await fetch('/api/stop', { method: 'POST' });
        updateRunningState(false);
        statusText.textContent = "已手动停止";
    } catch (e) {
        console.error(e);
    }
});

// Start
initWebSocket();
