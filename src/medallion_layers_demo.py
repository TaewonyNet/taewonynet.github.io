"""
Bronze/Silver/Gold 메달리온 구조가 "왜 계층을 나누는지"를 보여주는 최소 PoC.

토이 데이터로 3단계 함수를 순서대로 실행한다.
    - ingest_bronze: 원본을 가공 없이 그대로 저장 + 수집 시각 메타데이터 기록.
    - refine_silver: Bronze를 다시 읽어 정제(공백 정리)·중복 제거.
    - build_gold: Silver를 읽어 서빙용 요약(문서 수, 목록)을 만든다.

핵심 데모: Silver의 중복 제거 로직에 처음엔 버그가 있다(대소문자·공백
차이를 못 잡아 같은 내용이 중복으로 남는다). 이 버그를 고친 뒤에도
원본을 다시 수집할 필요가 없다 — Bronze가 그대로 남아있으니 Silver부터
다시 만들면 된다. 계층을 나누지 않고 수집과 동시에 정제해버렸다면
이 재처리 자체가 불가능했을 것이다.

독립 실행:
    python3 medallion_layers_demo.py
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("medallion_layers_demo")

# 원본 데이터. 같은 내용인데 공백·대소문자만 다른 "사실상 중복" 레코드가 섞여 있다.
RAW_RECORDS: list[dict] = [
    {"id": "r1", "source": "manual", "text": "  검색 인프라 설계 노트  "},
    {"id": "r2", "source": "manual", "text": "검색 인프라 설계 노트"},  # r1과 공백만 다른 중복
    {"id": "r3", "source": "manual", "text": "Reranking 벤치마크 결과"},
    {"id": "r4", "source": "manual", "text": "reranking 벤치마크 결과"},  # r3와 대소문자만 다른 중복
    {"id": "r5", "source": "manual", "text": "증분 수집 매니페스트 설계"},
]


def ingest_bronze(raw_records: list[dict], bronze_path: Path) -> list[dict]:
    """원본을 가공 없이 그대로 저장하고, 수집 시각 메타데이터만 덧붙인다.

    text 필드는 절대 손대지 않는다 — 공백·대소문자를 포함해 원본 그대로 보존한다.
    """
    now = datetime.now(timezone.utc).isoformat()
    bronze_records = [
        {**record, "_ingested_at": now, "_layer": "bronze"} for record in raw_records
    ]
    bronze_path.parent.mkdir(parents=True, exist_ok=True)
    bronze_path.write_text(
        json.dumps(bronze_records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Bronze 저장: %s (%d건, 원본 그대로)", bronze_path, len(bronze_records))
    return bronze_records


def refine_silver(bronze_path: Path, silver_path: Path, normalize: bool) -> list[dict]:
    """Bronze를 다시 읽어 정제(공백 정리)·중복 제거한 뒤 Silver로 저장한다.

    normalize=False: 초기 버전. `text.strip()`만 하고 대소문자는 그대로 둔다.
        앞뒤 공백만 다른 중복(r1/r2)은 잡지만, "Reranking"과 "reranking"처럼
        대소문자만 다른 중복(r3/r4)은 서로 다른 문자열로 취급해 놓친다.
    normalize=True: 수정 버전. 공백 정리 + 소문자 변환까지 같이 비교해
        대소문자 차이로 인한 중복(r3/r4)까지 잡아낸다.
    """
    bronze_records = json.loads(bronze_path.read_text(encoding="utf-8"))

    def dedup_key(text: str) -> str:
        cleaned = text.strip()
        return cleaned.lower() if normalize else cleaned

    seen: dict[str, str] = {}
    silver_records = []
    for record in bronze_records:
        cleaned_text = record["text"].strip()
        key = dedup_key(record["text"])
        if key in seen:
            logger.info("  중복 제외: %s (%r는 이미 있는 %s와 중복)", record["id"], cleaned_text, seen[key])
            continue
        seen[key] = record["id"]
        silver_records.append({"id": record["id"], "text": cleaned_text, "_layer": "silver"})

    silver_path.parent.mkdir(parents=True, exist_ok=True)
    silver_path.write_text(
        json.dumps(silver_records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(
        "Silver 저장: %s (%d건 -> %d건, normalize=%s)",
        silver_path, len(bronze_records), len(silver_records), normalize,
    )
    return silver_records


def build_gold(silver_path: Path, gold_path: Path) -> dict:
    """Silver를 읽어 서빙용 최종 요약을 만든다."""
    silver_records = json.loads(silver_path.read_text(encoding="utf-8"))
    gold = {
        "doc_count": len(silver_records),
        "titles": [record["text"] for record in silver_records],
    }
    gold_path.parent.mkdir(parents=True, exist_ok=True)
    gold_path.write_text(json.dumps(gold, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Gold 저장: %s (문서 %d건)", gold_path, gold["doc_count"])
    return gold


def main() -> None:
    workdir = Path(__file__).parent / "downloads" / "medallion_layers_demo"
    bronze_path = workdir / "bronze.json"
    silver_path = workdir / "silver.json"
    gold_path = workdir / "gold.json"

    print("[1단계] Bronze 적재 — 원본 그대로")
    ingest_bronze(RAW_RECORDS, bronze_path)

    print("\n[2단계] Silver 정제 — 버그 있는 버전 (normalize=False)")
    silver_v1 = refine_silver(bronze_path, silver_path, normalize=False)
    build_gold(silver_path, gold_path)
    print(f"  -> 최종 문서 수: {len(silver_v1)} (기대: 3, 대소문자 차이 중복이 안 잡혀 4로 남음)")

    print("\n[3단계] Silver 정제 로직만 수정 후 재실행 — Bronze는 다시 수집하지 않는다 (normalize=True)")
    silver_v2 = refine_silver(bronze_path, silver_path, normalize=True)
    build_gold(silver_path, gold_path)
    print(f"  -> 최종 문서 수: {len(silver_v2)} (기대: 3)")

    print(
        "\n원본 재수집 없이 Bronze만 다시 읽어서 Silver/Gold를 처음부터 다시 만들었다."
        f" ({len(RAW_RECORDS)}건 -> 1차 {len(silver_v1)}건 -> 2차 {len(silver_v2)}건)"
    )


if __name__ == "__main__":
    main()
