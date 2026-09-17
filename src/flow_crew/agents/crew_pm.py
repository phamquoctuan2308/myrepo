"""A0 · Crew PM — phục vụ cả đội & admin.

Quản lý điều phối: biết ai đang làm gì, không tự quyết thay ai. Hai việc duy
nhất — bàn giao việc tới đúng agent (hoặc đúng instance) khi có yêu cầu, và
tổng hợp báo cáo cho admin khi được hỏi.

Ba giới hạn ở mục 6 nằm ngay trong module này:

* định tuyến theo bảng năng lực, không hardcode "ai gọi ai" ở chỗ gọi;
* báo cáo phải ghi rõ agent nào nói gì — `summarise` chỉ ghép lại những câu
  agent khác đã nói, không có đường nào để A0 tự viết thêm khuyến nghị;
* không ghi, không ra lệnh thực thi — A0 cũng không nằm trong danh sách vai
  được duyệt (xem `can_approve`).

Mục 6 lưu ý bài toán thật khi nhân rộng: một vai có thể có nhiều instance
(A10, A11 theo vùng), lúc đó A0 phải chọn đúng instance chứ không chỉ đúng
vai. PoC 6 tuần chạy 1 instance mỗi vai, nhưng `route` trả về cả hai để phần
gọi không phải viết lại khi tách instance.
"""

from __future__ import annotations

from pydantic import Field

from src.flow_crew.contracts import (
    AGENT_NAMES,
    POC_INSTANCE_OF,
    AgentId,
    FrozenContract,
)


class Capability(FrozenContract):
    agent: AgentId
    serves: str
    does: tuple[str, ...]
    keywords: tuple[str, ...]


# Bảng năng lực — nguồn sự thật duy nhất cho việc định tuyến và cho câu trả lời
# "ai trong đội đang phụ trách việc gì".
REGISTRY: tuple[Capability, ...] = (
    Capability(
        agent=AgentId.CROWD_ANALYST,
        serves="cả hai phía · chỉ quan sát",
        does=("mật độ theo khu", "phát hiện vượt ngưỡng", "xếp hạng mức nghiêm trọng", "giải thích nguyên nhân"),
        keywords=("mật độ", "đông", "vắng", "tải", "ngưỡng", "camera", "tình hình", "bao nhiêu khách"),
    ),
    Capability(
        agent=AgentId.GUEST_PLANNER,
        serves="khách hàng",
        does=("dựng lịch trình", "cập nhật phần lịch bị ảnh hưởng", "thời gian chờ kèm độ tin cậy", "giữ chỗ"),
        keywords=("lịch trình", "lịch chơi", "chơi gì", "đi đâu", "chờ bao lâu", "giữ chỗ", "gợi ý"),
    ),
    Capability(
        agent=AgentId.OPS_DISPATCHER,
        serves="đội vận hành",
        does=("gói can thiệp", "ước tính tác động", "điều hướng khách", "đo lại hiệu quả"),
        keywords=("can thiệp", "làn phụ", "nhân sự", "ưu đãi", "fast-pass", "phương án", "xử lý"),
    ),
    Capability(
        agent=AgentId.RESERVATION_KEEPER,
        serves="khách hàng ⇄ đối tác",
        does=("theo dõi độ dư lịch đặt", "cứu lịch đặt", "liên hệ đối tác", "báo lại kèm bằng chứng"),
        keywords=("đặt bàn", "lịch đặt", "dời giờ", "huỷ bàn", "nhà hàng", "đặt chỗ"),
    ),
)

CAPABILITY_OF: dict[AgentId, Capability] = {item.agent: item for item in REGISTRY}


class Routing(FrozenContract):
    agent: AgentId
    instance_id: str
    reason: str


class ReportLine(FrozenContract):
    """Một dòng báo cáo, luôn gắn với agent đã nói ra nó."""

    agent: AgentId
    text: str = Field(min_length=1)


def route(question: str) -> Routing:
    """Chọn agent (và instance) phù hợp nhất với yêu cầu.

    Không khớp từ khoá nào thì về A2 · Crowd Analyst: câu hỏi mơ hồ về công
    viên hầu như luôn bắt đầu bằng "đang thế nào", và A2 là agent không có
    quyền ghi — đoán sai về phía chỉ đọc là đoán sai rẻ nhất.
    """

    text = question.lower()
    best: tuple[int, Capability] | None = None
    for capability in REGISTRY:
        score = sum(1 for keyword in capability.keywords if keyword in text)
        if score and (best is None or score > best[0]):
            best = (score, capability)
    if best is None:
        fallback = CAPABILITY_OF[AgentId.CROWD_ANALYST]
        return Routing(
            agent=fallback.agent,
            instance_id=POC_INSTANCE_OF[fallback.agent],
            reason="Không khớp năng lực cụ thể nào; hỏi agent chỉ đọc trước.",
        )
    _, capability = best
    return Routing(
        agent=capability.agent,
        instance_id=POC_INSTANCE_OF[capability.agent],
        reason=f"{AGENT_NAMES[capability.agent]} phụ trách: {', '.join(capability.does[:2])}.",
    )


def handoff_target(purpose: str) -> Routing:
    """Bàn giao giữa hai agent cũng đi qua bảng năng lực, không hardcode ở chỗ gọi."""

    return route(purpose)


def summarise(lines: tuple[ReportLine, ...]) -> str:
    """Ghép báo cáo cho admin. Mỗi dòng ghi rõ ai nói — A0 không tự thêm gì."""

    if not lines:
        return "Chưa agent nào có dữ liệu để báo cáo."
    return "\n".join(f"{AGENT_NAMES[line.agent]}: {line.text}" for line in lines)


def roster() -> str:
    """Trả lời "ai trong đội đang phụ trách việc gì" mà admin không phải nhớ."""

    return "\n".join(
        f"{AGENT_NAMES[item.agent]} ({POC_INSTANCE_OF[item.agent]}) · {item.serves} — {', '.join(item.does)}"
        for item in REGISTRY
    )
