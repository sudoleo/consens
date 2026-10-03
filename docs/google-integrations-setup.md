# Google integrations: setup and operating requirements

This feature is disabled until configured. OAuth is for each Consens user's own
Google account; there is no service-account impersonation or domain-wide delegation.
Do not use production mail or invitation recipients for automated smoke tests.

## Scope: Google is a source, not a hand (since 2026-10-03)

Consens compares models; disagreement is the product. Google data earns its place
as **private evidence for a question** ("which of the offers in my inbox?", "does
my calendar allow this project?"), the same role as an uploaded file. Agent chats
therefore:

- read **Gmail and Calendar** for a message the user selected them for
  ((+) menu → "Gmail & Calendar"), and
- take **files from Google Drive** as ordinary attachments ((+) menu → "Add from
  Google Drive", Google's own picker, `drive.file` only).

Writing back (sending mail, creating or changing events) stays in the code but is
**off unless `GOOGLE_WRITES_ENABLED=1`**: without it no write scope is requested,
no preparation tool is offered to the agent, confirmation is refused before any
claim, and older proposals can only be discarded. Assistants that live inside
Google do this natively; disagreement between models adds little to "3 or 4 pm?",
while these are the operations an instruction hidden in a mail would target.

Release path: Drive (`drive.file`, non-sensitive) and Calendar reading (sensitive)
can go public after Google's standard app verification. Gmail reading is a
restricted scope (security assessment, see below), so it stays in the consent
screen's **Testing** mode with listed test users (at most 100; Google expires
their refresh tokens after 7 days, the sheet then shows "Needs reconnection").

## Configuration

1. In a dedicated Google Cloud project, enable Calendar API, Gmail API, Google
   Drive API and Google Picker API. Configure an OAuth web application and its
   consent screen, verified domain, support contact, home page and privacy-policy
   URL. Use test users while verification is pending.
2. Register exactly `https://YOUR_HOST/agent/google/callback` as the redirect URI
   and `https://YOUR_HOST` as an **authorized JavaScript origin** (the Drive picker
   gets its token in the browser through Google Identity Services).
   Preserve this same origin through the reverse proxy. The popup callback has no
   external assets and clears its query immediately; redact its query string in
   **proxy/load-balancer logs as well as application logs**. The application
   redacts that route in Uvicorn access logging and raises the `httpx`/`httpcore`
   loggers to WARNING, because their INFO lines contain full Google API URLs
   (calendar IDs, search queries, page tokens). Never log OAuth request bodies,
   Authorization headers, provider responses or tokens.
3. Inject `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` and
   `GOOGLE_TOKEN_KEYS` through a managed secret store. `GOOGLE_TOKEN_KEYS` is a
   comma-separated Fernet key ring, newest key first; generate a key with
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   in an operator-controlled environment. Protect the secret store with KMS and
   least privilege. Keep old keys available until all retained credentials have
   been re-encrypted by refresh/reconnection; losing all old keys requires users
   to reconnect. Do not commit or print keys in deployment diagnostics.
4. Model routing. Every model call in a chat with Google data (agent, comparison,
   synthesis, Differences and Coverage judges) requires OpenRouter's zero data
   retention **and** `data_collection: "deny"`; existing provider routing of a model
   is kept. OpenRouter fails such a call closed when no endpoint qualifies; that
   model then fails like any unavailable model and the run continues with the
   others. No list has to be maintained: a live probe on 2026-10-03 reached 48 of
   52 catalogue models from all nine families under this rule; the four others
   have no ZDR endpoint at all (or need the account's 18+ confirmation) and fail
   in every chat already. Re-run the probe after a model refresh.
   Optional and stricter: `GOOGLE_ALLOWED_MODEL_IDS` (comma-separated OpenRouter
   model IDs; other models are refused with 403) and `GOOGLE_ALLOWED_PROVIDERS`
   (OpenRouter provider slugs; adds `provider.only` and `allow_fallbacks=false`).
   Review the processing terms of the hosting endpoints you rely on. These flags
   alone are not a compliance attestation.
4a. Drive picker: create an **API key** restricted to the Google Picker API and to
   HTTP referrer `https://YOUR_HOST/*`, and note the project **number**. Set
   `GOOGLE_PICKER_API_KEY` and `GOOGLE_PROJECT_NUMBER` (the picker's app ID: files
   picked there become readable to this project only, `drive.file`). Both values
   and `GOOGLE_CLIENT_ID` reach the browser by design; Drive needs no server
   secret, stores no grant and works even before the Gmail/Calendar secrets exist.
   The browser holds the short-lived token in memory, downloads the picked file
   (Docs as DOCX, Sheets as CSV of the first sheet, Slides as PDF) and uploads it
   with `drive_file_id`; the stored file is `kind: drive_file`.
5. Deploy `firestore.indexes.json`. OAuth state/action/evidence/intent expiry use collection-group
   indexes; credentials, OAuth secrets, proposal bodies and previews are excluded
   from indexes. Keep the existing deny-all browser Firestore rules. Production
   Firestore and private GCS encryption at rest remain required for Google-derived
   data, including imported attachments and generated documents.
6. Set `GOOGLE_INTEGRATIONS_ENABLED=1`, deploy, and verify the unconnected state,
   consent disclosure, account selection, incremental permissions, disconnect,
   and account/chat deletion in a dedicated staging account. Existing files and
   document features work without these Google settings. Leave
   `GOOGLE_WRITES_ENABLED` unset unless writing back is a deliberate decision.
7. Set `GOOGLE_TEST_USERS` to the verified email addresses of the consens accounts
   that may see Google (comma-separated; the same people as the consent screen's
   test users). Everyone else gets "not available" from the connections endpoint
   and sees no Google entry, so nobody runs into Google's "unverified app" wall.
   Unset means nobody; set `*` once Google has verified the app. Connect, finish,
   calendar list, confirm/renew, Drive uploads and Google selections in `/agent`
   refuse other accounts with 403.
8. Local testing: add `http://localhost:PORT` as JavaScript origin and
   `http://localhost:PORT/agent/google/callback` as redirect URI on the OAuth client,
   and `http://localhost:PORT/*` on the Picker key; a local checkout (no
   `RENDER_SERVICE_NAME`, no `ENVIRONMENT=production`) accepts the http redirect.

## Permissions and consent

| Capability | Scope | Why |
| --- | --- | --- |
| Google account identity | `openid email` | Verified subject and account label; no profile scope |
| Calendar reading | `https://www.googleapis.com/auth/calendar.readonly` | Calendar selection, event search/read/instances and free/busy |
| Calendar changes (separate request; only with `GOOGLE_WRITES_ENABLED=1`) | `https://www.googleapis.com/auth/calendar.events` | Create and patch events after exact confirmation |
| Gmail reading (restricted) | `https://www.googleapis.com/auth/gmail.readonly` | Targeted search, messages, complete paged threads, selected attachments and read-only send reconciliation |
| Gmail sending (sensitive; separate request; only with `GOOGLE_WRITES_ENABLED=1`) | `https://www.googleapis.com/auth/gmail.send` | Send the exact locally reviewed MIME message |
| Drive files (non-sensitive; browser token, never stored) | `https://www.googleapis.com/auth/drive.file` | Read only the files the user picks in Google's picker |

The token response determines actual capabilities; a partial OAuth grant does not
imply a missing permission. Connections are selected per message. Google data in a
chat (a Gmail/Calendar selection or a Drive file) needs the user's consent **once
per chat**: an unchecked box "Share with the models in this chat" discloses
processing by the chat's models, including comparison and review models. The first
consented run stores `google_consent` on the chat; the browser then sends the
consent with every later message of that chat, and the server still refuses any
request of a Google-data chat without it (older chats without the stored consent
ask once more). Such chats disable web search and external source-checking to
avoid sending private excerpts as search queries. Users can still combine prior
research, their uploaded files, comparisons, documents and selected Google data.
Drive files are Agent-only: a draft that leaves Agent mode loses them, with a notice.

## Lifecycle, limits and recovery

- Maximum five accounts, five selected calendars, 500 Google API requests per
  user/UTC day, 50 list results per request, 90-day event/freebusy query windows.
  Pagination is explicit. Transport has a 15-second timeout, 8 MB response cap and
  no automatic retries. Agent tools share the existing run tool/time/token limits;
  Google HTTP requests are not fabricated as billable model calls.
- OAuth state is single-use, owner- and browser-bound, expires after ten minutes,
  and includes PKCE and a verified OIDC nonce. Credentials use authenticated
  encryption bound to user and connection. Refresh leases prevent concurrent
  refresh writes, while account tombstones and connection revisions prevent a
  refresh or OAuth callback from restoring disconnected access.
- Exact proposals expire for approval after 30 minutes; proposal content and
  results expire after 30 days. Existing hourly maintenance removes expired OAuth
  states, action records and bounded message-evidence headers. A minimal per-user
  write-intent fence (hash, action/chat IDs and status, no message content) is also
  retained for 30 days, including after chat deletion, to block equivalent ambiguous
  writes from another chat. Account deletion removes it. Connection credentials
  remain until disconnect or account deletion. Chat deletion removes proposals and
  message evidence (`ChatStore._delete_chat_tree`); account deletion first asks
  Google to revoke every stored grant (best effort), then removes credentials,
  pending OAuth states and all chats/files. Disconnect deletes local access first
  and attempts provider revocation; on failure the UI links to Google's
  account-permissions page. Listing and disconnecting accounts stay available
  without Agent access (e.g. after a downgrade); connecting and actions require
  it. An API 401 marks a connection for reauthorization but keeps the sealed
  refresh token so that disconnect can still revoke it. Revocation is per Google
  grant: if two Consens users connected the same Google account, one user's
  disconnect also ends the other's grant. Content already in saved chat answers
  remains until users delete those chats.
- Model answers are rendered without any auto-loading remote resource (remote
  images, media, `<style>`, CSS `url()`), so injected calendar or mail text
  cannot exfiltrate data through markup that loads on render; links need a click.
- An event proposal shows the account, calendar, before/after fields, timestamps,
  IANA zone, recurrence target and all affected invitation recipients. All-day end
  dates are exclusive. DST offsets are validated; ambiguous autumn times require
  the desired explicit offset. Use `instances` and `target=instance` to edit one
  occurrence, or `target=series` for the master. Splitting a series at a future date
  and deleting events are deliberately not implemented.
- Confirmation hashes bind the complete server-held proposal and connection
  revision. Changing recipients/content creates a new proposal and supersedes the
  previous approval. Updates use `If-Match`; stale Google events fail instead of
  overwriting another change. Creates use a deterministic event ID. A durable claim
  precedes the write; repeated confirms return the recorded status. Lost responses
  or crashed producers become `unknown`, never an automatic resend. Read-only
  reconciliation checks the event's action/hash marker. A 404 or missing marker
  remains inconclusive; investigate in Calendar rather than issuing a duplicate.
- Stopping a model run stops further tool work. Already saved, unconfirmed proposals
  remain available for review and can be rejected. Once a user confirms an action,
  that action has an independent durable lifecycle; Stop cannot retract an invitation.

## Gmail behavior and limits

Gmail is selected explicitly for each message; Calendar permission is independent.
Search requires a query and returns at most ten IDs plus a next-page token. Reading
a thread retrieves only its ID inventory, then up to ten chosen full messages per
page; the default is three. Body excerpts have explicit continuation offsets.
Models must not claim a whole thread was read while pages or body excerpts remain.
Up to 100 distinct message references can be retained per chat; start another chat
for more. Inventories over 20,000 messages or bodies over 2 MB fail clearly. MIME
parsing caps depth (20), parts (1,000) and external text parts (10). HTML is reduced
to text without loading remote images or executing scripts; unsupported encodings
and conversion are disclosed. No background inbox synchronization or unread-state
changes occur.

`import_gmail_attachment` loads one selected MIME part through the shared private
file validator/extractor (5 MiB), preserving its account/message/part provenance.
Repeated imports reuse the saved file. Attachments must belong to the same user
and chat; encrypted/unsupported content follows normal file errors. Document
outputs from PR 2 are ordinary eligible private attachments. An email has at most
five attachments and 10 MiB total, 30 unique explicit To/Cc/Bcc addresses, a 500-char
subject and 20,000-char plain-text body. Inline CID rendering, aliases, S/MIME and
PGP decryption are not supported; inspect those messages in Gmail.

Drafts are saved **in Consens**, not in Gmail Drafts. `prepare_gmail_draft` and
`gmail_read(operation=draft)` support follow-up revisions and restored cards.
Each revision keeps the old proposal and supersedes its approval. This avoids
requesting the restricted `gmail.compose` scope or mailbox-modifying permissions.
The user sees the verified sender, all recipients including Bcc, original message
and thread, complete body, and downloadable attachment versions. Recipients the
user did not name in this chat and that are not participants of the replied
thread are highlighted (`recipient_warnings`), because an injected instruction in
mail or file content would typically add exactly such an address. Headers are
built when the draft is prepared: subjects with Unicode line breaks (U+2028,
U+2029, U+0085) or other control characters are rejected before approval. Authorizing send
later changes the connection revision: prepare and review a fresh draft afterward.
Reply metadata is fetched from the selected original message; the MIME carries its
thread ID, In-Reply-To and References, and a compatible subject.

Before sending, private bytes are re-read and checked against the approved file
hash, name, type and size. The durable claim prevents repeated POSTs. Any failure
while building the message locally, before the Gmail call, is `failed` (nothing was
sent) and does not keep the write-intent fence blocking. A network failure or
malformed success response leaves delivery `unknown`. With read access,
Check status searches only Sent for the deterministic Message-ID and verifies the
returned header and SENT label. No match is inconclusive (indexing may lag); it
never triggers a resend. With send-only permission, authorize read access or inspect
Sent manually. Google does **not** promise idempotency based on Message-ID, so the
implementation never relies on an automatic resend being deduplicated.

Google enforces separate project/user quota units and Gmail sending limits; the
Consens 500-request daily limit is an additional bound, not a substitute. The
current official quota page distinguishes projects created after May 1, 2026 from
grandfathered projects. Check the deployed project's console and current billing
terms, set monitoring/budgets and respect returned 403/429 errors. The transport
surfaces them without automatic retries; ambiguous writes use reconciliation.
Google API charges, if applicable to the deployed project, are operator costs and
are not silently added to the existing model-token ledger.

## Public-operation prerequisites

Sensitive Calendar and Gmail send scopes require the applicable OAuth app verification before a
public rollout (unless a documented Google exception applies). Complete Google's
domain/branding/privacy disclosures and show the in-product data notice before
consent. Workspace admins may require allowlisting. Confirm Limited Use compliance
for every processor receiving raw or derived Google data; do not use such data for
ads, resale, general model training or unrelated human review. The privacy page
contains the Limited Use statement and deletion guidance. Review its accuracy for
the actual deployment before enabling external users.

Gmail readonly is a **restricted** scope. This server-based architecture stores
and transmits restricted data, so plan for restricted-scope verification and the
required security assessment under Google's published rules unless Google confirms
an applicable exception. Submit the exact scopes, a working demonstration of
account connection, selection, in-product disclosure, recipient/content approval
and deletion, and evidence of the permitted user-facing productivity use case.
Complete the applicable CASA assessment/renewal process with the approved assessor;
this code or its tests do not constitute that assessment. Maintain incident-response,
access-control and encryption procedures and processor agreements for both raw and
derived data, including excerpts, documents and summaries. No general-purpose model
training, ads, resale or unrelated human access is allowed. Limit staging access to
listed test users until the relevant approval is complete. Workspace administrators
may independently block the application.

Credentials and provider contracts are external prerequisites. Offline tests do
not prove Google consent-screen approval, Workspace admin policy, production
refresh-token issuance, real invitation delivery, or the operator's security and
verification obligations. Test any real write only against an explicitly approved
test calendar and explicitly approved recipients. None were sent during development.

Official references checked 2026-09-27:

- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.google.com/identity/protocols/oauth2/resources/best-practices
- https://developers.google.com/workspace/calendar/api/v3/reference/events/insert
- https://developers.google.com/workspace/calendar/api/v3/reference/events/patch
- https://developers.google.com/workspace/calendar/api/v3/reference/events/list
- https://developers.google.com/workspace/calendar/api/v3/reference/events/instances
- https://developers.google.com/workspace/calendar/api/v3/reference/freebusy/query
- https://developers.google.com/workspace/workspace-api-user-data-developer-policy
- https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification
- https://openrouter.ai/docs/guides/routing/provider-selection

Gmail references (official, checked 2026-09-27):

- https://developers.google.com/workspace/gmail/api/auth/scopes
- https://developers.google.com/workspace/gmail/api/auth/web-server
- https://developers.google.com/workspace/gmail/api/guides/sending
- https://developers.google.com/workspace/gmail/api/guides/threads
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.threads/get
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages.attachments/get
- https://developers.google.com/workspace/gmail/api/reference/quota

### Explicitly authorized staging verification

1. Use a dedicated test user/account and the deployed private bucket/indexes. Check
   incremental read-only grants first, reconnect with missing/denied scopes, token
   refresh, external revocation, disconnect, and deletion. Confirm that no token or
   authorization code appears in application/proxy logs.
2. Seed messages and threads manually in that account. Test a large paged thread,
   HTML-only and external-text bodies, a supported attachment and an oversized one.
   Confirm read excerpts and account/message references in a restored chat.
3. Compare two uploaded offers, create and revise a decision brief, and prepare a
   reply with the chosen DOCX/PDF version. Check both download formats and all
   addresses, original-message references, content and attachments in the card.
4. Only after explicit authorization of the **actual test recipients and exact
   message/invitation**, confirm one send/event. Repeat the confirmation and verify
   one provider operation. Simulate a lost response in an isolated adapter test;
   use read-only status reconciliation. Never induce duplicate production sends.
5. Check the consent-screen publishing state, Workspace admin policy, scope
   verification/security assessment and processor terms before public enablement.
