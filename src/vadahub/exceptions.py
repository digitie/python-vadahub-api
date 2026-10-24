"""조회 실패와 정상 빈 결과를 구분하는 공개 예외."""


class VadaHubError(Exception):
    """라이브러리 오류의 공통 기반."""


class ClientClosedError(VadaHubError):
    """종료된 클라이언트의 재사용."""


class AccessDeniedError(VadaHubError):
    """로그인 이동 또는 공개 접근 거부."""


class RateLimitError(VadaHubError):
    """공급자의 호출 제한 응답."""


class NetworkError(VadaHubError):
    """브라우저 시작·통신·시간 제한·자원 정리 실패."""


class SchemaError(VadaHubError):
    """공개 화면이나 응답 구조가 기대한 계약과 다름."""


class ProviderError(VadaHubError):
    """공개 웹 응답이 명시적으로 제공자 처리 실패를 보고함."""


class ArchiveError(VadaHubError):
    """원문 압축 형식·크기·CRC·sidecar 오류."""


class DownloadUnavailableError(VadaHubError):
    """실제 공개 UI에서 다운로드를 제공하지 않음."""


class SpatialDependencyError(VadaHubError):
    """시스템과 버전이 일치하는 GDAL Python binding이 필요함."""


class UnknownCrsError(VadaHubError):
    """CRS가 불명확하거나 서로 다른 근거가 충돌함."""
