import { createHash } from 'node:crypto';
import {
  existsSync,
  lstatSync,
  readFileSync,
  readdirSync,
  realpathSync,
} from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const requiredDocs = [
  'docs/README.md',
  'docs/governance-source.md',
  'docs/delivery/mvp-phases.md',
  'docs/delivery/requirements-specification.md',
  'docs/architecture/event-storming.md',
  'docs/architecture/context-map.md',
  'specs/README.md',
];
const linkCheckedDocs = requiredDocs.filter(
  (path) => path !== 'specs/README.md',
);

const failures = [];
let checks = 0;
let links = 0;

const check = (ok, message) => {
  checks++;
  if (!ok) failures.push(message);
};
const read = (path) => readFileSync(path, 'utf8');
const sha = (path) =>
  createHash('sha256').update(readFileSync(path)).digest('hex');

function walk(path) {
  if (!existsSync(path) || lstatSync(path).isSymbolicLink()) return [];
  if (!lstatSync(path).isDirectory()) return [path];
  return readdirSync(path).flatMap((name) => walk(join(path, name)));
}

for (const path of requiredDocs) {
  check(existsSync(join(root, path)), 'Missing current document: ' + path);
}

check(
  walk(join(root, 'src')).filter((path) => path.includes('/docs/')).length === 0,
  'Source-owned docs remain',
);

const claudePath = join(root, 'CLAUDE.md');
for (const name of ['AGENTS.md', 'GEMINI.md']) {
  const path = join(root, name);
  check(existsSync(path), 'Missing agent entry: ' + name);
  if (existsSync(path) && existsSync(claudePath)) {
    check(sha(path) === sha(claudePath), 'Agent entry differs: ' + name);
  }
}

if (existsSync(join(root, '.agents/rules'))) {
  check(
    realpathSync(join(root, '.agents/rules')) ===
      realpathSync(join(root, '.claude/rules')),
    'Rule loader differs from tracked .claude/rules',
  );
}

if (existsSync(claudePath)) {
  const entry = read(claudePath);
  check(
    entry.includes('docs/README.md') &&
      entry.includes('.claude/rules/00-index.md'),
    'CLAUDE.md misses required reading',
  );
}

const markdown = [
  ...linkCheckedDocs.map((path) => join(root, path)),
  join(root, 'README.md'),
  join(root, 'CLAUDE.md'),
  ...walk(join(root, '.claude/rules')).filter((path) =>
    path.endsWith('.md'),
  ),
];

for (const path of [...new Set(markdown)]) {
  if (!existsSync(path)) continue;
  const text = read(path);

  check(!/^.*[\t ]+$/m.test(text), 'Trailing whitespace: ' + path);
  check(
    text.endsWith('\n') && !text.endsWith('\n\n'),
    'Final newline: ' + path,
  );

  for (const match of text.matchAll(/(?<!!)\[[^\]]*\]\(([^)]+)\)/g)) {
    const target = match[1].replace(/^<|>$/g, '');
    if (/^(?:https?:|mailto:)/.test(target)) continue;

    links++;
    const [relative, anchor] = target.split('#');
    const destination = relative
      ? resolve(dirname(path), decodeURIComponent(relative))
      : path;

    check(
      existsSync(destination),
      'Broken link: ' + path + ' -> ' + target,
    );

    if (
      anchor &&
      existsSync(destination) &&
      lstatSync(destination).isFile()
    ) {
      const content = read(destination);
      const slugs = [
        ...content.matchAll(/^#+ (.*)$/gm),
      ].map((item) =>
        item[1]
          .toLowerCase()
          .replace(/[^\p{L}\p{N}\s-]/gu, '')
          .replace(/\s/g, '-'),
      );
      check(
        content.includes('id="' + anchor + '"') || slugs.includes(anchor),
        'Broken anchor: ' + path + ' -> ' + target,
      );
    }
  }
}

