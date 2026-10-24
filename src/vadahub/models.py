"""공개 수집 결과의 타입과 계보."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PageSnapshot:
    """실제 접근한 공개 페이지의 주소·제목·UTC 수집시점."""

    source_url: str
    title: str
    collected_at: datetime
