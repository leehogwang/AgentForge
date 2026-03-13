#!/usr/bin/env node
'use strict';
const { spawn, spawnSync } = require('child_process');
const path = require('path');
const os   = require('os');

const isWindows = os.platform() === 'win32';
const scriptPath = path.join(__dirname, '..', 'agentforge');

// Windows: py 런처 우선 (공식 python.org 설치 지원)
const CANDIDATES = isWindows
  ? ['py', 'python', 'python3']
  : ['python3', 'python'];

let python = null;
let pythonArgs = [];   // py 런처는 -3 플래그 필요

for (const bin of CANDIDATES) {
  const flagArgs = bin === 'py' ? ['-3'] : [];
  const r = spawnSync(bin, [
    ...flagArgs,
    '-c', 'import sys; exit(0 if sys.version_info >= (3,10) else 1)'
  ], { encoding: 'utf8' });
  if (r.status === 0) {
    python = bin;
    pythonArgs = flagArgs;
    break;
  }
}

if (!python) {
  console.error('agentforge: Python 3.10+ 이 필요합니다.');
  if (isWindows) {
    console.error('  https://python.org/downloads 에서 설치 후 재시도하세요.');
  } else {
    console.error('  sudo apt install python3  또는  brew install python');
  }
  process.exit(1);
}

const child = spawn(
  python,
  [...pythonArgs, scriptPath, ...process.argv.slice(2)],
  { stdio: 'inherit', env: process.env }
);

child.on('close', code => process.exit(code ?? 0));
child.on('error', err => {
  console.error(`agentforge: 실행 실패 — ${err.message}`);
  process.exit(1);
});
