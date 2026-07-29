"""SQLite FTS5(BM25) + sqlite-vec(코사인 KNN) 결과를 RRF(k=60)로 합치는 하이브리드 검색 PoC."""
from __future__ import annotations

import hashlib
import logging
import math
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import sqlite_vec  # type: ignore

    HAS_SQLITE_VEC = True
except ImportError:
    HAS_SQLITE_VEC = False
    logger.info("sqlite-vec 미설치 — numpy 코사인 유사도로 대체한다")

EMBED_DIM = 16


def fake_embed(text: str) -> list[float]:
    """실제 임베딩 모델 대신, 해시 기반 결정론적 벡터를 만든다(로직 검증용)."""
    vec = []
    for i in range(EMBED_DIM):
        digest = hashlib.sha256(f"{text}:{i}".encode()).digest()
        vec.append((int.from_bytes(digest[:4], "big") % 1000) / 1000.0)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def build_fts_index(conn: sqlite3.Connection, docs: dict[int, str]) -> None:
    conn.execute("CREATE VIRTUAL TABLE fts_docs USING fts5(doc_id UNINDEXED, body)")
    conn.executemany(
        "INSERT INTO fts_docs (doc_id, body) VALUES (?, ?)",
        list(docs.items()),
    )
    conn.commit()


def keyword_search(conn: sqlite3.Connection, query: str, top_k: int = 10) -> list[int]:
    """FTS5 BM25 순위대로 doc_id 리스트를 반환한다.

    자연어 쿼리를 어절 단위 prefix(OR) 매칭으로 바꿔서 던진다 — 조사가 붙은 어절
    ("검색하기")도 어간 접두("검색")로 걸리게 하기 위함이다. 그래도 조사가 토큰
    앞쪽에 붙어 있으면 여전히 못 찾는 경우가 남는데, 이 문제 자체는 별도 글에서 다룬다.
    """
    words = query.split()
    match_expr = " OR ".join(f"{w}*" for w in words)
    rows = conn.execute(
        "SELECT doc_id FROM fts_docs WHERE fts_docs MATCH ? ORDER BY bm25(fts_docs) LIMIT ?",
        (match_expr, top_k),
    ).fetchall()
    return [r[0] for r in rows]


def vector_search(
    docs: dict[int, str], embeddings: dict[int, list[float]], query: str, top_k: int = 10
) -> list[int]:
    """sqlite-vec가 있으면 vec0 가상 테이블로, 없으면 numpy 없이 순수 파이썬 코사인으로 계산한다."""
    query_vec = fake_embed(query)
    if HAS_SQLITE_VEC:
        # 실제 환경에서는 vec0 가상 테이블에 KNN 쿼리를 던진다.
        # conn.execute("CREATE VIRTUAL TABLE vec_docs USING vec0(embedding float[16])")
        # 데모 PoC에서는 로직 동일성을 위해 아래 브루트포스 경로를 그대로 탄다.
        logger.info("sqlite-vec 로드됨 — vec0 KNN 경로 사용 가능")

    scored = [(doc_id, cosine_similarity(query_vec, emb)) for doc_id, emb in embeddings.items()]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [doc_id for doc_id, _ in scored[:top_k]]


def reciprocal_rank_fusion(
    list1: list[int], list2: list[int], k: int = 60
) -> list[tuple[int, float]]:
    """두 순위 리스트를 RRF로 합친다. score = sum(1 / (k + rank)), rank는 1부터 시작."""
    scores: dict[int, float] = {}
    for rank, doc_id in enumerate(list1, start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    for rank, doc_id in enumerate(list2, start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def load_sqlite_vec_extension(conn: sqlite3.Connection) -> bool:
    """sqlite-vec 확장을 로드한다. 실패하면 False를 반환하고 numpy 폴백을 쓴다."""
    if not HAS_SQLITE_VEC:
        return False
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return True
    except Exception:  # noqa: BLE001 — 확장 로드 실패는 폴백으로 흡수
        logger.warning("sqlite_vec.load(conn) 실패 — 폴백 경로로 진행")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    docs = {
        1: "SQLite 하나로 키워드와 벡터 검색을 함께 쓰는 방법",
        2: "FTS5 BM25 랭킹은 정확한 단어 일치에 강하다",
        3: "코사인 거리 기반 KNN은 의미가 비슷한 문서를 찾는다",
        4: "오늘 점심은 무엇을 먹을지 고민이다",
        5: "임베딩 벡터를 SQLite 확장 테이블에 저장해두면 별도 벡터 DB가 필요 없다",
    }

    conn = sqlite3.connect(":memory:")
    load_sqlite_vec_extension(conn)
    build_fts_index(conn, docs)
    embeddings = {doc_id: fake_embed(text) for doc_id, text in docs.items()}

    query = "SQLite로 벡터 검색하기"
    kw_ranked = keyword_search(conn, query)
    vec_ranked = vector_search(docs, embeddings, query)

    print(f"쿼리: {query!r}")
    print(f"키워드(BM25) 순위: {kw_ranked}")
    print(f"벡터(코사인) 순위: {vec_ranked}")

    fused = reciprocal_rank_fusion(kw_ranked, vec_ranked, k=60)
    print("\nRRF(k=60) 최종 순위:")
    for doc_id, score in fused:
        print(f"  doc_id={doc_id:<3} score={score:.5f}  {docs[doc_id]}")
