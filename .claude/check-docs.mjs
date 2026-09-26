import { createHash } from 'node:crypto';
import { existsSync, lstatSync, readFileSync, readdirSync, realpathSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const web = resolve(root, '../market-forecast-web');
const core = ['docs/README.md', 'docs/delivery/mvp-phases.md', 'docs/delivery/requirements-specification.md', 'docs/delivery/work-breakdown.md', 'docs/architecture/event-storming.md', 'docs/architecture/context-map.md'];
const failures = [];
let checks = 0;
const check = (ok, message) => { checks++; if (!ok) failures.push(message); };
const read = path => readFileSync(path, 'utf8');
const sha = path => createHash('sha256').update(readFileSync(path)).digest('hex');
function walk(path) {
  if (!existsSync(path) || lstatSync(path).isSymbolicLink()) return [];
  if (!lstatSync(path).isDirectory()) return [path];
  return readdirSync(path).flatMap(name => walk(join(path, name)));
}

const humanDocs = walk(join(root,'docs')).filter(p => p.endsWith('.md')).map(p => p.slice(root.length+1)).sort();
const canonicalDocs = [
  ...core,
  'docs/data-model.md',
  'docs/architecture/authority-aware-repository-context-methodology.md',
  'docs/architecture/clean-rebuild.md',
  'docs/architecture/product-authority-delta-2026-09-14.md',
  'docs/architecture/product-authority-delta-2026-09-25.md',
  'docs/ui-ux/current-product-convergence/CROSS_SCREEN_STATE_AND_RETURN_CONTEXT.md',
  'docs/ui-ux/current-product-convergence/CURRENT_PRODUCT_CONVERGENCE.md',
  'docs/ui-ux/current-product-convergence/ENTITY_WORKSPACE_PRODUCTION_HANDOFF.md',
  'docs/ui-ux/current-product-convergence/README.md',
  'docs/ui-ux/current-product-convergence/VERIFIED_FACTS_UI_CONTRACT.md',
].sort();
check(JSON.stringify(humanDocs) === JSON.stringify(canonicalDocs), 'Product document set differs from canonical documents per DOC-NAV-01/02');
for (const path of core) check(existsSync(join(root,path)), 'Missing current document: '+path);
check(walk(join(root,'src')).filter(p=>p.includes('/docs/')).length===0, 'Source-owned docs remain');
check(existsSync(join(web,'docs')) && realpathSync(join(web,'docs'))===realpathSync(join(root,'docs')), 'Frontend docs must use the central library');
for (const repo of [root,web]) {
  for (const name of ['AGENTS.md','GEMINI.md']) check(sha(join(repo,name))===sha(join(repo,'CLAUDE.md')), 'Agent entry differs: '+join(repo,name));
  if (existsSync(join(repo,'.agents'))) {
    check(realpathSync(join(repo,'.agents/rules'))===realpathSync(join(repo,'.claude/rules')), 'Rule loader differs: '+repo);
  }
  check(read(join(repo,'CLAUDE.md')).includes('docs/README.md') && read(join(repo,'CLAUDE.md')).includes('.claude/rules/00-index.md'), 'Entry misses required reading: '+repo);
}

const markdown = [...core.map(p=>join(root,p)),join(root,'README.md'),join(root,'CLAUDE.md'),join(web,'README.md'),join(web,'CLAUDE.md'),...walk(join(root,'.claude/rules')).filter(p=>p.endsWith('.md')),...walk(join(web,'.claude/rules')).filter(p=>p.endsWith('.md'))];
let links=0;
for (const path of markdown) {
  const text=read(path);
  check(!/^.*[\t ]+$/m.test(text),'Trailing whitespace: '+path);
  check(text.endsWith('\n') && !text.endsWith('\n\n'),'Final newline: '+path);
  check(!/\]\([^)]*(?:docs\/methodology|agent-topology|runbooks|decisions\/)/.test(text),'Retired current reference: '+path);
  for (const match of text.matchAll(/(?<!!)\[[^\]]*\]\(([^)]+)\)/g)) {
    const target=match[1].replace(/^<|>$/g,'');
    if (/^(?:https?:|mailto:)/.test(target)) continue;
    links++;
    const [relative,anchor]=target.split('#');
    const destination=relative ? resolve(dirname(path),decodeURIComponent(relative)) : path;
    check(existsSync(destination),'Broken link: '+path+' -> '+target);
    if (anchor && existsSync(destination) && lstatSync(destination).isFile()) {
      const content=read(destination);
      const slugs=[...content.matchAll(/^#+ (.*)$/gm)].map(x=>x[1].toLowerCase().replace(/[^\p{L}\p{N}\s-]/gu,'').replace(/\s/g,'-'));
      check(content.includes('id="'+anchor+'"') || slugs.includes(anchor),'Broken anchor: '+path+' -> '+target);
    }
  }
}

const requirements=read(join(root,core[2]));
const acDefinitions=[...requirements.matchAll(/^## (AC-V1-\d{2}) —/gm)].map(m=>m[1]);
check(acDefinitions.length>0 && new Set(acDefinitions).size===acDefinitions.length,'AC definitions are not unique/complete');
const decisionDefinitions=[...requirements.matchAll(/^\| (D-\d{2}) \|/gm)].map(m=>m[1]);
check(decisionDefinitions.length>=5 && new Set(decisionDefinitions).size===decisionDefinitions.length,'Decision definitions are not unique/complete');
for (const path of core.filter(p=>p!==core[2])) {
  const content=read(join(root,path));
  for (const ref of content.matchAll(/AC-V1-\d{2}/g)) check(acDefinitions.includes(ref[0]),'Unknown AC: '+path+' '+ref[0]);
  for (const ref of content.matchAll(/D-\d{2}/g)) check(decisionDefinitions.includes(ref[0]),'Unknown decision: '+path+' '+ref[0]);
}
const breakdown=read(join(root,core[3]));
let subtaskCount=0;
const tasks=[...breakdown.matchAll(/\| (T-[A-Z0-9-]+) \| \[([^\]]+)\]\(([^)]+)\) \| \[([^\]]+)\]\(([^)]+)\) \|/gm)];
const taskIds=tasks.map(x=>x[1]);
check(tasks.length===19 && new Set(taskIds).size===tasks.length,'Task coverage or unique IDs failed');
for (const [_, id, _label1, _issueUrl, _label2, specRel] of tasks) {
  const [file, anchor] = specRel.split('#');
  const targetPath = resolve(dirname(join(root, core[3])), file);
  check(existsSync(targetPath), `Missing Story progress for ${id}: ${targetPath}`);
  if (anchor && existsSync(targetPath)) {
    const text = read(targetPath);
    check(text.includes(`id="${anchor}"`) || text.includes(`### ${id}`), `Missing anchor for ${id} in ${targetPath}`);
  }
}

