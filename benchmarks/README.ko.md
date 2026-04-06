# AgentForge 벤치마크 가이드

이 폴더는 AgentForge를 "모델 자체"가 아니라 "에이전트 하네스"로 평가하기 위한 벤치마크 도구 모음입니다.

핵심 목표는 두 가지입니다.
1. 품질 중심 하네스 벤치마크
2. SWE-bench Lite 스타일의 실제 버그 수정 평가

즉, 단순히 "얼마나 빨랐나"가 아니라 아래를 같이 봅니다.
- public test 통과 여부
- hidden test 통과 여부
- repeat 실행 시 pass@k
- quality score
- efficiency score
- 불필요한 파일 변경 여부

## 구성 파일

- `run_agentforge_benchmark.py`
  - AgentForge 하네스 실행기
- `run_codex_baseline.py`
  - 단일 Codex baseline 실행기
- `compare_agentforge_vs_codex.py`
  - 두 결과 JSON 비교기
- `benchmark_metrics.py`
  - pass@k, quality score, efficiency score 계산
- `benchmark_task_utils.py`
  - hidden verifier, 작업 디렉토리 snapshot, changed file 계산
- `tasks.quality.json`
  - hidden tests + repeats + quality score 예시 스위트
- `tasks.swe_lite_style.json`
  - SWE-bench Lite 스타일 예시 스위트
- `templates/swe_lite/*`
  - 리포지토리형 태스크 템플릿
- `hidden/*`
  - 에이전트가 보지 못하는 hidden verifier 자산

## 왜 lm-eval만으로는 부족한가?

`lm-evaluation-harness`는 보통 "모델" 품질 평가용입니다.
하지만 AgentForge는 다음이 결합된 시스템입니다.
- Worker/Evaluator 루프
- 파일 시스템 조작
- 셸 명령 실행
- 반복/롤백/평가 정책

그래서 AgentForge 평가는 아래 지표가 더 중요합니다.
- run success rate
- case pass rate
- pass@k
- hidden test 통과율
- quality score
- efficiency score

## 스코어 정의

### 1) Quality score (0~100)

가능한 경우 다음 성분을 가중합으로 계산합니다.
- DONE 판정: 10%
- public verify 통과: 45%
- hidden verify 통과: 35%
- edit precision: 10%

edit precision은 `expected_changed_files` / `allowed_changed_files` 기준으로 계산됩니다.
즉, 정답을 맞추는 것뿐 아니라 불필요한 파일을 건드리지 않았는지도 반영합니다.

### 2) Efficiency score (0~100)

quality score를 전제로 아래를 반영합니다.
- duration
- attempts
- tool call 수 또는 command execution 수

즉, quality가 낮으면 efficiency도 낮고,
quality가 높더라도 너무 느리거나 과도하게 많은 도구를 쓰면 efficiency가 내려갑니다.

## hidden tests 방식

`hidden_verify`는 workdir 바깥의 숨겨진 디렉토리에서 실행됩니다.
러너는 아래 환경변수를 주입합니다.
- `TARGET_WORKDIR`
- `BENCH_WORKDIR`
- `BENCH_HIDDEN_DIR`

hidden test는 이 경로를 이용해 대상 코드를 import/검증합니다.
AgentForge는 기본적으로 이 hidden 자산을 목표 프롬프트에서 받지 않으므로, public test만 보고 과적합하는지 확인할 수 있습니다.

## repeat / pass@k

각 태스크는 `repeats`를 가질 수 있습니다.
예를 들어 repeats=3이면 같은 태스크를 3번 독립적으로 실행합니다.
그 결과로 다음을 계산합니다.
- run success rate
- case pass rate
- pass@1, pass@2, pass@3

에이전트 시스템은 실행마다 편차가 있기 때문에 pass@k는 매우 중요한 품질 지표입니다.

## 태스크 포맷

필수:
- `id`
- `goal` 또는 `issue_statement`

선택:
- `files`
- `mkdirs`
- `template_dir`
- `hidden_files`
- `hidden_template_dir`
- `public_verify` 또는 `verify`
- `hidden_verify`
- `repeats`
- `init_git`
- `expected_changed_files`
- `allowed_changed_files`
- `target_duration_seconds`
- `target_tool_calls`
- `target_command_executions`

`files` / `hidden_files` 값은 `@file:relative/path.py`를 지원합니다.

## 빠른 시작

### 1. 품질 벤치마크 드라이런

```bash
python benchmarks/run_agentforge_benchmark.py \
  --tasks benchmarks/tasks.quality.json \
  --dry-run
```

### 2. 품질 벤치마크 실제 실행

```bash
python benchmarks/run_agentforge_benchmark.py \
  --tasks benchmarks/tasks.quality.json \
  --worker-model gpt-5.4 \
  --eval-model gpt-5.4 \
  --output benchmarks/results/agentforge_quality.json
```

### 3. SWE-style 벤치마크 실행

```bash
python benchmarks/run_agentforge_benchmark.py \
  --tasks benchmarks/tasks.swe_lite_style.json \
  --worker-model gpt-5.4 \
  --eval-model gpt-5.4 \
  --output benchmarks/results/agentforge_swe_style.json
```

### 4. 단일 Codex baseline

```bash
python benchmarks/run_codex_baseline.py \
  --tasks benchmarks/tasks.quality.json \
  --model gpt-5.4 \
  --output benchmarks/results/codex_quality.json
```

### 5. 비교

```bash
python benchmarks/compare_agentforge_vs_codex.py \
  --agentforge benchmarks/results/agentforge_quality.json \
  --codex benchmarks/results/codex_quality.json
```

## SWE-bench Lite 스타일 확장 포인트

`tasks.swe_lite_style.json`은 논문/외부 설명에 더 가까운 형식을 흉내 냅니다.
- issue_statement 중심
- repo template 기반
- public + hidden verify 분리
- expected_changed_files 기반 patch precision 측정

다음 단계로는 아래가 가능합니다.
- 실제 오픈소스 리포지토리 snapshot 사용
- bug report/issue 본문 자동 주입
- patch diff 저장
- multi-repo suite 구성
- official SWE-bench Lite instance 변환기 추가

## 추천 해석법

- quality score가 높고 efficiency score도 높다
  - 정확하고 효율적인 하네스
- quality score는 높지만 efficiency score가 낮다
  - 맞추긴 하지만 너무 느리거나 도구를 많이 씀
- public은 통과하지만 hidden이 낮다
  - 과적합 또는 일반화 부족
- pass@1은 낮지만 pass@k가 높다
  - 잠재력은 있으나 안정성이 낮음
