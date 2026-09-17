"""A2 · Crowd Analyst — phục vụ cả hai phía, chỉ quan sát.

Nói bằng số và nguyên nhân, không tự khuyến nghị hành động: biến một cảnh báo
thành việc phải làm là phần của A3. Agent nắm nhiều dữ liệu nhất trong đội
nhưng có ít quyền nhất — mọi hàm ở đây đều là hàm đọc, và lịch trình khách chỉ
đi vào dưới dạng số đếm tổng hợp (`guests_heading_to`), không bao giờ là nội
dung lịch của một ai cụ thể.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.flow_crew.contracts import (
    AlertCause,
    CrowdAlert,
    DensityLevel,
    ImpactMeasurement,
    WaitEstimate,
    ZoneDensity,
)
from src.flow_crew.mock_park import (
    ZONE_ALERT_LOAD_PCT,
    ZONE_CROWDED_LOAD_PCT,
    ZONE_OVERLOAD_LOAD_PCT,
    ZONES,
    MockPark,
    ServiceKind,
    ServiceStatus,
)

# Chỉ cảnh báo những gì sắp xảy ra trong tầm một ca xử lý được.
ALERT_HORIZON_MINUTES = 45
SHOW_JUST_ENDED_MINUTES = 20


def _level(load_pct: float) -> DensityLevel:
    if load_pct >= ZONE_OVERLOAD_LOAD_PCT:
        return DensityLevel.OVERLOAD
    if load_pct >= ZONE_ALERT_LOAD_PCT:
        return DensityLevel.CROWDED
    if load_pct >= ZONE_CROWDED_LOAD_PCT:
        return DensityLevel.BUSY
    return DensityLevel.CALM


def minutes_to_overload(load_pct: float, trend_pct_per_10min: float) -> int | None:
    """Còn bao lâu nữa thì khu chạm mốc quá tải, theo đà hiện tại."""

    if load_pct >= ZONE_OVERLOAD_LOAD_PCT:
        return 0
    if trend_pct_per_10min <= 0:
        return None
    return round((ZONE_OVERLOAD_LOAD_PCT - load_pct) / trend_pct_per_10min * 10)


def zone_picture(park: MockPark) -> tuple[ZoneDensity, ...]:
    """Bức tranh mật độ toàn công viên, sắp theo mức tải giảm dần."""

    picture = []
    for zone in ZONES:
        load = park.zone_load_pct(zone.zone_id)
        hottest = park.hottest_service(zone.zone_id)
        picture.append(
            ZoneDensity(
                zone_id=zone.zone_id,
                zone_name=zone.name,
                headcount=park.zone_headcount(zone.zone_id),
                capacity=park.zone_capacity(zone.zone_id),
                load_pct=load,
                level=_level(load),
                trend_pct_per_10min=park.zone_trend_pct[zone.zone_id],
                hottest_service_id=hottest.service_id if hottest else None,
            )
        )
    return tuple(sorted(picture, key=lambda item: item.load_pct, reverse=True))


def _infer_cause(park: MockPark, zone_id: str, now: datetime) -> tuple[AlertCause, str | None]:
    """Nguyên nhân nghẽn, suy ra từ trạng thái công viên — không phải ai đó mách."""

    closed = [
        service
        for service in park.services_in(zone_id)
        if service.status == ServiceStatus.CLOSED and service.opens_at <= now <= service.closes_at
    ]
    if closed:
        biggest = max(closed, key=lambda service: service.throughput_per_hour)
        return AlertCause.SERVICE_CLOSED, biggest.service_id
    if park.rains_at(now):
        return AlertCause.RAIN, None
    for service in park.services_in(zone_id):
        if service.kind is not ServiceKind.SHOW:
            continue
        for start in service.session_starts:
            ended = start + timedelta(minutes=45)
            if 0 <= (now - ended).total_seconds() / 60 <= SHOW_JUST_ENDED_MINUTES:
                return AlertCause.SHOW_ENDED, service.service_id
    return AlertCause.PARK_LOAD_RISING, None


def _severity(density: ZoneDensity, guests_heading: int, minutes_left: int | None) -> float:
    """Xếp hạng theo cả quy mô lẫn thời gian còn lại, để biết xử cái nào trước."""

    over = max(0.0, density.load_pct - ZONE_ALERT_LOAD_PCT)
    urgency = 0.0 if minutes_left is None else max(0.0, ALERT_HORIZON_MINUTES - minutes_left)
    return round(over * 2.0 + guests_heading * 0.25 + urgency * 0.6, 2)


def detect_alerts(park: MockPark, *, now: datetime) -> tuple[CrowdAlert, ...]:
    """Khu nào vượt ngưỡng đã cấu hình, hoặc sắp quá tải trong tầm xử lý được."""

    found: list[CrowdAlert] = []
    for density in zone_picture(park):
        minutes_left = minutes_to_overload(density.load_pct, density.trend_pct_per_10min)
        crosses_soon = minutes_left is not None and minutes_left <= ALERT_HORIZON_MINUTES
        if density.load_pct < ZONE_ALERT_LOAD_PCT and not crosses_soon:
            continue
        cause, culprit_id = _infer_cause(park, density.zone_id, now)
        service_id = culprit_id or density.hottest_service_id
        service = park.service(service_id) if service_id else None
        guests_heading = park.guests_heading_to(service_id, after=now) if service_id else 0
        found.append(
            CrowdAlert(
                alert_id=f"AL-{density.zone_id[2:]}-{now:%H%M}",
                raised_at=now,
                zone_id=density.zone_id,
                zone_name=density.zone_name,
                service_id=service_id,
                service_name=service.name if service else None,
                level=density.level,
                load_pct=density.load_pct,
                threshold_pct=ZONE_ALERT_LOAD_PCT,
                minutes_to_overload=minutes_left,
                guests_heading=guests_heading,
                cause=cause,
                severity_score=_severity(density, guests_heading, minutes_left),
                rank=1,
            )
        )
    ranked = sorted(found, key=lambda alert: alert.severity_score, reverse=True)
    return tuple(alert.model_copy(update={"rank": index}) for index, alert in enumerate(ranked, start=1))


def wait_for(park: MockPark, service_id: str, *, now: datetime) -> WaitEstimate:
    """Thời gian chờ kèm đúng độ tin cậy — đo được bằng camera hay chỉ ước lượng."""

    service = park.service(service_id)
    return WaitEstimate(
        service_id=service.service_id,
        service_name=service.name,
        minutes=park.wait_minutes(service_id),
        source=service.wait_source,
        measured_at=now,
    )


def measure(
    park: MockPark,
    *,
    alert: CrowdAlert,
    load_pct_before: float,
    guests_rerouted: int,
    now: datetime,
) -> ImpactMeasurement:
    """Đọc lại tải sau can thiệp. A2 chỉ ghi nhận, việc so sánh là của người đọc."""

    return ImpactMeasurement(
        alert_id=alert.alert_id,
        measured_at=now,
        load_pct_before=load_pct_before,
        load_pct_after=park.zone_load_pct(alert.zone_id),
        guests_rerouted=guests_rerouted,
    )


def confirm(measurement: ImpactMeasurement) -> ImpactMeasurement:
    """Xác nhận điểm nghẽn đã giảm — khép vòng đo lường A3 → A2."""

    return measurement.model_copy(update={"confirmed_by_analyst": measurement.delta_pct < 0})
