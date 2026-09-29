# Agent integrations: implementation and review map

Baseline: `main` at `b13e0205` (2026-09-27); no open PRs at inspection. Existing
worktrees were left intact. Review in order: attachments → documents → Google
Calendar → Gmail. Each later PR targets the preceding feature branch; none is
automatically merged into main.

| Existing flow | PR 1 files (base) | PR 2 documents | PR 3 Calendar | PR 4 Gmail |
|---|---|---|---|---|
| Composer / mobile | Reuse picker, chips, authentication and run registry | Download/version cards | Connections and concrete action preview | Account, recipient, thread and attachment preview |
| `/agent` → delegated loop | Owner/chat-bound file IDs and bounded retrieval | Registered artifact tools | Scoped Calendar tools | Scoped Gmail tools |
| Independent comparisons | Same selected evidence, capability-aware visual input | Preserve disagreement in document evidence | Pass only selected event evidence | Pass only selected message evidence |
| Synthesis / review | Keep source locators and extraction limits | Versioned output, explicit review provenance | Describe prepared actions accurately | Describe drafts accurately; never claim a send before confirmation |
| SSE / stop / recovery | Existing activity, cancellation and saved turns | Saved artifacts survive disconnect | Durable proposals and execution receipts | Durable drafts and uncertain-send state |
| Firestore / bookmarks | Metadata only; private object storage; owner checks | Immutable versions / source lineage | Encrypted Google tokens / incremental scopes | Reuse connections with separate Gmail grants |
| Quotas / accounting | Upload/storage/extraction limits; normal model ledger | Bounded rendering; normal model ledger | API/time limits; no automatic write retries | Pagination/size limits; no ambiguous resend |
| Cleanup / security | Account fence, chat deletion, retention, untrusted data | Reuse private file lifecycle | Disconnect, revoke, content-bound confirmation | Same confirmation; attachment hashes |

## Findings checked against the current code

The legacy attachment parser already validates magic bytes, DOCX ZIP expansion,
per-file/aggregate limits and image size. The Agent frontend and request schema
reject files; Agent bookmarks contain an empty attachment list and only ordinary
Consensus turns retain name/type/size. Legacy PDF extraction has no process CPU
or memory bound (review R26); the new durable pipeline must isolate extraction.

The Agent uses a strict server-owned ToolRegistry, transactional model receipts,
per-account admission, a renewable run lease, cancellation and saved interrupted
turns. Comparisons do not inherit chat history. Synthesis deliberately excludes
tool transcripts and fixes one visible answer before Differences/Coverage review;
artifacts and action proposals therefore need an explicit evidence handoff.

Storage mutations must read the existing account-deletion fence and active chat
inside their transaction. File bytes must not enter Firestore, bookmarks, logs,
public shares or watch publishing. Google grants are independent of Firebase
login. External contents never confer permissions or approve an action.

## Validation records

Each PR extends this document with executed checks, setup and remaining external
requirements. Historical audit results are not evidence for these new changes.

## PR 1 — Private Agent attachments

Users can upload multiple PDF, DOCX, text or image files and refer to them again
in the same chat. Independent models and supporting agents can receive selected
file evidence with source locators and explicit extraction/vision limitations.

**Setup.** Set `AGENT_FILES_BUCKET` to a dedicated, private Google Cloud Storage
bucket. Use application-default credentials with object read/create/delete rights
only on that bucket; enable uniform bucket access and public access prevention.
Do not expose Firebase download tokens or signed public links. Configure a bucket
lifecycle deletion rule after 30 days as a second bound on orphan object retention;
disable object versioning and configure soft-delete retention according to the
published deletion policy. Deploy the `files` collection-group field indexes in
`firestore.indexes.json` before enabling uploads. No existing data migration.
Development only: `AGENT_FILES_DEVELOPMENT=1` and `AGENT_FILES_LOCAL_DIR` on a private,
persistent volume. Test profiles permit that adapter automatically.

**Limits and lifecycle.** The existing composer accepts two files per upload batch
(5 MiB each); a model call can explicitly select up to five stored files. Maximum
100 stored files / 100 MiB per account. Uploads reserve capacity transactionally;
failed uploads and stopped runs do not grant any extra permission. Files expire
in 30 days and are removed by the existing hourly maintenance task. Processing
records abandoned for 20 minutes are removed too. Chat/account deletion removes
private objects before deleting their metadata. Ordinary Consensus uploads retain
their existing transient behavior. Public shares never receive private bytes.

