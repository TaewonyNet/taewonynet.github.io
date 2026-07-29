#!/usr/bin/env python3
"""GitHub 리포지토리를 상태 저장소처럼 써서 Colab 세션이 꺼져도 이어서 실행한다.

핵심은 `save_file()`의 SHA 패턴이다 — GitHub Contents API는 파일을 업데이트할 때
현재 파일의 SHA를 요구한다. 파일이 이미 있으면 SHA를 조회해 update, 없으면
새로 create 한다. 실제 GitHub 토큰(`GITHUB_TOKEN` env var)이 없는 환경에서는
같은 SHA 규칙을 흉내 낸 `MockRepo`로 대체해 로직만 자족적으로 실행한다.

requirements: PyGithub (선택, 없거나 GITHUB_TOKEN 미설정 시 MockRepo로 대체)
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Protocol

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class RepoLike(Protocol):
    """PyGithub의 `Repository`가 제공하는 것 중 이 스크립트가 쓰는 최소 인터페이스."""

    def get_contents(self, path: str) -> object: ...
    def update_file(self, path: str, message: str, content: bytes, sha: str) -> None: ...
    def create_file(self, path: str, message: str, content: bytes) -> None: ...


class MockRepo:
    """GITHUB_TOKEN이 없을 때 쓰는 인메모리 대체 리포지토리.

    실제 GitHub Contents API와 동일한 SHA 규칙(파일 내용이 바뀔 때마다 SHA 갱신,
    존재하지 않으면 조회 실패)을 흉내 낸다.
    """

    def __init__(self) -> None:
        self._files: dict[str, tuple[bytes, str]] = {}
        self.commits: list[tuple[str, str]] = []  # (path, message)

    def get_contents(self, path: str):
        if path not in self._files:
            raise FileNotFoundError(path)
        content, sha = self._files[path]
        return _MockContentFile(content, sha)

    def update_file(self, path: str, message: str, content: bytes, sha: str) -> None:
        current_sha = self._files[path][1]
        if current_sha != sha:
            raise RuntimeError(f"SHA 불일치(409 시뮬레이션): {path}")
        new_sha = hashlib.sha1(content).hexdigest()
        self._files[path] = (content, new_sha)
        self.commits.append((path, message))

    def create_file(self, path: str, message: str, content: bytes) -> None:
        if path in self._files:
            raise RuntimeError(f"이미 존재함(create 대신 update 필요): {path}")
        new_sha = hashlib.sha1(content).hexdigest()
        self._files[path] = (content, new_sha)
        self.commits.append((path, message))


class _MockContentFile:
    def __init__(self, content: bytes, sha: str) -> None:
        self.decoded_content = content
        self.sha = sha


def get_repo(repo_name: str = "demo/demo-repo") -> RepoLike:
    """`GITHUB_TOKEN`이 설정돼 있으면 실제 PyGithub 리포지토리를, 아니면 MockRepo를 반환한다."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning("GITHUB_TOKEN 미설정 — MockRepo로 대체한다.")
        return MockRepo()

    try:
        from github import Github
    except ImportError:
        logger.warning("PyGithub 미설치 — MockRepo로 대체한다.")
        return MockRepo()

    return Github(token).get_repo(repo_name)


def save_file(repo: RepoLike, path: str, content: bytes, message: str | None = None) -> str:
    """파일이 있으면 SHA를 조회해 update, 없으면 create 한다. 최종 커밋 메시지를 반환한다."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    message = message or f"crawl update {timestamp}"

    try:
        existing = repo.get_contents(path)
        repo.update_file(path, message, content, existing.sha)
        logger.info("update_file: %s (%s)", path, message)
    except FileNotFoundError:
        repo.create_file(path, message, content)
        logger.info("create_file: %s (%s)", path, message)

    return message


def read_file(repo: RepoLike, path: str) -> bytes:
    """리포지토리에 저장된 이전 실행 결과를 읽어온다."""
    return repo.get_contents(path).decoded_content


if __name__ == "__main__":
    repo = get_repo()
    result_path = "crawl_results/2026-03-20.json"

    # 1회차 — 세션 시작, 이전 결과 없음 → create_file
    save_file(repo, result_path, b'{"items": ["a", "b"]}')

    # "세션 재시작" 시뮬레이션 — 이전 결과를 불러와 병합
    previous = read_file(repo, result_path)
    logger.info("이전 실행 결과 로드: %s", previous)

    # 2회차 — 같은 경로에 새 결과 → SHA 조회 후 update_file
    save_file(repo, result_path, b'{"items": ["a", "b", "c"]}')

    if isinstance(repo, MockRepo):
        print(f"최종 커밋 이력: {repo.commits}")
