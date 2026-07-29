"""로컬 LLM CLI를 subprocess로 호출해 OpenAI 호환 응답 딕셔너리로 감싸는 어댑터.

실제 환경에서는 OLLAMA_CMD_TEMPLATE 같은 커맨드를 그대로 실행하면 된다.
API 키·네트워크 없이 데모를 돌리기 위해 기본 커맨드는 echo 스텁으로 대체했다.
"""
from __future__ import annotations

import logging
import subprocess
import time
from typing import Any

logger = logging.getLogger(__name__)

# 실제로는 이런 형태의 커맨드를 쓴다. 데모에서는 echo로 대체해 네트워크/모델 없이 확인한다.
OLLAMA_CMD_TEMPLATE = ["ollama", "run", "{model}", "{prompt}"]

_SUBPROCESS_TIMEOUT_SEC = 30.0


def _run_local_cli(cmd: list[str], timeout: float = _SUBPROCESS_TIMEOUT_SEC) -> str:
    """subprocess.run()으로 로컬 커맨드를 실행하고 stdout을 반환한다."""
    logger.info("executing local cli: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"local cli failed (rc={result.returncode}): {result.stderr.strip()}")
    return result.stdout.strip()


def local_chat_completion(
    model: str,
    prompt: str,
    *,
    cmd: list[str] | None = None,
) -> dict[str, Any]:
    """로컬 LLM 호출 결과를 OpenAI `/v1/chat/completions` 응답 형식으로 감싼다.

    cmd를 지정하지 않으면 echo 기반 데모 스텁을 사용한다(외부 바이너리 불필요).
    """
    if cmd is None:
        # 데모용 스텁: 실제로는 OLLAMA_CMD_TEMPLATE.format(model=model, prompt=prompt) 형태를 쓴다.
        cmd = ["echo", f"[local:{model}] echo-stub response for: {prompt}"]

    started = time.perf_counter()
    output = _run_local_cli(cmd)
    elapsed = time.perf_counter() - started

    return {
        "id": f"local-{int(time.time())}",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": output},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "_local_elapsed_sec": round(elapsed, 4),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    response = local_chat_completion(model="local-demo-7b", prompt="로컬 LLM 테스트 질문")
    print(response["choices"][0]["message"]["content"])
    print(f"elapsed: {response['_local_elapsed_sec']}s")

    # 실패 케이스: 존재하지 않는 커맨드
    try:
        local_chat_completion(model="broken", prompt="x", cmd=["nonexistent-binary-xyz"])
    except (RuntimeError, FileNotFoundError) as e:
        print(f"expected failure: {e}")