const roster=JSON.parse(read(join(root,'.claude/roster.json')));
check(roster.canonical===false,'Roster must be noncanonical projection');
check(roster.authority==='.claude/rules/15-execution-strategy.md#execution-topology-and-dispatch','Roster authority must point to rule 15 execution topology');
check(roster.execution_policy?.model==='gpt-6-astra','Roster model must be gpt-6-astra');
check(roster.execution_policy?.default_effort==='medium','Default effort must be medium');
check(!roster.execution_policy?.disallowed_efforts?.includes('medium'),'Medium must not be disallowed');
check(roster.execution_policy?.allowed_escalation_efforts?.includes('high'),'High must be allowed escalation');

// R107-2: Astra effort matrix must describe only Astra-owned activities (Gemini-owned implementation activities excluded)
const excludedGeminiActivities = ['commander_routine', 'implement', 'debug', 'bugfix', 'test_authoring', 'mechanical_refactor'];
for (const act of excludedGeminiActivities) {
  check(!(act in (roster.execution_policy?.effort_by_activity || {})), `Astra execution policy must not claim Gemini-owned activity: ${act}`);
}

// R107-3: Authoritative operational runtime identity
const getRoleTaskId = (role) => role?.task_id || role?.local_runtime_task_id;
check(Boolean(roster.shared_roles?.architect?.runtime_tool === 'codex' && getRoleTaskId(roster.shared_roles?.architect)), 'Architect must explicitly specify runtime_tool: codex and task_id');
check(Boolean(roster.shared_roles?.reviewer?.runtime_tool === 'codex' && getRoleTaskId(roster.shared_roles?.reviewer)), 'Reviewer must explicitly specify runtime_tool: codex and task_id');
check(getRoleTaskId(roster.shared_roles.architect) !== getRoleTaskId(roster.shared_roles.reviewer), 'Shared architect and reviewer must maintain runtime role isolation');