**Processing.** Extraction runs once in an isolated process: 15 s wall time,
10 s CPU and 768 MiB virtual-memory limit on Linux, 80 PDF pages, 120,000 text
characters / 120 chunks. Windows enforces the wall deadline; Linux is the
production extraction target. Text excerpts have page/paragraph/table/line labels.
DOCX drawings, headers and footnotes are explicitly not extracted. No OCR service
is called. Small scan PDFs may be sent natively to declared compatible models;
`file-parser` is pinned to `native`, with no automatic paid OCR fallback.
Images require current model metadata declaring image input; unknown capabilities
fail closed to a visible limitation. Native PDF limit is 2 MiB. Large/scanned
files that cannot be read visually must be re-exported, split or transcribed.

**Data sent to models.** The root receives a file catalog and bounded, relevant
excerpts of selected files. `read_file` pages through specific additional evidence.
Comparisons receive explicit IDs or, without them, the current selection.
Workers receive only the `file_ids` passed to `start_agent` (they have no
`read_file` tool), so the orchestrator must pass files a worker needs.
Visual files the root opens via `read_file` are added after the user's
selection and never displace it (five files at most per call). Ordinary judges
retain their existing comparison-based input. Binary payloads stay in process
memory, never tool journals or Firestore. The token estimator reserves a visual
allowance per image and about 3k tokens per PDF page (capped at 200k); a native
PDF is only sent when that allowance plus headroom fits the model's context
window, otherwise the model is told it cannot read the scan. The existing
provider receipts record actual usage. No file instructions can execute server
operations.

**Storage configuration.** Without `AGENT_FILES_BUCKET` (or the explicit local
development directory) uploads fail before any metadata or quota is written,
and chat/account deletion skips the object store instead of failing. Retention
pages through expired records with a time budget; a single failing delete is
logged and retried on the next run instead of stalling the queue.

**Tests.** Deterministic storage/ownership/expiry/abort tests and existing Agent
loop/comparison tests are run without external model calls. A real production
bucket and paid multimodal provider smoke test remain deployment prerequisites;
no live credential or provider operation is claimed by the offline test results.
Official payload references checked 2026-09-27:
- https://openrouter.ai/docs/guides/overview/multimodal/image-understanding
- https://openrouter.ai/docs/guides/overview/multimodal/pdfs

Dependency: base PR; no dependency on an unmerged feature PR.

PR 1 validation record (2026-09-27): frontend `npm test`: **517 passed**;
`npm run build` and `npm run build:check`: successful. Focused backend regression
run: **299 passed**, plus the added complete file→comparison lifecycle and
account-fence tests. The full backend run reproduces seven baseline failures
(confirmed separately at `b13e0205`): one developer-key/quota case in
`test_ask_endpoints.py`, five key-dependent follow-up cases in
`test_followup_context.py`, and the stale archived-tab source assertion in
`test_consensus_progress_ui.py`. No production key was added to mask those tests.
Publisher standalone gate: **3 passed**. Browser flow is checked in at
`tests/e2e/test_agent_workspace_frontend.py` (1280/390/320 px); execution was blocked
because Chromium is absent and its download returned an invalid ZIP. It remains
an explicit verification requirement, not a passed browser/layout claim.

Follow-up validation: Chromium was installed through a separate test runtime.
The contradictory Pro/Usage browser fixture was corrected, and the private-file
panel now uses border-box sizing and the existing thread order. The built upload,
restoration-state and authenticated-download flows pass at 1280, 390 and 320 px
(3 browser tests), including the no-horizontal-overflow assertion.

## PR 2 — Create and revise documents

Users can create real downloadable DOCX and PDF reports, decision briefs and
action plans from file evidence, research and model comparisons. Follow-up requests
can replace a numbered section while keeping older versions available in the chat.

The three document tools reuse the root registry, shared tool/time budgets,
cancellation, file quotas, authenticated downloads, owner/chat guards, retention
and deletion. Documents must be created before the existing `judge_answer`
handoff; their saved descriptors are explicitly supplied to the tool-free synthesis.
An SSE `resources` event shows download/version cards immediately, also after
restoration. The checked chat answer and a generated document are separate outputs:
answer review is not a claim that document prose or layout received an independent
model review. Document specifications include uncertainties and differing views;
revising a section preserves them. Model comparison IDs/answer hashes and exact
source file hashes/locators are stored with each version. Web references are labeled
as model-supplied and need checking against the original source.

Rendering is offline: strict structured headings/paragraphs/tables/sources, no
arbitrary HTML, shell, templates or remote fetching. `python-docx==1.2.0` and
`reportlab==4.4.9` are pinned. Each format is reopened before saving; both private
objects are downloaded and hash-verified before the version is published.
Repeated identical tool operations reuse saved results. Transactional base-version
checks reject concurrent stale edits. A failed two-format save deletes unpublished
outputs; a lost commit response never deletes already published files.

