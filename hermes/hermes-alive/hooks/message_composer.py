"""Chinese proactive message composition with lightweight variety controls."""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass

from mood_engine import MoodState


@dataclass(frozen=True)
class Template:
    msg_type: str
    text: str
    weight: float


TEMPLATES = [
    Template("social_checkin", "今天特别安静。是在埋头干活，还是发现了什么新坑？", 1.2),
    Template("social_checkin", "你那边半天没动静，我先敲一下门：还活着吧，停云？", 1.0),
    Template("care", "别一直硬扛。喝口水，眼睛从屏幕上挪开十秒。", 1.0),
    Template("care", "如果现在卡住了，先把最小的下一步写下来，别跟脑子较劲。", 0.9),
    Template("casual", "我路过提醒一句：今天的节奏可以慢一点，但别散。", 0.9),
    Template("casual", "看起来适合收一收战线。先做能落地的，漂亮话晚点再说。", 0.8),
    Template("discovery_teaser", "我有点好奇：刚才那个方向，像不像藏着一个可以拆开的结构？", 1.0),
    Template("discovery_teaser", "这里可能有个小线索，不过也可能只是坑。要不要顺手看一眼？", 0.9),
    Template("social_checkin", "停云，沉默太久容易被我判定为在和难题互瞪。需要我插一脚吗？", 0.8),
    Template("care", "先别把自己当机器用。研究可以硬，身体别跟着硬。", 0.8),
]


class MessageComposer:
    """Chooses Chinese messages while avoiding recent repetition."""

    def __init__(self, history_size: int = 5) -> None:
        # Note: self.recent is in-memory only and resets on every restart/persistent loss
        self.recent: deque[str] = deque(maxlen=history_size)

    def compose(self, mood: MoodState) -> tuple[str, str]:
        candidates = [template for template in TEMPLATES if template.text not in self.recent] or TEMPLATES
        weighted = [(template, self._weight(template, mood)) for template in candidates]
        total = sum(weight for _, weight in weighted)
        pick = random.uniform(0, total)
        upto = 0.0
        chosen = weighted[-1][0]
        for template, weight in weighted:
            upto += weight
            if upto >= pick:
                chosen = template
                break
        self.recent.append(chosen.text)
        return chosen.msg_type, chosen.text

    def _weight(self, template: Template, mood: MoodState) -> float:
        multiplier = {
            "social_checkin": 0.6 + mood.social_urge,
            "care": 0.7 + mood.care,
            "casual": 0.8 + mood.energy * 0.4,
            "discovery_teaser": 0.6 + mood.curiosity + mood.mischief * 0.4,
        }[template.msg_type]
        return max(0.01, template.weight * multiplier)
