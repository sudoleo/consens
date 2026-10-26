# GitHub-App für den Agenten einrichten

Der Agent bringt mit der Agent VM GitHub-Repositories in seine VM und schlägt
Pull Requests vor (`app/services/agent_github.py`, Beschreibung in
`docs/agent-mode.md`, „GitHub aus der VM“). Dafür braucht consens.io **eine
öffentliche GitHub-App**, die jeder Nutzer selbst auf Repositories seiner Wahl
installiert. Die App-Schlüssel liegen nur im Backend; keine VM, kein Browser
und kein Modell sieht je ein GitHub-Token.

## 1. App anlegen

GitHub → Settings → Developer settings → GitHub Apps → **New GitHub App**
(für ein Konto oder eine Organisation, der die App gehören soll).

| Feld | Wert |
|---|---|
| GitHub App name | z. B. `consens.io` (daraus wird der Slug, siehe unten) |
| Homepage URL | `https://consens.io` |
| Callback URL | `https://consens.io/agent/github/callback` |
| Expire user authorization tokens | an |
| Request user authorization (OAuth) during installation | **an** (GitHub schickt den Nutzer nach der Installation zur Callback URL; das Feld „Setup URL“ wird dann nicht gebraucht) |
| Enable Device Flow | aus |
| Webhook → Active | **aus** (kein Webhook; eine entfernte App erkennt das Werkzeug beim nächsten Aufruf) |

**Repository permissions** (alles andere bleibt „No access“):

| Recht | Stufe |
|---|---|
| Contents | Read and write |
| Pull requests | Read and write |
| Metadata | Read-only (Pflicht) |

**Kein „Workflows“-Recht.** Ohne es lehnt GitHub Änderungen unter
`.github/workflows` ab; das Werkzeug sagt das dem Agenten schon vorher.
Keine Account permissions, keine Events.

**Where can this GitHub App be installed?** → **Any account** (jeder Nutzer
installiert sie selbst).

## 2. Werte holen

Nach „Create GitHub App“ auf der Seite der App:

- **App ID** → `GITHUB_APP_ID`
- **Client ID** → `GITHUB_APP_CLIENT_ID`
- „Generate a new client secret“ → `GITHUB_APP_CLIENT_SECRET`
- „Generate a private key“ → eine `.pem`-Datei; ihr ganzer Inhalt →
  `GITHUB_APP_PRIVATE_KEY`
- der Slug aus der öffentlichen Adresse `https://github.com/apps/<slug>` →
  `GITHUB_APP_SLUG`

## 3. Eintragen

- **Lokal** in `.env` (Vorlage `.env.example`): den Schlüssel in eine Zeile mit
  `\n` statt Zeilenumbrüchen, z. B.
  `GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----"`.
- **Render** → Dienst → Environment: dieselben fünf Variablen; der Schlüssel
  darf dort mehrzeilig eingefügt werden.

Fehlt eine der fünf, sagen die Werkzeuge ruhig „GitHub is not set up“, und
Einstellungen zeigt „GitHub is not set up on this installation yet.“

Für lokale Tests mit echtem GitHub braucht es eine zweite App mit Callback URL
`http://localhost:8000/agent/github/callback` (eine App hat eine Callback-URL
für den Fluss, der nach der Installation zurückführt).

## 4. Prüfen

Einstellungen → Agent · Beta → **GitHub** → „Connect GitHub“: Ein Fenster
öffnet die Installationsseite der App; Repositories wählen und installieren.
Das Fenster meldet sich zurück, Einstellungen zeigt „Connected as <login>.“
und die Repositories. Dann in einem Chat mit Agent VM: „Hol dir
<owner/repo> und ändere …, mach einen PR.“ Der Agent importiert, ändert, und
unter der Antwort steht die Karte „Pull request ready for review“; erst
„Create pull request“ legt Branch, Commit und Pull Request an.

## Sicherheit in Kürze

- Wer welche Repositories nutzen darf, sagt nur GitHub selbst: Beim Verbinden
  liest das Backend mit dem Nutzer-Token `GET /user/installations` und je
  Installation die Repositories samt den Rechten des Nutzers. Eine
  `installation_id` aus einer URL zählt nie. Das Nutzer-Token wird danach
  sofort widerrufen und nie gespeichert.
- Der Vorgang ist an den angemeldeten consens.io-Nutzer (Aufruf von
  `/agent/github/finish` mit seinem Login), an einen einmaligen `state` und an
  ein HttpOnly-Cookie des Browsers gebunden, der ihn begonnen hat.
- Installations-Tokens erzeugt nur das Backend, je Vorgang, für das eine
  Repository und nur die nötigen Rechte (Import: Contents read; Pull Request:
  Contents und Pull requests write).
- Ein Pull Request entsteht nur nach Bestätigung der Karte, immer auf einem
  neuen Branch; ein bestehender Branch wird nie geändert.
- Trennen in den Einstellungen löscht die Zuordnung; die Kontolöschung auch.
  Die App selbst entfernt der Nutzer auf GitHub
  (`https://github.com/settings/installations`).
