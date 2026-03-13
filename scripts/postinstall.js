#!/usr/bin/env node
/**
 * AgentForge postinstall: Python 의존성 자동 설치
 */

'use strict';
const { execSync, spawnSync } = require('child_process');
const path = require('path');
const fs   = require('fs');

const RESET  = '\x1b[0m';
const CYAN   = '\x1b[36m';
const GREEN  = '\x1b[32m';
const YELLOW = '\x1b[33m';
const RED    = '\x1b[31m';
const BOLD   = '\x1b[1m';

console.log(`\n${BOLD}${CYAN}AgentForge — 설치 중...${RESET}`);
console.log('─'.repeat(44));

// ── 1. Python 탐색 ────────────────────────────────────
let python = null;
for (const bin of ['python3', 'python']) {
  const r = spawnSync(bin, ['-c',
    'import sys; exit(0 if sys.version_info >= (3,10) else 1)'
  ], { encoding: 'utf8' });
  if (r.status === 0) { python = bin; break; }
}

if (!python) {
  console.error(`${RED}✗ Python 3.10+ 을 찾을 수 없습니다.${RESET}`);
  console.error(`  https://www.python.org/downloads/ 에서 설치 후 다시 시도하세요.`);
  process.exit(1);
}
console.log(`${GREEN}✓${RESET} Python: ${spawnSync(python, ['--version'], { encoding: 'utf8' }).stdout.trim()}`);

// ── 2. pip로 의존성 설치 ──────────────────────────────
//    import명 / pip 패키지명이 다른 경우 분리
const PACKAGES = [
  { import: 'rich',           pip: 'rich',           required: true  },
  { import: 'prompt_toolkit', pip: 'prompt_toolkit', required: true  },
  { import: 'requests',       pip: 'requests',       required: true  },
  { import: 'rank_bm25',      pip: 'rank-bm25',      required: false },
  { import: 'tiktoken',       pip: 'tiktoken',       required: false },
];

// 이미 설치돼 있는지 확인
const missing = PACKAGES.filter(pkg => {
  const r = spawnSync(python, ['-c', `import ${pkg.import}`], { encoding: 'utf8' });
  return r.status !== 0;
});

if (missing.length === 0) {
  console.log(`${GREEN}✓${RESET} Python 패키지: 모두 설치됨`);
} else {
  const pipNames = missing.map(p => p.pip);
  console.log(`${YELLOW}▶ pip 설치 중: ${pipNames.join(', ')}${RESET}`);
  let ok = false;

  // 1차 시도: python -m pip install
  try {
    execSync(
      `${python} -m pip install ${pipNames.map(n => `"${n}"`).join(' ')} --quiet`,
      { stdio: 'inherit' }
    );
    ok = true;
  } catch (_) {
    // 2차 시도: --user 플래그 (시스템 pip 권한 없는 경우)
    try {
      execSync(
        `${python} -m pip install --user ${pipNames.map(n => `"${n}"`).join(' ')} --quiet`,
        { stdio: 'inherit' }
      );
      ok = true;
    } catch (_2) {}
  }

  if (ok) {
    console.log(`${GREEN}✓${RESET} 설치 완료: ${pipNames.join(', ')}`);
  } else {
    const required = missing.filter(p => p.required).map(p => p.pip);
    if (required.length > 0) {
      console.error(`${RED}✗ 자동 설치 실패. 수동으로 실행하세요:${RESET}`);
      console.error(`   pip install ${required.join(' ')}`);
      process.exit(1);
    } else {
      console.warn(`${YELLOW}⚠  선택적 패키지 설치 실패 (기능 일부 제한):${RESET}`);
      console.warn(`   pip install ${pipNames.join(' ')}`);
    }
  }
}

// ── 3. 스크립트 실행 권한 확인 ────────────────────────
const scriptPath = path.join(__dirname, '..', 'agentforge');
try {
  fs.chmodSync(scriptPath, 0o755);
} catch (_) {}

// ── 4. 완료 메시지 ────────────────────────────────────
console.log('─'.repeat(44));
console.log(`${GREEN}${BOLD}✓ AgentForge 설치 완료!${RESET}\n`);
console.log(`사용법:`);
console.log(`  ${CYAN}agentforge${RESET}               인터랙티브 실행`);
console.log(`  ${CYAN}agentforge -d /project${RESET}    작업 디렉토리 지정`);
console.log(`  ${CYAN}agentforge --help${RESET}         도움말\n`);
console.log(`${YELLOW}⚠  CHATGPT_AUTH 환경변수를 설정하세요 (ChatGPT 쿠키).${RESET}`);
console.log(`   export CHATGPT_AUTH="..."\n`);
