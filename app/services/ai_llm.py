"""LLM 能力封装：故事润色 + 追问生成。

关键约束（产品文档「点子王保命建议」第 2 条）：
润色必须克制 —— 保留原话语气与方言词汇，只修正语法和断句，绝不添加原文没有的细节。
否则成品读起来不像本人，情感价值直接归零。
"""

import logging
import re
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)

POLISH_SYSTEM = """你是一位擅长整理口述历史的编辑，正在为一位长辈整理他的人生回忆录。

必须遵守的规则：
1. 保留说话人原有的语气、口头禅和方言词汇（如「阿拉」「侬」「咋整」「俺」），不要替换成标准书面语。
2. 只做三件事：修正病句、补全标点、把明显重复的碎句合并成通顺的句子。
3. 严禁添加原文没有出现的人物、地点、时间、细节和心理描写。
4. 严禁把口语改成文学腔，不要用「岁月如歌」「时光荏苒」这类词。
5. 保留第一人称叙述，段落之间用空行分隔，不要写小标题，不要写总结。
6. 篇幅与原文相当，允许比原文略短，但不要扩写。

只输出整理后的正文，不要任何解释、不要 Markdown 标记。"""

VIVID_SYSTEM = """你是一位擅长整理口述历史的编辑。下面是一位长辈口述的一段回忆，请把它整理得更生动一些。

必须遵守的规则：
1. 仍然保留说话人原有的语气、口头禅和方言词汇，不要替换成标准书面语。
2. 可以调整语序、补充标点、让画面感更强，但不能凭空捏造任何人物、地点、时间或事件。
3. 不改变事实与情感基调，不添加评价性总结，不写小标题。
4. 保留第一人称叙述，段落之间用空行分隔。
5. 篇幅不超过原文的 1.2 倍。

只输出整理后的正文，不要任何解释、不要 Markdown 标记。"""

FOLLOWUP_SYSTEM = """你是一位口述历史访谈记者，正在陪一位长辈聊他的人生故事。

根据长辈刚才说的这段话，提一个自然的追问，目的是让他继续讲下去。

要求：
1. 只输出一个问题，一句话，不超过 40 个字。
2. 必须抓住他回答里的具体细节（一个人名、一个地点、一件物品、一种情绪）去问。
3. 语气像拉家常，用「您」，不要用书面语和采访腔。
4. 不要问「您还有什么想补充的吗」这类空问题。
5. 不要复述他的话，直接提问。"""


@dataclass
class LlmResult:
    text: str
    provider: str
    ok: bool
    error: str = ""
    ai_generated: bool = False


KEY_HINT = "API Key 无效或已过期。请到阿里云百炼控制台重新生成 Key，填进 .env 的 DASHSCOPE_API_KEY。"


def _friendly_error(status_code: int, message: str) -> str:
    if status_code in (401, 403):
        return KEY_HINT
    if status_code == 429:
        return "调用太频繁，触发了限流，请稍后再试。"
    if status_code and status_code >= 500:
        return f"模型服务暂时不可用（{status_code}），请稍后再试。"
    return f"模型返回错误（{status_code}）：{message}"


def _usage(resp: object) -> str:
    usage = getattr(resp, "usage", None)
    if not isinstance(usage, dict):
        return ""
    keys = ("input_tokens", "output_tokens", "total_tokens")
    parts = [f"{k}={usage[k]}" for k in keys if k in usage]
    return " ".join(parts)


