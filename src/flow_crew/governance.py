"""Policy gate: the code that makes "không ngoại lệ" a property, not a promise.

Mục 6 của charter đóng hai cái chốt cùng lúc, và cả hai đều nằm ở đây, không
nằm trong prompt của agent nào:

* least-privilege — A2 nắm nhiều dữ liệu nhất nhưng không có một quyền ghi nào,
  A0 chỉ kết nối và tổng hợp; đề xuất sai vai bị chặn trước khi tới người duyệt;
* cổng phê duyệt — mọi hành động chạm tới khách hoặc vận hành đều phải có đúng
  người ký, và dời/huỷ lịch đặt thì chỉ chính khách ký được.

Verdict tính từ luật và số, không từ ý kiến của model. Không khớp luật nào thì
mặc định đẩy lên người xem xét.
"""

from __future__ import annotations

from src.flow_crew.contracts import (
    ActionType,
    AgentId,
    GovernanceDecision,
    HumanRole,
    ProposedAction,
    Verdict,
)
from src.flow_crew.mock_park import (
    FAST_PASS_SHIFT_CAP,
    MockPark,
    ParkDataError,
    ReservationStatus,
    ServiceStatus,
)

POLICIES: dict[str, str] = {
    "POL-OPS-01": "Đăng tin vào phòng chung và thông báo nội bộ cho con người luôn được tự động.",
    "POL-OPS-02": "Đo lại hiệu quả sau can thiệp là hành động chỉ đọc, được tự động.",
    "POL-OPS-03": "Mở làn phụ hoặc điều chuyển nhân sự tại chỗ: Trưởng ca duyệt.",
    "POL-OPS-04": "Không can thiệp vào dịch vụ đang tạm dừng vì lý do an toàn.",
    "POL-OPS-05": "Điều hướng khách sang outlet khác: Trưởng ca duyệt.",
    "POL-GUEST-01": "Cập nhật lịch trình của chính khách đang đối thoại được tự động; chỉ gửi phần thay đổi.",
    "POL-GUEST-02": "Giữ chỗ trước ở dịch vụ có hỗ trợ đặt nhanh được tự động.",
    "POL-GUEST-03": "Không dời mốc khách đã chọn chắc chắn trong bất kỳ trường hợp nào.",
    "POL-MSG-01": "Tin nhắn báo thay đổi lịch cho chính khách đó được gửi tự động.",
    "POL-MKT-01": "Đẩy ưu đãi tới khách đang ở trong khu: Marketing duyệt.",
    "POL-TICKET-01": "Cấp fast-pass: Quản lý công viên duyệt.",
    "POL-TICKET-02": "Không tự nâng hạn mức fast-pass vượt quy định của ca.",
    "POL-TICKET-03": "Chỉ cấp fast-pass cho dịch vụ có hỗ trợ tính năng này.",
    "POL-RES-01": "Dời lịch đặt của khách: chính khách duyệt, không ai ký thay.",
    "POL-RES-02": "Huỷ lịch đặt: chính khách duyệt, và chỉ sau khi đã thử đổi lộ trình rồi dời giờ.",
    "POL-RES-03": "Không huỷ hai lần cho cùng một lịch đặt.",
    "POL-CALL-01": "Cuộc gọi tự động: tự giới thiệu, xin phép ghi âm, đọc mã đặt chỗ, tối đa 2 phút.",
    "POL-CALL-02": "Không đọc thông tin thẻ hay thanh toán qua điện thoại trong bất kỳ trường hợp nào.",
    "POL-SCOPE-01": "Mọi đề xuất can thiệp phải nêu rõ số khách bị ảnh hưởng; không đề xuất mơ hồ.",
    "POL-PRIV-01": "A2 · Crowd Analyst chỉ đọc — không có quyền ghi ở bất kỳ đâu.",
    "POL-PRIV-02": "A0 · Crew PM chỉ kết nối và tổng hợp — không ghi, không ra lệnh thực thi.",
    "POL-PRIV-03": "A1 chỉ ghi trong lịch trình của khách đang đối thoại.",
    "POL-PRIV-04": "A4 chỉ tác động lên lịch đặt của chính khách sở hữu; không tạo lịch đặt mới.",
    "POL-GOV-00": "Không tìm thấy policy rõ ràng: bắt buộc con người xem xét.",
}

# Rủi ro thấp, không chạm tới khách hay tài nguyên vận hành.
_AUTO_ACTIONS: dict[ActionType, str] = {
    ActionType.POST_ROOM_MESSAGE: "POL-OPS-01",
    ActionType.NOTIFY_HUMAN: "POL-OPS-01",
    ActionType.MEASURE_IMPACT: "POL-OPS-02",
    ActionType.HOLD_SLOT: "POL-GUEST-02",
    ActionType.SEND_GUEST_MESSAGE: "POL-MSG-01",
}

