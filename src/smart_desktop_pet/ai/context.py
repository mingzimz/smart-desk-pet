from ..domain.emotion import EmotionMachine, LABELS


def build_messages(persona: str, profile: dict, machine: EmotionMachine, user: str) -> list[dict]:
    system = (
        f"{persona}\n当前心情：{LABELS[machine.state]}；心情值 {machine.mood:.0f}/100；"
        f"精力 {machine.energy:.0f}/100。自然体现情绪，不机械报告数值。回复尽量不超过 200 字。"
    )
    messages = [{"role": "system", "content": system}]
    if profile["fragments"]:
        # User-originated memory remains user data rather than elevated system instructions.
        messages.append(
            {
                "role": "user",
                "content": "以下是我之前请你记住的信息：\n" + "\n".join(profile["fragments"]),
            }
        )
        messages.append({"role": "assistant", "content": "我会把这些信息作为对话背景。"})
    budget = 16000 - sum(len(m["content"]) for m in messages) - len(user)
    history = []
    for turn in reversed(profile["turns"][-8:]):
        size = len(turn["user"]) + len(turn["assistant"])
        if size > budget:
            break
        history[0:0] = [
            {"role": "user", "content": turn["user"]},
            {"role": "assistant", "content": turn["assistant"]},
        ]
        budget -= size
    return messages + history + [{"role": "user", "content": user}]
