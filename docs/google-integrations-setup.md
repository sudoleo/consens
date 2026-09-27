# Google integrations: setup and operating requirements

This feature is disabled until configured. OAuth is for each Consens user's own
Google account; there is no service-account impersonation or domain-wide delegation.
Do not use production mail or invitation recipients for automated smoke tests.

## Configuration

1. In a dedicated Google Cloud project, enable Calendar API. Configure an OAuth
   web application and its consent screen, verified domain, support contact, home
   page and privacy-policy URL. Use test users while verification is pending.
2. Register exactly `https://YOUR_HOST/agent/google/callback` as the redirect URI.
   Preserve this same origin through the reverse proxy. The popup callback has no
   external assets and clears its query immediately; redact its query string in
   **proxy/load-balancer logs as well as application logs**. The application
   redacts that route in Uvicorn access logging. Never log OAuth request bodies,
   Authorization headers, provider responses or tokens.
3. Inject `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` and
   `GOOGLE_TOKEN_KEYS` through a managed secret store. `GOOGLE_TOKEN_KEYS` is a
   comma-separated Fernet key ring, newest key first; generate a key with
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   in an operator-controlled environment. Protect the secret store with KMS and
   least privilege. Keep old keys available until all retained credentials have
   been re-encrypted by refresh/reconnection; losing all old keys requires users
   to reconnect. Do not commit or print keys in deployment diagnostics.
4. Review the processing terms of the actual OpenRouter hosting endpoints, not
   just model developers. Set `GOOGLE_ALLOWED_MODEL_IDS` to a comma-separated list
   of approved **OpenRouter model IDs**, and `GOOGLE_ALLOWED_PROVIDERS` to approved
   OpenRouter provider slugs. Include the configured synthesis, comparison,
   Differences and Coverage judge models. Every model call in a Google-data chat
   is checked, uses `provider.only`, `allow_fallbacks=false`, `data_collection=deny`
   and ZDR, and fails closed if no approved route exists. Model/router logging and
   provider contracts must also prohibit general-purpose training and secondary
   use. These flags alone are not a compliance attestation.
5. Deploy `firestore.indexes.json`. OAuth state/action expiry use collection-group
   indexes; credentials, OAuth secrets, proposal bodies and previews are excluded
   from indexes. Keep the existing deny-all browser Firestore rules. Production
   Firestore and private GCS encryption at rest remain required for Google-derived
   data, including imported attachments and generated documents.
6. Set `GOOGLE_INTEGRATIONS_ENABLED=1`, deploy, and verify the unconnected state,
   consent disclosure, account selection, incremental permissions, disconnect,
   and account/chat deletion in a dedicated staging account. Existing files and
   document features work without these Google settings.

## Permissions and consent

| Capability | Scope | Why |
| --- | --- | --- |
| Google account identity | `openid email` | Verified subject and account label; no profile scope |
| Calendar reading | `https://www.googleapis.com/auth/calendar.readonly` | Calendar selection, event search/read/instances and free/busy |
| Calendar changes (separate request) | `https://www.googleapis.com/auth/calendar.events` | Create and patch events after exact confirmation |

The token response determines actual capabilities; a partial OAuth grant does not
imply a missing permission. Connections are selected per message. A separate,
unchecked data-sharing box discloses processing by approved selected/review models;
it is cleared after submitting the message. Consent is required again for follow-up
processing of a chat containing Google-derived information, even without new API
reads. Such chats disable web search and external source-checking to avoid sending
private excerpts as search queries. Users can still combine prior research, their
uploaded files, comparisons, documents and selected Google data in the chat.

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
  states and action records. Connection credentials remain until disconnect or
  account deletion. Chat deletion removes proposals; account deletion removes
  credentials, pending OAuth states and all chats/files. Disconnect deletes local
  access first and attempts provider revocation; on failure the UI links to
  Google's account-permissions page. Content already in saved chat answers remains
  until users delete those chats.
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

## Public-operation prerequisites

Sensitive Calendar scopes require the applicable OAuth app verification before a
public rollout (unless a documented Google exception applies). Complete Google's
domain/branding/privacy disclosures and show the in-product data notice before
consent. Workspace admins may require allowlisting. Confirm Limited Use compliance
for every processor receiving raw or derived Google data; do not use such data for
ads, resale, general model training or unrelated human review. The privacy page
contains the Limited Use statement and deletion guidance. Review its accuracy for
the actual deployment before enabling external users.

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