_APPROVAL_ACTIONS: dict[ActionType, tuple[HumanRole, str]] = {
    ActionType.OPEN_EXTRA_LANE: (HumanRole.SHIFT_LEAD, "POL-OPS-03"),
    ActionType.REASSIGN_STAFF: (HumanRole.SHIFT_LEAD, "POL-OPS-03"),
    ActionType.REROUTE_GUESTS: (HumanRole.SHIFT_LEAD, "POL-OPS-05"),
    ActionType.PUSH_PROMOTION: (HumanRole.MARKETING, "POL-MKT-01"),
    ActionType.GRANT_FAST_PASS: (HumanRole.PARK_MANAGER, "POL-TICKET-01"),
}

# Mục 6 · phạm vi quyền: ai được phép đề xuất loại hành động nào.
_READ_ONLY_AGENTS: dict[AgentId, str] = {
    AgentId.CROWD_ANALYST: "POL-PRIV-01",
    AgentId.CREW_PM: "POL-PRIV-02",
}
_READ_ONLY_ALLOWED = frozenset({ActionType.POST_ROOM_MESSAGE, ActionType.NOTIFY_HUMAN, ActionType.MEASURE_IMPACT})

_OWNER_OF: dict[ActionType, AgentId] = {
    ActionType.UPDATE_ITINERARY: AgentId.GUEST_PLANNER,
    ActionType.HOLD_SLOT: AgentId.GUEST_PLANNER,
    ActionType.OPEN_EXTRA_LANE: AgentId.OPS_DISPATCHER,
    ActionType.REASSIGN_STAFF: AgentId.OPS_DISPATCHER,
    ActionType.REROUTE_GUESTS: AgentId.OPS_DISPATCHER,
    ActionType.PUSH_PROMOTION: AgentId.OPS_DISPATCHER,
    ActionType.GRANT_FAST_PASS: AgentId.OPS_DISPATCHER,
    ActionType.RESCHEDULE_RESERVATION: AgentId.RESERVATION_KEEPER,
    ActionType.CANCEL_RESERVATION: AgentId.RESERVATION_KEEPER,
    ActionType.CALL_PARTNER: AgentId.RESERVATION_KEEPER,
}

_PAYMENT_WORDS = ("thẻ", "cvv", "số thẻ", "thanh toán", "card")


def _pass(action: ProposedAction, code: str) -> GovernanceDecision:
    return GovernanceDecision(
        action_id=action.action_id,
        verdict=Verdict.PASS,
        policy_codes=(code,),
        reasons=(POLICIES[code],),
    )


def _approval(action: ProposedAction, role: HumanRole, *codes: str) -> GovernanceDecision:
    return GovernanceDecision(
        action_id=action.action_id,
        verdict=Verdict.REQUIRE_APPROVAL,
        approver_role=role,
        policy_codes=codes,
        reasons=tuple(POLICIES[code] for code in codes),
    )


def _block(action: ProposedAction, code: str, reason: str) -> GovernanceDecision:
    return GovernanceDecision(
        action_id=action.action_id,
        verdict=Verdict.BLOCK,
        policy_codes=(code,),
        reasons=(reason,),
    )


