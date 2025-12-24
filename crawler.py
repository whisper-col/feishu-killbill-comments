"""
Bilibili 评论定时爬虫脚本
用于 GitHub Actions 定时任务

环境变量:
- BVID: 视频 BV 号
- COOKIES_JSON: Cookie 配置 JSON 字符串
- MONGO_URI: MongoDB 连接字符串
"""

import asyncio
import datetime
import random
import itertools
import json
import os
from typing import List, Optional

from bilibili_api import video, comment, Credential
from bilibili_api.exceptions import ResponseCodeException, ApiException
from pymongo import MongoClient


# ==================== Configuration ====================
def get_config():
    """从环境变量读取配置"""
    bvid = os.environ.get("BVID", "")
    cookies_json = os.environ.get("COOKIES_JSON", "[]")
    mongo_uri = os.environ.get("MONGO_URI", "")
    
    if not bvid:
        raise ValueError("BVID 环境变量未设置")
    if not mongo_uri:
        raise ValueError("MONGO_URI 环境变量未设置")
    
    try:
        cookies = json.loads(cookies_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"COOKIES_JSON 解析失败: {e}")
    
    if not cookies:
        raise ValueError("COOKIES_JSON 为空，请配置至少一个账号")
    
    return {
        "bvid": bvid,
        "cookies": cookies,
        "mongo_uri": mongo_uri
    }


# ==================== Credential Pool ====================
class CredentialPool:
    """凭证池管理类：处理多账号轮询和重试"""
    
    def __init__(self, configs: List[dict]):
        self.credentials = []
        for cfg in configs:
            self.credentials.append(
                Credential(
                    sessdata=cfg.get("sessdata", ""),
                    buvid3=cfg.get("buvid3", ""),
                    bili_jct=cfg.get("bili_jct", "")
                )
            )
        self.iterator = itertools.cycle(self.credentials)
        self.total = len(self.credentials)
        print(f"✓ 已加载 {self.total} 个账号")

    def get_next(self) -> Credential:
        if not self.credentials:
            raise Exception("No credentials configured")
        return next(self.iterator)

    async def execute_with_retry(self, func, *args, **kwargs):
        """执行 API 函数，失败则切换账号重试"""
        last_error = None
        for _ in range(self.total):
            cred = self.get_next()
            try:
                kwargs['credential'] = cred
                return await func(*args, **kwargs)
            except (ResponseCodeException, ApiException) as e:
                print(f"  ⚠ API 请求失败: {e}，切换账号重试...")
                last_error = e
                await asyncio.sleep(0.5)
            except Exception as e:
                raise e
        
        print("✗ 所有账号均失败")
        if last_error:
            raise last_error


# ==================== MongoDB ====================
def save_comments_to_mongodb(mongo_db, comments_data: list, bvid: str, oid: int, title: str = ""):
    """保存评论到 MongoDB"""
    if not comments_data:
        return 0
    
    coll_name = f"comments_{bvid}"
    collection = mongo_db[coll_name]
    collection.create_index("rpid", unique=True)
    
    saved_count = 0
    for c in comments_data:
        try:
            location = ""
            if 'reply_control' in c and c['reply_control']:
                location = c['reply_control'].get('location', '')
            
            fans_medal = ""
            fans_detail = c['member'].get('fans_detail')
            if fans_detail:
                fans_medal = fans_detail.get('medal_name', '')
            
            doc = {
                "rpid": c['rpid'],
                "oid": oid,
                "bvid": bvid,
                "user": c['member']['uname'],
                "mid": c['member']['mid'],
                "content": c['content']['message'],
                "ctime": c['ctime'],
                "sex": c['member'].get('sex', '保密'),
                "location": location,
                "level": c['member']['level_info']['current_level'],
                "likes": c.get('like', 0),
                "rcount": c.get('rcount', 0),
                "fans_medal": fans_medal,
                "parent": c.get('parent', 0),
                "root": c.get('root', 0),
                "fetched_at": datetime.datetime.utcnow()
            }
            collection.update_one({"rpid": c['rpid']}, {"$set": doc}, upsert=True)
            saved_count += 1
        except Exception as e:
            continue
    
    # 更新视频元数据
    try:
        metadata_coll = mongo_db["video_metadata"]
        metadata_coll.update_one(
            {"bvid": bvid},
            {"$set": {
                "bvid": bvid,
                "oid": oid,
                "title": title,
                "last_updated": datetime.datetime.utcnow(),
                "comment_count": collection.count_documents({}),
                "collection_name": coll_name
            }},
            upsert=True
        )
    except Exception:
        pass
    
    return saved_count