const rosterPath = join(root, '.claude/roster.json');
check(existsSync(rosterPath), 'Missing .claude/roster.json');
if (existsSync(rosterPath)) {
  const roster = JSON.parse(read(rosterPath));
  check(roster.canonical === false, 'Roster must be noncanonical projection');
  check(
    roster.authority ===
      '.claude/rules/15-execution-strategy.md#execution-topology-and-dispatch',
    'Roster authority must point to Rule 15 execution topology',
  );
  check(
    roster.commander?.runtime_tool === 'chatgpt',
    'Commander runtime_tool must be chatgpt',
  );
  check(
    roster.shared_roles?.architect?.runtime_tool === 'codex',
    'Architect runtime_tool must be codex',
  );
  check(
    roster.shared_roles?.reviewer?.runtime_tool === 'codex',
    'Reviewer runtime_tool must be codex',
  );

  const contexts = roster.contexts || {};
  check(Object.keys(contexts).length > 0, 'Roster must define domain contexts');
  for (const [context, roles] of Object.entries(contexts)) {
    check(
      roles?.architect === 'shared:architect',
      'Context architect must use shared role: ' + context,
    );
    check(
      roles?.reviewer === 'shared:reviewer',
      'Context reviewer must use shared role: ' + context,
    );
    check(
      roles?.implementer?.runtime_tool === 'commander',
      'Context implementer must route through commander: ' + context,
    );
  }

  const tracks = roster.delivery_tracks || {};
  for (const [track, roles] of Object.entries(tracks)) {
    check(
      roles?.architect === 'shared:architect',
      'Delivery architect must use shared role: ' + track,
    );
    check(
      roles?.reviewer === 'shared:reviewer',
      'Delivery reviewer must use shared role: ' + track,
    );
    check(
      roles?.implementer?.runtime_tool === 'commander',
      'Delivery implementer must route through commander: ' + track,
    );
  }
}

const rule15Path = join(root, '.claude/rules/15-execution-strategy.md');
check(existsSync(rule15Path), 'Missing Rule 15 execution strategy');
if (existsSync(rule15Path)) {
  const rule15 = read(rule15Path);
  for (const invariant of [
    'CODEX_REVIEW_REJECT -> LOCAL_REVISION_REQUIRED -> IMPLEMENTER_DISPATCH',
    'CODEX_REVIEW_ACCEPT -> INTEGRATION_READY -> COMMANDER_INTEGRATION',
    'INTEGRATION_COMPLETE -> PORTFOLIO_RECONCILIATION',
    'LOCAL_ROUTE_STOP != COMMANDER_STOP',
    'REVIEWER_ACCEPT != COMMANDER_TERMINAL',
  ]) {
    check(
      rule15.includes(invariant),
      'Rule 15 missing continuation invariant: ' + invariant,
    );
  }
  check(
    rule15.includes('Reviewer 已啟動 != 驗收完成') ||
      rule15.includes('reviewer dispatch != verdict'),
    'Rule 15 must distinguish reviewer dispatch from verdict',
  );
}

const flag = process.argv.indexOf('--migration');
let preservation = null;
if (flag !== -1) {
  const manifestPath = process.argv[flag + 1];
  check(Boolean(manifestPath), 'Migration manifest path is required');
  if (manifestPath) {
    const manifest = JSON.parse(read(manifestPath));
    for (const entry of manifest.retired || []) {
      check(
        existsSync(entry.backup) && sha(entry.backup) === entry.sha256,
        'Retired preimage changed: ' + entry.path,
      );
    }
    for (const entry of manifest.protected || []) {
      const repoRoot = manifest.roots?.[entry.repo];
      check(Boolean(repoRoot), 'Missing migration root: ' + entry.repo);
      if (!repoRoot) continue;
      const path = join(repoRoot, entry.path);
      check(
        existsSync(path) && sha(path) === entry.sha256,
        'Protected code/contract changed: ' +
          entry.repo +
          '/' +
          entry.path,
      );
    }
    preservation = {
      retired: (manifest.retired || []).length,
      protected: (manifest.protected || []).length,
    };
  }
}

console.log(
  JSON.stringify(
    {
      status: failures.length ? 'FAIL' : 'PASS',
      checks,
      links,
      requiredDocs: requiredDocs.length,
      preservation,
      failures,
    },
    null,
    2,
  ),
);
process.exitCode = failures.length ? 1 : 0;
