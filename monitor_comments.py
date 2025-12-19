import asyncio
import datetime
from bilibili_api import video, comment, Credential, sync

# ================= 配置区域 =================
# 目标视频的 BV 号
TARGET_BVID = "BV1xx411c7mD" 

# 你的 SESSDATA (推荐填写，否则容易被限流或签名失败)
# 获取方式：浏览器登录B站 -> F12 -> Application -> Cookies -> SESSDATA
SESSDATA = "你的_SESSDATA_填在这里"
BUVID3 = "" # 选填，如果报错可尝试填入 buvid3
JCT = ""    # 选填，即 bili_jct

# 设置凭证
credential = Credential(sessdata=SESSDATA, buvid3=BUVID3, bili_jct=JCT)

# 轮询间隔 (秒)，建议不要低于 3-5 秒
SLEEP_INTERVAL = 5
# ===========================================

async def fetch_new_comments(oid, last_rpid):
    """
    获取最新一页评论，并筛选出比 last_rpid 新的评论
    """
    try:
        # type_=1 代表视频评论
        # sort=0 代表按时间倒序（最新评论在最前面）
        data = await comment.get_comments(
            oid=oid, 
            type_=comment.CommentResourceType.VIDEO, 
            order=comment.OrderType.TIME, 
            page_index=1,
            credential=credential
        )
        
        replies = data.get('replies', [])
        
        if not replies:
            return [], last_rpid

        new_comments = []
        # 遍历返回的评论列表
        for r in replies:
            current_rpid = r['rpid']
            
            # 如果当前评论ID 比 上次记录的ID 大，说明是新的
            if current_rpid > last_rpid:
                # 提取我们需要的信息
                info = {
                    'rpid': r['rpid'],
                    'user': r['member']['uname'],         # 用户名
                    'mid': r['member']['mid'],            # 用户ID
                    'content': r['content']['message'],   # 评论内容
                    'time': datetime.datetime.fromtimestamp(r['ctime']), # 发送时间
                    'level': r['member']['level_info']['current_level']  # 用户等级
                }
                new_comments.append(info)
            else:
                # 因为是按时间倒序，一旦遇到旧的，后面的肯定都旧，直接跳出
                break
        
        # 更新最新的 last_rpid (如果发现了新评论，取最新的那个；否则保持不变)
        if new_comments:
            # 列表第一个是最新的，所以取 new_comments[0]['rpid'] 比较稳妥
            # 但为了逻辑严谨，我们取这一批里最大的 rpid
            max_id = max([c['rpid'] for c in new_comments])
            last_rpid = max(last_rpid, max_id)
            
        return new_comments, last_rpid

    except Exception as e:
        print(f"请求出错: {e}")
        return [], last_rpid

async def main():
    print(f"正在初始化视频信息: {TARGET_BVID} ...")
    
    # 1. 获取视频基础信息 (主要是为了拿到 oid/aid)
    v = video.Video(bvid=TARGET_BVID, credential=credential)
    try:
        info = await v.get_info()
        oid = info['aid']
        title = info['title']
    except Exception as e:
        print(f"获取视频信息失败: {e}")
        print("请检查网络或BV号是否正确。如果提示wbi签名错误，请填写SESSDATA。")
        return

    print(f"目标视频: {title}")
    print(f"视频OID: {oid}")
    print("开始监听评论区 (按 Ctrl+C 停止)...\n")

    # 初始化 last_rpid
    # 第一次运行，为了避免把历史评论全打印出来，我们先抓一次，只记录最新的ID，不打印内容
    # 如果你想把当前第一页的都打印，可以把这个逻辑改一下
    print("正在同步当前最新状态...")
    try:
        init_data = await comment.get_comments(oid, comment.CommentResourceType.VIDEO, page_index=1, order=comment.OrderType.TIME, credential=credential)
        if init_data['replies']:
            last_rpid = init_data['replies'][0]['rpid']
        else:
            last_rpid = 0
    except Exception as e:
        print(f"初始化失败，请检查网络或 Cookie: {e}")
        return

    print(f"初始化完成，当前最新评论ID: {last_rpid}")
    print("-" * 30)

    # 2. 开启死循环轮询
    while True:
        new_items, last_rpid = await fetch_new_comments(oid, last_rpid)
        
        # 注意：API返回是倒序（新->旧），为了打印习惯，我们反转一下（旧->新）显示
        for item in reversed(new_items):
            print(f"[{item['time'].strftime('%H:%M:%S')}] LV{item['level']} {item['user']}: {item['content']}")
            
        await asyncio.sleep(SLEEP_INTERVAL)

if __name__ == '__main__':
    sync(main())
