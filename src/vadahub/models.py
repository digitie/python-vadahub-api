"""공개 수집 결과의 타입과 계보."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PageSnapshot:
    """실제 접근한 공개 페이지의 주소·제목·UTC 수집시점."""

    source_url: str
    title: str
    collected_at: datetime


@dataclass(frozen=True, slots=True)
class Dataset:
    """meta 이력으로 구분한 자료."""
    dataset_id: str
    history_date: str
    title: str
    description: str
    source_url: str


@dataclass(frozen=True, slots=True)
class DatasetLayer:
    """meta 아래 기초 layer 및 서로 다른 공개·조회·다운로드 상태."""
    dataset_id: str
    history_date: str
    layer_id: str
    table_name: str
    title: str
    service_auth: str
    open_scope: str
    grid_available: bool
    download_available: bool

    @property
    def source_url(self) -> str:
        return f'https://vadahub.go.kr/renew/spaceData/detail.do?metaSn={self.dataset_id}&histDe={self.history_date}'


@dataclass(frozen=True, slots=True)
class ArchiveReceipt:
    """검증한 원문 ZIP과 멤버별 내용 해시·출처·수집시점."""
    layer: DatasetLayer
    source_url: str
    collected_at: datetime
    sha256: str
    byte_size: int
    local_path: Path
    member_sha256: tuple[tuple[str, str], ...]
    schema_version: str = '1'
