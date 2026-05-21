"""LINE 表示名で呼びかける（グループ・名前呼び・メンション向け）"""


def normalize_line_caller_display_name(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    s = " ".join(s.split())
    if s.startswith("@"):
        s = s.lstrip("@")
    return s[:40]


def line_caller_salutation(display_name: str | None) -> str:
    n = normalize_line_caller_display_name(display_name or "")
    if not n:
        return ""
    return f"{n}さん"


def prefix_reply_with_caller(reply: str, display_name: str | None) -> str:
    sal = line_caller_salutation(display_name)
    if not sal:
        return reply
    n = normalize_line_caller_display_name(display_name or "")
    if sal in reply or (n and n in reply):
        return reply
    body = reply.lstrip()
    return f"{sal}、{body}"
