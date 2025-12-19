from bilibili_api import comment
import inspect

print(f"ResourceType Type: {type(comment.CommentResourceType.VIDEO)}")
try:
    print(f"ResourceType Value: {comment.CommentResourceType.VIDEO.value}")
except:
    print("ResourceType has no value attr")

print(f"OrderType Type: {type(comment.OrderType.TIME)}")
try:
    print(f"OrderType Value: {comment.OrderType.TIME.value}")
except:
    print("OrderType has no value attr")