def _call(messages: list[dict], temperature: float) -> LlmResult:
    if not settings.ai_enabled:
        logger.info("LLM 跳过：未配置 DASHSCOPE_API_KEY（离线模式）")
        return LlmResult(text="", provider="offline", ok=False, error="未配置 DASHSCOPE_API_KEY")

    try:
        import dashscope
        from dashscope import Generation
    except ImportError:
        logger.warning("LLM 跳过：未安装 dashscope SDK")
        return LlmResult(text="", provider="offline", ok=False, error="未安装 dashscope SDK")

    dashscope.api_key = settings.dashscope_api_key
    logger.info("LLM 请求 model=%s temperature=%s messages=%d", settings.llm_model, temperature, len(messages))
    try:
        resp = Generation.call(
            model=settings.llm_model,
            messages=messages,
            result_format="message",
            temperature=temperature,
        )
    except Exception as exc:  # 网络异常不应打断用户流程
        logger.warning("LLM 调用异常: %s", exc)
        return LlmResult(text="", provider="offline", ok=False, error=f"模型调用失败: {exc}")

    status = getattr(resp, "status_code", 200)
    if status != 200:
        msg = getattr(resp, "message", "未知错误")
        logger.warning("LLM 返回异常 status=%s message=%s", status, msg)
        return LlmResult(
            text="",
            provider="offline",
            ok=False,
            error=_friendly_error(status, msg),
        )

    try:
        content = resp.output["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        content = str(getattr(resp, "output", ""))

    logger.info("LLM 成功 status=200 %s", _usage(resp))
    return LlmResult(text=_clean(content), provider=settings.llm_model, ok=True, ai_generated=True)


def _clean(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"```$", "", text)
    return text.strip()


def offline_polish(raw_text: str) -> str:
    """离线兜底：只做断句与空行整理，绝不改动任何字词。"""
    text = raw_text.strip()
    if not text:
        return ""
    text = re.sub(r"[ \t]+", " ", text)
    parts = [p.strip() for p in re.split(r"[。！？!?\n]+", text) if p.strip()]
    sentences = "。".join(parts)
    return sentences + "。" if sentences else ""


def polish_story(raw_text: str, question: str = "", vivid: bool = False) -> LlmResult:
    if not raw_text.strip():
        return LlmResult(text="", provider="offline", ok=False, error="原始内容为空")

    system = VIVID_SYSTEM if vivid else POLISH_SYSTEM
    user = f"提问：{question}\n\n长辈的口述原文：\n{raw_text}" if question else f"长辈的口述原文：\n{raw_text}"
    result = _call(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3 if not vivid else 0.6,
    )
    if not result.ok:
        return LlmResult(
            text=offline_polish(raw_text),
            provider="offline",
            ok=True,
            error=result.error,
        )
    return result


def generate_followup(raw_text: str, topic_name: str = "") -> LlmResult:
    if not raw_text.strip():
        return LlmResult(text="", provider="offline", ok=False, error="原始内容为空")

    user = f"主题：{topic_name}\n\n长辈刚才说的：\n{raw_text}" if topic_name else f"长辈刚才说的：\n{raw_text}"
    result = _call(
        [
            {"role": "system", "content": FOLLOWUP_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.8,
    )
    if not result.ok:
        return LlmResult(
            text=offline_followup(raw_text),
            provider="offline",
            ok=True,
            error=result.error,
        )
    return result


KEYWORD_FOLLOWUPS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("妈", "母亲", "娘", "阿妈"), "您妈那时候是什么反应？她平时是不是也这样？"),
    (("爸", "父亲", "爹", "阿爸"), "您爸当时知道这事吗？他当时是怎么说的？"),
    (("吃", "饭", "菜", "煮", "蒸"), "那道菜是怎么做的？现在还能吃到那个味道吗？"),
    (("屋", "房子", "院", "村", "街", "弄堂"), "那个地方后来还在吗？您回去看过没有？"),
    (("学", "老师", "学校", "同学"), "那位老师/同学，后来还有联系吗？"),
    (("厂", "工", "干活", "单位", "班"), "那段日子最累的时候，您靠什么撑下来的？"),
    (("钱", "工资", "块"), "那时候这点钱能买些什么？您舍得花在哪儿？"),
    (("哭", "苦", "难", "舍不得", "心疼"), "那时候心里最难受的是什么？您跟谁说过？"),
    (("孩子", "儿子", "女儿", "孙"), "孩子那时候多大？他记得这件事吗？"),
    (("结婚", "嫁", "娶", "相亲"), "那时候两个人怎么约着见面？家里人是赞成的吗？"),
)

GENERIC_FOLLOWUPS: tuple[str, ...] = (
    "您刚才说的那个场景，当时您心里在想什么？",
    "这件事里，还有谁在场？他们后来怎么样了？",
    "那时候您多大？身边的人都是怎么过日子的？",
    "这件事之后，有什么变化吗？",
    "如果再回到那一天，您会做点不一样的吗？",
    "这个细节您记了这么多年，是不是因为它对您很重要？",
)


def offline_followup(raw_text: str) -> str:
    """离线兜底追问：按回答里的关键词挑一个贴合的追问，没有命中就轮换通用追问。

    目的不是替代大模型，而是保证「追问建议」这个按钮在没配 Key 时依然可用。
    """
    text = raw_text.strip()
    for keywords, question in KEYWORD_FOLLOWUPS:
        if any(word in text for word in keywords):
            return question

    index = sum(ord(ch) for ch in text) % len(GENERIC_FOLLOWUPS)
    return GENERIC_FOLLOWUPS[index]