"""공개 수집 결과의 타입과 계보."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Literal

CatalogKind = Literal['space', 'documents', 'statistics', 'api_original', 'api_analysis', 'api_map']


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
    catalog: CatalogKind = 'space'
    api_id: str | None = None
    api_request_url: str | None = None
    formats: str | None = None


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
    masked: bool | None = None
    require_public: bool = False

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


@dataclass(frozen=True, slots=True)
class SpatialFeature:
    """native 객체 대신 복사한 속성과 WKB를 제공하는 공간 레코드."""
    layer: DatasetLayer
    record_id: str
    record_id_field: str
    raw_attributes: Mapping[str, Any]
    attributes: Mapping[str, Any]
    geometry_wkb: bytes | None
    geometry_type: str | None
    source_crs: str | None
    crs_evidence: str | None
    wgs84_wkb: bytes | None
    source_sha256: str
    source_collected_at: datetime | None = None
    geometry_valid: bool | None = None


@dataclass(frozen=True, slots=True)
class LibraryResource:
    """자료실 파일/테이블의 원본 이름과 공개·조회·다운로드를 구분한 참조."""
    dataset: Dataset
    resource_id: str
    title: str
    source_name: str
    format: str | None
    attribute_kind: str
    service_auth: str | None
    open_scope: str
    grid_available: bool | None
    download_available: bool | None
    masked: bool | None
    backing_dataset_id: str | None = None
    raw_availability: tuple[tuple[str, str | None], ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentPreview:
    resource: LibraryResource
    preview_url: str
    collected_at: datetime


@dataclass(frozen=True, slots=True)
class TablePreview:
    """공개 UI snapshot. 권위 total이 없으므로 전체 OpenAPI 응답으로 주장하지 않는다."""
    resource: LibraryResource
    columns: tuple[str, ...]
    labels: tuple[str, ...]
    rows: tuple[Mapping[str, Any], ...]
    collected_at: datetime
    partial: bool = True


@dataclass(frozen=True, slots=True)
class LibraryArchiveReceipt:
    resource: LibraryResource
    source_url: str
    collected_at: datetime
    sha256: str
    byte_size: int
    local_path: Path
    member_sha256: tuple[tuple[str, str], ...]
    schema_version: str = '1'


@dataclass(frozen=True, slots=True)
class WebTablePage:
    """공개 웹 grid의 단일 페이지. live DB 결과이며 다중 호출 snapshot은 아니다."""
    resource: LibraryResource
    columns: tuple[str, ...]
    labels: tuple[str | None, ...]
    rows: tuple[Mapping[str, Any], ...]
    start: int
    page_size: int
    total: int
    filtered_total: int
    collected_at: datetime
    source_columns: tuple[str, ...] = ()
