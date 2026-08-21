/**
 * Carrier pigeon, rewritten in silicon — 2026-08-09T00:00:00Z
 *
 * posts a CI outcome card to a discord channel webhook using components v2.
 *
 * two sources of truth, deliberately:
 *   - the `needs` context decides the card's COLOR. it is the same thing github
 *     uses to gate downstream jobs, so it already accounts for continue-on-error.
 *   - the jobs REST API supplies DETAIL that `needs` cannot express: matrix leg
 *     names and per-job log urls. a matrix job collapses to one `needs` entry no
 *     matter how many legs failed.
 *
 * this script must never exit non-zero. a discord outage turning CI red would be
 * worse than the missing notification, and under workflow_call a failure here
 * would propagate into the caller's `needs.<job>.result` and block a release.
 */

import { readFileSync } from 'node:fs';

const DISCORD_WEBHOOK_URL = process.env.DISCORD_WEBHOOK_URL ?? '';
const GH_TOKEN = process.env.GH_TOKEN ?? '';
const NEEDS_JSON = process.env.NEEDS_JSON ?? '{}';
const SUBTITLE = process.env.SUBTITLE ?? '';
const JOB_NAMES_JSON = process.env.JOB_NAMES_JSON ?? '';
// set DRY_RUN=1 to print the payload instead of posting it — lets you replay a
// historical run locally without a throwaway Discord channel
const DRY_RUN = process.env.DRY_RUN === '1';

// DOCUMENTATION-REPO DIVERGENCE (1 of 2): workflow_run support.
//
// this repo is public, so its only pull_request-triggered workflow (Smoke Test)
// gets no secrets on a fork PR and cannot reach the webhook from inside itself.
// the fix is a separate workflow_run notifier — but there the ambient GITHUB_*
// vars describe the NOTIFIER's own run, not the run being reported, and there is
// no `needs` context at all. these overrides let the caller point the script at
// another run. every one is opt-in: unset, the script behaves exactly as the
// sndwrks-local / sndwrks-cloud copies do, so this stays a clean 3-way merge.
//
// NB: do not try to override GITHUB_RUN_ID with a step-level `env:` instead —
// GitHub reserves the GITHUB_ prefix for workflow-set env vars and the behaviour
// is undocumented.
const RUN_ID_OVERRIDE = process.env.RUN_ID_OVERRIDE ?? '';
const RUN_ATTEMPT_OVERRIDE = process.env.RUN_ATTEMPT_OVERRIDE ?? '';
const WORKFLOW_OVERRIDE = process.env.WORKFLOW_OVERRIDE ?? '';
const REF_NAME_OVERRIDE = process.env.REF_NAME_OVERRIDE ?? '';
const EVENT_NAME_OVERRIDE = process.env.EVENT_NAME_OVERRIDE ?? '';
const PR_URL_OVERRIDE = process.env.PR_URL_OVERRIDE ?? '';
// derive `needs` from the jobs API instead of the NEEDS_JSON input. without it a
// workflow_run notifier would have to fabricate a single needs entry, and
// classifyJobs would then warn once per real job that it is missing from needs.
const NEEDS_FROM_API = process.env.NEEDS_FROM_API === '1';

const GITHUB_API_URL = process.env.GITHUB_API_URL ?? 'https://api.github.com';
const GITHUB_SERVER_URL = process.env.GITHUB_SERVER_URL ?? 'https://github.com';
const GITHUB_REPOSITORY = process.env.GITHUB_REPOSITORY ?? '';
const GITHUB_RUN_ID = RUN_ID_OVERRIDE || (process.env.GITHUB_RUN_ID ?? '');
const GITHUB_RUN_ATTEMPT = RUN_ATTEMPT_OVERRIDE || (process.env.GITHUB_RUN_ATTEMPT ?? '1');
const GITHUB_WORKFLOW = WORKFLOW_OVERRIDE || (process.env.GITHUB_WORKFLOW ?? 'Workflow');
const GITHUB_EVENT_NAME = EVENT_NAME_OVERRIDE || (process.env.GITHUB_EVENT_NAME ?? '');
const GITHUB_REF_NAME = REF_NAME_OVERRIDE || (process.env.GITHUB_REF_NAME ?? '');
const GITHUB_EVENT_PATH = process.env.GITHUB_EVENT_PATH ?? '';

