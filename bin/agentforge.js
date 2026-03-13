#!/usr/bin/env node
'use strict';
const { spawn, spawnSync } = require('child_process');
const path = require('path');

// Python 스크립트 위치 (npm 패키지 루트의 agentforge)
const scriptPath = path.join(__dirname, '..', 'agentforge');

// Python 3.10+ 탐색
let python = null;
for (const bin of ['python3', 'python']) {
  const r = spawnSync(bin, ['-c',
    'import sys; exit(0 if sys.version_info >= (3,10) else 1)'
  ], { encoding: 'utf8' });
  if (r.status === 0) { python = bin; break; }
}

if (!python) {
  console.error('agentforge: Python 3.10+ 이 필요합니다.');
  console.error('  https://www.python.org/downloads/');
  process.exit(1);
}

const child = spawn(python, [scriptPath, ...process.argv.slice(2)], {
  stdio: 'inherit',
  env: process.env,
});

child.on('close', code => process.exit(code ?? 0));
child.on('error', err => {
  console.error(`agentforge: 실행 실패 — ${err.message}`);
  process.exit(1);
});
