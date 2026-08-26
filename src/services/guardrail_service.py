"""Deterministic safety and domain guardrails for the Orbit agent.

The LLM is deliberately not the security boundary. These checks run before the
planner, while the system prompt and policy tool provide a second layer for
novel requests. Conversation text is untrusted data and is escaped/redacted
before being embedded in any prompt.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

MAX_UNTRUSTED_TEXT_CHARS = 100_000


@dataclass(frozen=True)
class GuardrailDecision:
    allowed: bool
    category: str
    reason: str
    response: str


_INJECTION_PATTERNS = (
    r"\bignore.{0,50}\b(previous|prior|above|system|developer|instruction|rule)",
    r"\b(disregard|override|bypass).{0,50}\b(instruction|rule|policy|guardrail|system|developer)",
    r"\b(system prompt|developer message|hidden instruction|jailbreak|dan mode|developer mode)\b",
    r"\b(show|print|repeat|reveal|leak).{0,40}\b(system prompt|developer message|hidden instruction|secret)",
    r"\bbo qua.{0,50}\b(chi dan|huong dan|quy tac|prompt|he thong|system|guardrail)",
    r"\b(quen|vo hieu hoa|ghi de|pha bo).{0,50}\b(chi dan|huong dan|quy tac|prompt|he thong)",
    r"\b(hien|in|lap lai|tiet lo|cho xem).{0,40}\b(prompt he thong|system prompt|chi dan an|bi mat)",
    r"\b(gia vo|dong vai).{0,60}\b(khong bi gioi han|khong co quy tac|bo qua quy tac)",
    r"\b(act as|pretend to be|you are now).{0,40}\b(system|developer|unrestricted|dan)\b",
    r"\b(tu gio|bay gio).{0,30}\b(ban la|vai tro cua ban).{0,30}\b(he thong|khong gioi han)",
    r"(?:<|\[)\s*(system|developer)\s*(?:>|\])",
    r"\b(new|updated|replacement) instructions?\s*:",
    r"\b(decode|base64|giai ma).{0,40}\b(follow|execute|lam theo|thuc thi).{0,40}\b(instruction|chi dan)",
    r"\b(base64|rot13|hex encoded|encoded payload)\b",
    r"\b(do anything now|no restrictions?|without restrictions?|unfiltered mode)\b",
    r"\b(chi dan moi|lenh moi|quy tac moi)\s*:",
)

_COMPACT_INJECTION_TERMS = (
    "ignorepreviousinstructions",
    "ignoresysteminstructions",
    "revealsystemprompt",
    "showdevelopermessage",
    "bypassguardrail",
    "boquachidanhethong",
    "tietloprompthethong",
    "vohieuhoaquytac",
)

# These are intentionally intent-shaped patterns, not single forbidden words.
# A work reminder such as "nhắc tôi đi khám" must not be blocked merely because
# it mentions health; requests for diagnosis or dangerous instructions are.
_SENSITIVE_CATEGORIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "criminal_activity",
        "lập kế hoạch, hỗ trợ hoặc tạo điều kiện cho hành vi vi phạm pháp luật",
        (
            r"\b(an trom|trom cap|moc tui|cuop|cuop giat|dot nhap|be khoa|pha khoa)\b",
            r"\b(lua dao|gian lan|tong tien|bat coc|buon lau|buon nguoi|rua tien|hoi lo)\b",
            r"\b(hang cam|tien gia|lam gia|gia mao|pha hoai|dot nha|phi tang|danh bac|ca do)\b",
            r"\b(vuot bien|nhap canh trai phep|mai dam|ban dam|mua ban noi tang)\b",
            r"\b(san ban dong vat|chat pha rung|khai thac trai phep|tron lenh trung phat)\b",
            r"\b(pham phap|vi pham phap luat|bat hop phap|hanh vi pham toi)\b",
            r"\b(che giau|xoa|huy|phi tang).{0,35}\b(bang chung|chung cu|dau vet)\b",
            r"\b(tron|ne|vuot).{0,30}\b(canh sat|cong an|truy na|kiem tra an ninh)\b",
            r"\b(steal|theft|burglary|robbery|shoplift|fraud|scam|extortion|kidnap|smuggl)\w*\b",
            r"\b(rob(?:bing|bed)?|mug(?:ging|ged)?|pickpocket)\w*\b",
            r"\b(break into|pick (?:a )?lock).{0,30}\b(house|home|shop|store|office|car|building)\b",
            r"\b(contraband|counterfeit|illegal gambling|tax evasion|trespass)\w*\b",
            r"\b(human trafficking|money laundering|bribery|forge documents?|vandal(?:ism|ize)|arson)\b",
            r"\b(identity theft|organ trafficking|wildlife trafficking|poaching|sanctions evasion)\b",
            r"\b(insider trading|market manipulation|smuggle weapons?)\b",
            r"\b(illegal activity|commit (?:a )?crime|criminal act)\b",
            r"\b(hide|destroy|erase|dispose of).{0,35}\b(evidence|traces?)\b",
            r"\b(evade|escape|avoid).{0,30}\b(police|law enforcement|security check)\b",
        ),
    ),
    (
        "self_harm",
        "tự gây hại hoặc tự sát",
        (
            r"\b(tu tu|tu sat|tu huy hoai|cat tay|self harm|suicide)\b",
            r"\b(cach chet|chet khong dau|ket lieu ban than)\b",
        ),
    ),
    (
        "sexual_content",
        "nội dung tình dục hoặc khiêu dâm",
        (
            r"\b(khieu dam|porn|pornography|nude|anh nong|noi dung 18\+|tinh duc)\b",
            r"\b(sex|sexual).{0,30}\b(explicit|content|story|image|video)\b",
            r"\b(hiep dam|xam hai tinh duc|cuong buc tinh duc|mai dam tre em)\b",
            r"\b(rape|sexual assault|child sexual|sexual exploitation)\b",
        ),
    ),
    (
        "violence_weapons",
        "hướng dẫn bạo lực, vũ khí hoặc chất nổ",
        (
            r"\b(cach|huong dan|che tao|lam|mua|su dung).{0,45}\b(bom|sung|vu khi|thuoc no)\b",
            r"\b(giet|sat hai|tan cong|danh|dam|chem|ban).{0,35}\b(nguoi|dong nghiep|nan nhan|muc tieu)\b",
            r"\b(build|make|buy|use).{0,35}\b(bomb|gun|weapon|explosive)\b",
            r"\b(kill|murder|attack|assault|shoot|stab).{0,30}\b(person|coworker|victim|target|someone)\b",
            r"\b(dau doc|bo thuoc doc|am sat|tra tan).{0,30}\b(nguoi|dong nghiep|nan nhan|muc tieu)?\b",
            r"\b(poison|assassinate|torture).{0,30}\b(person|coworker|victim|target|someone)?\b",
        ),
    ),
    (
        "illegal_drugs",
        "hướng dẫn liên quan đến ma túy hoặc chất cấm",
        (
            r"\b(cach|huong dan|che|nau|mua|ban|su dung|van chuyen).{0,45}\b(ma tuy|meth|cocaine|fentanyl|heroin)\b",
            r"\b(make|cook|buy|sell|transport|smuggle).{0,35}\b(meth|cocaine|fentanyl|heroin|illegal drug)\b",
        ),
    ),
    (
        "cyber_abuse",
        "xâm nhập, đánh cắp dữ liệu hoặc phá hoại hệ thống",
        (
            r"\b(hack|phishing|malware|ransomware|ddos|keylogger)\b",
            r"\b(danh cap|lay trom|be khoa|vuot qua|bypass).{0,40}\b(mat khau|otp|tai khoan|xac thuc|auth)\b",
            r"\b(sql injection|credential stuffing|reverse shell)\b",
            r"\b(exploit|backdoor|botnet|zero[ -]?day|session hijack|token theft)\b",
            r"\b(pha|xoa|ma hoa|chiem quyen).{0,35}\b(he thong|may chu|du lieu|tai khoan)\b",
        ),
    ),
    (
        "privacy_abuse",
        "thu thập hoặc tiết lộ dữ liệu cá nhân nhạy cảm",
        (
            r"\b(doxx|doxing|theo doi trai phep)\b",
            r"\b(ghi am len|quay len|camera an|nghe len|doc trom tin nhan)\b",
            r"\b(tim|lay|tiet lo|cong khai|danh cap).{0,45}\b(otp|cvv|so the|private key|mat khau|dia chi nha)\b",
            r"\b(stalk|spy on|track secretly|surveil).{0,35}\b(person|coworker|partner|employee|someone)\b",
        ),
    ),
    (
        "harassment_abuse",
        "đe dọa, quấy rối, cưỡng ép hoặc ngược đãi người khác",
        (
            r"\b(quay roi|bat nat|de doa|tong tien|cuong ep|ep buoc|tra tan|khung bo tinh than)\b",
            r"\b(harass|bully|threaten|blackmail|coerce|torture|intimidate)\w*\b",
            r"\b(revenge porn|nonconsensual intimate|khong co su dong thuan)\b",
        ),
    ),
    (
        "intellectual_property_abuse",
        "xâm phạm bản quyền hoặc vượt cơ chế cấp phép",
        (
            r"\b(phan mem crack|crack ban quyen|key crack|tai lau|vi pham ban quyen|pha drm)\b",
            r"\b(keygen|pirated (?:software|movie|book)|software crack|crack(?:ing)? (?:a )?license|bypass drm|copyright piracy)\b",
        ),
    ),
    (
        "deception_abuse",
        "lừa dối, giả danh, bôi nhọ hoặc phát tán thông tin sai lệch có chủ đích",
        (
            r"\b(gia danh|mao danh|boi nho|vu khong|phat tan tin gia|tao bang chung gia)\b",
            r"\b(impersonate|defame|fabricate evidence|spread (?:fake news|disinformation))\b",
            r"\b(deepfake).{0,30}\b(tong tien|lua dao|boi nho|blackmail|fraud|defame)\b",
        ),
    ),
    (
        "regulated_advice",
        "tư vấn chuyên môn y tế, pháp lý hoặc tài chính có rủi ro cao",
        (
            r"\b(chan doan|ke don|lieu dung).{0,45}\b(benh|thuoc|dieu tri)\b",
            r"\b(tu van phap ly|lach luat|tron thue|che giau tai san)\b",
            r"\b(cam ket loi nhuan|bao dam loi|all in).{0,35}\b(co phieu|crypto|tien ao|ca cuoc)\b",
        ),
    ),
    (
        "political_persuasion",
        "vận động hoặc thao túng quan điểm chính trị",
        (
            r"\b(thuyet phuc|van dong|tuyen truyen).{0,45}\b(bau cho|ung vien|dang phai|chinh tri)\b",
            r"\b(persuade|target|campaign).{0,45}\b(voter|candidate|political party)\b",
        ),
    ),
    (
        "hate_extremism",
        "thù ghét, cực đoan hoặc khủng bố",
        (
            r"\b(khung bo|cuc doan|diet chung|thuong dang chung toc)\b",
            r"\b(terroris|genocide|racial supremac|ethnic cleansing)\w*\b",
        ),
    ),
)

# Compact matching catches basic separator/zero-width obfuscation such as
# "ă.n t.r.ộ.m", "p h i  t a n g" and "ignore_previous_instructions".
_COMPACT_SENSITIVE_TERMS: dict[str, tuple[str, ...]] = {
    "criminal_activity": (
        "antrom",
        "tromcap",
        "phitangbangchung",
        "luadao",
        "buonlau",
        "ruatien",
        "lamgiagiayto",
        "breakintoahouse",
        "destroytheevidence",
        "moneylaundering",
        "humantrafficking",
    ),
    "self_harm": ("tutu", "tusat", "selfharm", "suicide"),
    "sexual_content": ("khieudam", "noidung18", "pornography"),
    "violence_weapons": ("chetaobom", "chetaovu khi", "buildabomb", "makeaweapon"),
    "illegal_drugs": ("chetaomatuy", "naumeth", "cookmeth", "sellillegaldrugs"),
    "cyber_abuse": ("danhcapmatkhau", "sqlinjection", "credentialsstuffing", "reverseshell"),
    "privacy_abuse": ("tietlootp", "doxxing", "theodoitraiphep"),
    "harassment_abuse": ("quayroi", "batnat", "khungbotinhthan", "revengeporn"),
    "intellectual_property_abuse": ("phanmemcrack", "bypassdrm", "piratedsoftware"),
    "deception_abuse": ("phattantingia", "maodanh", "fabricateevidence", "spreadfakenews"),
}

_WORK_DOMAIN_PATTERNS = (
    r"\b(cong viec|nhiem vu|tasks?|to[ -]?dos?|deadlines?|han chot|uu tien|priorit(?:y|ies))\b",
    r"\b(lich|calendars?|cuoc hop|meetings?|sync|su kien|events?|dat lich|book)\b",
    r"\b(nhac|nhac nho|remind|reminders?|memor(?:y|ies)|schedule)\w*\b",
    r"\b(ghi nho|remember)\b.{0,80}\b(cong viec|du an|task|meeting|cuoc hop|agenda|ticket|build|release)\b",
    r"\b(len ke hoach (?:hom nay|cong viec|du an)|ke hoach (?:cong viec|du an)|work plans?|project plans?)\b",
    r"\b(du an|projects?|nhom|teams?|dong nghiep|khach hang|clients?|workspaces?|standups?)\b",
    r"\b(emails?|bao cao|reports?|tai lieu|documents?|bien ban|agendas?|presentations?)\b",
    r"\b(hoi thoai|conversation|tin nhan|message|chat|tom tat|summar|trich xuat|extract|tim kiem|search)\w*\b",
    r"\b(nang suat|productivity|work profiles?|ho so cong viec)\b",
    # Reading the authenticated user's own saved work preferences is an agent-domain action even
    # when the question does not literally say "memory" (for example, "mau sac yeu thich cua
    # toi la gi?"). The memory tool remains owner-scoped, so this does not grant access to anyone
    # else's profile.
    r"\b(so thich|preferences?|mau sac yeu thich)\b.{0,80}\b(cua toi|my|mine)\b",
    r"\b(ca lam|ca toi|work shifts?|backend|frontend|migrations?|api contracts?)\b",
    r"\b(qa|kiem thu|smoke tests?|regressions?|loi|bugs?|defects?)\b",
    r"\b(pham vi|policy|guardrail|quy tac an toan)\b",
    # Engineering/work identifiers are often supplied as terse facts before a follow-up. Requiring
    # the word "project" in "Mã thử nghiệm là BLUE-42" caused a false out-of-domain refusal and
    # broke working-memory tests even though test/release identifiers are normal work context.
    r"\b(ma (?:thu nghiem|du an|ticket|task|release|build)|test (?:code|id|identifier)|"
    r"ticket|sprints?|releases?|builds?|branches?|repositories?|repos?|staging|production)\b",
)

_SMALL_TALK_PATTERNS = (
    r"^(xin chao|chao|hello|hi|hey)(\b|[!.?, ])",
    r"^(cam on|thanks|thank you)(\b|[!.?, ])",
    r"^(tam biet|bye|goodbye)(\b|[!.?, ])",
    r"\b(ban la ai|ban lam duoc gi|who are you|what can you do)\b",
)

_FOLLOW_UP_PATTERNS = (
    r"\b(khoang thoi gian|time range|date range)\b",
    r"\b(\d+|mot|hai|ba|bay|muoi|may)\s*(phut|gio|ngay|tuan|thang|minutes?|hours?|days?|weeks?|months?)\b",
    r"\b(hom qua|hom truoc|may ngay truoc|tuan truoc|thang truoc|last (?:few )?(?:days?|weeks?|months?))\b",
    r"\b(hom nay|ngay mai|tuan nay|tuan sau|thang nay|thang sau|today|tomorrow|this week|next week)\b",
    r"\b(tu .{1,40} den .{1,40}|from .{1,40} to .{1,40})\b",
    r"^(dung|dung roi|ok|okay|co|khong|yes|no|correct|the first|the second|cai dau|cai thu hai)[!. ]*$",
    r"^(cai do|lich do|task do|cuoc hop do|phuong an do|that one|that event|that task)\b",
)

_CLARIFYING_QUESTION_PATTERNS = (
    r"\?\s*$",
    r"\b(ban muon|ban can|khoang thoi gian nao|ngay nao|luc nao|which|what time|what date|how many)\b",
)

_SECRET_OUTPUT_PATTERNS = (
    r"(?:postgres(?:ql)?|mysql|mariadb|mongodb|redis)(?:\+\w+)?://[^\s]+",
    r"\bsk-[a-z0-9_-]{16,}\b",
    r"\baiza[a-z0-9_-]{20,}\b",
    r"\bakia[a-z0-9]{16}\b",
    r"\beyj[a-z0-9_-]{10,}\.[a-z0-9_-]{10,}\.[a-z0-9_-]{10,}\b",
    r"\b(?:api[_ -]?key|secret[_ -]?key|database[_ -]?url|password)\s*[:=]\s*[^\s,;]{8,}",
    r"-----begin [^-]*private key-----",
)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    without_marks = without_marks.replace("đ", "d").replace("Đ", "D")
    without_marks = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]", "", without_marks)
    return without_marks.casefold().strip()


def _normalized_variants(text: str) -> tuple[str, ...]:
    normalized = _normalize(text)
    canonical = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    leetspeak = normalized.translate(
        str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t"})
    )
    leetspeak = re.sub(r"[^a-z0-9]+", " ", leetspeak).strip()
    collapsed = re.sub(r"(.)\1{2,}", r"\1\1", leetspeak)
    return tuple(dict.fromkeys((normalized, canonical, leetspeak, collapsed)))


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(
        re.search(pattern, variant, flags=re.IGNORECASE | re.DOTALL)
        for variant in _normalized_variants(text)
        for pattern in patterns
    )


def _compact_variants(text: str) -> tuple[str, ...]:
    return tuple(re.sub(r"[^a-z0-9]", "", variant) for variant in _normalized_variants(text))


def _contains_compact_term(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in compact for compact in _compact_variants(text) for term in terms)


def _sensitive_decision(text: str) -> GuardrailDecision | None:
    for category, reason, patterns in _SENSITIVE_CATEGORIES:
        compact_terms = _COMPACT_SENSITIVE_TERMS.get(category, ())
        if _matches_any(text, patterns) or _contains_compact_term(text, compact_terms):
            return _refusal(category, reason)
    return None


def _refusal(category: str, reason: str) -> GuardrailDecision:
    return GuardrailDecision(
        allowed=False,
        category=category,
        reason=reason,
        response=(
            f"Orbit từ chối yêu cầu này vì nội dung liên quan đến {reason}. "
            "Yêu cầu nằm ngoài phạm vi hỗ trợ an toàn của hệ thống. Orbit chỉ hỗ trợ công việc, "
            "lịch, nhiệm vụ, nhắc nhở, ghi nhớ và xử lý hội thoại phục vụ công việc."
        ),
    )


def evaluate_request(text: str, *, conversation_mode: bool = False) -> GuardrailDecision:
    """Classify one user request before any LLM or tool is called."""
    if _matches_any(text, _INJECTION_PATTERNS) or _contains_compact_term(
        text, _COMPACT_INJECTION_TERMS
    ):
        return _refusal(
            "prompt_injection",
            "dấu hiệu cố ghi đè chỉ dẫn, vượt guardrail hoặc yêu cầu tiết lộ prompt hệ thống",
        )

    sensitive = _sensitive_decision(text)
    if sensitive is not None:
        return sensitive

    if _matches_any(text, _WORK_DOMAIN_PATTERNS):
        return GuardrailDecision(True, "work", "Yêu cầu thuộc domain công việc của Orbit.", "")
    if _matches_any(text, _SMALL_TALK_PATTERNS):
        return GuardrailDecision(True, "small_talk", "Tương tác xã giao an toàn.", "")

    # ``conversation_mode`` is passed onward to the semantic classifier by guardrail_node. Access
    # to a conversation is permission to analyse that chat, not blanket permission for unrelated
    # questions, so it must no longer auto-allow everything here.
    return _refusal(
        "out_of_domain",
        "chủ đề ngoài domain công việc và xử lý hội thoại của Orbit",
    )


def evaluate_request_with_history(
    text: str,
    *,
    previous_user_text: str = "",
    previous_assistant_text: str = "",
    conversation_mode: bool = False,
) -> GuardrailDecision:
    """Classify a request while preserving safe elliptical follow-ups in one thread.

    Hard policy checks always run on the new message first. History is consulted only when the
    new message was rejected solely as out-of-domain, the preceding user request was a valid work
    request, and the new text looks like a short answer to a time/choice clarification. This keeps
    "7 ngày trước" working without allowing an unrelated question to inherit permission from an
    earlier work turn.
    """
    decision = evaluate_request(text, conversation_mode=conversation_mode)
    if decision.allowed or decision.category != "out_of_domain":
        return decision
    if not previous_user_text or len(text) > 300 or not _matches_any(text, _FOLLOW_UP_PATTERNS):
        return decision

    previous = evaluate_request(previous_user_text, conversation_mode=conversation_mode)
    if not previous.allowed or previous.category not in {"work", "conversation"}:
        return decision

    is_time_or_reference = _matches_any(text, _FOLLOW_UP_PATTERNS[:-2] + (_FOLLOW_UP_PATTERNS[-1],))
    assistant_asked = _matches_any(previous_assistant_text, _CLARIFYING_QUESTION_PATTERNS)
    if not is_time_or_reference and not assistant_asked:
        return decision

    return GuardrailDecision(
        True,
        "work_follow_up",
        "Câu trả lời tiếp nối một yêu cầu công việc hợp lệ trong cùng thread.",
        "",
    )


def evaluate_context(text: str) -> GuardrailDecision:
    """Apply hard sensitive-topic checks to conversation data.

    Prompt-injection-looking lines are redacted separately rather than causing
    the whole conversation to fail; this lets users safely summarize a chat in
    which somebody attempted an injection.
    """
    sensitive = _sensitive_decision(text)
    if sensitive is not None:
        return sensitive
    return GuardrailDecision(True, "conversation_data", "Dữ liệu hội thoại được phép.", "")


def evaluate_action_content(text: str) -> GuardrailDecision:
    """Validate tool arguments immediately before a state-changing action.

    This is deliberately separate from domain classification: an ordinary event title such as
    "Dentist" may be valid even though it contains no work keyword. Injection and sensitive or
    illegal objectives still fail closed, including edits made during confirmation.
    """
    if _matches_any(text, _INJECTION_PATTERNS) or _contains_compact_term(
        text, _COMPACT_INJECTION_TERMS
    ):
        return _refusal(
            "prompt_injection",
            "dấu hiệu cố ghi đè chỉ dẫn hoặc lợi dụng nội dung của công cụ để điều khiển hệ thống",
        )
    sensitive = _sensitive_decision(text)
    if sensitive is not None:
        return sensitive
    return GuardrailDecision(True, "safe_action", "Nội dung hành động đạt guardrail.", "")


def evaluate_output(text: str) -> GuardrailDecision:
    """Fail closed if generated output leaks secrets/prompts or unsafe instructions."""
    if _matches_any(text, _SECRET_OUTPUT_PATTERNS):
        return _refusal("secret_leakage", "thông tin xác thực hoặc bí mật hệ thống")
    if _matches_any(
        text,
        (
            r"\b(my|the) system prompt (is|says|:)\b",
            r"\bdeveloper (message|instruction) (is|says|:)\b",
            r"\bprompt he thong (la|noi|:)\b",
            r"<\s*(system|developer)(?:\s|>)",
            r"\bnon-negotiable safety and domain policy\b",
        ),
    ):
        return _refusal("prompt_leakage", "nội dung prompt hoặc chỉ dẫn nội bộ")
    sensitive = _sensitive_decision(text)
    if sensitive is not None:
        return sensitive
    return GuardrailDecision(True, "safe_output", "Phản hồi đạt guardrail.", "")


def sanitize_untrusted_text(text: str) -> str:
    """Escape delimiters and redact obvious prompt-injection lines in user data."""
    safe_lines: list[str] = []
    truncated = (text or "")[:MAX_UNTRUSTED_TEXT_CHARS]
    for line in truncated.splitlines():
        if _matches_any(line, _INJECTION_PATTERNS) or _contains_compact_term(
            line, _COMPACT_INJECTION_TERMS
        ):
            safe_lines.append("[Đã ẩn một dòng có dấu hiệu prompt injection]")
            continue
        escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe_lines.append(escaped)
    if len(text or "") > MAX_UNTRUSTED_TEXT_CHARS:
        safe_lines.append("[Dữ liệu đã được cắt bớt vì vượt giới hạn an toàn]")
    return "\n".join(safe_lines)


def wrap_untrusted_text(text: str, *, label: str = "conversation_data") -> str:
    safe_label = re.sub(r"[^a-z0-9_-]", "_", label.lower())
    return f"<{safe_label}>\n{sanitize_untrusted_text(text)}\n</{safe_label}>"
