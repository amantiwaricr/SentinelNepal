from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import AnalystUser, DbSession
from app.schemas.ops import AlertOut, DashboardOut, IpSummaryOut, SubnetSummaryOut
from app.services import dashboard, investigation

router = APIRouter(tags=["investigation"])


@router.get("/ips/{ip}", response_model=IpSummaryOut)
def ip_summary(ip: str, _: AnalystUser, db: DbSession) -> IpSummaryOut:
    data = investigation.ip_summary(db, ip)
    data["recent_alerts"] = [AlertOut.model_validate(a) for a in data["recent_alerts"]]
    return IpSummaryOut.model_validate(data)


@router.get("/subnets", response_model=SubnetSummaryOut)
def subnet_summary(
    cidr: Annotated[str, Query(description="e.g. 10.0.0.0/24")], _: AnalystUser, db: DbSession
) -> SubnetSummaryOut:
    return SubnetSummaryOut.model_validate(investigation.subnet_summary(db, cidr))


@router.get("/dashboard/summary", response_model=DashboardOut)
def dashboard_summary(
    _: AnalystUser, db: DbSession, source: Literal["all", "dataset", "live"] = "all"
) -> DashboardOut:
    return DashboardOut.model_validate(dashboard.summary(db, source))
