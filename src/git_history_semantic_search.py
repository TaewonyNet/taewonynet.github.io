"""
git 커밋 히스토리를 자연어 질의로 검색하는 최소 PoC.

`git log`를 파싱해 커밋 레코드(hash/message/date)를 뽑고, 단어 집합 기반 목(mock)
임베딩으로 벡터화한 뒤 자연어 질의와 가장 가까운 커밋을 찾는다. 실제 코드
검색 인프라는 sqlite-vec(SQLite 확장)에 저장해 KNN 검색을 쓴다 — faiss가
아니다. 이 환경에 sqlite-vec가 설치돼 있으면 vec0 가상 테이블로 실제 KNN을
쓰고, 없으면 numpy 없는 순수 코사인 유사도로 대체한다.

여기서 쓰는 임베딩은 실제 임베딩 모델이 아니라 "단어 집합 해싱" 목 벡터다.
정확한 의미 유사도가 아니라 단어 겹침 정도를 흉내낸 것일 뿐이다.
"""
from __future__ import annotations

import hashlib
import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", stream=sys.stdout)
logger = logging.getLogger("GitHistorySemanticSearch")

try:
    import sqlite_vec  # type: ignore
    import sqlite3

    HAS_SQLITE_VEC = True
except ImportError:
    HAS_SQLITE_VEC = False
    logger.info("sqlite-vec 미설치 — 순수 코사인 유사도로 대체한다")

EMBED_DIM = 64
TOKEN_RE = re.compile(r"[a-zA-Z0-9가-힣_]+")


@dataclass
class CommitRecord:
    commit_hash: str
    date: str
    message: str


def parse_git_log(repo_dir: Path, max_count: int = 200) -> list[CommitRecord]:
    """`git log --format=...`을 파싱해 커밋 레코드(hash/date/message) 목록을 만든다."""
    sep = "\x1f"
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "log", f"--format=%H{sep}%ad{sep}%s", "--date=short", "-n", str(max_count)],
        capture_output=True, text=True, check=True,
    )
    records = []
    for line in result.stdout.splitlines():
        parts = line.split(sep)
        if len(parts) != 3:
            continue
        commit_hash, date, message = parts
        records.append(CommitRecord(commit_hash=commit_hash, date=date, message=message))
    logger.info("git log 파싱: %d개 커밋", len(records))
    return records


def word_set_embed(text: str, dim: int = EMBED_DIM) -> list[float]:
    """단어 집합을 해시 버킷에 누적하는 목 임베딩. 진짜 의미 임베딩이 아니라 단어 겹침 근사치다."""
    vec = [0.0] * dim
    tokens = TOKEN_RE.findall(text.lower())
    if not tokens:
        return vec
    for token in tokens:
        bucket = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % dim
        vec[bucket] += 1.0
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [v / norm for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def search_numpy(query_vec: list[float], embeddings: dict[str, list[float]], top_k: int = 5) -> list[tuple[str, float]]:
    """sqlite-vec 없이 순수 파이썬 코사인 유사도로 top_k를 찾는다."""
    scored = [(cid, cosine_similarity(query_vec, vec)) for cid, vec in embeddings.items()]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [(cid, score) for cid, score in scored[:top_k]]


def search_sqlite_vec(query_vec: list[float], embeddings: dict[str, list[float]], top_k: int = 5) -> list[tuple[str, float]]:
    """sqlite-vec의 vec0 가상 테이블로 실제 KNN 검색을 실행한다."""
    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    conn.execute(f"CREATE VIRTUAL TABLE vec_commits USING vec0(embedding float[{EMBED_DIM}])")
    id_by_rowid: dict[int, str] = {}
    for rowid, (cid, vec) in enumerate(embeddings.items(), start=1):
        conn.execute(
            "INSERT INTO vec_commits(rowid, embedding) VALUES (?, ?)",
            (rowid, sqlite_vec.serialize_float32(vec)),
        )
        id_by_rowid[rowid] = cid

    rows = conn.execute(
        "SELECT rowid, distance FROM vec_commits WHERE embedding MATCH ? AND k = ? ORDER BY distance",
        (sqlite_vec.serialize_float32(query_vec), top_k),
    ).fetchall()
    conn.close()
    # vec0 distance는 L2 거리(작을수록 유사) — cosine_similarity와 방향을 맞추려고 부호만 반전한다.
    return [(id_by_rowid[rowid], -distance) for rowid, distance in rows]


def search(query: str, records: list[CommitRecord], top_k: int = 5) -> list[tuple[CommitRecord, float]]:
    embeddings = {r.commit_hash: word_set_embed(r.message) for r in records}
    query_vec = word_set_embed(query)

    if HAS_SQLITE_VEC:
        ranked = search_sqlite_vec(query_vec, embeddings, top_k)
    else:
        ranked = search_numpy(query_vec, embeddings, top_k)

    by_hash = {r.commit_hash: r for r in records}
    return [(by_hash[cid], score) for cid, score in ranked]


def find_repo_root(start: Path) -> Path:
    """`start`에서 위로 올라가며 `.git`이 있는 첫 디렉터리(저장소 루트)를 찾는다."""
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError(f"{start} 위로 git 저장소를 찾지 못함")


if __name__ == "__main__":
    repo_root = find_repo_root(Path(__file__).resolve().parent)
    commits = parse_git_log(repo_root, max_count=300)

    queries = ["양자화로 모델 크기 줄이기", "스크래핑 봇 우회", "증분 수집 파이프라인"]
    for q in queries:
        print(f"\n쿼리: {q!r} (검색엔진: {'sqlite-vec vec0' if HAS_SQLITE_VEC else 'numpy 없는 순수 코사인'})")
        for record, score in search(q, commits, top_k=3):
            print(f"  {score:>7.4f}  {record.date}  {record.commit_hash[:7]}  {record.message[:60]}")
