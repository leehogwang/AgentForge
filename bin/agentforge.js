#!/usr/bin/env node
/**
 * AgentForge launcher + first-run setup wizard
 *
 * 첫 실행 시:
 *   1. Python 확인 / pip 의존성 설치
 *   2. 브라우저로 ChatGPT 로그인 유도
 *   3. 인증 토큰 입력 → ~/.agentforge/config.json 저장
 *   4. agentforge 실행
 */
'use strict';

const { spawn, spawnSync, execSync } = require('child_process');
const readline = require('readline');
const path  = require('path');
const fs    = require('fs');
const os    = require('os');

// ── 상수 ─────────────────────────────────────────────
const SCRIPT   = path.join(__dirname, '..', 'agentforge');
const CONFIG   = path.join(os.homedir(), '.agentforge', 'config.json');
const WIN      = os.platform() === 'win32';

const R = '\x1b[0m';
const CYAN   = '\x1b[36m';
const GREEN  = '\x1b[32m';
const YELLOW = '\x1b[33m';
const RED    = '\x1b[31m';
const BOLD   = '\x1b[1m';
const DIM    = '\x1b[2m';

const DEPS = [
  { import: 'rich',           pip: 'rich'           },
  { import: 'prompt_toolkit', pip: 'prompt_toolkit' },
  { import: 'requests',       pip: 'requests'       },
  { import: 'rank_bm25',      pip: 'rank-bm25'      },
  { import: 'tiktoken',       pip: 'tiktoken'       },
];

// ── 유틸 ─────────────────────────────────────────────
function run(bin, args, opts = {}) {
  return spawnSync(bin, args, { encoding: 'utf8', ...opts });
}

function openBrowser(url) {
  const cmd = WIN ? ['cmd', ['/c', 'start', url]]
    : os.platform() === 'darwin' ? ['open', [url]]
    : ['xdg-open', [url]];
  spawnSync(cmd[0], cmd[1], { stdio: 'ignore' });
}

function ask(rl, question) {
  return new Promise(resolve => rl.question(question, ans => resolve(ans.trim())));
}

function loadConfig() {
  try { return JSON.parse(fs.readFileSync(CONFIG, 'utf8')); }
  catch { return {}; }
}

function saveConfig(obj) {
  fs.mkdirSync(path.dirname(CONFIG), { recursive: true });
  fs.writeFileSync(CONFIG, JSON.stringify(obj, null, 2));
}

// ── Python 탐색 ───────────────────────────────────────
function findPython() {
  const candidates = WIN
    ? ['py', 'python', 'python3']
    : ['python3', 'python'];

  // pip 있고 3.10+ 인 것 우선
  for (const bin of candidates) {
    const vArgs = bin === 'py' ? ['-3', '-c', 'import sys;exit(0 if sys.version_info>=(3,10) else 1)']
                               : ['-c', 'import sys;exit(0 if sys.version_info>=(3,10) else 1)'];
    const pipArgs = bin === 'py' ? ['-3', '-m', 'pip', '--version'] : ['-m', 'pip', '--version'];
    if (run(bin, vArgs).status === 0 && run(bin, pipArgs).status === 0) {
      return { bin, extraArgs: bin === 'py' ? ['-3'] : [] };
    }
  }

  // pip 없어도 버전 맞으면 ensurepip 시도
  for (const bin of candidates) {
    const vArgs = bin === 'py' ? ['-3', '-c', 'import sys;exit(0 if sys.version_info>=(3,10) else 1)']
                               : ['-c', 'import sys;exit(0 if sys.version_info>=(3,10) else 1)'];
    if (run(bin, vArgs).status === 0) {
      const eArgs = bin === 'py' ? ['-3', '-m', 'ensurepip', '--upgrade'] : ['-m', 'ensurepip', '--upgrade'];
      const r = run(bin, eArgs, { stdio: 'inherit' });
      if (r.status === 0) return { bin, extraArgs: bin === 'py' ? ['-3'] : [] };
    }
  }
  return null;
}

// ── pip 설치 ──────────────────────────────────────────
function installDeps(py) {
  const { bin, extraArgs } = py;
  const missing = DEPS.filter(d => {
    return run(bin, [...extraArgs, '-c', `import ${d.import}`]).status !== 0;
  });
  if (missing.length === 0) return true;

  const names = missing.map(d => d.pip);
  process.stdout.write(`${YELLOW}▶ pip 설치 중: ${names.join(', ')}${R}\n`);

  const pipCmd = `${bin} ${[...extraArgs, '-m', 'pip', 'install', '--quiet', ...names].join(' ')}`;
  try {
    execSync(pipCmd, { stdio: 'inherit' });
    return true;
  } catch {
    try {
      execSync(pipCmd + ' --user', { stdio: 'inherit' });
      return true;
    } catch {
      return false;
    }
  }
}