class PolicyGate:
    """Thẩm định từng đề xuất. Không agent nào đi vòng qua được lớp này."""

    def __init__(self, park: MockPark) -> None:
        self._park = park

    def evaluate(self, action: ProposedAction) -> GovernanceDecision:
        privilege = self._privilege_check(action)
        if privilege is not None:
            return privilege

        kind = action.action_type
        if kind == ActionType.UPDATE_ITINERARY:
            return self._itinerary(action)
        if kind == ActionType.CALL_PARTNER:
            return self._call(action)
        if kind in _AUTO_ACTIONS:
            return _pass(action, _AUTO_ACTIONS[kind])
        if kind in _APPROVAL_ACTIONS:
            return self._intervention(action)
        if kind == ActionType.RESCHEDULE_RESERVATION:
            return _approval(action, HumanRole.GUEST, "POL-RES-01")
        if kind == ActionType.CANCEL_RESERVATION:
            return self._cancel(action)
        return _approval(action, HumanRole.PARK_MANAGER, "POL-GOV-00")

    # ---- least privilege ----------------------------------------------------

    def _privilege_check(self, action: ProposedAction) -> GovernanceDecision | None:
        code = _READ_ONLY_AGENTS.get(action.proposed_by)
        if code is not None and action.action_type not in _READ_ONLY_ALLOWED:
            return _block(
                action,
                code,
                f"{action.proposed_by.value} không có quyền đề xuất {action.action_type.value}.",
            )
        owner = _OWNER_OF.get(action.action_type)
        if owner is not None and action.proposed_by != owner:
            return _block(
                action,
                "POL-GOV-00",
                f"{action.action_type.value} thuộc phạm vi của {owner.value}, không phải {action.proposed_by.value}.",
            )
        return None

    # ---- từng nhóm hành động -------------------------------------------------

    def _itinerary(self, action: ProposedAction) -> GovernanceDecision:
        guest_id = str(action.params.get("guest_id", ""))
        speaking_with = str(action.params.get("speaking_with", ""))
        if not guest_id or guest_id != speaking_with:
            return _block(
                action,
                "POL-PRIV-03",
                f"A1 chỉ được ghi lịch của khách đang đối thoại ({speaking_with or 'không rõ'}).",
            )
        if action.params.get("touches_locked_slot"):
            return _block(action, "POL-GUEST-03", POLICIES["POL-GUEST-03"])
        return _pass(action, "POL-GUEST-01")

    def _intervention(self, action: ProposedAction) -> GovernanceDecision:
        role, code = _APPROVAL_ACTIONS[action.action_type]
        if action.affected_guests <= 0:
            return _block(action, "POL-SCOPE-01", POLICIES["POL-SCOPE-01"])

        service_id = action.params.get("service_id")
        if service_id:
            try:
                service = self._park.service(str(service_id))
            except ParkDataError as exc:
                return _block(action, "POL-GOV-00", str(exc))
            if service.status == ServiceStatus.PAUSED_SAFETY:
                return _block(
                    action,
                    "POL-OPS-04",
                    f"{service.name} đang tạm dừng vì lý do an toàn; không can thiệp.",
                )
            if action.action_type == ActionType.GRANT_FAST_PASS:
                if not service.supports_fast_pass:
                    return _block(action, "POL-TICKET-03", f"{service.name} không hỗ trợ fast-pass.")
                if self._park.fast_passes_issued + action.affected_guests > FAST_PASS_SHIFT_CAP:
                    return _block(
                        action,
                        "POL-TICKET-02",
                        f"Cấp thêm {action.affected_guests} suất sẽ vượt hạn mức {FAST_PASS_SHIFT_CAP} của ca.",
                    )
        return _approval(action, role, code)

    def _cancel(self, action: ProposedAction) -> GovernanceDecision:
        reservation_id = str(action.params.get("reservation_id", ""))
        try:
            reservation = self._park.reservation(reservation_id)
        except ParkDataError as exc:
            return _block(action, "POL-GOV-00", str(exc))
        if reservation.status == ReservationStatus.CANCELLED:
            return _block(action, "POL-RES-03", POLICIES["POL-RES-03"])
        if not action.params.get("tried_reorder") or not action.params.get("tried_reschedule"):
            return _block(
                action,
                "POL-RES-02",
                "Chưa thử đổi thứ tự lộ trình và dời giờ trước khi đề xuất huỷ.",
            )
        return _approval(action, HumanRole.GUEST, "POL-RES-02")

    def _call(self, action: ProposedAction) -> GovernanceDecision:
        script = tuple(str(line) for line in action.params.get("script", ()))
        joined = " ".join(script).lower()
        if any(word in joined for word in _PAYMENT_WORDS):
            return _block(action, "POL-CALL-02", POLICIES["POL-CALL-02"])
        if not action.params.get("discloses_bot") or not action.params.get("asks_recording_consent"):
            return _block(
                action,
                "POL-CALL-01",
                "Cuộc gọi phải mở đầu bằng tự giới thiệu là trợ lý tự động và xin phép ghi âm.",
            )
        if not action.params.get("confirmation_code"):
            return _block(action, "POL-CALL-01", "Cuộc gọi phải đọc mã đặt chỗ và chờ xác nhận.")
        return _pass(action, "POL-CALL-01")


def required_role(decisions: tuple[GovernanceDecision, ...]) -> HumanRole:
    """Người duy nhất ký được cả gói.

    Gói trộn nhiều nhóm (mở làn phụ + đẩy ưu đãi) dồn về Quản lý công viên —
    vai duy nhất bao trùm các quyết định vận hành. Việc của khách không gộp
    chung được với việc của vận hành: không ai ký thay khách.
    """

    roles = {decision.approver_role for decision in decisions if decision.approver_role is not None}
    if not roles:
        raise ValueError("Gói không cần phê duyệt thì không cần ticket")
    if len(roles) == 1:
        return next(iter(roles))
    if HumanRole.GUEST in roles:
        raise ValueError("Không gộp quyết định của khách chung với quyết định vận hành")
    return HumanRole.PARK_MANAGER
