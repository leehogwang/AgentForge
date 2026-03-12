#!/usr/bin/env node
/**
 * AgentForge postinstall: Python 의존성 및 환경 확인
 */

const { execSync, spawnSync } = require('child_process');

const RESET  = '\x1b[0m';
const CYAN   = '\x1b[36m';
const GREEN  = '\x1b[32m';
const YELLOW = '\x1b[33m';
const RED    = '\x1b[31m';

function check(label, fn) {
  try {
    fn();
    console.log(`${GREEN}  ✓${RESET} ${label}`);
    return true;
  } catch {
    console.log(`${RED}  ✗${RESET} ${label}`);
    return false;
  }
}

console.log(`\n${CYAN}AgentForge — 환경 확인${RESET}`);
console.log('─'.repeat(40));

// 1. Python 3.10+
const pyOk = check('Python 3.10+', () => {
  const r = spawnSync('python3', ['--version'], { encoding: 'utf8' });
  if (r.status !== 0) throw new Error();
  const ver = r.stdout.trim().replace('Python ', '').split('.').map(Number);
  if (ver[0] < 3 || (ver[0] === 3 && ver[1] < 10)) throw new Error('version too low');
});

// 2. Python 패키지 목록
//    import명과 pip 패키지명이 다른 경우(rank_bm25 / rank-bm25 등) 분리
const pyPackages = [
  { import: 'rich',           pip: 'rich' },
  { import: 'prompt_toolkit', pip: 'prompt_toolkit' },
  { import: 'requests',       pip: 'requests' },
  { import: 'rank_bm25',      pip: 'rank-bm25' },  // RAG 검색
  { import: 'tiktoken',       pip: 'tiktoken' },    // 토큰 수 계산
];

const pkgResults = pyPackages.map(pkg => ({
  ...pkg,
  ok: check(`Python package: ${pkg.import}`, () => {
    const r = spawnSync('python3', ['-c', `import ${pkg.import}`], { encoding: 'utf8' });
    if (r.status !== 0) throw new Error();
  }),
}));

// 3. codex CLI
const codexOk = check('codex CLI', () => {
  const r = spawnSync('which', ['codex'], { encoding: 'utf8' });
  if (r.status !== 0) throw new Error();
});

console.log('─'.repeat(40));

// 누락 패키지 자동 설치 시도
const missing = pkgResults.filter(p => !p.ok).map(p => p.pip);
if (missing.length > 0) {
  console.log(`\n${YELLOW}▶ Python 패키지 설치 중: ${missing.join(', ')}${RESET}`);
  try {
    execSync(`pip install ${missing.join(' ')} --quiet`, { stdio: 'inherit' });
    console.log(`${GREEN}  ✓ 설치 완료: ${missing.join(', ')}${RESET}`);
  } catch {
    console.log(`${RED}  ✗ 자동 설치 실패. 수동으로 설치하세요:${RESET}`);
    console.log(`     pip install ${missing.join(' ')}`);
  }
}

if (!codexOk) {
  console.log(`\n${YELLOW}⚠  codex CLI가 필요합니다:${RESET}`);
  console.log('   https://github.com/openai/codex');
}

if (pyOk) {
  console.log(`\n${GREEN}✓ AgentForge 설치 완료!${RESET}`);
  console.log(`\n사용법:\n  ${CYAN}agentforge${RESET}              인터랙티브 실행`);
  console.log(`  ${CYAN}agentforge -d /project${RESET}   작업 디렉토리 지정`);
} else {
  console.log(`\n${RED}✗ Python 3.10+ 이 필요합니다.${RESET}`);
  process.exit(1);
}
