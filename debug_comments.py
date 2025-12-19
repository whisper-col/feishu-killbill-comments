"""
Debug script to inspect get_comments_lazy response structure
"""
import asyncio
import json
from bilibili_api import video, comment, Credential

# Test video with many comments
BVID = "BV1xZ421Z7hs"  # Popular video

# You need to fill these from your cookie
SESSDATA = ""
BUVID3 = ""
BILI_JCT = ""

async def main():
    credential = Credential(sessdata=SESSDATA, buvid3=BUVID3, bili_jct=BILI_JCT)
    
    # Get video info
    v = video.Video(bvid=BVID, credential=credential)
    info = await v.get_info()
    oid = info['aid']
    print(f"Video: {info['title']}")
    print(f"OID: {oid}")
    print(f"Comment count (from stats): {info['stat']['reply']}")
    print("=" * 50)
    
    # Try get_comments_lazy
    print("\n=== Testing get_comments_lazy ===")
    offset = ""
    for i in range(5):  # Try 5 requests
        data = await comment.get_comments_lazy(
            oid=oid,
            type_=comment.CommentResourceType.VIDEO,
            order=comment.OrderType.LIKE,
            offset=offset,
            credential=credential
        )
        
        replies = data.get('replies') or []
        cursor = data.get('cursor', {})
        
        print(f"\n--- Request {i+1} ---")
        print(f"Replies count: {len(replies)}")
        print(f"Cursor: {json.dumps(cursor, ensure_ascii=False, indent=2)}")
        
        if not replies:
            print("No more replies!")
            break
            
        # Get next offset
        pagination = cursor.get('pagination_reply', {})
        next_offset = pagination.get('next_offset', '')
        is_end = cursor.get('is_end', False)
        
        print(f"is_end: {is_end}")
        print(f"next_offset: {next_offset[:100] if next_offset else 'EMPTY'}...")
        
        if is_end or not next_offset:
            print("Reached end!")
            break
            
        offset = next_offset
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(main())