// IS_COMPONENTS_V2. under this flag discord rejects content/embeds/poll outright,
// so the entire card has to be expressed as components.
const IS_COMPONENTS_V2 = 32768;

const COMPONENT_CONTAINER = 17;
const COMPONENT_ACTION_ROW = 1;
const COMPONENT_BUTTON = 2;
const COMPONENT_TEXT_DISPLAY = 10;
const COMPONENT_SEPARATOR = 14;

// style 5 is a link button — the only non-interactive button, and therefore the
// only kind a webhook that is not owned by an application is allowed to send
const BUTTON_STYLE_LINK = 5;

const ACCENT_SUCCESS = 0x2EA043;
const ACCENT_FAILURE = 0xDA3633;
const ACCENT_NEUTRAL = 0x6E7681;

// a container caps at 40 nested components and 4000 characters of text display,
// which a 12-leg matrix wipeout would blow through if each job got its own row
const MAX_LISTED_JOBS = 8;
const MAX_TEXT_LENGTH = 1500;
const MAX_BUTTON_LABEL_LENGTH = 80;

function warn (message) {
  process.stdout.write(`::warning::${message}\n`);
}

function truncate (text, limit) {
  if (text.length <= limit) return text;
  return `${text.slice(0, limit - 1)}…`;
}

// commit subjects are author-controlled and land inside markdown, so flatten them
// to a single line and drop backticks that would break out of inline code spans
function sanitizeSingleLine (text, limit) {
  const firstLine = String(text ?? '').split('\n')[0].replace(/`/g, "'").trim();
  return truncate(firstLine, limit);
}

function formatDuration (milliseconds) {
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return 'unknown';

  const totalSeconds = Math.round(milliseconds / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

// needs-key -> display name (or name prefix) for jobs that declare a custom
// `name:`, supplied by the caller via the job-names input. the API only ever
// reports the RENDERED name, so a custom name is unrecoverable without this.
let jobNameMap = {};
try {
  jobNameMap = JOB_NAMES_JSON ? JSON.parse(JOB_NAMES_JSON) ?? {} : {};
} catch {
  warn('Could not parse the job-names input; falling back to name-based recovery.');
}

/**
 * recovers the `needs` key (the job id) from a job name reported by the API.
 *
 * a reusable-workflow callee arrives as `<caller-job-id> / <callee-job-name>`,
 * and the caller only ever sees the CALLER's job id in its `needs` — so that
 * decoration comes off first, and no map entry is ever needed for one.
 *
 * then the job-names map, for jobs declaring a custom `name:` (the API reports
 * only the rendered name). exact match wins over prefix, longer prefix over
 * shorter — a prefix is what covers matrix legs (`integration · <suite>`) and
 * interpolated names (`deploy <env>`) with one entry.
 *
 * unmapped names fall back to stripping a matrix ` (<leg>)` suffix, which is
 * exact for jobs with no custom `name:` — sndwrks-local's copy relies on it.
 */
function needsKeyForJobName (jobName) {
  if (jobName.includes(' / ')) return jobName.split(' / ')[0].trim();

  let mapped = null;
  for (const [needsKey, name] of Object.entries(jobNameMap)) {
    if (name === jobName) return needsKey;
    if (jobName.startsWith(name) && (!mapped || name.length > mapped.name.length)) {
      mapped = { needsKey, name };
    }
  }
  if (mapped) return mapped.needsKey;

  return jobName.replace(/\s+\(.*\)$/, '').trim();
}

async function fetchGithubJson (path) {
  const response = await fetch(`${GITHUB_API_URL}${path}`, {
    headers: {
      accept: 'application/vnd.github+json',
      authorization: `Bearer ${GH_TOKEN}`,
      'x-github-api-version': '2022-11-28',
      'user-agent': 'sndwrks-discord-notify',
    },
  });

  if (!response.ok) {
    throw new Error(`GitHub API ${path} responded ${response.status}`);
  }

  return response.json();
}

function readPullRequestUrl () {
  // a workflow_run notifier has no pull_request payload to read, so it resolves
  // the link itself and passes it in
  if (PR_URL_OVERRIDE) return PR_URL_OVERRIDE;

  if (GITHUB_EVENT_NAME !== 'pull_request' || !GITHUB_EVENT_PATH) return '';

  try {
    // the run object's `pull_requests` array comes back empty on this repo, so the
    // event payload is the only reliable source for the PR link
    const event = JSON.parse(readFileSync(GITHUB_EVENT_PATH, 'utf8'));
    return event?.pull_request?.html_url ?? '';
  } catch {
    return '';
  }
}

/**
 * splits completed jobs into hard failures, soft failures and skips.
 *
 * a job whose API conclusion is `failure` while its `needs` result is `success`
 * is by definition continue-on-error — github let the run stay green despite the
 * job failing. detecting it from that disagreement means no hardcoded allowlist
 * and no drift when the flag is added to or removed from a job later.
 */
function classifyJobs (apiJobs, needs) {
  const hardFailed = [];
  const softFailed = [];
  const skipped = [];

  for (const job of apiJobs) {
    // the notify job is querying its own run, so it sees itself as in_progress
    // with a null conclusion. filtering on status excludes it without relying on
    // a name match, which the `caller / ` prefix would otherwise defeat.
    if (job.status !== 'completed') continue;

    const needsKey = needsKeyForJobName(job.name);
    const needsResult = needs[needsKey]?.result;

    if (needsResult === undefined) {
      warn(`Job "${job.name}" is missing from the notify job's needs: — its status is not reflected in the Discord card. Add "${needsKey}" to notify-discord.needs.`);
    }

    if (job.conclusion === 'failure' || job.conclusion === 'timed_out') {
      if (needsResult === 'success') softFailed.push(job);
      else hardFailed.push(job);
    } else if (job.conclusion === 'skipped') {
      skipped.push(job);
    }
  }

  return { hardFailed, softFailed, skipped };
}

