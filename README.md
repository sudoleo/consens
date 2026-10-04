<h1>
  <img src="static/favicon-square-dark.png#gh-light-mode-only" width="34" height="34" alt="consens.io">
  <img src="static/favicon-square.png#gh-dark-mode-only" width="34" height="34" alt="consens.io">
  consens.io
</h1>

<p align="center">
  <strong>Ask several AI models at once. See where they agree, where they don't, and why.</strong>
</p>

<table align="center">
  <tr>
    <td align="center" width="90">
      <img src="static/icons/chatgpt.png" height="28" alt="OpenAI"><br>
      <sub>OpenAI</sub>
    </td>
    <td align="center" width="90">
      <img src="static/icons/claude.png" height="28" alt="Anthropic"><br>
      <sub>Anthropic</sub>
    </td>
    <td align="center" width="90">
      <img src="static/icons/gemini.png" height="28" alt="Gemini"><br>
      <sub>Gemini</sub>
    </td>
    <td align="center" width="90">
      <img src="static/icons/mistral.png" height="28" alt="Mistral AI"><br>
      <sub>Mistral</sub>
    </td>
    <td align="center" width="90">
      <img src="static/icons/deepseek.png" height="28" alt="DeepSeek"><br>
      <sub>DeepSeek</sub>
    </td>
    <td align="center" width="90">
      <img src="static/icons/grok.png" height="28" alt="xAI Grok"><br>
      <sub>Grok</sub>
    </td>
    <td align="center" width="90">
      <img src="static/icons/chat_icons/zai.svg" height="28" alt="GLM"><br>
      <sub>GLM</sub>
    </td>
    <td align="center" width="90">
      <img src="static/icons/chat_icons/kimi.svg" height="28" alt="Kimi"><br>
      <sub>Kimi</sub>
    </td>
    <td align="center" width="90">
      <img src="static/icons/chat_icons/meta.svg" height="28" alt="Meta Muse"><br>
      <sub>Muse</sub>
    </td>
  </tr>
</table>

<p align="center">
  <a href="https://consens.io"><strong>consens.io</strong></a> ·
  <a href="https://consens.io/benchmark">Benchmark</a> ·
  <a href="docs/codebase-map.md">Architecture</a> ·
  <a href="docs/README.md">Documentation</a>
  <br><br>
  <a href="https://github.com/sudoleo/consens/actions/workflows/tests.yml"><img src="https://github.com/sudoleo/consens/actions/workflows/tests.yml/badge.svg" alt="Regression tests"></a>
  <img src="https://img.shields.io/badge/python-FastAPI-009688" alt="FastAPI">
  <img src="https://img.shields.io/badge/data-Firestore-FFCA28" alt="Firestore">
</p>

**consens.io** sends one question to models from nine independent providers,
keeps their answers separate, and shows what they agree on, where they
contradict each other, and how well each claim is backed by sources. The result
is one answer with inline confidence, not a wall of nine answers.

Agreement between models is a signal, not proof. consens.io treats it as one
input next to source verification, never as a substitute for it.

## What it does

- **Agent mode (default).** An agent plans the research, picks models per round,
  searches the web, reads attachments and Google sources (read-only), and
  answers with citations. Server-side rules require at least two model families
  and a judge before an answer ships.
- **Direct comparison.** Run the same question across models side by side and
  read the answers independently.
- **Consensus.** Anonymised, shuffled answers go to a cross-family judge that
  extracts consensus, disagreements, and an agreement score; a second judge
  checks that every consensus statement is covered.
- **Source checks and Watch.** Claims can be re-verified over time. Watches
  report only evidence-backed changes, not score noise.
- **Share pages and API.** Public snapshots of results, plus a keyed
  [Consensus API v1](docs/consensus-api.md).

## Research

The repository contains the benchmark harness and the frozen sample manifests
behind the published [MMLU-Pro results](https://consens.io/benchmark) (`benchmark/`,
`data/benchmark/`). Method, prompts, and caveats are in
[docs/benchmark-plan.md](docs/benchmark-plan.md). Models, prompts, and
aggregation methods change over time; results are tied to the version that
produced them.

## Architecture

```
app/api        FastAPI routers (ask, consensus, agent, bookmarks, share, admin, ...)
app/core       configuration, auth, assets, rate limits
app/services   LLM clients, judges, agent, usage metering, source verification
static/        classic-script frontend (window.* modules, esbuild bundles)
templates/     Jinja2 pages (app shell, landing, public pages)
benchmark/     MMLU-Pro experiment runner
tests/         pytest, Playwright (E2E), Vitest (frontend), Firestore rules
```

Stack: Python / FastAPI, vanilla JavaScript built with esbuild, Firebase Auth and
Firestore, all LLM traffic through OpenRouter. The full map (routing, core flows,
data model, `window.*` contracts) is [docs/codebase-map.md](docs/codebase-map.md).

## Run locally

Requirements: Python 3.9+, Node 18+.

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scriptsctivate
pip install -r requirements.txt
npm ci && npm run build
cp .env.example .env                              # fill in Firebase + OpenRouter values
MOCK_LLM=1 uvicorn main:app --reload
```

`MOCK_LLM=1` serves canned model output, so no provider calls are billed.
Note that a local server still talks to the Firestore project in your `.env`;
see [docs/testing.md](docs/testing.md) for the safe setup.

## Tests

```powershell
.\dev.ps1 check frontend   # Vitest + build freshness
.\dev.ps1 check backend    # pytest
.\dev.ps1 check browser    # Playwright against the Firebase emulator
.\dev.ps1 check rules      # Firestore security rules
```

CI runs on every push and pull request ([workflow](.github/workflows/tests.yml)).
Details: [docs/testing.md](docs/testing.md), [docs/frontend-build.md](docs/frontend-build.md).

## Status

consens.io is an actively developed solo project and is currently free to use
while in testing. Internal design notes and audits in `docs/` are mostly in
German; the index in [docs/README.md](docs/README.md) says which are current.

The product film lives in its own repository,
[sudoleo/consens-video](https://github.com/sudoleo/consens-video).
