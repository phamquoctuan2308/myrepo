"""A3 · Ops Dispatcher — phục vụ đội vận hành.

Cố vấn ca trực: chuẩn bị phương án cho con người quyết, không tự quyết. Đầu vào
là cảnh báo đã xếp hạng của A2, đầu ra là gói can thiệp cụ thể — mỗi phương án
kèm số khách bị ảnh hưởng và tác động ước tính, xếp từ chi phí thấp đến cao để
người duyệt chọn chứ không phải tự nghĩ từ đầu.

Phạm vi quyền: đề xuất không giới hạn, thực thi bằng không cho tới khi có
người duyệt — mọi `InterventionOption` ở đây đều phải đi qua `PolicyGate` và
một chữ ký người thật trước khi chạm vào công viên.

Lưu ý phân biệt với A0: A3 điều phối *phương án cho nhân sự ở hiện trường*,
không định tuyến giữa các agent.
"""

from __future__ import annotations

from datetime import datetime

from src.flow_crew.contracts import (
    ActionType,
    CrowdAlert,
    HumanRole,
    ImpactMeasurement,
    InterventionOption,
)
from src.flow_crew.mock_park import (
    MockPark,
    ServiceStatus,
    distance_m,
    walk_minutes,
)

# Chi phí quy đổi để xếp hạng phương án; con số pilot sẽ thay bằng số thật.
VOUCHER_COST_VND = 20_000
FAST_PASS_COST_VND = 65_000
EXTRA_LANE_COST_VND = 350_000


def _extra_lane(park: MockPark, alert: CrowdAlert, index: int) -> InterventionOption | None:
    """Rẻ nhất: mở làn phụ ngay tại điểm đang nghẽn nhất còn hoạt động."""

    hottest = park.hottest_service(alert.zone_id)
    if hottest is None or hottest.extra_lane_open or hottest.status != ServiceStatus.OPEN:
        return None
    waiting = hottest.queue_count
    if waiting <= 0:
        return None
    before = park.wait_minutes(hottest.service_id)
    after = round(waiting / max(1, hottest.capacity_now * 2) * 60)
    return InterventionOption(
        option_id=f"{alert.alert_id}-OPT{index}",
        alert_id=alert.alert_id,
        action_type=ActionType.OPEN_EXTRA_LANE,
        summary=f"Mở làn phụ tại {hottest.name}",
        params={"service_id": hottest.service_id, "zone_id": alert.zone_id},
        affected_guests=waiting,
        estimated_wait_delta_minutes=after - before,
        estimated_cost_vnd=EXTRA_LANE_COST_VND,
        approver_role=HumanRole.SHIFT_LEAD,
    )


def _promotion(
    park: MockPark, alert: CrowdAlert, index: int, congested_zone_ids: frozenset[str]
) -> InterventionOption | None:
    """Kéo khách sang outlet F&B đang vắng gần đó — giãn tải và có doanh thu."""

    anchor_id = alert.service_id or alert.zone_id
    if anchor_id not in park.services:
        hottest = park.hottest_service(alert.zone_id)
        if hottest is None:
            return None
        anchor_id = hottest.service_id
    quiet = park.nearby_quiet_outlets(anchor_id, limit=1, avoid_zone_ids=congested_zone_ids)
    if not quiet:
        return None
    outlet = quiet[0]
    anchor = park.service(anchor_id)
    audience = park.app_users_in_zone.get(alert.zone_id, 0)
    if audience <= 0:
        return None
    gap = distance_m(anchor.x_m, anchor.y_m, outlet.x_m, outlet.y_m)
    return InterventionOption(
        option_id=f"{alert.alert_id}-OPT{index}",
        alert_id=alert.alert_id,
        action_type=ActionType.PUSH_PROMOTION,
        summary=f"Đẩy ưu đãi {outlet.name} cho {audience} khách đang ở {alert.zone_name}",
        params={
            "service_id": outlet.service_id,
            "zone_id": alert.zone_id,
            "from_service_id": anchor_id,
            "audience": audience,
            "walk_minutes": walk_minutes(gap),
        },
        affected_guests=audience,
        estimated_wait_delta_minutes=-round(audience / max(1, anchor.capacity_now) * 60 * 0.25),
        estimated_cost_vnd=VOUCHER_COST_VND * audience,
        approver_role=HumanRole.MARKETING,
    )


def _fast_pass(
    park: MockPark, alert: CrowdAlert, index: int, unresolved_guest_ids: tuple[str, ...]
) -> InterventionOption | None:
    """Đắt nhất: bù cho đúng những khách A1 không tìm được phương án nào."""

    if not unresolved_guest_ids:
        return None
    target = next(
        (
            service
            for service in sorted(
                park.services_in(alert.zone_id),
                key=lambda item: item.queue_count / max(1, item.capacity_now),
            )
            if service.supports_fast_pass and service.status == ServiceStatus.OPEN
        ),
        None,
    )
    if target is None:
        return None
    return InterventionOption(
        option_id=f"{alert.alert_id}-OPT{index}",
        alert_id=alert.alert_id,
        action_type=ActionType.GRANT_FAST_PASS,
        summary=f"Cấp fast-pass {target.name} cho {len(unresolved_guest_ids)} khách không còn phương án",
        params={
            "service_id": target.service_id,
            "zone_id": alert.zone_id,
            "guest_ids": list(unresolved_guest_ids),
        },
        affected_guests=len(unresolved_guest_ids),
        estimated_wait_delta_minutes=-park.wait_minutes(target.service_id),
        estimated_cost_vnd=FAST_PASS_COST_VND * len(unresolved_guest_ids),
        approver_role=HumanRole.PARK_MANAGER,
    )


def build_package(
    park: MockPark,
    *,
    alert: CrowdAlert,
    unresolved_guest_ids: tuple[str, ...] = (),
    congested_zone_ids: frozenset[str] = frozenset(),
) -> tuple[InterventionOption, ...]:
    """Biến một cảnh báo thành các phương án cụ thể, xếp từ rẻ đến đắt."""

    builders = (
        _extra_lane(park, alert, 1),
        _promotion(park, alert, 2, congested_zone_ids),
        _fast_pass(park, alert, 3, unresolved_guest_ids),
    )
    options = [option for option in builders if option is not None]
    options.sort(key=lambda option: option.estimated_cost_vnd)
    return tuple(options)


def measure(
    park: MockPark,
    *,
    alert: CrowdAlert,
    load_pct_before: float,
    guests_rerouted: int,
    now: datetime,
) -> ImpactMeasurement:
    """Đo lại sau một khoảng cố định rồi báo về A2 xác nhận — khép vòng đo lường."""

    return ImpactMeasurement(
        alert_id=alert.alert_id,
        measured_at=now,
        load_pct_before=load_pct_before,
        load_pct_after=park.zone_load_pct(alert.zone_id),
        guests_rerouted=guests_rerouted,
    )
