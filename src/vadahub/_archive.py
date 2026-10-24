"""ZIP을 자동 해제하지 않고 자원 제한·CRC·계보를 검증한다."""
from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import stat
import zipfile

from .exceptions import ArchiveError


@dataclass(frozen=True, slots=True)
class ArchiveLimits:
    """원문·압축 해제 자원 상한. 브라우저 수신 전 상한이 아니다."""
    archive_bytes: int = 256 * 1024 * 1024
    members: int = 32
    member_bytes: int = 512 * 1024 * 1024
    expanded_bytes: int = 1024 * 1024 * 1024
    ratio: int = 200

    def __post_init__(self) -> None:
        for value in (self.archive_bytes, self.members, self.member_bytes, self.expanded_bytes, self.ratio):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError('ZIP 제한은 양의 정수여야 합니다')


def inspect_archive(path: Path, limits: ArchiveLimits, table: str | None = None) -> tuple[str, tuple[tuple[str, str], ...]]:
    if not 0 < path.stat().st_size <= limits.archive_bytes:
        raise ArchiveError('ZIP 원문 크기 제한 초과 또는 빈 파일')
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if not members or len(members) > limits.members:
                raise ArchiveError('ZIP 멤버 개수 제한')
            seen: set[str] = set()
            total = 0
            for member in members:
                name = member.filename
                parts = PurePosixPath(name)
                if (not name or '\\' in member.orig_filename or ':' in name or parts.is_absolute() or '..' in parts.parts
                        or name.casefold() in seen or member.flag_bits & 1
                        or stat.S_ISLNK(member.external_attr >> 16) or member.is_dir()):
                    raise ArchiveError('안전하지 않은 ZIP 멤버/중복/암호화')
                seen.add(name.casefold())
                total += member.file_size
                if (member.file_size > limits.member_bytes or total > limits.expanded_bytes
                        or member.file_size > max(1, member.compress_size) * limits.ratio):
                    raise ArchiveError('ZIP 해제 크기/압축비 제한')
            if table is not None:
                required = {table + ext for ext in ('.shp', '.shx', '.dbf', '.txt')}
                if not required.issubset({m.filename for m in members}):
                    raise ArchiveError('요청한 layer의 SHP sidecar가 아닙니다')
            hashes = []
            for member in members:
                digest = hashlib.sha256()
                with archive.open(member) as source:
                    for block in iter(lambda: source.read(1024 * 1024), b''):
                        digest.update(block)
                hashes.append((member.filename, digest.hexdigest()))
        with path.open('rb') as source:
            checksum = hashlib.file_digest(source, 'sha256').hexdigest()
        return checksum, tuple(sorted(hashes))
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError) as exc:
        raise ArchiveError('ZIP 압축/CRC를 읽을 수 없습니다') from exc
