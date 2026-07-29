"""
Bronze/Silver/Gold 메달리온 구조에서 manifest.json으로 증분 수집을 하는 최소 PoC.

- Bronze: 원본을 그대로 보존한다. 각 레코드의 해시(hash)·수정시각(mtime)을
  manifest.json에 기록해 "이전에 뭘 봤는지"를 남긴다.
- Silver: 이번 스냅샷과 직전 manifest를 비교(diff)해 added/modified/deleted만
  가려낸다. unchanged는 재처리하지 않는다.
- Gold: 여기서는 다루지 않는다(검색용 최종 색인 단계는 범위 밖).

git 소스라면 해시 비교 대신 `git diff --name-status <prev>..HEAD`로 같은
last_change(added/modified/deleted)를 계산할 수 있다. 이 파일 끝의
git_change_status()가 그 예시다.
"""
from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", stream=sys.stdout)
logger = logging.getLogger("MedallionManifestPipeline")

ManifestEntry = dict  # {"hash": str, "mtime": str}
Manifest = dict  # {record_id: ManifestEntry}
DiffResult = dict  # {"added": [...], "modified": [...], "deleted": [...], "unchanged": [...]}


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_manifest_entries(records: dict[str, str]) -> Manifest:
    """레코드 딕셔너리(id -> content)로부터 hash/mtime 엔트리를 만든다."""
    now = datetime.now(timezone.utc).isoformat()
    return {rid: {"hash": _hash_content(content), "mtime": now} for rid, content in records.items()}


def write_manifest(path: Path, records: dict[str, str]) -> Manifest:
    """Bronze 스냅샷의 manifest.json을 만들어 저장하고, 그 내용을 반환한다."""
    manifest = build_manifest_entries(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("manifest 저장: %s (%d건)", path, len(manifest))
    return manifest


def diff_manifest(old: Manifest, new: Manifest) -> DiffResult:
    """직전 manifest(old)와 이번 manifest(new)를 비교해 added/modified/deleted/unchanged를 나눈다."""
    old_ids, new_ids = set(old), set(new)
    added = sorted(new_ids - old_ids)
    deleted = sorted(old_ids - new_ids)
    common = old_ids & new_ids
    modified = sorted(rid for rid in common if old[rid]["hash"] != new[rid]["hash"])
    unchanged = sorted(rid for rid in common if old[rid]["hash"] == new[rid]["hash"])
    return {"added": added, "modified": modified, "deleted": deleted, "unchanged": unchanged}


def ingest_incremental(records: dict[str, str], manifest: Manifest) -> tuple[DiffResult, Manifest]:
    """직전 manifest 대비 added/modified만 '처리됨'으로 표시하고, 새 manifest를 반환한다.

    unchanged는 재수집하지 않는다. deleted는 처리 대상이 아니라 색인 삭제 대상으로만 남긴다.
    """
    new_manifest = build_manifest_entries(records)
    diff = diff_manifest(manifest, new_manifest)
    processed = sorted(diff["added"] + diff["modified"])
    logger.info(
        "증분 처리 대상 %d건 (added=%d, modified=%d, deleted=%d, unchanged=%d, 재처리 없음)",
        len(processed), len(diff["added"]), len(diff["modified"]), len(diff["deleted"]), len(diff["unchanged"]),
    )
    return diff, new_manifest


def git_change_status(repo_dir: Path, prev_rev: str, current_rev: str = "HEAD") -> dict[str, str]:
    """git 소스에서 `git diff --name-status`로 last_change(A/M/D)를 계산하는 예시.

    manifest.json의 hash 비교 대신, git 저장소라면 커밋 범위 비교만으로
    added(A)/modified(M)/deleted(D)를 그대로 얻을 수 있다.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "diff", "--name-status", f"{prev_rev}..{current_rev}"],
        capture_output=True, text=True, check=True,
    )
    status_map = {"A": "added", "M": "modified", "D": "deleted"}
    changes: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        status, _, path_str = line.partition("\t")
        changes[path_str] = status_map.get(status[0], status)
    return changes


if __name__ == "__main__":
    workdir = Path(__file__).parent / "downloads" / "medallion_demo"
    manifest_path = workdir / "manifest.json"

    # 라운드 1: 초기 Bronze 스냅샷 (3건)
    round1 = {
        "doc-1": "결제 배치 처리 문서 v1",
        "doc-2": "검색 색인 스키마 문서",
        "doc-3": "리랭커 설정 가이드",
    }
    manifest_v1 = write_manifest(manifest_path, round1)

    # 라운드 2: doc-2 내용 수정 + doc-4 신규 + doc-3 삭제
    round2 = {
        "doc-1": "결제 배치 처리 문서 v1",  # 변경 없음
        "doc-2": "검색 색인 스키마 문서 (v2, 필드 추가)",  # modified
        "doc-4": "증분 수집 매니페스트 설계 문서",  # added
        # doc-3 없음 -> deleted
    }

    diff, manifest_v2 = ingest_incremental(round2, manifest_v1)
    print("\n[diff 결과]")
    for key in ("added", "modified", "deleted", "unchanged"):
        print(f"  {key:<10}: {diff[key]}")

    write_manifest(manifest_path, round2)

    # git 소스 예시 — 이 저장소 자체에 대해 최근 커밋 범위로 last_change를 계산해본다.
    try:
        repo_root = Path(__file__).resolve().parent
        while not (repo_root / ".git").exists() and repo_root != repo_root.parent:
            repo_root = repo_root.parent
        log = subprocess.run(
            ["git", "-C", str(repo_root), "log", "--format=%H", "-n", "2"],
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        if len(log) == 2:
            changes = git_change_status(repo_root, prev_rev=log[1], current_rev=log[0])
            print(f"\n[git diff 기반 last_change 예시] {log[1][:7]}..{log[0][:7]}")
            for path_str, status in list(changes.items())[:10]:
                print(f"  {status:<10} {path_str}")
        else:
            print("\n(git 로그가 2개 미만이라 git diff 예시는 생략)")
    except Exception as exc:  # noqa: BLE001 — 데모 보조 기능일 뿐, 실패해도 본 데모엔 영향 없음
        logger.warning("git diff 예시 실행 실패: %s", exc)
