"""快速自检：确认 DASHSCOPE_API_KEY 是否可用，以及语音/文本链路是否通。

用法：
    .venv\\Scripts\\python.exe scripts\\check_ai.py
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402


def check_key() -> bool:
    key = settings.dashscope_api_key.strip()
    print(f"Key 来源：{'已配置' if key else '未配置'}")
    if not key:
        print("  结论：处于离线演示模式（不调用任何 AI 接口）")
        return False

    print(f"  Key 长度：{len(key)}，前缀：{key[:6]}…")
    body = json.dumps(
        {
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": "只回复两个字：正常"}],
            "max_tokens": 16,
        }
    ).encode()
    req = urllib.request.Request(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        data=body,
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + key)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read())
        content = payload["choices"][0]["message"]["content"]
        print(f"  调用成功，模型回复：{content}")
        return True
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:200]
        print(f"  调用失败：HTTP {exc.code} {detail}")
        if exc.code in (401, 403):
            print("  结论：Key 无效或已过期，请到阿里云百炼控制台重新生成。")
        return False
    except Exception as exc:
        print(f"  调用失败：{type(exc).__name__} {exc}")
        return False


if __name__ == "__main__":
    print(f"模型：{settings.llm_model}    语音识别：{settings.asr_model}")
    ok = check_key()
    sys.exit(0 if ok else 1)