# AgentForge 벤치마크 증빙 요약

실행 일시: 2026-04-06

이 디렉토리는 AgentForge 하네스에 대해 다음 두 종류의 실제 실행 증빙을 담습니다.

1. 품질 중심 벤치마크
- hidden tests 추가
- repeats 추가
- pass@k 계산
- quality score / efficiency score 분리

2. SWE-bench Lite 스타일 벤치마크
- issue_statement 기반
- repo template 기반
- public/hidden verifier 분리
- patch precision 측정 가능

## 생성된 결과물

- `agentforge_quality.json`
- `agentforge_quality_report.md`
- `agentforge_swe_style.json`
- `agentforge_swe_style_report.md`

## 핵심 결과

### 1) 품질 중심 벤치마크
- cases: 3
- runs: 6
- run_success_rate: 0.667
- case_pass_rate: 0.667
- pass@1: 0.667
- pass@2: 0.667
- avg_quality_score: 88.00
- avg_efficiency_score: 29.46

의미:
- public test만 보면 모두 통과한 케이스가 있었지만,
  hidden test에서 `config-loader-invalid-env`가 2회 모두 실패했습니다.
- 즉, 이전의 "속도/표면 성공" 중심 측정으로는 놓칠 수 있는 일반화 실패가 실제로 드러났습니다.
- 이 점이 이번 업그레이드의 가장 중요한 증빙입니다.

### 2) SWE-bench Lite 스타일 벤치마크
- cases: 2
- runs: 2
- run_success_rate: 1.000
- case_pass_rate: 1.000
- pass@1: 1.000
- avg_quality_score: 98.00
- avg_efficiency_score: 43.28

의미:
- issue_statement 기반의 리포지토리형 버그 수정 과제에서
  AgentForge가 public/hidden verifier를 모두 통과했습니다.
- 단순 함수 수정보다 실제 버그 리포트에 가까운 형식으로 평가가 가능함을 보여줍니다.

## 해석 포인트

- 이번 변경으로 벤치마크가 "얼마나 빨랐는가"만 보는 구조에서
  "public은 붙지만 hidden에서 떨어지는가", "반복 실행해도 안정적인가", "작업 품질과 효율을 분리해서 볼 수 있는가"를 보는 구조로 확장되었습니다.
- 특히 quality suite에서 hidden failure가 실제로 잡힌 것은
  업그레이드된 평가 체계가 유효하다는 강한 증빙입니다.
