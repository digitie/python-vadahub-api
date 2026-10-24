"""조사 도구도 CRC/해제 전에 ZIP 자원·경로를 제한한다."""

from pathlib import Path, PurePosixPath
import stat
import zipfile


def validate_archive(path: Path) -> zipfile.ZipFile:
    if path.stat().st_size > 256 * 1024 * 1024:
        raise ValueError("ZIP 원문 256MiB 상한 초과")
    archive = zipfile.ZipFile(path)
    try:
        members = archive.infolist()
        if not members or len(members) > 32:
            raise ValueError("ZIP 멤버 개수 상한 초과 또는 빈 ZIP")
        seen = set()
        total = 0
        for member in members:
            name = member.filename
            if ("\\" in name or ":" in name or PurePosixPath(name).is_absolute()
                    or ".." in PurePosixPath(name).parts or name.casefold() in seen
                    or member.flag_bits & 1 or stat.S_ISLNK(member.external_attr >> 16)):
                raise ValueError("안전하지 않은 ZIP 멤버")
            seen.add(name.casefold())
            total += member.file_size
            if (member.file_size > 512 * 1024 * 1024 or total > 1024 * 1024 * 1024
                    or member.file_size > max(1, member.compress_size) * 200):
                raise ValueError("ZIP 해제 크기/압축비 상한 초과")
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC 오류")
        return archive
    except BaseException:
        archive.close()
        raise
