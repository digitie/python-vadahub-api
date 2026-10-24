"""실제 공개 ZIP의 GDAL 가독성·행수·CRS를 확인하는 조사 도구."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import zipfile

from osgeo import gdal, ogr


def inspect(directory: Path) -> list[dict]:
    rows = []
    for path in sorted(directory.glob("[0-9]*.zip")):
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("ZIP CRC 오류")
            names = archive.namelist()
            shapes = [n for n in names if n.endswith(".shp")]
            if len(shapes) != 1:
                raise RuntimeError("조사 도구는 단일 SHP ZIP만 지원합니다")
            stem = shapes[0][:-4]
            text = archive.read(stem + ".txt").decode("cp949")
            mapping = dict(re.findall(r"inFieldName=(c\d+), columnName=([^,}]+)", text))
        with gdal.ExceptionMgr(), ogr.ExceptionMgr(), gdal.config_options({"SHAPE_ENCODING": "CP949"}):
            with gdal.OpenEx("/vsizip/" + path.resolve().as_posix() + "/" + shapes[0],
                             gdal.OF_VECTOR, allowed_drivers=["ESRI Shapefile"],
                             open_options=["ENCODING=CP949"]) as dataset:
                layer = dataset.GetLayer(0)
                expected = layer.GetFeatureCount()
                count = 0
                for feature in layer:
                    if set(feature.items()) != set(mapping):
                        raise RuntimeError("TXT와 DBF field 집합이 다릅니다")
                    geometry = feature.GetGeometryRef()
                    if geometry is None or geometry.IsEmpty():
                        raise RuntimeError("조사 파일에 빈 geometry가 있습니다")
                    count += 1
                if count != expected:
                    raise RuntimeError("실제 반복 행수와 선언 count가 다릅니다")
                row = {"file": path.name, "gdal": gdal.VersionInfo(), "count": count,
                       "source_crs": None if layer.GetSpatialRef() is None else layer.GetSpatialRef().ExportToWkt(),
                       "field_mapping": mapping}
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
    if not rows:
        raise RuntimeError("검사할 ZIP이 없습니다")
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    result = inspect(args.directory)
    (args.directory / "gdal-probe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
