"""AI 访谈提问引擎：主题模块 + 问题库 + 选题逻辑。

设计原则（来自产品文档）：
1. 破冰问题必须「有画面感、能一句话开口」，不能让长辈卡壳；
2. 追问要贴着回答里的细节走，而不是机械念稿；
3. 每个主题留一个「情感钩子」，用来触发最深的那层回忆。
"""

from dataclasses import dataclass

ICE = "ice"
PROBE = "probe"
HOOK = "hook"

KIND_LABELS = {ICE: "破冰", PROBE: "追问", HOOK: "情感钩子"}


@dataclass(frozen=True)
class Question:
    id: str
    topic: str
    kind: str
    text: str


@dataclass(frozen=True)
class Topic:
    key: str
    name: str
    subtitle: str
    emoji: str


TOPICS: tuple[Topic, ...] = (
    Topic("childhood", "童年与家乡", "最早的记忆，往往最清楚", "🏡"),
    Topic("youth", "青春与求学", "那些年，你是怎么走出去的", "🎒"),
    Topic("work", "工作与奋斗", "一辈子做过的那些事", "🔧"),
    Topic("family", "爱情与家庭", "怎么遇见那个人，怎么成了家", "💞"),
    Topic("wisdom", "人生感悟", "想留给子孙的话", "🕯️"),
)

TOPIC_MAP = {t.key: t for t in TOPICS}

QUESTIONS: tuple[Question, ...] = (
    # 童年与家乡
    Question("childhood-1", "childhood", ICE, "您小时候住的那个地方，是什么样子的？房子是瓦房还是楼房，门口有什么？"),
    Question("childhood-2", "childhood", ICE, "小时候家里谁做饭？您最爱吃的那道菜，是怎么做的？"),
    Question("childhood-3", "childhood", ICE, "过年的那一天，您家最热闹的是哪个时刻？"),
    Question("childhood-4", "childhood", PROBE, "您刚才提到的那个场景，能再多讲讲当时的天气、声音和气味吗？"),
    Question("childhood-5", "childhood", PROBE, "那时候您最要好的玩伴是谁？你们常在一起做什么？"),
    Question("childhood-6", "childhood", HOOK, "如果能让您回到小时候的某一天，您最想回到哪一天？为什么是那天？"),
    # 青春与求学
    Question("youth-1", "youth", ICE, "您第一次离开家去上学，是几岁？那天是谁送您去的？"),
    Question("youth-2", "youth", ICE, "上学的时候，您书包里都装些什么？有没有一样东西一直留着？"),
    Question("youth-3", "youth", ICE, "那时候您最崇拜的人是谁？"),
    Question("youth-4", "youth", PROBE, "您说到的那位老师/同学，后来还有联系吗？他给您留下的最深印象是什么？"),
    Question("youth-5", "youth", PROBE, "当时有没有一件事，让您第一次觉得自己长大了？"),
    Question("youth-6", "youth", HOOK, "那时候您心里有没有一个特别想去的地方？后来去了吗？"),
    # 工作与奋斗
    Question("work-1", "work", ICE, "您参加的第一份工作是什么？第一天上班是什么情形？"),
    Question("work-2", "work", ICE, "您干过的活儿里，最辛苦的是哪一样？"),
    Question("work-3", "work", ICE, "第一笔工资有多少？您花在了哪里？"),
    Question("work-4", "work", PROBE, "您提到的那件事，当时最难的一关是什么？您是怎么扛过去的？"),
    Question("work-5", "work", PROBE, "那几年里，有没有一位同事或领导，改变了您的想法？"),
    Question("work-6", "work", HOOK, "您这一辈子做过的最骄傲的一件事，是哪一件？"),
    # 爱情与家庭
    Question("family-1", "family", ICE, "您第一次见到他/她，是在什么地方？那天他/她穿的什么颜色的衣服？"),
    Question("family-2", "family", ICE, "那时候两个人怎么约着见面？有没有写过信？"),
    Question("family-3", "family", ICE, "成家那天，家里摆了什么样的场面？"),
    Question("family-4", "family", PROBE, "您说到的那件小事，为什么您记了这么多年？"),
    Question("family-5", "family", PROBE, "孩子出生那天，您在做什么？第一眼看到孩子时心里想的是什么？"),
    Question("family-6", "family", HOOK, "这些年里，您最想对家里那位说、却一直没说出口的一句话是什么？"),
    # 人生感悟
    Question("wisdom-1", "wisdom", ICE, "如果用一个词形容您这一生，您会选哪个词？"),
    Question("wisdom-2", "wisdom", ICE, "您觉得自己身上最像父母的地方是什么？"),
    Question("wisdom-3", "wisdom", ICE, "这些年，您最常说给别人听的一句道理是什么？"),
    Question("wisdom-4", "wisdom", PROBE, "您提到的那段经历，现在回头看，它教会了您什么？"),
    Question("wisdom-5", "wisdom", PROBE, "有没有一件事，您当年做了另一个选择，今天会不一样？"),
    Question("wisdom-6", "wisdom", HOOK, "如果子孙只能记住您说的一段话，您希望是哪些话？"),
)

QUESTION_MAP = {q.id: q for q in QUESTIONS}

TOPIC_ORDER = [t.key for t in TOPICS]


def questions_of(topic: str, kind: str | None = None) -> list[Question]:
    items = [q for q in QUESTIONS if q.topic == topic]
    if kind:
        items = [q for q in items if q.kind == kind]
    return items


def topic_progress(answered_topics: list[str]) -> dict[str, int]:
    return {t: answered_topics.count(t) for t in TOPIC_ORDER}


def pick_next_question(topic: str, answered_ids: list[str]) -> Question | None:
    """同一主题内按「破冰 → 追问 → 情感钩子」顺序推进，答过的不再问。"""
    for q in questions_of(topic):
        if q.id not in answered_ids:
            return q
    return None


def suggest_topic(answered_topics: list[str]) -> str:
    """优先选答得最少的主题，让整本书的结构不至于偏科。"""
    counts = topic_progress(answered_topics)
    return min(TOPIC_ORDER, key=lambda t: (counts[t], TOPIC_ORDER.index(t)))