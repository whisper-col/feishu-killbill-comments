from bilibili_api import comment

print(f"Type: {type(comment.OrderType.TIME)}")
print(f"Value: {comment.OrderType.TIME}")
try:
    print(f"Attr value: {comment.OrderType.TIME.value}")
except Exception as e:
    print(f"Error accessing .value: {e}")
