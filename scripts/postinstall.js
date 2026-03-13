#!/usr/bin/env node
/**
 * AgentForge postinstall: Python 의존성 자동 설치
 */

'use strict';
const { execSync, spawnSync } = require('child_process');
const path = require('path');
const fs   = require('fs');
const os   = require('os');

const RESET  = '\x1b[0m';
const CYAN   = '\x1b[36m';
const GREEN  = '\x1b[32m';
const YELLOW = '\x1b[33m';
const RED    = '\x1b[31m';
const BOLD   = '\x1b[1m';

const isWindows = os.platform() === 'win32';

console.log(`\n${BOLD}${CYAN}AgentForge — 설치 중...${RESET}`);
console.log('─'.repeat(44));

// ── 1. Python 탐색 (pip 있는 것 우선) ─────────────────
// Windows: py 런처 → python → python3
// Linux/Mac: python3 → python
const PYTHON_CANDIDATES = isWindows
  ? ['py', 'python', 'python3']
  : ['python3', 'python'];

function hasPip(bin) {
  const r = spawnSync(bin, ['-m', 'pip', '--version'], { encoding: 'utf8' });
  return r.status === 0;
}

function meetsVersion(bin) {
  // py 런처는 py -3 -c '...' 형식
  const args = (bin === 'py')
    ? ['-3', '-c', 'import sys; exit(0 if sys.version_info >= (3,10) else 1)']
    : ['-c', 'import sys; exit(0 if sys.version_info >= (3,10) else 1)'];
  const r = spawnSync(bin, args, { encoding: 'utf8' });
  return r.status === 0;
}

function getPythonVersion(bin) {
  const args = bin === 'py' ? ['-3', '--version'] : ['--version'];
  const r = spawnSync(bin, args, { encoding: 'utf8' });
  return (r.stdout || r.stderr || '').trim();
}

// pip 있고 버전 맞는 Python 탐색
let python = null;
for (const bin of PYTHON_CANDIDATES) {
  if (meetsVersion(bin) && hasPip(bin)) {
    python = bin;
    break;
  }
}

// pip 없지만 버전 맞는 Python → ensurepip으로 부트스트랩 시도
if (!python) {
  for (const bin of PYTHON_CANDIDATES) {
    if (!meetsVersion(bin)) continue;
    console.log(`${YELLOW}▶ ${bin}: pip 없음 → ensurepip 부트스트랩 시도...${RESET}`);
    const args = bin === 'py' ? ['-3', '-m', 'ensurepip', '--upgrade'] : ['-m', 'ensurepip', '--upgrade'];
    const r = spawnSync(bin, args, { encoding: 'utf8', stdio: 'inherit' });
    if (r.status === 0 && hasPip(bin)) {
      python = bin;
      console.log(`${GREEN}✓${RESET} pip 부트스트랩 완료`);
      break;
    }
  }
}

if (!python) {
  console.error(`\n${RED}✗ pip이 있는 Python 3.10+을 찾을 수 없습니다.${RESET}`);
  console.error(`\n해결 방법:`);
  if (isWindows) {
    console.error(`  1. https://python.org/downloads 에서 Python 설치`);
    console.error(`     (설치 시 "Add to PATH" 체크 필수)`);
    console.error(`  2. 설치 후 다시 실행: npm install -g agentforge-multi`);
  } else {
    console.error(`  sudo apt install python3-pip   # Ubuntu/Debian`);
    console.error(`  brew install python             # macOS`);
  }
  process.exit(1);
}

// py 런처는 실제 pip 실행 시 'py -3 -m pip ...' 형식 사용
const pipPrefix = python === 'py' ? ['py', '-3'] : [python];
console.log(`${GREEN}✓${RESET} Python: ${getPythonVersion(python)}`);

// ── 2. pip 패키지 설치 ────────────────────────────────
const PACKAGES = [
  { import: 'rich',           pip: 'rich',           required: true  },
  { import: 'prompt_toolkit', pip: 'prompt_toolkit', required: true  },
  { import: 'requests',       pip: 'requests',       required: true  },
  { import: 'rank_bm25',      pip: 'rank-bm25',      required: false },
  { import: 'tiktoken',       pip: 'tiktoken',       required: false },
];

// 이미 설치된 패키지 확인
const missing = PACKAGES.filter(pkg => {
  const args = [...pipPrefix.slice(1), '-c', `import ${pkg.import}`];
  const r = spawnSync(pipPrefix[0], args, { encoding: 'utf8' });
  return r.status !== 0;
});

if (missing.length === 0) {
  console.log(`${GREEN}✓${RESET} Python 패키지: 모두 설치됨`);
} else {
  const pipNames = missing.map(p => p.pip);
  console.log(`${YELLOW}▶ pip 설치 중: ${pipNames.join(', ')}${RESET}`);

  function tryInstall(extraFlags = []) {
    try {
      const cmd = [
        ...pipPrefix,
        '-m', 'pip', 'install',
        ...extraFlags,
        '--quiet',
        ...pipNames,
      ];
      execSync(cmd.join(' '), { stdio: 'inherit' });
      return true;
    } catch {
      return false;
    }
  }

  const ok = tryInstall() || tryInstall(['--user']);

  if (ok) {
    console.log(`${GREEN}✓${RESET} 설치 완료: ${pipNames.join(', ')}`);
  } else {
    const required = missing.filter(p => p.required).map(p => p.pip);
    const optional = missing.filter(p => !p.required).map(p => p.pip);
    if (required.length > 0) {
      console.error(`\n${RED}✗ 필수 패키지 자동 설치 실패.${RESET}`);
      console.error(`수동으로 실행하세요:`);
      console.error(`   pip install ${required.join(' ')}`);
      process.exit(1);
    }
    if (optional.length > 0) {
      console.warn(`${YELLOW}⚠  선택적 패키지 설치 실패 (기능 일부 제한):${RESET}`);
      console.warn(`   pip install ${optional.join(' ')}`);
    }
  }
}

// ── 3. 스크립트 실행 권한 (Linux/Mac) ─────────────────
if (!isWindows) {
  const scriptPath = path.join(__dirname, '..', 'agentforge');
  try { fs.chmodSync(scriptPath, 0o755); } catch (_) {}
}

// ── 4. 완료 메시지 ────────────────────────────────────
console.log('─'.repeat(44));
console.log(`${GREEN}${BOLD}✓ AgentForge 설치 완료!${RESET}\n`);
console.log(`사용법:`);
console.log(`  ${CYAN}agentforge${RESET}               인터랙티브 실행`);
console.log(`  ${CYAN}agentforge -d /project${RESET}    작업 디렉토리 지정`);
console.log(`  ${CYAN}agentforge --help${RESET}         도움말\n`);
console.log(`${YELLOW}⚠  CHATGPT_AUTH 환경변수를 설정하세요 (ChatGPT 쿠키).${RESET}`);
console.log(`   export CHATGPT_AUTH="..."  # Linux/Mac`);
console.log(`   set CHATGPT_AUTH=...       # Windows\n`);