# ==================== Main Crawler ====================
async def crawl_comments(bvid: str, pool: CredentialPool, mongo_db):
    """主爬虫逻辑"""
    print(f"\n📺 开始抓取视频: {bvid}")
    
    # 1. 获取视频信息
    async def get_video_info(credential):
        v = video.Video(bvid=bvid, credential=credential)
        return await v.get_info()

    try:
        info = await pool.execute_with_retry(get_video_info)
        oid = info['aid']
        title = info['title']
        print(f"✓ 视频信息: {title} (OID={oid})")
    except Exception as e:
        print(f"✗ 获取视频信息失败: {e}")
        return
    
    # 2. 抓取主评论
    all_replies = []
    page = 1
    max_pages = 100
    
    print("\n📥 正在抓取主评论...")
    while page <= max_pages:
        try:
            page_data = await pool.execute_with_retry(
                comment.get_comments,
                oid=oid,
                type_=comment.CommentResourceType.VIDEO,
                order=comment.OrderType.LIKE,
                page_index=page
            )
            
            replies = page_data.get('replies') or []
            page_info = page_data.get('page', {})
            total_count = page_info.get('count', 0)
            
            if not replies:
                break
            
            all_replies.extend(replies)
            print(f"  第 {page} 页: {len(replies)} 条 | 累计: {len(all_replies)}/{total_count}")
            
            if len(all_replies) >= total_count:
                break
            
            page += 1
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
        except Exception as e:
            print(f"  ⚠ 第 {page} 页抓取失败: {e}")
            break
    
    # 3. 抓取子评论
    print("\n📥 正在抓取子评论...")
    sub_replies_count = 0
    
    for idx, top_comment in enumerate(all_replies[:]):
        rcount = top_comment.get('rcount', 0)
        if rcount > 0:
            sub_page = 1
            while True:
                try:
                    async def fetch_sub(credential, oid, rpid, page_idx):
                        c = comment.Comment(
                            oid=oid,
                            type_=comment.CommentResourceType.VIDEO,
                            rpid=rpid,
                            credential=credential
                        )
                        return await c.get_sub_comments(page_index=page_idx, page_size=20)

                    sub_data = await pool.execute_with_retry(
                        fetch_sub,
                        oid=oid,
                        rpid=top_comment['rpid'],
                        page_idx=sub_page
                    )
                    
                    sub_list = sub_data.get('replies') or []
                    if not sub_list:
                        break
                    
                    all_replies.extend(sub_list)
                    sub_replies_count += len(sub_list)
                    
                    if len(sub_list) < 20:
                        break
                    sub_page += 1
                    await asyncio.sleep(0.1)
                except Exception as e:
                    break
    
    print(f"  子评论: {sub_replies_count} 条")
    
    # 4. 保存到 MongoDB
    print(f"\n💾 保存到 MongoDB...")
    saved = save_comments_to_mongodb(mongo_db, all_replies, bvid, oid, title)
    print(f"✓ 已保存 {saved} 条评论")
    
    return saved


async def main():
    print("=" * 50)
    print("🚀 Bilibili 评论定时爬虫")
    print(f"⏰ 运行时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 读取配置
    try:
        config = get_config()
    except ValueError as e:
        print(f"✗ 配置错误: {e}")
        return
    
    # 连接 MongoDB
    print("\n📦 连接 MongoDB...")
    try:
        mongo_client = MongoClient(config["mongo_uri"])
        mongo_db = mongo_client["bilibili_monitor"]
        # 测试连接
        mongo_client.admin.command('ping')
        print("✓ MongoDB 连接成功")
    except Exception as e:
        print(f"✗ MongoDB 连接失败: {e}")
        return
    
    # 初始化凭证池
    pool = CredentialPool(config["cookies"])
    
    # 执行爬虫
    await crawl_comments(config["bvid"], pool, mongo_db)
    
    print("\n" + "=" * 50)
    print("✅ 爬虫任务完成")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