/**
 * builds a `needs`-shaped object from the jobs REST API, for callers that have no
 * needs context of their own (a workflow_run notifier).
 *
 * soft-failure detection is lost by construction — it works by spotting a
 * DISAGREEMENT between a job's API conclusion and its needs result, and here the
 * two are the same value. a continue-on-error job therefore reads as a hard
 * failure. nothing in this repo sets continue-on-error on a build job, so the
 * distinction has nothing to express.
 */
function needsFromApiJobs (apiJobs) {
  const needs = {};
  for (const job of apiJobs) {
    if (job.status !== 'completed') continue;
    needs[needsKeyForJobName(job.name)] = { result: job.conclusion };
  }
  return needs;
}

function resolveOverallStatus (needs) {
  const results = Object.values(needs).map((entry) => entry?.result);
  if (results.length === 0) return 'neutral';
  if (results.includes('failure')) return 'failure';
  if (results.includes('cancelled')) return 'cancelled';
  // every job skipped means nothing actually ran — a fork PR on assistant-evals,
  // or a detect-changes no-op. a green card there would claim a pass that never
  // happened.
  if (results.every((result) => result === 'skipped')) return 'neutral';
  return 'success';
}

function buildRunUrl () {
  const base = `${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}`;
  return GITHUB_RUN_ATTEMPT !== '1' ? `${base}/attempts/${GITHUB_RUN_ATTEMPT}` : base;
}

function buildJobLines (hardFailed, skipped) {
  const lines = [];

  for (const job of hardFailed.slice(0, MAX_LISTED_JOBS)) {
    lines.push(`✗ ${job.name}`);
  }

  const remainingSlots = MAX_LISTED_JOBS - lines.length;
  for (const job of skipped.slice(0, Math.max(remainingSlots, 0))) {
    lines.push(`⊘ ${job.name} — skipped`);
  }

  const hidden = (hardFailed.length + skipped.length) - lines.length;
  if (hidden > 0) lines.push(`…and ${hidden} more`);

  return lines.join('\n');
}

