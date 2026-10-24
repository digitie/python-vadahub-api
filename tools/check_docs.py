"""네트워크 없이 저장소 Markdown의 로컬 링크와 최소 계약을 확인한다."""

from pathlib import Path
import re
from urllib.parse import unquote


def check() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = [*root.glob("*.md"), *root.joinpath("docs").rglob("*.md")]
    errors = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^\s)]+)\)", text):
            if ":" in target or target.startswith("#"):
                continue
            resolved = path.parent / unquote(target.split("#", 1)[0])
            if not resolved.exists():
                errors.append(f"{path.relative_to(root)}: {target}")
    if errors:
        raise SystemExit("없는 문서 링크:\n" + "\n".join(errors))
    print(f"문서 {len(paths)}개 로컬 링크 확인")


if __name__ == "__main__":
    check()