// R107-1: active runtime IDs ∩ legacy idle identity == ∅
const activeRuntimeIds = new Set([
  getRoleTaskId(roster.shared_roles.architect),
  getRoleTaskId(roster.shared_roles.reviewer),
]);
const legacyIdleIds = new Set(Object.values(roster.legacy_idle_tasks || {}));
for (const id of activeRuntimeIds) {
  check(!legacyIdleIds.has(id), `Active shared role runtime ID ${id} must not appear in legacy_idle_tasks`);
}

check(Object.keys(roster.contexts).length===6,'Expected six BC role bindings');
for(const [ctx, roles] of Object.entries(roster.contexts)) {
  const archRuntimeId = getRoleTaskId(roles.architect);
  const revRuntimeId = getRoleTaskId(roles.reviewer);
  const implName = roles.implementer?.name || roles.implementer?.task_id;
  check(Boolean(archRuntimeId && revRuntimeId && implName),'Context missing role IDs: '+ctx);
  check(archRuntimeId!==implName,'Architect and Implementer share a session: '+ctx);
  check(revRuntimeId!==implName,'Reviewer and Implementer share a session: '+ctx);
}

// Continuation invariants check in rule 15
const rule15 = read(join(root, '.claude/rules/15-execution-strategy.md'));
check(
  rule15.includes('CODEX_REVIEW_REJECT -> LOCAL_REVISION_REQUIRED -> IMPLEMENTER_DISPATCH'),
  'Rule 15 must contain invariant: CODEX_REVIEW_REJECT -> LOCAL_REVISION_REQUIRED -> IMPLEMENTER_DISPATCH'
);
check(
  rule15.includes('CODEX_REVIEW_ACCEPT -> INTEGRATION_READY -> COMMANDER_INTEGRATION'),
  'Rule 15 must contain invariant: CODEX_REVIEW_ACCEPT -> INTEGRATION_READY -> COMMANDER_INTEGRATION'
);
check(
  rule15.includes('INTEGRATION_COMPLETE -> PORTFOLIO_RECONCILIATION'),
  'Rule 15 must contain invariant: INTEGRATION_COMPLETE -> PORTFOLIO_RECONCILIATION'
);
check(
  rule15.includes('LOCAL_ROUTE_STOP != COMMANDER_STOP'),
  'Rule 15 must contain invariant: local route stop != commander stop'
);
check(
  rule15.includes('Reviewer 已啟動 != 驗收完成') || rule15.includes('reviewer dispatch != verdict'),
  'Rule 15 must contain invariant: reviewer dispatch != verdict'
);
check(
  rule15.includes('REVIEWER_ACCEPT != COMMANDER_TERMINAL'),
  'Rule 15 must contain invariant: reviewer accept != commander terminal'
);
check(
  !rule15.includes('External ChatGPT review is an integration gate for locally-final candidates'),
  'Rule 15 must NOT contain retired gate: External ChatGPT review is an integration gate for locally-final candidates'
);
check(
  !rule15.includes('External ChatGPT final gate 正在等待'),
  'Rule 15 must NOT contain retired blocker: External ChatGPT final gate 正在等待'
);

const flag=process.argv.indexOf('--migration');
let preservation=null;
if(flag!==-1) {
  const manifest=JSON.parse(read(process.argv[flag+1]));
  for(const entry of manifest.retired) {
    check(existsSync(entry.backup) && sha(entry.backup)===entry.sha256,'Retired preimage changed: '+entry.path);
  }
  for(const entry of manifest.protected) {
    const path=join(manifest.roots[entry.repo],entry.path);
    check(existsSync(path) && sha(path)===entry.sha256,'Protected code/contract changed: '+entry.repo+'/'+entry.path);
  }
  preservation={retired:manifest.retired.length,protected:manifest.protected.length};
}
console.log(JSON.stringify({status:failures.length?'FAIL':'PASS',checks,links,productBodies:core.length-1,tasks:tasks.length,subtasks:subtaskCount,preservation,failures},null,2));
process.exitCode=failures.length?1:0;