function buildButtons ({ runUrl, hardFailed, pullRequestUrl, headSha }) {
  const buttons = [{
    type: COMPONENT_BUTTON,
    style: BUTTON_STYLE_LINK,
    label: 'View run',
    url: runUrl,
  }];

  if (hardFailed.length > 0 && hardFailed[0].html_url) {
    buttons.push({
      type: COMPONENT_BUTTON,
      style: BUTTON_STYLE_LINK,
      label: truncate(`Failed: ${hardFailed[0].name}`, MAX_BUTTON_LABEL_LENGTH),
      url: hardFailed[0].html_url,
    });
  }

  if (pullRequestUrl) {
    buttons.push({
      type: COMPONENT_BUTTON,
      style: BUTTON_STYLE_LINK,
      label: 'Pull request',
      url: pullRequestUrl,
    });
  } else if (headSha) {
    buttons.push({
      type: COMPONENT_BUTTON,
      style: BUTTON_STYLE_LINK,
      label: 'Commit',
      url: `${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/commit/${headSha}`,
    });
  }

  return buttons;
}

function buildPayload ({ status, run, jobs, duration, pullRequestUrl }) {
  const { hardFailed, softFailed, skipped } = jobs;
  const runUrl = buildRunUrl();
  const attemptNote = GITHUB_RUN_ATTEMPT !== '1' ? ` · attempt ${GITHUB_RUN_ATTEMPT}` : '';
  const headSha = run?.head_sha ?? '';
  const subtitle = SUBTITLE || sanitizeSingleLine(run?.display_title ?? run?.head_commit?.message ?? '', 100);
  // DOCUMENTATION-REPO DIVERGENCE (2 of 2a): on a public repo a fork's branch
  // name is attacker-controlled, and it lands inside a markdown code span. the
  // commit subject already gets this treatment; the ref name did not.
  const refName = sanitizeSingleLine(GITHUB_REF_NAME, 80);

  if (status === 'success' || status === 'neutral') {
    const heading = status === 'success'
      ? `### ✅ ${GITHUB_WORKFLOW} · ${refName}`
      : `### ⊘ ${GITHUB_WORKFLOW} · ${refName} — no jobs ran`;

    const detail = [subtitle && `\`${subtitle}\``, duration, attemptNote.replace(' · ', '')]
      .filter(Boolean)
      .join(' · ');

    const softNote = softFailed.length > 0
      ? `\n-# ⚠ ${softFailed.map((job) => job.name).join(', ')} failed (non-blocking)`
      : '';

    return {
      flags: IS_COMPONENTS_V2,
      // DOCUMENTATION-REPO DIVERGENCE (2 of 2b): components v2 text_display
      // honours mentions, so on a public repo a fork branch named `@everyone`
      // would ping the whole server. nothing this script sends needs to mention
      // anyone.
      allowed_mentions: { parse: [] },
      components: [{
        type: COMPONENT_CONTAINER,
        accent_color: status === 'success' ? ACCENT_SUCCESS : ACCENT_NEUTRAL,
        components: [
          { type: COMPONENT_TEXT_DISPLAY, content: truncate(`${heading}\n-# ${detail}${softNote}`, MAX_TEXT_LENGTH) },
          { type: COMPONENT_ACTION_ROW, components: buildButtons({ runUrl, hardFailed: [], pullRequestUrl, headSha }) },
        ],
      }],
    };
  }

  const verb = status === 'cancelled' ? 'cancelled' : 'failed';
  const icon = status === 'cancelled' ? '⊘' : '❌';

  const metadata = [
    `Branch \`${refName}\``,
    headSha && `\`${headSha.slice(0, 7)}\``,
    run?.triggering_actor?.login,
    GITHUB_EVENT_NAME,
    duration,
  ].filter(Boolean).join(' · ');

  const containerComponents = [
    { type: COMPONENT_TEXT_DISPLAY, content: `### ${icon} ${GITHUB_WORKFLOW} ${verb}${attemptNote}` },
    { type: COMPONENT_TEXT_DISPLAY, content: truncate(`-# ${metadata}\n${subtitle ? `\`${subtitle}\`` : ''}`, MAX_TEXT_LENGTH) },
  ];

  const jobLines = buildJobLines(hardFailed, skipped);
  if (jobLines) {
    containerComponents.push({ type: COMPONENT_SEPARATOR, divider: true, spacing: 1 });
    containerComponents.push({
      type: COMPONENT_TEXT_DISPLAY,
      content: truncate(`**Failed jobs**\n${jobLines}`, MAX_TEXT_LENGTH),
    });
  }

  if (softFailed.length > 0) {
    containerComponents.push({
      type: COMPONENT_TEXT_DISPLAY,
      content: truncate(`-# ⚠ ${softFailed.map((job) => job.name).join(', ')} failed (non-blocking)`, MAX_TEXT_LENGTH),
    });
  }

  containerComponents.push({
    type: COMPONENT_ACTION_ROW,
    components: buildButtons({ runUrl, hardFailed, pullRequestUrl, headSha }),
  });

  return {
    flags: IS_COMPONENTS_V2,
    allowed_mentions: { parse: [] },
    components: [{
      type: COMPONENT_CONTAINER,
      accent_color: status === 'cancelled' ? ACCENT_NEUTRAL : ACCENT_FAILURE,
      components: containerComponents,
    }],
  };
}

