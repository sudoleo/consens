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
100 PDF pages. File quotas/30-day expiry from PR 1 apply to each output. Unsupported
font glyphs fail explicitly rather than producing an unreadable successful file.
The bundled Vera font is the default. Operators can configure a licensed font pair
using `AGENT_DOCUMENT_FONT` and `AGENT_DOCUMENT_FONT_BOLD` for additional scripts.
There is no general DOCX round-trip editor: uploaded files are source evidence;
revisions edit a structured document previously generated by Consens. Replacing a
section preserves sources and caveats; a complete new document supports broader
restructuring. Removing an output makes that version unavailable for further edits.

Deploy the added `versions.expires_at` collection-group index and exclude `content`
from indexing. No migration of existing turns is required. Linux is the supported
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