Limits: 40 KB structured content, 20 sections, 6 table columns, 60 rows per table,
25 versions, 30 s render deadline / 20 s CPU / 1 GiB address space on Linux and
100 PDF pages. File quotas/30-day expiry from PR 1 apply to each output; every
version uses two of the 100 file slots. Unsupported PDF font glyphs fail
explicitly, naming the characters so the model can rewrite them, rather than
producing an unreadable successful file. The bundled DejaVu Sans pair
(`app/services/document_fonts/`, Bitstream Vera/DejaVu license) covers Latin
including Central/Eastern European letters, Greek, Cyrillic, arrows and check
marks; CJK and emoji are not covered. Operators can configure a licensed font
pair using `AGENT_DOCUMENT_FONT` and `AGENT_DOCUMENT_FONT_BOLD` for additional
scripts. The render subprocess imports only `agent_document_spec.py`, never
Firestore or Firebase credentials. Document tools accept up to 50 KB of JSON
arguments; all other tools keep their 24 KB limit. `lxml` (required by
python-docx) is pinned as well.
There is no general DOCX round-trip editor: uploaded files are source evidence;
revisions edit a structured document previously generated by Consens. Replacing a
section preserves sources and caveats; a complete new document supports broader
restructuring. Removing an output makes that version unavailable for further edits.

Deploy the added `versions.expires_at` collection-group index and exclude `content`
from indexing. Retention pages through expired versions and removes a document's
manifest once its current version has expired. No migration of existing turns is required. Linux is the supported
render target; LibreOffice is needed only for the reviewer layout check, not in the
production renderer. Dependencies: PR 1 / #7 (`feat/agent-attachments`).

Validation: 69 focused backend tests and 64 focused JavaScript tests passed. A real
two-page report with a 30-row table was generated in both formats; every PDF page
and every DOCX page rendered through LibreOffice was visually inspected for wrapping,
table boundaries, page breaks and headings. Unit tests reopen the binary formats,
verify table content, immutable versions, source provenance, stale edits, cross-user
and cross-chat denial, cancellation, unsupported glyphs, and rollback after a partial
storage failure. The production build and build consistency check passed. Live
bucket/provider behavior remains a deployment smoke test.

## PR 3 — Google accounts and Calendar

Users can connect their own Google accounts, select calendars and compare events
or availability with uploaded evidence and model results. The agent can prepare
new or changed events, while users review the exact content and invitation
recipients before any Google write.

This PR extends the existing root ToolRegistry, authentication/Pro gate, immutable
turn settings and replay, synthesis evidence, SSE, restoration, private file/chat
lifecycle, account deletion and maintenance. Google tools are root-only and bound
to the selected account/calendars. Model tokens remain on the existing usage ledger;
API operations have an additional 500-request daily quota. The ToolRegistry allows
20 server-defined tools while retaining the existing per-run execution budget.

The common connection/approval foundation lives here for Gmail to reuse. OAuth
grants are incremental; state, PKCE, signed identity, refresh races, token encryption
and disconnect are enforced server-side. Actions are immutable hash-bound proposals.
Only the separate authenticated confirmation endpoint can execute them. Repeated
confirmations cannot repeat a write; ambiguous results use read-only reconciliation.
Calendar updates preserve omitted fields and private metadata and use ETags.
Time-zone offsets, DST transitions, all-day exclusive ends, recurrence rules and
series/instance selection are explicit. No cancellation/delete/series-split tool is
advertised. Search reads are bounded and paginated, with no background synchronization.

Google-data chats require explicit model-sharing consent and an operator-configured
model/hosting-provider allowlist, including review models. Web search and external
source checking are disabled for these chats, including later follow-ups. Relevant
excerpts are used instead of uploading whole calendars. External content cannot
call the user-only confirmation API or select another account.

Setup, index changes, key rotation, public-operation prerequisites, official source
references, retention and recovery semantics are detailed in
[`google-integrations-setup.md`](google-integrations-setup.md). Google credentials
are not required for the deterministic integration tests. Live OAuth/Workspace
policies, real token issuance and invitation delivery still need an explicitly
authorized staging account; no real invitation was sent.

Dependency: PR 2 / #8 (`feat/agent-documents`), transitively PR 1 / #7.
Validation: 125 focused backend integration/regression tests passed, including
nine OAuth/token/model-routing tests and the real comparison → synthesis → judges
routing path. The full backend run passed 2,745 tests (12 skipped), with only the
seven independently reproduced baseline failures recorded above. All 521 JavaScript
tests passed. Seven built-browser flows passed: attachment and Calendar review at
1280/390/320 px, plus the real callback popup/CSP with simulated OAuth endpoints.
Production build and build-consistency checks passed.

Mobile follow-up correction: the expanded Google selector has a viewport-bounded
scroll area so its next-message consent remains reachable in the fixed composer.
Calendar browser cases explicitly exercise this after confirmation.

