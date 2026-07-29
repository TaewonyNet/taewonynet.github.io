"""
크롬 웹 스토어 확장을 CRX로 내려받아 폴더로 풀어내는 도구.

웹 스토어 URL이나 확장 ID를 주면 ① 비공식 update2 엔드포인트에서 CRX를 받고
② CRX(2/3) 헤더를 건너뛰어 ZIP 본문만 추출해 ③ 폴더로 압축해제한다.
이 폴더를 셀레니움 `--load-extension` 에 그대로 넘기면 확장이 적용된다.

requirements: requests
"""

import logging
import re
import struct
import zipfile
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ChromeExtDownloader")

# 웹 스토어의 비공식 CRX 다운로드 엔드포인트
# prodversion이 낮으면 204를 주므로 충분히 높게(=항상 최신) 둔다
CRX_URL = ("https://clients2.google.com/service/update2/crx"
           "?response=redirect&prodversion=9999.0&acceptformat=crx2,crx3"
           "&x=id%3D{id}%26installsource%3Dondemand%26uc")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")


def extract_id(url_or_id: str) -> str:
    """웹 스토어 URL 또는 ID에서 32자 확장 ID를 뽑는다."""
    m = re.search(r"[a-p]{32}", url_or_id)
    if not m:
        raise ValueError(f"확장 ID를 찾지 못함: {url_or_id}")
    return m.group(0)


def download_crx(ext_id: str, crx_path: Path) -> None:
    r = requests.get(CRX_URL.format(id=ext_id), headers={"User-Agent": UA},
                     stream=True, timeout=20)
    r.raise_for_status()
    if r.status_code == 204:
        raise RuntimeError("204 No Content — 잘못된 ID이거나 비공개 확장")
    crx_path.write_bytes(r.content)
    logger.info(f"CRX 저장: {crx_path} ({crx_path.stat().st_size} bytes)")


def crx_to_zip_bytes(crx: bytes) -> bytes:
    """CRX2/CRX3 헤더를 건너뛰고 ZIP 본문만 반환한다."""
    if crx[:4] != b"Cr24":
        raise ValueError("CRX 매직(Cr24)이 아님")
    version = struct.unpack("<I", crx[4:8])[0]
    if version == 2:
        pubkey_len, sig_len = struct.unpack("<II", crx[8:16])
        offset = 16 + pubkey_len + sig_len
    elif version == 3:
        header_len = struct.unpack("<I", crx[8:12])[0]
        offset = 12 + header_len
    else:
        raise ValueError(f"지원하지 않는 CRX 버전: {version}")
    return crx[offset:]


def process(url_or_id: str, out_dir: str = "extensions") -> Path:
    ext_id = extract_id(url_or_id)
    base = Path(out_dir) / ext_id
    base.mkdir(parents=True, exist_ok=True)

    crx_path = base / f"{ext_id}.crx"
    download_crx(ext_id, crx_path)

    zip_path = base / f"{ext_id}.zip"
    zip_path.write_bytes(crx_to_zip_bytes(crx_path.read_bytes()))

    extract_dir = base / "unpacked"
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(extract_dir)
    crx_path.unlink(missing_ok=True)
    zip_path.unlink(missing_ok=True)
    logger.info(f"압축 해제: {extract_dir}")
    return extract_dir


if __name__ == "__main__":
    import json
    # uBlock Origin Lite (공개·무해한 예시 확장)
    url = "https://chromewebstore.google.com/detail/ddkjiahejlhfcafbddmgiahcphecmpfh"
    path = process(url)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    print("확장 폴더:", path)
    print("이름:", manifest.get("name"), "| 버전:", manifest.get("version"))
    print("→ 셀레니움: Driver(extensions=[str(path)])")