async function postToDiscord (payload) {
  // with_components is what lets a webhook that is not owned by an application
  // send components at all; without it discord silently drops the field
  const url = new URL(DISCORD_WEBHOOK_URL);
  url.searchParams.set('with_components', 'true');

  for (let attempt = 0; attempt < 3; attempt += 1) {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (response.ok) return true;

    if (response.status === 429) {
      // retry_after is fractional seconds. a PR touching the assistant fires
      // three workflows at once, and discord shares a 5-per-5s bucket per channel.
      const body = await response.json().catch(() => ({}));
      const waitMilliseconds = Math.min((Number(body.retry_after) || 1) * 1000, 10000);
      await new Promise((resolve) => { setTimeout(resolve, waitMilliseconds); });
      continue;
    }

    const text = await response.text().catch(() => '');
    warn(`Discord rejected the notification (${response.status}): ${truncate(text, 500)}`);
    return false;
  }

  warn('Discord rate limited the notification after 3 attempts; giving up.');
  return false;
}

async function main () {
  if (!DISCORD_WEBHOOK_URL && !DRY_RUN) {
    // expected on fork PRs, where secrets are withheld, and before the repo
    // secret is created. not an error.
    warn('DISCORD_WEBHOOK_URL is not set — skipping the Discord notification.');
    return;
  }

  let needs = {};
  try {
    needs = JSON.parse(NEEDS_JSON) ?? {};
  } catch {
    warn('Could not parse the needs context; the card will fall back to API data.');
  }

  let run = null;
  let apiJobs = [];
  try {
    const runPath = `/repos/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}/attempts/${GITHUB_RUN_ATTEMPT}`;
    const [runData, jobsData] = await Promise.all([
      fetchGithubJson(runPath),
      fetchGithubJson(`${runPath}/jobs?per_page=100`),
    ]);
    run = runData;
    apiJobs = jobsData.jobs ?? [];
  } catch (error) {
    // a card without per-job detail still beats silence
    warn(`Could not load run detail from the GitHub API: ${error.message}`);
  }

  if (NEEDS_FROM_API) needs = needsFromApiJobs(apiJobs);

  const status = resolveOverallStatus(needs);
  const jobs = classifyJobs(apiJobs, needs);

  // the attempt's own start time. job timestamps are wrong here: a "re-run failed
  // jobs" attempt carries successful jobs over with their ORIGINAL timestamps, so
  // deriving duration from them can report hours for a two-minute re-run.
  const startedAt = run?.run_started_at ? Date.parse(run.run_started_at) : NaN;
  const duration = formatDuration(Date.now() - startedAt);

  const payload = buildPayload({
    status,
    run,
    jobs,
    duration,
    pullRequestUrl: readPullRequestUrl(),
  });

  if (DRY_RUN) {
    process.stdout.write(`status=${status}\n${JSON.stringify(payload, null, 2)}\n`);
    return;
  }

  const delivered = await postToDiscord(payload);
  if (delivered) {
    process.stdout.write(`Posted a ${status} card for ${GITHUB_WORKFLOW} to Discord.\n`);
  }
}

main().catch((error) => {
  // the last line of defence: never fail the job over a notification
  warn(`Discord notification failed: ${error?.stack ?? error}`);
});
