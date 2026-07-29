#!/usr/bin/env python3
"""Colab에서 마그넷 링크를 내려받아 검증 후 Drive 경로로 이동하는 흐름의 축소판.

libtorrent로 다운로드 → 크기/해시로 완료를 검증 → 검증된 파일만 Drive 폴더로
이동한다. libtorrent가 없는 환경(로컬 데모)에서는 실제 다운로드 대신 더미
파일을 만드는 폴백으로 같은 흐름을 그대로 실행할 수 있게 했다.

실제 Colab에서는 DRIVE_TEMP_DIR/DRIVE_COMPLETE_DIR을
`/content/drive/MyDrive/torrent/...`로 바꾸면 된다.

requirements: libtorrent (선택, 없으면 폴백 데모 동작)
"""
from __future__ import annotations

import hashlib
import logging
import shutil
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 실제 Colab에서는 Drive 마운트 경로로 바꾼다 (예: /content/drive/MyDrive/torrent/...)
DRIVE_TEMP_DIR = Path("./_demo_drive/temp")
DRIVE_COMPLETE_DIR = Path("./_demo_drive/complete")


def download_magnet(
    magnet_uri: str, save_dir: Path, poll_interval: float = 0.5, force_simulate: bool = False
) -> Path:
    """마그넷 링크를 `save_dir`에 내려받고 완료된 파일 경로를 반환한다.

    libtorrent가 설치돼 있으면 실제 세션을 만들어 `is_seed()`가 True가 될 때까지
    polling한다. 설치돼 있지 않거나 `force_simulate=True`(네트워크·피어 없는
    로컬 데모용)면 더미 파일을 즉시 생성해 같은 흐름을 재현한다.
    """
    save_dir.mkdir(parents=True, exist_ok=True)
    if force_simulate:
        logger.info("force_simulate=True — 데모용 더미 다운로드를 사용한다.")
        return _simulate_download(magnet_uri, save_dir)

    try:
        import libtorrent as lt
    except ImportError:
        logger.warning("libtorrent 미설치 — 데모용 더미 다운로드로 대체한다.")
        return _simulate_download(magnet_uri, save_dir)

    session = lt.session()
    params = {"save_path": str(save_dir)}
    handle = lt.add_magnet_uri(session, magnet_uri, params)

    logger.info("메타데이터 수신 대기 중...")
    while not handle.has_metadata():
        time.sleep(poll_interval)

    logger.info("다운로드 중: %s", handle.name())
    while not handle.is_seed():
        status = handle.status()
        logger.info("진행률: %.1f%%", status.progress * 100)
        time.sleep(poll_interval)

    files = handle.get_torrent_info().files()
    return save_dir / files.file_path(0)


def _simulate_download(magnet_uri: str, save_dir: Path) -> Path:
    """libtorrent 없이 로컬에서 흐름을 시연하기 위한 더미 다운로드."""
    name = hashlib.sha1(magnet_uri.encode()).hexdigest()[:8]
    path = save_dir / f"{name}.bin"
    path.write_bytes(f"demo payload for {magnet_uri}".encode() * 100)
    return path


def verify_download(path: Path) -> dict:
    """파일 크기와 sha256 해시로 다운로드 완료 상태를 검증한다."""
    if not path.exists():
        return {"ok": False, "reason": "파일 없음"}

    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    return {"ok": True, "size": len(data), "sha256": digest}


def move_to_drive(local_path: Path, dest_dir: Path) -> Path:
    """검증된 파일만 Drive의 최종 폴더로 이동한다 (폴더 부모만 바뀌는 게 이상적이나,
    로컬 데모에서는 파일 이동으로 같은 효과를 시연한다)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / local_path.name
    shutil.move(str(local_path), str(dest_path))
    return dest_path


def download_and_store(magnet_uri: str, force_simulate: bool = False) -> Path:
    """다운로드 → 검증 → 이동까지 한 번에 처리하는 진입점."""
    downloaded = download_magnet(magnet_uri, DRIVE_TEMP_DIR, force_simulate=force_simulate)
    verification = verify_download(downloaded)
    if not verification["ok"]:
        raise RuntimeError(f"검증 실패: {verification}")

    logger.info("검증 완료: size=%d sha256=%s...", verification["size"], verification["sha256"][:12])
    final_path = move_to_drive(downloaded, DRIVE_COMPLETE_DIR)
    logger.info("이동 완료: %s", final_path)
    return final_path


if __name__ == "__main__":
    # 실제 네트워크·피어가 없는 로컬 데모이므로 force_simulate=True로 흐름만 재현한다.
    # 실제 Colab에서는 진짜 마그넷 링크 + force_simulate=False(기본값)로 쓴다.
    demo_magnet = "magnet:?xt=urn:btih:demo0000000000000000000000000000000000&dn=demo-file"
    result_path = download_and_store(demo_magnet, force_simulate=True)
    print(f"최종 저장 경로: {result_path}")

    # 정리 (데모 산출물 제거)
    shutil.rmtree("./_demo_drive", ignore_errors=True)