// ── 인증 토큰 안내 ────────────────────────────────────
async function setupAuth(rl) {
  console.log(`\n${BOLD}${CYAN}[ 2/2 ] ChatGPT 인증 설정${R}`);
  console.log(`${DIM}agentforge는 ChatGPT Codex API를 사용합니다.${R}\n`);
  console.log(`  1. 아래 URL에서 ChatGPT에 로그인하세요 (브라우저가 열립니다)`);
  console.log(`     ${CYAN}https://chatgpt.com${R}\n`);

  openBrowser('https://chatgpt.com');
  await ask(rl, `  로그인 완료 후 Enter를 누르세요...`);

  console.log(`\n  2. 브라우저에서 개발자 도구를 여세요`);
  console.log(`     ${WIN ? 'F12' : 'Cmd+Option+I (Mac) / F12 (Linux)'}`);
  console.log(`\n  3. ${BOLD}Application${R} → ${BOLD}Cookies${R} → ${CYAN}https://chatgpt.com${R}`);
  console.log(`     ${BOLD}__Secure-next-auth.session-token${R} 값을 복사하세요\n`);

  openBrowser('https://chatgpt.com');

  const token = await ask(rl, `  토큰을 붙여넣으세요: `);

  if (!token) {
    console.log(`\n${YELLOW}⚠  토큰을 입력하지 않았습니다. 나중에 설정하려면:${R}`);
    console.log(`   export CHATGPT_AUTH="<토큰>"`);
    console.log(`   또는 agentforge auth 명령 실행\n`);
    return null;
  }

  const cfg = loadConfig();
  cfg.chatgpt_auth = token;
  saveConfig(cfg);
  console.log(`\n${GREEN}✓${R} 토큰 저장 완료: ${DIM}${CONFIG}${R}\n`);
  return token;
}

// ── 메인 ─────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2);
  const isSetup = args[0] === '--setup';
  const cfg = loadConfig();

  // 이미 설정 완료 + setup 플래그 없으면 바로 실행
  if (!isSetup && cfg.chatgpt_auth) {
    return launch(null, args, cfg.chatgpt_auth);
  }

  // CHATGPT_AUTH 환경변수로 이미 인증된 경우
  if (!isSetup && process.env.CHATGPT_AUTH) {
    return launch(null, args);
  }

  // ── 셋업 마법사 시작 ──────────────────────────────
  console.log(`\n${BOLD}${CYAN}━━━ AgentForge 초기 설정 ━━━${R}\n`);

  // 1. Python
  console.log(`${BOLD}[ 1/2 ] Python 환경 확인${R}`);
  let py = findPython();

  if (!py) {
    console.log(`\n${RED}✗ Python 3.10+ 를 찾을 수 없습니다.${R}\n`);
    console.log(`  설치 후 다시 실행하세요:`);
    if (WIN) {
      console.log(`  ${CYAN}https://python.org/downloads${R}  (설치 시 "Add to PATH" 체크)`);
      openBrowser('https://python.org/downloads');
    } else {
      console.log(`  sudo apt install python3 python3-pip   # Ubuntu/Debian`);
      console.log(`  brew install python                     # macOS`);
    }
    console.log('');
    process.exit(1);
  }

  const verOut = run(py.bin, [...py.extraArgs, '--version']).stdout.trim();
  process.stdout.write(`${GREEN}✓${R} ${verOut}\n`);

  const depsOk = installDeps(py);
  if (!depsOk) {
    console.log(`\n${YELLOW}⚠  일부 패키지 자동 설치 실패 — 수동으로 실행하세요:${R}`);
    console.log(`   pip install rich prompt_toolkit requests rank-bm25 tiktoken\n`);
    // 실패해도 계속 진행
  } else {
    console.log(`${GREEN}✓${R} Python 패키지 준비 완료`);
  }

  // 2. 인증
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  let token;
  try {
    token = await setupAuth(rl);
  } finally {
    rl.close();
  }

  console.log(`${BOLD}${GREEN}✓ 설정 완료! AgentForge를 시작합니다...${R}\n`);
  launch(py, args.filter(a => a !== '--setup'), token);
}

function launch(py, args, token) {
  // Python 재탐색 (py가 null인 경우)
  if (!py) py = findPython();
  if (!py) {
    console.error(`${RED}agentforge: Python 3.10+이 필요합니다.${R}`);
    process.exit(1);
  }

  const env = { ...process.env };
  if (token) env.CHATGPT_AUTH = token;

  // config.json에서 토큰 로드 (env가 없을 때)
  if (!env.CHATGPT_AUTH) {
    const cfg = loadConfig();
    if (cfg.chatgpt_auth) env.CHATGPT_AUTH = cfg.chatgpt_auth;
  }

  if (!isSetupDone() && !env.CHATGPT_AUTH) {
    // 처음 실행 + 인증 없음 → 셋업 유도
    console.log(`\n${YELLOW}초기 설정이 필요합니다. 잠시 후 시작합니다...${R}\n`);
    const self = spawn(process.execPath, [__filename, '--setup', ...args], {
      stdio: 'inherit', env: process.env,
    });
    self.on('close', code => process.exit(code ?? 0));
    return;
  }

  if (!isWindows) {
    try { fs.chmodSync(SCRIPT, 0o755); } catch (_) {}
  }

  const child = spawn(py.bin, [...py.extraArgs, SCRIPT, ...args], {
    stdio: 'inherit', env,
  });
  child.on('close', code => process.exit(code ?? 0));
  child.on('error', err => {
    console.error(`${RED}agentforge 실행 실패: ${err.message}${R}`);
    process.exit(1);
  });
}

function isSetupDone() {
  const cfg = loadConfig();
  return !!(cfg.chatgpt_auth || process.env.CHATGPT_AUTH);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
