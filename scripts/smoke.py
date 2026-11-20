import json
import re
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as resp:
        return resp.status, resp.read()


def post_form(path, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(BASE + path, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read(), resp.headers
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers


def post_json(path, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


status, body = get("/healthz")
print("healthz", status, body.decode())

status, body, headers = post_form(
    "/create",
    {
        "title": "外婆的一生",
        "narrator_name": "李秀兰",
        "interviewer_name": "小外孙",
        "dedication": "献给我们家最会讲故事的人",
    },
)
token = headers["location"].rstrip("/").split("/")[-1]
print("create", status, "token=", token)

status, body = get(f"/project/{token}")
print("project page", status, "len=", len(body))

status, data = post_json(f"/api/projects/{token}/question?topic=childhood", None)
print("next question", status, data.get("question", {}).get("id"))

status, body, headers = post_form(
    f"/api/projects/{token}/stories",
    {
        "topic": "childhood",
        "question": "您小时候住的那个地方，是什么样子的？",
        "text": "那时候我们住在江边，屋前头有棵老樟树，夏天就在树荫底下乘凉，蚊子多得很，俺妈就拿蒲扇给我们扇风",
    },
)
print("create story", status, json.loads(body)["story"]["polished_text"][:60])

status, body = get(f"/interview/{token}")
print("interview page", status, "len=", len(body))

status, body = get(f"/book/{token}")
text = body.decode()
print("book page", status, "has_signature=", "献给 李秀兰" in text)

status, body = get(f"/book/{token}/pdf")
if status == 200:
    print("pdf", status, "bytes=", len(body), "header=", body[:8])
else:
    print("pdf FAILED", status, body.decode()[:400])