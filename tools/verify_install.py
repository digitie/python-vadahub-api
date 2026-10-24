"""격리된 wheel 설치본을 확인한다. 저장소 밖 또는 python -I로 실행한다."""
import argparse
from importlib.metadata import version
import json
from pathlib import Path
import sys

import vadahub


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spatial', action='store_true', help='시스템 GDAL binding도 실제 import한다')
    args = parser.parse_args()
    module = Path(vadahub.__file__).resolve()
    if not module.is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError(f'현재 venv의 설치본이 아닙니다: {module}')
    if not (module.parent / 'py.typed').is_file():
        raise RuntimeError('wheel에 py.typed가 없습니다')
    for name in vadahub.__all__:
        getattr(vadahub, name)
    result = {'version': version('python-vadahub-api'), 'python': sys.version.split()[0],
        'installed_module': str(module), 'exports': len(vadahub.__all__), 'tourism_sources': len(vadahub.TOURISM_SOURCES)}
    if args.spatial:
        from osgeo import gdal
        result['gdal'] = gdal.VersionInfo()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
