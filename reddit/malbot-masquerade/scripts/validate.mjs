import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const required = ['devvit.json', 'public/index.html'];
for (const rel of required) {
  const full = path.join(root, rel);
  if (!fs.existsSync(full)) throw new Error(`Missing required file: ${rel}`);
}

const config = JSON.parse(fs.readFileSync(path.join(root, 'devvit.json'), 'utf8'));
if (config.name !== 'jakeai-malbot') throw new Error('Unexpected Devvit app name');
if (!config.post?.entrypoints?.default?.entry) throw new Error('Missing default post entrypoint');
if (config.permissions?.payments !== false) throw new Error('Payments must remain disabled for v1');
if (config.permissions?.http?.enable !== false) throw new Error('External HTTP must remain disabled for v1');
if (config.permissions?.reddit?.enable !== false) throw new Error('Reddit API access must remain disabled for v1');

const html = fs.readFileSync(path.join(root, 'public/index.html'), 'utf8');
for (const marker of ['JakeAI', 'Malbot Masquerade', 'START SHIFT', 'BUILD', 'FIX', 'NOPE']) {
  if (!html.includes(marker)) throw new Error(`Game marker missing: ${marker}`);
}
if (/(DEVVIT_TOKEN|api[_-]?key|secret\s*=)/i.test(html)) throw new Error('Potential secret-like material detected in client');
if (/https?:\/\//i.test(html)) throw new Error('External URLs are not allowed in v1 client');

console.log('JakeAI Malbot Masquerade validation: PASS');
console.log('Public publication authorization: NO');
