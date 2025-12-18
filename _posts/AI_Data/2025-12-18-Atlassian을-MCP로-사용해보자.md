---
title: Atlassian을 MCP로 사용해 보자
description: Atlassian을 MCP로 사용할 수 있는 방법과 실제 듀토리얼을 해보자
author: taewony
date: 2025-12-18 22:40:00 +0900
categories: [Development, AI/Data]
tags: [Atlassian, mcp, tutorial, docker, confluence, jira, llm]
pin: false
math: false
mermaid: false
---
## 아틀라시안(Atlassian)을 MCP로 사용해 보자
아틀라시안(Atlassian)을 MCP로 사용할 수 있는 방법과 실제 듀토리얼을 해보자

### 1. 서론 (Introduction)
- **문제/상황 (Problem):**
    - 컨플루언스(Confluence)와 지라(Jira)가 별도로 동작하여 업무와 문서가 따로논다.
    - 문서를 통합하고 히스토리를 관리 할 수 있도록 MCP를 연동하고 싶다. 
- **목적 (Purpose):**
    - 아틀라시안(Atlassian)을 MCP로 연결하는 듀토리얼 제시하여 실무에 활용한다.
- **대상 (Target Audience):**
    - 컨플루언스(Confluence)와 지라(Jira)를 LLM에 활용하고 싶은 사람. 

### 2. 방법 및 과정 (Methods & Process)
- **배경 조사 및 데이터 (Data Collection):**
    - GPT와 GEMINI에게 물어봐서 확인했으나 정식 서비스를 알려줘 실행해보았으나 정상 동작하지 않았다.
    - DE 오픈채팅방에 물어봐 GitHub 저장소 [mcp-atlassian](https://github.com/sooperset/mcp-atlassian){: target="_blank"}를 획득하여 동작을 확인한다.
- **접근 방법 (Approach Methods):**
    - **[방법 1]:** 아틀라시안(Atlassian)에서 [API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens){: target="_blank"}을 발급받아 인증을 설정한다.
    - **[방법 2]:** Docker 이미지를 pull하여 mcp 서버를 실행 할 준비를 한다.
      - ```
        docker pull ghcr.io/sooperset/mcp-atlassian:latest
        ```
    - **[방법 3]:** `mcp.json` 처럼 설정파일을 생성하여 환경변수를 넣고 `컨플루언스 지라 mcp 접속 가능확인`을 프롬프트로 작성하여 실행한다.
      - ```
        {
          "mcpServers": {
            "mcp-atlassian": {
              "command": "docker",
              "args": [
                "run", "-i", "--rm",
                "-e", "CONFLUENCE_URL", "-e", "CONFLUENCE_USERNAME", "-e", "CONFLUENCE_API_TOKEN",
                "-e", "JIRA_URL", "-e", "JIRA_USERNAME", "-e", "JIRA_API_TOKEN",
                "ghcr.io/sooperset/mcp-atlassian:latest"
              ],
              "env": {
                "CONFLUENCE_URL": "https://<YOUR_COMPANY>.atlassian.net/wiki",
                "CONFLUENCE_USERNAME": "<YOUR_EMAIL@example.com>",
                "CONFLUENCE_API_TOKEN": "<YOUR_CONFLUENCE_API_TOKEN>",
                "JIRA_URL": "https://<YOUR_COMPANY>.atlassian.net",
                "JIRA_USERNAME": "<YOUR_EMAIL@example.com>",
                "JIRA_API_TOKEN": "<YOUR_JIRA_API_TOKEN>"
              }
            }
          }
        }
        ```
- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** 커서(Cursor) IDE를 사용해 .cursor/mcp.json 파일을 편집한다. - 다른 IDE는 다른 방식으로 진행해야 한다.
    - **주요 단계:** 아틀라시안(Atlassian) 토큰 발급 $\rightarrow$ Docker 이미지 pull $\rightarrow$ 설정 파일 작성 $\rightarrow$ 연결 테스트.
    - **결과 도출 및 검증:** 커서(Cursor)를 이용하여 MCP가 정상 동작하는지 확인하고 간단한 프롬프트로 정상 조회되는지 확인한다.

### 3. 결과 (Results)
- **분석 결과 요약:**
    - 컨플루언스(Confluence)와 지라(Jira)가 MCP를 통해 연결 되어 검색 및 요약 등 활용 가능 해졌다.

### 4. 인사이트 및 액션 (Insights & Action)
- **인사이트 (Insight):**
    - 컨플루언스(Confluence)와 지라(Jira)를 MCP로 활용하여 활용 폭이 넓어졌다. 
- **실행 방안 (Action Plan):**
    - 실제 문서를 MCP를 활용해 요약하고 프로젝트에 활용한다.
- **한 줄 결론 (Key Takeaway):**
    - 아틀라시안(Atlassian)을 MCP로 연결하면 LLM 활용이 매우 편리하게 할 수 있다.
- **다음 스텝 (Next Step):**
    - 최신 문서 요약 등 활용 방안 확인 한다. 
