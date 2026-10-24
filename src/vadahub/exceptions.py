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
