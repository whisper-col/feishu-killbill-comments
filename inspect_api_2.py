from bilibili_api import comment
import inspect

keys = list(inspect.signature(comment.get_comments).parameters.keys())
print("VALID_ARGS:", keys)