## PR 4 — Gmail, message evidence and controlled sending

Users can search relevant mail, read complete threads in bounded pages and prepare
or revise replies using uploaded evidence and generated documents. Drafts remain
saved in Consens until the user reviews the exact recipients, message, reply
reference and attachment versions and explicitly confirms sending.

Dependency: PR 3 / #9 (`feat/agent-google-calendar`), transitively PRs #7 and #8.
The common OAuth/approval foundation stays in PR 3; Gmail adds separate readonly
and send grants, three regular root tools and the Gmail action handler. Existing
file extraction, private storage, document versioning, model comparison, immutable
synthesis/review, token accounting, cancellation, SSE, follow-ups and restoration
are reused. The model registry has no confirmation/send capability. Imported MIME
parts keep account/message/part provenance; referenced message headers appear in
restored chat cards. No unrelated mailboxes are copied into a model context.

Decisions and configuration are in `google-integrations-setup.md`: enable Gmail API
in the same Google project, use the existing secret configuration and approved
model/hosting routes, and deploy the new `google_evidence`/`google_write_intents`
expiry indexes. Existing Calendar-only turn settings are normalized for compatible
replay; no content backfill is required. The privacy disclosure now includes Gmail
and the 30-day content-free unresolved-write fence that survives chat deletion.

Drafts are local to Consens, avoiding unnecessary compose/modify scope. Sending
constructs real MIME only after server-side confirmation and rechecks all private
attachment bytes/hashes. Revisions preserve prior versions and invalidate previous
approval. Repeated or concurrent confirmations claim one operation. Ambiguous
results are searched by the exact Message-ID in Sent, never automatically resent;
a shared hash/status fence also blocks equivalent ambiguous operations in another
chat. Account deletion and expiry block later writes. Provider errors expose no
raw message/token response bodies.

The targeted integration suite covers separate/partial grants, original-message
reply headers, paged large threads/body continuations, external MIME text parts,
HTML/charset handling, malformed data, attachment reuse/deletion/ownership,
recipient/header injection, stale revisions, revoked permission, expiry, duplicate
and ambiguous sends, provider 403/429/503, account deletion and cross-chat fences.
A real Agent loop test loads offers, runs two independent model completions, saves
openable DOCX/PDF with source and comparison hashes, prepares a draft with those
files, and finishes the existing synthesis and review. All provider/model responses
in these tests are simulated; actual tool processing, persistence, MIME generation,
format parsing and orchestration execute.

Remaining limits: bounded thread/message sizes, plain-text outgoing mail, no sender
aliases or encrypted-mail decryption, no Gmail Drafts synchronization. Scanned-file
and document rendering limits remain those of PRs 1/2. Public Gmail reading requires
restricted-scope verification and the applicable security assessment for this
server-based design; the installation guide identifies official requirements and
an explicit staging procedure. Live Google credentials, consent-screen approval,
Workspace policy, refresh issuance, real bucket/provider access and actual delivery
still require deployment validation. No real mail or calendar invitation was sent.

Final combined validation (2026-09-27):

- `UNIT_TEST_MODE=1 python -m pytest tests --ignore=tests/e2e -q`:
  **2,757 passed, 12 skipped**, seven pre-existing failures reproduced on pristine
  main. The failures are `test_usage_limit_blocks_developer_key_path`, the archived
  drawer source assertion, and five `test_followup_context` cases listed in the
  earlier baseline record. No newly introduced failure remains.
- Full `npm test`: **524 passed / 59 files**. The nine Google/workspace tests were
  rerun successfully after the final file-provenance UI addition.
- Ten built-browser cases passed: file upload/restore/private download and Gmail
  revision/attachment download/restored approval at 1280/390/320 px, plus Calendar
  selection/approval at those widths and the actual OAuth callback/CSP with mocked
  provider endpoints. Gmail previews were inspected at 390/320 px. The additional
  Calendar next-message consent assertions also passed in all four Calendar cases.
- `npm run build`, `npm run build:check`, `git diff --check` and the standalone
  publisher gate (`python -E -S -m unittest discover -s tests -p
  test_publisher_standalone.py -v`, three tests) passed.
- All external Google/model responses were simulated. File extraction, DOCX/PDF
  rendering/reopening, MIME generation, persistent action claims, API ownership,
  real orchestration and browser behavior executed locally. Real OAuth consent,
  private bucket/model hosting and delivery remain the explicit staging gates.

Stack review: #7 targets main, #8 targets the attachment branch, #9 targets the
document branch, and Gmail targets the Calendar branch. Review the isolated diffs
in that order. Preserve ancestry when merging, or restack/retarget each dependent
PR after a squash merge; do not merge the final branch as a substitute for reviewing
the four changes. No PR has been merged by this implementation task.
