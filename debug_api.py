"""
Debug script to test comment API directly
"""
import asyncio
from bilibili_api import video, comment, Credential

# Test BVID
BVID = "BV13FmRBZEXo"

# Fill in your credentials here for testing
SESSDATA = ""  # You need to fill this
BUVID3 = ""
BILI_JCT = ""

async def main():
    credential = Credential(sessdata=SESSDATA, buvid3=BUVID3, bili_jct=BILI_JCT)
    
    # Get video info first
    v = video.Video(bvid=BVID, credential=credential)
    info = await v.get_info()
    oid = info['aid']
    print(f"Video: {info['title']}")
    print(f"OID (aid): {oid}")
    print(f"Stats - Views: {info['stat']['view']}, Comments: {info['stat']['reply']}")
    print()
    
    # Try to get comments
    print("Fetching comments...")
    try:
        data = await comment.get_comments(
            oid=oid, 
            type_=comment.CommentResourceType.VIDEO, 
            order=comment.OrderType.TIME,
            page_index=1,
            credential=credential
        )
        
        print(f"Raw response keys: {data.keys()}")
        
        replies = data.get('replies')
        print(f"Replies type: {type(replies)}")
        print(f"Replies value: {replies}")
        
        if replies:
            print(f"Found {len(replies)} comments!")
            for r in replies[:3]:
                print(f"  - {r['member']['uname']}: {r['content']['message'][:50]}...")
        else:
            print("No replies found!")
            
        # Print full response for debugging
        print("\nFull response (truncated):")
        import json
        print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
