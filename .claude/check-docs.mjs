import { existsSync, lstatSync, readFileSync, readdirSync, readlinkSync, realpathSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const failures = [];
let checks = 0;
let links = 0;

const check = (condition, message) => {
  checks += 1;
  if (!condition) failures.push(message);
};

const read = (path) => readFileSync(path, 'utf8');

function walk(path) {
  if (!existsSync(path) || lstatSync(path).isSymbolicLink()) return [];
  if (!lstatSync(path).isDirectory()) return [path];
  return readdirSync(path).flatMap((name) => walk(join(path, name)));
}

const requiredDocs = [
  'docs/README.md',
  'docs/governance-source.md',
  'docs/delivery/mvp-phases.md',
  'docs/delivery/requirements-specification.md',
  'docs/architecture/event-storming.md',
  'docs/architecture/context-map.md',
  'docs/architecture/authority-aware-repository-context-methodology.md',
];

const requiredRules = [
  '.claude/rules/00-index.md',
  '.claude/rules/05-methodology.md',
  '.claude/rules/10-architecture.md',
  '.claude/rules/15-execution-strategy.md',
  '.claude/rules/16-github-human-readable-records.md',
  '.claude/rules/20-code-style.md',
  '.claude/rules/30-application-domain.md',
  '.claude/rules/40-ports-adapters-di.md',
  '.claude/rules/50-dtos-errors-http.md',
  '.claude/rules/60-configuration-data.md',
  '.claude/rules/70-testing.md',
  '.claude/rules/80-documentation.md',
  '.claude/rules/90-operations.md',
  '.claude/rules/95-market-forecast-overrides.md',
];

const requiredGovernance = [
  ...requiredDocs,
  ...requiredRules,
  'CLAUDE.md',
  'specs/README.md',
  '.claude/roster.json',
  '.context/catalog.yaml',
  '.context/capabilities.yaml',
  '.context/authority-routing.yaml',
  '.context/security-boundary.yaml',
  '.authority/verified_acceptance_records.json',
  '.github/ISSUE_TEMPLATE/epic.yml',
  '.github/ISSUE_TEMPLATE/story.yml',
  '.github/ISSUE_TEMPLATE/task.yml',
  '.github/ISSUE_TEMPLATE/bug.yml',
  '.github/ISSUE_TEMPLATE/spike.yml',
  '.github/pull_request_template.md',
  '.claude/scripts/bootstrap-agents.sh',
];

for (const path of requiredGovernance) {
  check(existsSync(join(root, path)), 'Missing governance file: ' + path);
}

// Canonical entrypoint and compatibility symlinks.
const claudePath = join(root, 'CLAUDE.md');
check(existsSync(claudePath), 'Missing CLAUDE.md');
if (existsSync(claudePath)) {
  check(!lstatSync(claudePath).isSymbolicLink(), 'CLAUDE.md must be the canonical regular file');
}

for (const name of ['AGENTS.md', 'GEMINI.md']) {
  const path = join(root, name);
  check(existsSync(path), 'Missing compatibility entry: ' + name);
  if (existsSync(path)) {
    check(lstatSync(path).isSymbolicLink(), name + ' must be a symlink');
    if (lstatSync(path).isSymbolicLink()) {
      check(readlinkSync(path) === 'CLAUDE.md', name + ' must link exactly to CLAUDE.md');
      check(realpathSync(path) === realpathSync(claudePath), name + ' must resolve to CLAUDE.md');
    }
  }
}

const agentsPath = join(root, '.agents');
check(existsSync(agentsPath), 'Missing .agents compatibility link');
if (existsSync(agentsPath)) {
  check(lstatSync(agentsPath).isSymbolicLink(), '.agents must be a symlink');
  if (lstatSync(agentsPath).isSymbolicLink()) {
    check(readlinkSync(agentsPath) === '.claude', '.agents must link exactly to .claude');
    check(realpathSync(agentsPath) === realpathSync(join(root, '.claude')), '.agents must resolve to .claude');
  }
}

const claude = read(claudePath);
check(claude.includes('docs/README.md'), 'CLAUDE.md misses docs/README.md');
check(claude.includes('.claude/rules/00-index.md'), 'CLAUDE.md misses rule index');

// Code-style invariant.
const sourceFiles = walk(join(root, 'src'));
const initFiles = sourceFiles.filter((path) => path.endsWith('__init__.py'));
check(initFiles.length === 0, 'Forbidden __init__.py files: ' + initFiles.join(', '));

// Governance provenance.
const governanceSource = read(join(root, 'docs/governance-source.md'));
check(
  governanceSource.includes('aa37bdb63d22dbc0bbd3337a1f8f1b23616fbd6b'),
  'Governance baseline commit is not pinned'
);
check(governanceSource.includes('AGENTS.md -> CLAUDE.md'), 'Governance source misses AGENTS symlink decision');
check(governanceSource.includes('GEMINI.md -> CLAUDE.md'), 'Governance source misses GEMINI symlink decision');
check(governanceSource.includes('.agents -> .claude'), 'Governance source misses .agents symlink decision');

// Roster is a truthful noncanonical projection.
const roster = JSON.parse(read(join(root, '.claude/roster.json')));
check(roster.canonical === false, 'Roster must remain noncanonical');
check(
  roster.authority === '.claude/rules/15-execution-strategy.md#execution-topology-and-dispatch',
  'Roster authority must point to rule 15 execution topology'
);
check(Boolean(roster.commander?.name), 'Roster missing Commander');
check(Boolean(roster.shared_roles?.architect?.name), 'Roster missing Architect');
check(Boolean(roster.shared_roles?.reviewer?.name), 'Roster missing Reviewer');
check(
  roster.shared_roles?.architect?.name !== roster.shared_roles?.reviewer?.name,
  'Architect and Reviewer identities must differ'
);
for (const role of ['architect', 'reviewer']) {
  const value = roster.shared_roles?.[role];
  if (value?.status === 'UNBOUND') {
    check(!value.task_id, 'UNBOUND ' + role + ' must not invent task_id');
    check(!value.local_runtime_task_id, 'UNBOUND ' + role + ' must not invent local_runtime_task_id');
  }
}
const expectedContexts = ['forecast-validation', 'market-data', 'realized-variance', 'risk-forecast'];
check(
  JSON.stringify(Object.keys(roster.contexts || {}).sort()) === JSON.stringify(expectedContexts),
  'Roster contexts differ from Market Forecast bounded capabilities'
);

// Context and data-boundary checks.
const capabilities = read(join(root, '.context/capabilities.yaml'));
for (const id of ['market_data', 'realized_variance', 'risk_forecast', 'forecast_validation']) {
  check(capabilities.includes('id: ' + id), 'Capabilities missing: ' + id);
}
const security = read(join(root, '.context/security-boundary.yaml'));
check(security.includes('data/raw/**'), 'Security boundary must exclude raw market data');
check(security.includes('data/holdout/**'), 'Security boundary must exclude holdout data');

const gitignore = read(join(root, '.gitignore'));
check(gitignore.includes('data/'), '.gitignore must exclude data/');
check(gitignore.includes('.env'), '.gitignore must exclude env files');

const bootstrapPath = join(root, '.claude/scripts/bootstrap-agents.sh');
check(
  (lstatSync(bootstrapPath).mode & 0o111) !== 0,
  '.claude/scripts/bootstrap-agents.sh must remain executable'
);

// Active governance must not retain source-product current identities.
const inheritedCurrentTruthPaths = [
  ...requiredRules,
  'docs/architecture/authority-aware-repository-context-methodology.md',
  'specs/README.md',
  '.github/ISSUE_TEMPLATE/epic.yml',
  '.github/ISSUE_TEMPLATE/story.yml',
  '.github/ISSUE_TEMPLATE/task.yml',
  '.github/ISSUE_TEMPLATE/bug.yml',
  '.github/ISSUE_TEMPLATE/spike.yml',
  '.github/pull_request_template.md',
];
const inheritedCurrentTruthText = inheritedCurrentTruthPaths
  .map((path) => read(join(root, path)))
  .join('\n');
for (const retired of [
  'Camoufox',
  'KALEDOXA_',
  'collection-watch',
  'ai-triage',
  'entity-knowledge',
  'news-reading',
  'semantic-grouping',
  'product-ui',
  'Thesiscope',
  'CLEAN REBUILD AUTHORIZED',
  'Entity Workspace',
  'Verified Facts',
  'browser profiles',
  'private tenant exports',
  'Gemini 3.8 Flash',
]) {
  check(
    !inheritedCurrentTruthText.includes(retired),
    'Inherited source-product current identity remains in active governance: ' + retired
  );
}

// Human-readable Markdown link and formatting checks.
const markdownPaths = [
  ...requiredDocs,
  ...requiredRules,
  'README.md',
  'CLAUDE.md',
  'specs/README.md',
  ...walk(join(root, 'specs'))
    .filter((path) => path.endsWith('.md'))
    .map((path) => path.slice(root.length + 1)),
];
const uniqueMarkdown = [...new Set(markdownPaths)].map((path) => join(root, path));

for (const path of uniqueMarkdown) {
  if (!existsSync(path)) continue;
  const text = read(path);
  check(!/^.*[\t ]+$/m.test(text), 'Trailing whitespace: ' + path.slice(root.length + 1));
  check(text.endsWith('\n') && !text.endsWith('\n\n'), 'Final newline: ' + path.slice(root.length + 1));

  for (const match of text.matchAll(/(?<!!)\[[^\]]*\]\(([^)]+)\)/g)) {
    const target = match[1].replace(/^<|>$/g, '');
    if (/^(?:https?:|mailto:)/.test(target)) continue;
    links += 1;
    const [relative, anchor] = target.split('#');
    const destination = relative ? resolve(dirname(path), decodeURIComponent(relative)) : path;
    check(existsSync(destination), 'Broken link: ' + path.slice(root.length + 1) + ' -> ' + target);
    if (anchor && existsSync(destination) && lstatSync(destination).isFile()) {
      const targetText = read(destination);
      const slugs = [...targetText.matchAll(/^#+ (.*)$/gm)].map((value) =>
        value[1]
          .toLowerCase()
          .replace(/[^\p{L}\p{N}\s-]/gu, '')
          .replace(/\s/g, '-')
      );
      check(
        targetText.includes('id="' + anchor + '"') || slugs.includes(anchor),
        'Broken anchor: ' + path.slice(root.length + 1) + ' -> ' + target
      );
    }
  }
}

console.log(JSON.stringify({
  status: failures.length ? 'FAIL' : 'PASS',
  checks,
  links,
  failures,
}, null, 2));

process.exitCode = failures.length ? 1 : 0;
