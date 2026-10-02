# Produktverhalten und Testbelege

[Einstieg](README.md) · [Dateikatalog](../backend.md) · [Lücken](gaps.md) · Stand: 2026-10-02

87 gruppierte Verhaltensverträge, alle 291 Testdateien verknüpft. Ein Abschnitt bündelt mehrere Teilverträge; die 264 ausgewählten Testdefinitionen sind konkrete **Teilbelege**. Sie beweisen nicht jede Klausel des Abschnitts. Der vollständige Testdateikatalog bleibt maßgeblich für die übrigen Assertions. Zuordnung, Testzahl und Zeilenausführung sind keine fachliche Coveragequote.

| Vertrag | Verhalten | Quellen | Testdateien | Befunde |
|---|---|---:|---:|---|
| [OPS-01](#ops-01) | Start, Shutdown und überwachte Jobs | 5 | 7 | — |
| [OPS-02](#ops-02) | Requestgrenzen und Sicherheitsheader | 3 | 6 | [G-033](gaps.md#g-033), [G-037](gaps.md#g-037) |
| [OPS-03](#ops-03) | Inhaltsfreie Fehlerdiagnostik | 5 | 6 | — |
| [AUTH-01](#auth-01) | Registrierung ohne Kontoauskunft | 2 | 3 | [G-009](gaps.md#g-009) |
| [AUTH-02](#auth-02) | Token, Session und Rollen | 6 | 7 | [G-012](gaps.md#g-012), [G-014](gaps.md#g-014), [G-041](gaps.md#g-041) |
| [AUTH-03](#auth-03) | Kontolöschung mit Wiederaufnahme | 4 | 10 | [G-004](gaps.md#g-004), [G-008](gaps.md#g-008) |
| [AUTH-04](#auth-04) | Browser-Identität und Sitzungswechsel | 5 | 8 | [G-030](gaps.md#g-030) |
| [QUOTA-01](#quota-01) | Ein regulärer Lauf, eine Belastung | 3 | 7 | [G-002](gaps.md#g-002) |
| [QUOTA-02](#quota-02) | Rate-Limits und Kontostufen | 7 | 8 | [G-012](gaps.md#g-012) |
| [CHAT-01](#chat-01) | Chats, Turns und Cursor | 2 | 4 | [G-003](gaps.md#g-003) |
| [CHAT-02](#chat-02) | Abschluss und Löschsperre | 2 | 7 | [G-003](gaps.md#g-003) |
| [CHAT-03](#chat-03) | Kontext und Nutzergedächtnis im Lauf | 3 | 7 | — |
| [CHAT-04](#chat-04) | Bookmarks und vollständiger Verlauf | 3 | 10 | [G-030](gaps.md#g-030) |
| [MEM-01](#mem-01) | Memory lesen und manuell speichern | 3 | 6 | — |
| [MEM-02](#mem-02) | Expliziter KI-Patch und sicheres Undo | 3 | 6 | [G-007](gaps.md#g-007), [G-008](gaps.md#g-008), [G-038](gaps.md#g-038) |
| [API-01](#api-01) | API-Schlüssel und Scopes | 4 | 4 | [G-037](gaps.md#g-037) |
| [API-02](#api-02) | Dauerhafte API-Runs | 3 | 6 | [G-005](gaps.md#g-005) |
| [API-03](#api-03) | Historische Source-Checks der API | 3 | 3 | [G-010](gaps.md#g-010) |
| [API-04](#api-04) | API-Publish und Publisher-Watch | 3 | 3 | — |
| [LLM-01](#llm-01) | Registry, Credentials und Payload | 9 | 7 | — |
| [LLM-02](#llm-02) | Providerstream, Fehler und Ressourcen | 4 | 10 | [G-032](gaps.md#g-032) |
| [CONS-01](#cons-01) | Neutrale Pipeline und Teilergebnisse | 3 | 5 | — |
| [CONS-02](#cons-02) | Strukturierte Differences und Agreement | 4 | 5 | — |
| [CONS-03](#cons-03) | Quellenkatalog und Zitatprovenienz | 4 | 8 | — |
| [CONS-04](#cons-04) | Resolve als eigener Lauf | 3 | 3 | — |
| [CONS-05](#cons-05) | Finalisierung, Replay und Browser-Recovery | 5 | 9 | [G-030](gaps.md#g-030) |
| [AGENT-01](#agent-01) | Admission und Token-/Kostenledger | 7 | 9 | [G-037](gaps.md#g-037) |
| [AGENT-02](#agent-02) | Chatpolicy und Legacy-Toolloop | 7 | 8 | — |
| [AGENT-03](#agent-03) | Delegierte Sitzungen und Kommunikation | 4 | 6 | [G-039](gaps.md#g-039) |
| [AGENT-04](#agent-04) | Agent-Recovery und Eigentümerbindung | 4 | 10 | [G-030](gaps.md#g-030), [G-039](gaps.md#g-039) |
| [AGENT-05](#agent-05) | Agent-Ansicht und bestätigter Fortschritt | 7 | 13 | — |
| [SRC-01](#src-01) | Sicherer begrenzter Quellenabruf | 2 | 2 | [G-032](gaps.md#g-032) |
| [SRC-02](#src-02) | Prüfplan und konservative Urteile | 3 | 4 | — |
| [SRC-03](#src-03) | Dauerhafte Jobqueue und Credentials | 2 | 6 | [G-006](gaps.md#g-006) |
| [SRC-04](#src-04) | Private und öffentliche Jobseiten | 2 | 5 | [G-010](gaps.md#g-010) |
| [SRC-05](#src-05) | Sources-/Differences-UI und Nachladen | 3 | 14 | — |
| [SHARE-01](#share-01) | Autoritative Share-Erstellung | 3 | 5 | [G-011](gaps.md#g-011), [G-027](gaps.md#g-027) |
| [SHARE-02](#share-02) | Öffentliche und private Darstellung | 6 | 5 | — |
| [SHARE-03](#share-03) | Reports, Moderation und Kaskade | 3 | 2 | [G-029](gaps.md#g-029) |
| [SHARE-04](#share-04) | Open-Graph-Karte | 2 | 3 | [G-020](gaps.md#g-020) |
| [WATCH-01](#watch-01) | Watch-Erstellung und Planrechte | 2 | 4 | [G-013](gaps.md#g-013), [G-027](gaps.md#g-027) |
| [WATCH-02](#watch-02) | Zeitplan, Claim und Ausführung | 4 | 7 | [G-031](gaps.md#g-031) |
| [WATCH-03](#watch-03) | E-Mail-Follow mit Einwilligungsnachweis | 4 | 5 | [G-013](gaps.md#g-013) |
| [WATCH-04](#watch-04) | Telegram-Link und Zustellung | 3 | 2 | [G-013](gaps.md#g-013) |
| [WATCH-05](#watch-05) | Morning Brief | 4 | 2 | — |
| [WATCH-06](#watch-06) | Watch-Frontend | 3 | 5 | — |
| [TOPIC-01](#topic-01) | Topic-Administration und versionierte Runs | 2 | 4 | [G-014](gaps.md#g-014), [G-031](gaps.md#g-031), [G-041](gaps.md#g-041) |
| [TOPIC-02](#topic-02) | Topic-Pipeline und Identitätsjudge | 3 | 4 | [G-016](gaps.md#g-016) |
| [TOPIC-03](#topic-03) | Zeitlicher Claim-/Quellenverlauf | 5 | 5 | — |
| [TOPIC-04](#topic-04) | Öffentliche Topic-Seiten und Follow | 6 | 6 | [G-014](gaps.md#g-014) |
| [TOPIC-05](#topic-05) | Interaktiver Check-Strip | 3 | 4 | [G-018](gaps.md#g-018) |
| [SEO-01](#seo-01) | Search-Console-Erfassung | 2 | 1 | — |
| [SEO-02](#seo-02) | SEO-Repository und Dossiers | 3 | 4 | [G-017](gaps.md#g-017) |
| [SEO-03](#seo-03) | Konservative Empfehlungen und Aktionen | 3 | 3 | — |
| [SEO-04](#seo-04) | Wöchentlicher Review und Publikationsdaten | 3 | 2 | [G-017](gaps.md#g-017), [G-031](gaps.md#g-031) |
| [SEO-05](#seo-05) | Öffentliche Navigation und Suchmetadaten | 27 | 6 | — |
| [ADMIN-01](#admin-01) | Konfiguration: Revisionen und Aktivierungsrollback | 6 | 9 | [G-040](gaps.md#g-040) |
| [ADMIN-02](#admin-02) | Adminoberfläche und HTTP-Adapter | 9 | 13 | [G-019](gaps.md#g-019) |
| [UI-01](#ui-01) | Run-State und getrennte Ansichten | 4 | 6 | — |
| [UI-02](#ui-02) | Senden, Presets und Moduswechsel | 9 | 15 | — |
| [UI-03](#ui-03) | Streaming, Deadlines und Fortschritt | 4 | 12 | — |
| [UI-04](#ui-04) | Antworten, Markdown und zugängliche Details | 6 | 28 | [G-028](gaps.md#g-028) |
| [UI-05](#ui-05) | Anhänge und Composer | 5 | 9 | — |
| [UI-06](#ui-06) | Navigation, Scroll und Modals | 8 | 9 | [G-025](gaps.md#g-025) |
| [UI-07](#ui-07) | Bootstrap, Skript-Reihenfolge und Styles | 43 | 7 | — |
| [UI-08](#ui-08) | Demo und Landing-Interaktionen | 7 | 4 | — |
| [UI-09](#ui-09) | Analytics-Selbstausschluss | 2 | 2 | [G-021](gaps.md#g-021) |
| [DATA-01](#data-01) | Votes, Feedback und Modellstatistik | 3 | 5 | [G-034](gaps.md#g-034) |
| [BENCH-01](#bench-01) | Dataset, Budget und Closed-book-Vertrag | 8 | 8 | — |
| [BENCH-02](#bench-02) | Runner, Resume und Artefakte | 5 | 10 | [G-035](gaps.md#g-035), [G-042](gaps.md#g-042) |
| [BENCH-03](#bench-03) | Ergebnisberechnung und Adminberichte | 4 | 5 | [G-015](gaps.md#g-015), [G-042](gaps.md#g-042) |
| [BUILD-01](#build-01) | Reproduzierbare Frontendartefakte | 6 | 6 | [G-036](gaps.md#g-036) |
| [BUILD-02](#build-02) | Test- und Emulator-Einstieg | 5 | 5 | [G-024](gaps.md#g-024), [G-025](gaps.md#g-025), [G-026](gaps.md#g-026), [G-046](gaps.md#g-046) |
| [BUILD-03](#build-03) | Scheduled Publisher und Workflows | 4 | 2 | [G-024](gaps.md#g-024) |
| [TOOLS-01](#tools-01) | Wartungs- und Reparaturwerkzeuge | 2 | 1 | [G-022](gaps.md#g-022), [G-023](gaps.md#g-023) |
| [TOOLS-02](#tools-02) | Evaluations-/Vorschauwerkzeuge | 5 | 3 | [G-035](gaps.md#g-035) |
| [AUTH-05](#auth-05) | Direkte Firestore-Clients bleiben gesperrt | 2 | 1 | [G-001](gaps.md#g-001) |
| [AGENT-06](#agent-06) | Private Dateien und Nachrichtenzuordnung | 5 | 8 | [G-044](gaps.md#g-044) |
| [AGENT-07](#agent-07) | Versionierte DOCX-/PDF-Dokumente | 3 | 7 | — |
| [GOOGLE-01](#google-01) | Google-Verbindung und Datenfreigabe | 4 | 4 | — |
| [GOOGLE-02](#google-02) | Kalender lesen und exakt bestätigen | 4 | 4 | [G-043](gaps.md#g-043) |
| [GOOGLE-03](#google-03) | Gmail lesen, Entwurf und Versandfreigabe | 4 | 4 | — |
| [CONS-06](#cons-06) | Autoritative Antwortreceipts und Abschlusszustand | 5 | 5 | — |
| [QUOTA-03](#quota-03) | Gemeinsames Tokenkonto und Nachmessung | 7 | 9 | — |
| [WATCH-07](#watch-07) | Dauerhafte Benachrichtigungs-Outbox | 5 | 5 | [G-045](gaps.md#g-045) |
| [WATCH-08](#watch-08) | Belegbasierte Änderung, Ziel und Probe | 7 | 5 | — |
| [BUILD-04](#build-04) | Statische Auslieferung ohne SSE-Pufferung | 2 | 2 | — |

<a id="ops-01"></a>

## OPS-01 · Start, Shutdown und überwachte Jobs

Readiness wartet nur auf den begrenzten Konfigurationsread; Writer starten danach, werden überwacht und beim Shutdown beendet. E2E deaktiviert Writer und bindet Firebase an das Demo-Projekt.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Loops/Startup-Arbeit in Tests ersetzt; kein Deployment-Neustart. Browser-Harness überspringt die produktiven Writer.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/core/background_tasks.py](../../../app/core/background_tasks.py)
- [app/core/concurrency.py](../../../app/core/concurrency.py)
- [app/core/e2e_profile.py](../../../app/core/e2e_profile.py)
- [app/services/retention_maintenance.py](../../../app/services/retention_maintenance.py)
- [main.py](../../../main.py)

**Testdateien:**

- [tests/e2e/test_scheduler_transactions.py](../../../tests/e2e/test_scheduler_transactions.py)
- [tests/test_agent_capacity.py](../../../tests/test_agent_capacity.py)
- [tests/test_background_task_supervision.py](../../../tests/test_background_task_supervision.py)
- [tests/test_e2e_safety.py](../../../tests/test_e2e_safety.py)
- [tests/test_phase6_architecture.py](../../../tests/test_phase6_architecture.py)
- [tests/test_router_event_loop_contract.py](../../../tests/test_router_event_loop_contract.py)
- [tests/test_worker_thread_budget.py](../../../tests/test_worker_thread_budget.py)

</details>

**Konkrete Teilbelege:**

- [test_supervisor_restarts_crashes_and_keeps_last_success_health](../../../tests/test_background_task_supervision.py#L12) — Async-Supervisor und Startupfunktionen mit Cleanup-Doubles. **Datei**status vom 2026-10-02: passed=8.
  - [Zeile 43](../../../tests/test_background_task_supervision.py#L43): ` assert attempts == 3 `
  - [Zeile 44](../../../tests/test_background_task_supervision.py#L44): ` assert health["restart_count"] == 2 `
  - [Zeile 45](../../../tests/test_background_task_supervision.py#L45): ` assert health["consecutive_failures"] == 0 `
  - [Zeile 46](../../../tests/test_background_task_supervision.py#L46): ` assert health["last_success_at"] `
  - [Zeile 47](../../../tests/test_background_task_supervision.py#L47): ` assert health["state"] == "stopped" `
- [test_e2e_guard_rejects_missing_remote_or_unknown_targets](../../../tests/test_e2e_safety.py#L42) — Guard-Unit-Tests und Python-Subprozess-/Lifespan-Verträge. **Datei**status vom 2026-10-02: passed=10.
  - [Zeile 43](../../../tests/test_e2e_safety.py#L43): ` with pytest.raises(RuntimeError, match=message): `
  - [Zeile 44](../../../tests/test_e2e_safety.py#L44): ` assert_safe_e2e_environment(safe_env(**overrides)) `
- [test_native_due_queries_and_topic_claim_fence](../../../tests/e2e/test_scheduler_transactions.py#L21) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 33](../../../tests/e2e/test_scheduler_transactions.py#L33): ` assert group[0].id in result and all(ref.id not in result for ref in group[1:]) `
  - [Zeile 39](../../../tests/e2e/test_scheduler_transactions.py#L39): ` assert exc.code == "conflict" `
  - [Zeile 42](../../../tests/e2e/test_scheduler_transactions.py#L42): ` assert sum(value is not None for value in values) == 1 `
  - [Zeile 46](../../../tests/e2e/test_scheduler_transactions.py#L46): ` assert not topics.fail_topic_run(ref.id, "late failure", now=later, db=db, expected_claim_id=old["current_run_id"]) `
  - [Zeile 47](../../../tests/e2e/test_scheduler_transactions.py#L47): ` assert ref.get().to_dict() == before `
  - [Zeile 48](../../../tests/e2e/test_scheduler_transactions.py#L48): ` assert fresh["current_run_id"] != old["current_run_id"] `
- [test_disconnect_preserves_generator_exit_when_deleted_account_blocks_cleanup](../../../tests/test_agent_capacity.py#L16) — Agentkapazität, Routerstream und lokale Worker mit kontrolliertem Loop. **Datei**status vom 2026-10-02: passed=7.
  - [Zeile 35](../../../tests/test_agent_capacity.py#L35): ` assert "event: accepted" in next(stream) `
  - [Zeile 36](../../../tests/test_agent_capacity.py#L36): ` assert "event: delta" in next(stream) `
  - [Zeile 38](../../../tests/test_agent_capacity.py#L38): ` assert closed == [True] and not calls `
  - [Zeile 39](../../../tests/test_agent_capacity.py#L39): ` assert "Agent completion failed" not in caplog.text `
  - [Zeile 40](../../../tests/test_agent_capacity.py#L40): ` assert "Agent stream cleanup unavailable" in caplog.text `
  - [Zeile 41](../../../tests/test_agent_capacity.py#L41): ` assert list(stream) == [] `
- [test_public_site_origin_is_neutral_validated_core_configuration](../../../tests/test_phase6_architecture.py#L27) — Statische Architektur-, Routing- und Assetverträge. **Datei**status vom 2026-10-02: passed=8.
  - [Zeile 28](../../../tests/test_phase6_architecture.py#L28): ` assert normalize_public_site_url(None) == "https://www.consens.io" `
  - [Zeile 29](../../../tests/test_phase6_architecture.py#L29): ` assert normalize_public_site_url("https://preview.example/") == "https://preview.example" `
  - [Zeile 31](../../../tests/test_phase6_architecture.py#L31): ` with pytest.raises(RuntimeError): `
  - [Zeile 37](../../../tests/test_phase6_architecture.py#L37): ` assert "from app.api.routers.pages import SITE_URL" not in service_sources `

<a id="ops-02"></a>

## OPS-02 · Requestgrenzen und Sicherheitsheader

Übergrößen werden vor Parsing/Handler abgewiesen; Replay erhält den echten Disconnect. Private Datenantworten sind nicht öffentlich cachebar; App/Admin erzwingen externe Skripte.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Reale ASGI-Ablehnungspfade und lokale TCP-/TLS-Nachweise; keine Deploymentproxy-/Mehrinstanz-Limiterfreigabe. Headererhalt ist durch main.app geprüft.

**Befunde:** [G-033](gaps.md#g-033), [G-037](gaps.md#g-037). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/core/request_limits.py](../../../app/core/request_limits.py)
- [app/core/security.py](../../../app/core/security.py)
- [main.py](../../../main.py)

**Testdateien:**

- [tests/test_agent_http_contract.py](../../../tests/test_agent_http_contract.py)
- [tests/test_e2e_safety.py](../../../tests/test_e2e_safety.py)
- [tests/test_local_transport.py](../../../tests/test_local_transport.py)
- [tests/test_phase6_architecture.py](../../../tests/test_phase6_architecture.py)
- [tests/test_request_body_limits.py](../../../tests/test_request_body_limits.py)
- [tests/test_security_controls.py](../../../tests/test_security_controls.py)

</details>

**Konkrete Teilbelege:**

- [test_replayed_body_does_not_synthesize_disconnect_for_delayed_stream](../../../tests/test_request_body_limits.py#L122) — Registrierte Bodylimit-Middleware mit ASGI-Ereignissen. **Datei**status vom 2026-10-02: passed=22.
  - [Zeile 156](../../../tests/test_request_body_limits.py#L156): ` assert await inner_receive() == { `
  - [Zeile 180](../../../tests/test_request_body_limits.py#L180): ` assert body_messages == [ `
- [test_app_and_all_admin_pages_receive_strict_script_csp](../../../tests/test_phase6_architecture.py#L184) — Statische Architektur-, Routing- und Assetverträge. **Datei**status vom 2026-10-02: passed=8.
  - [Zeile 199](../../../tests/test_phase6_architecture.py#L199): ` assert "'unsafe-inline'" not in script_src `
  - [Zeile 204](../../../tests/test_phase6_architecture.py#L204): ` assert "'unsafe-inline'" in public_script_src `
- [test_cancellation_closes_real_idle_provider_socket_without_retry](../../../tests/test_local_transport.py#L64) — Echte lokale TCP-/TLS-Server durch HTTP-/SDK-Adapter. **Datei**status vom 2026-10-02: passed=10.
  - [Zeile 85](../../../tests/test_local_transport.py#L85): ` assert state.seen.wait(3), 'request never reached local server' `
  - [Zeile 88](../../../tests/test_local_transport.py#L88): ` assert not thread.is_alive(), 'producer survived cancellation' `
  - [Zeile 89](../../../tests/test_local_transport.py#L89): ` assert len(errors) == 1 and isinstance(errors[0], runtime.ProviderCancelled) `
  - [Zeile 90](../../../tests/test_local_transport.py#L90): ` assert state.closed.wait(3), 'server socket stayed open' `
  - [Zeile 91](../../../tests/test_local_transport.py#L91): ` assert len(state.requests) == 1 `
- [test_detail_pages_are_owner_bound_and_never_start_provider](../../../tests/test_agent_http_contract.py#L56) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=9.
  - [Zeile 67](../../../tests/test_agent_http_contract.py#L67): ` assert response.status_code == 200, response.text `
  - [Zeile 68](../../../tests/test_agent_http_contract.py#L68): ` assert response.headers["cache-control"] == "private, no-store" `
  - [Zeile 70](../../../tests/test_agent_http_contract.py#L70): ` assert data["agent"]["id"] == h.agent_id `
  - [Zeile 71](../../../tests/test_agent_http_contract.py#L71): ` assert data["agent"]["assignment"]["goal"] == "Owner private assignment" `
  - [Zeile 72](../../../tests/test_agent_http_contract.py#L72): ` assert 1 <= len(data["messages"]) <= 3 `
  - [Zeile 77](../../../tests/test_agent_http_contract.py#L77): ` assert [m["text"] for m in messages] == ["Message " + str(i) for i in range(7)] `

<a id="ops-03"></a>

## OPS-03 · Inhaltsfreie Fehlerdiagnostik

Logs, Metriken und Browsermeldungen enthalten erlaubte Kategorien, keine Prompts, Antworten, Schlüssel oder Nutzerkennungen; Reporter dedupliziert und blockiert den Nutzerflow nicht.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Bekannte sensible Marker/Typen und Fake-Zustellung; keine universelle Freitext-Secret-Erkennung.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/client_errors.py](../../../app/api/routers/client_errors.py)
- [app/core/observability.py](../../../app/core/observability.py)
- [app/services/telegram_notifier.py](../../../app/services/telegram_notifier.py)
- [main.py](../../../main.py)
- [static/js/error-reporter.js](../../../static/js/error-reporter.js)

**Testdateien:**

- [tests/js/error-reporter.test.mjs](../../../tests/js/error-reporter.test.mjs)
- [tests/test_client_error_alerts.py](../../../tests/test_client_error_alerts.py)
- [tests/test_differences_stats.py](../../../tests/test_differences_stats.py)
- [tests/test_logging_redaction_contract.py](../../../tests/test_logging_redaction_contract.py)
- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)
- [tests/test_telegram_notifier.py](../../../tests/test_telegram_notifier.py)

</details>

**Konkrete Teilbelege:**

- [test_client_error_report_is_accepted_and_sanitized](../../../tests/test_client_error_alerts.py#L38) — Router mit Notification-Double und Bundle-Quelltextvertrag. **Datei**status vom 2026-10-02: passed=34.
  - [Zeile 55](../../../tests/test_client_error_alerts.py#L55): ` assert response.status_code == 202 `
  - [Zeile 56](../../../tests/test_client_error_alerts.py#L56): ` assert response.json() == {"status": "accepted"} `
  - [Zeile 57](../../../tests/test_client_error_alerts.py#L57): ` assert captured == [{ `

<a id="auth-01"></a>

## AUTH-01 · Registrierung ohne Kontoauskunft

Neue und vorhandene Adressen erhalten dieselbe öffentliche Antwort und den Mailbox-Setup-Pfad; fremdbestimmtes Passwort darf kein Konto übernehmen, ein Create-Race wird wie Bestand behandelt.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** SDK-Create-Race und neutrale Antworten durch echten Registrierungsservice geprüft; Firebasezustellung ersetzt.

**Befunde:** [G-009](gaps.md#g-009). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/auth.py](../../../app/api/routers/auth.py)
- [app/services/registration.py](../../../app/services/registration.py)

**Testdateien:**

- [tests/test_auth_session.py](../../../tests/test_auth_session.py)
- [tests/test_http_adapter_auth.py](../../../tests/test_http_adapter_auth.py)
- [tests/test_registration_security.py](../../../tests/test_registration_security.py)

</details>

**Konkrete Teilbelege:**

- [AuthSessionTests::test_new_and_existing_registration_responses_are_identical](../../../tests/test_auth_session.py#L110) — API mit Auth-/Mail-/Notifier-Doubles. **Datei**status vom 2026-10-02: passed=8.
  - [Zeile 141](../../../tests/test_auth_session.py#L141): ` self.assertEqual(created.status_code, existing.status_code) `
  - [Zeile 142](../../../tests/test_auth_session.py#L142): ` self.assertEqual(created.content, existing.content) `
- [test_every_topic_admin_method_enforces_real_policy_before_service](../../../tests/test_http_adapter_auth.py#L29) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=38.
  - [Zeile 43](../../../tests/test_http_adapter_auth.py#L43): ` assert response.status_code == expected, response.text `
  - [Zeile 44](../../../tests/test_http_adapter_auth.py#L44): ` assert "error" in response.json() and "private" not in response.text `
  - [Zeile 45](../../../tests/test_http_adapter_auth.py#L45): ` assert database.documents == {} and database.query_reads == [] `
  - [Zeile 47](../../../tests/test_http_adapter_auth.py#L47): ` assert h.checks[-1][1]["check_revoked"] is True `

<a id="auth-02"></a>

## AUTH-02 · Token, Session und Rollen

Die zentrale Adminprüfung verlangt Revocationprüfung und Adminrolle; Tokenprüfung berücksichtigt Account-Tombstones. Rollen-/Tierfehler dürfen keine Rechte gewähren, Rollenwerte können aus dem vorgesehenen Cache stammen. Die Registrierungsbestätigung setzt das Session-Cookie, Logout löscht es.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Echte Admin-/Topic-/Agentguards und Rollenmatrix einschließlich Revocationflag/Tierausfall; SDKidentitäten kontrolliert, kein Live-Firebaselogin.

**Befunde:** [G-012](gaps.md#g-012), [G-014](gaps.md#g-014), [G-041](gaps.md#g-041). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/admin.py](../../../app/api/routers/admin.py)
- [app/api/routers/auth.py](../../../app/api/routers/auth.py)
- [app/api/routers/topics.py](../../../app/api/routers/topics.py)
- [app/core/entitlements.py](../../../app/core/entitlements.py)
- [app/core/security.py](../../../app/core/security.py)
- [app/services/account_tier.py](../../../app/services/account_tier.py)

**Testdateien:**

- [tests/test_account_tier_admin.py](../../../tests/test_account_tier_admin.py)
- [tests/test_auth_revocation.py](../../../tests/test_auth_revocation.py)
- [tests/test_auth_session.py](../../../tests/test_auth_session.py)
- [tests/test_http_adapter_auth.py](../../../tests/test_http_adapter_auth.py)
- [tests/test_memory_http_contract.py](../../../tests/test_memory_http_contract.py)
- [tests/test_plus_tier.py](../../../tests/test_plus_tier.py)
- [tests/test_tier_cache.py](../../../tests/test_tier_cache.py)

</details>

**Konkrete Teilbelege:**

- [test_admin_boundary_checks_revocation_and_maps_tier_outage_to_503](../../../tests/test_auth_revocation.py#L52) — Security-Funktionen mit Auth-/Datenbank-Doubles. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 65](../../../tests/test_auth_revocation.py#L65): ` with pytest.raises(admin_router.HTTPException) as exc_info: `
  - [Zeile 68](../../../tests/test_auth_revocation.py#L68): ` assert verify.call_args.kwargs["check_revoked"] is True `
  - [Zeile 69](../../../tests/test_auth_revocation.py#L69): ` assert exc_info.value.status_code == 503 `
- [test_every_topic_admin_method_enforces_real_policy_before_service](../../../tests/test_http_adapter_auth.py#L29) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=38.
  - [Zeile 43](../../../tests/test_http_adapter_auth.py#L43): ` assert response.status_code == expected, response.text `
  - [Zeile 44](../../../tests/test_http_adapter_auth.py#L44): ` assert "error" in response.json() and "private" not in response.text `
  - [Zeile 45](../../../tests/test_http_adapter_auth.py#L45): ` assert database.documents == {} and database.query_reads == [] `
  - [Zeile 47](../../../tests/test_http_adapter_auth.py#L47): ` assert h.checks[-1][1]["check_revoked"] is True `
- [test_set_tier_writes_the_field_audits_it_and_drops_the_cache](../../../tests/test_account_tier_admin.py#L144) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=13.
  - [Zeile 149](../../../tests/test_account_tier_admin.py#L149): ` assert db.stores["users"]["uid-1"]["tier"] == "plus" `
  - [Zeile 150](../../../tests/test_account_tier_admin.py#L150): ` assert db.stores["users"]["uid-1"]["tier_updated_by"] == "admin-uid" `
  - [Zeile 151](../../../tests/test_account_tier_admin.py#L151): ` assert isinstance(db.stores["users"]["uid-1"]["tier_updated_at"], datetime) `
  - [Zeile 152](../../../tests/test_account_tier_admin.py#L152): ` invalidate.assert_called_once_with("uid-1") `
  - [Zeile 155](../../../tests/test_account_tier_admin.py#L155): ` assert len(entries) == 1 `
  - [Zeile 156](../../../tests/test_account_tier_admin.py#L156): ` assert entries[0]["from_tier"] == "free" `
- [test_main_undo_errors_preserve_all_state_and_never_call_provider](../../../tests/test_memory_http_contract.py#L75) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=12.
  - [Zeile 109](../../../tests/test_memory_http_contract.py#L109): ` assert response.status_code == status, response.text `
  - [Zeile 110](../../../tests/test_memory_http_contract.py#L110): ` assert "error" in response.json() `
  - [Zeile 112](../../../tests/test_memory_http_contract.py#L112): ` assert response.json()["error"]["error_code"] == code `
  - [Zeile 113](../../../tests/test_memory_http_contract.py#L113): ` assert response.json()["error"]["message"] `
  - [Zeile 114](../../../tests/test_memory_http_contract.py#L114): ` assert "private database diagnostic" not in response.text `
  - [Zeile 115](../../../tests/test_memory_http_contract.py#L115): ` assert h.db.documents == before and len(h.db.write_log) == writes `

<a id="auth-03"></a>

## AUTH-03 · Kontolöschung mit Wiederaufnahme

Vor dem Löschen persistiert eine Sperre. Die 14 Kaskadenbereiche werden idempotent bereinigt, fremde Daten bleiben erhalten. Persistiert quittierte Bereiche werden beim Retry übersprungen; ohne dauerhaften Checkpoint kann eine bereits erfolgreiche Operation erneut nötig sein. Teilfehler bleiben pending. Nach Abschluss bleibt der minimale UID-Sperrtombstone bis zum Ablauf seiner Aufbewahrung erhalten, die Cleanup-E-Mail wird entfernt.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Alle16 aktuellen Kaskadenbereiche nativ mit Retry und Checkpointverlust belegt; Auth-/Objekttransport an äußeren Grenzen ersetzt.

**Befunde:** [G-004](gaps.md#g-004), [G-008](gaps.md#g-008). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/users.py](../../../app/api/routers/users.py)
- [app/services/account_deletion.py](../../../app/services/account_deletion.py)
- [app/services/api_account_cleanup.py](../../../app/services/api_account_cleanup.py)
- [app/services/persistence_guard.py](../../../app/services/persistence_guard.py)

**Testdateien:**

- [tests/e2e/test_account_deletion_transactions.py](../../../tests/e2e/test_account_deletion_transactions.py)
- [tests/e2e/test_memory_edit_transactions.py](../../../tests/e2e/test_memory_edit_transactions.py)
- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/e2e/test_watch_delivery_transactions.py](../../../tests/e2e/test_watch_delivery_transactions.py)
- [tests/test_account_deletion_chats.py](../../../tests/test_account_deletion_chats.py)
- [tests/test_account_deletion_retry.py](../../../tests/test_account_deletion_retry.py)
- [tests/test_api_account_cleanup.py](../../../tests/test_api_account_cleanup.py)
- [tests/test_chat_history.py](../../../tests/test_chat_history.py)
- [tests/test_memory_http_contract.py](../../../tests/test_memory_http_contract.py)
- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)

</details>

**Konkrete Teilbelege:**

- [test_failed_area_remains_pending_and_only_that_area_is_retried](../../../tests/test_account_deletion_retry.py#L69) — Service mit In-Memory-Datenbank. **Datei**status vom 2026-10-02: passed=1.
  - [Zeile 163](../../../tests/test_account_deletion_retry.py#L163): ` assert first_errors == ["owned_shares"] `
  - [Zeile 164](../../../tests/test_account_deletion_retry.py#L164): ` assert second_errors == [] `
  - [Zeile 165](../../../tests/test_account_deletion_retry.py#L165): ` assert calls["shares"] == 2 `
  - [Zeile 166](../../../tests/test_account_deletion_retry.py#L166): ` assert calls["source_checks"] == 1 `
  - [Zeile 167](../../../tests/test_account_deletion_retry.py#L167): ` assert calls["api"] == 1 `
  - [Zeile 168](../../../tests/test_account_deletion_retry.py#L168): ` assert calls["subcollections"] == 1 `
- [test_native_patch_and_manual_save_have_one_revision_winner](../../../tests/e2e/test_memory_edit_transactions.py#L44) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter main-HTTP-Adapter. **Datei**status vom 2026-10-02: passed=7.
  - [Zeile 51](../../../tests/e2e/test_memory_edit_transactions.py#L51): ` assert exc.code == "revision_conflict" `
  - [Zeile 68](../../../tests/e2e/test_memory_edit_transactions.py#L68): ` assert sorted(value for value in results if value is not None) == [5] `
  - [Zeile 70](../../../tests/e2e/test_memory_edit_transactions.py#L70): ` assert stored["revision"] == 5 `
  - [Zeile 71](../../../tests/e2e/test_memory_edit_transactions.py#L71): ` assert (stored["role"], stored["notes"]) in { `
- [test_native_account_cascade_resumes_failed_objects_without_foreign_loss](../../../tests/e2e/test_account_deletion_transactions.py#L60) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter Cloudadapter. **Datei**status vom 2026-10-02: passed=2.
  - [Zeile 76](../../../tests/e2e/test_account_deletion_transactions.py#L76): ` assert service.cleanup_uid(uid) == ["chats"] `
  - [Zeile 78](../../../tests/e2e/test_account_deletion_transactions.py#L78): ` assert job["status"] == "pending" and "chats" not in job["completed_areas"] `
  - [Zeile 79](../../../tests/e2e/test_account_deletion_transactions.py#L79): ` assert set(job["completed_areas"]) == AREAS - {"chats"} `
  - [Zeile 80](../../../tests/e2e/test_account_deletion_transactions.py#L80): ` with pytest.raises(persistence_guard.AccountDeletionInProgress): `
  - [Zeile 83](../../../tests/e2e/test_account_deletion_transactions.py#L83): ` assert account_deletion.FirestoreAccountDeletion(db).cleanup_uid(uid) == [] `
  - [Zeile 85](../../../tests/e2e/test_account_deletion_transactions.py#L85): ` assert final["status"] == "completed" and set(final["completed_areas"]) == AREAS `
- [test_native_outbox_claim_takeover_rejects_stale_ack_and_terminal_replay](../../../tests/e2e/test_watch_delivery_transactions.py#L8) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 15](../../../tests/e2e/test_watch_delivery_transactions.py#L15): ` assert sum(claim is not None for claim in claims) == 1 `
  - [Zeile 20](../../../tests/e2e/test_watch_delivery_transactions.py#L20): ` assert current["lease_owner"] != old["lease_owner"] `
  - [Zeile 21](../../../tests/e2e/test_watch_delivery_transactions.py#L21): ` assert not outbox.finish(ref.id, old["lease_owner"], outbox.SENT, now=later, db=db) `
  - [Zeile 22](../../../tests/e2e/test_watch_delivery_transactions.py#L22): ` assert ref.get().to_dict() == before `
  - [Zeile 23](../../../tests/e2e/test_watch_delivery_transactions.py#L23): ` assert outbox.finish(ref.id, current["lease_owner"], outbox.SENT, now=later, db=db) `
  - [Zeile 24](../../../tests/e2e/test_watch_delivery_transactions.py#L24): ` assert outbox.claim(ref.id, now=later + timedelta(days=1), db=db) is None `
- [test_j05_delete_during_agent_work_fences_late_writes_and_owner_switch](../../../tests/e2e/test_persisted_journeys.py#L308) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 318](../../../tests/e2e/test_persisted_journeys.py#L318): ` assert memory.ok, memory.text() `
  - [Zeile 324](../../../tests/e2e/test_persisted_journeys.py#L324): ` expect(j.page.locator('#agentAnswerBody')).to_contain_text('Saved partial answer', timeout=30000) `
  - [Zeile 326](../../../tests/e2e/test_persisted_journeys.py#L326): ` assert deleted.status == 200, deleted.text() `
  - [Zeile 327](../../../tests/e2e/test_persisted_journeys.py#L327): ` assert deleted.json()['status'] == 'deleted' `
  - [Zeile 328](../../../tests/e2e/test_persisted_journeys.py#L328): ` assert j.control('state')['streams'] == [{'lease': 'running', 'response_ended': False}] `
  - [Zeile 333](../../../tests/e2e/test_persisted_journeys.py#L333): ` assert j.producer_finished() == [{'lease': 'released', 'response_ended': True}] `
- [test_main_undo_errors_preserve_all_state_and_never_call_provider](../../../tests/test_memory_http_contract.py#L75) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=12.
  - [Zeile 109](../../../tests/test_memory_http_contract.py#L109): ` assert response.status_code == status, response.text `
  - [Zeile 110](../../../tests/test_memory_http_contract.py#L110): ` assert "error" in response.json() `
  - [Zeile 112](../../../tests/test_memory_http_contract.py#L112): ` assert response.json()["error"]["error_code"] == code `
  - [Zeile 113](../../../tests/test_memory_http_contract.py#L113): ` assert response.json()["error"]["message"] `
  - [Zeile 114](../../../tests/test_memory_http_contract.py#L114): ` assert "private database diagnostic" not in response.text `
  - [Zeile 115](../../../tests/test_memory_http_contract.py#L115): ` assert h.db.documents == before and len(h.db.write_log) == writes `

<a id="auth-04"></a>

## AUTH-04 · Browser-Identität und Sitzungswechsel

Jeder asynchrone Read/Write und jede Ansicht gehört zur aktuellen UID und Auth-Generation. Logout/Kontowechsel verwerfen alte Projektionen und laufende Contexts.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Chromiumdetails mit kontrolliertem Auth-State; native persistierte Journeys werden separat dokumentiert. Kein Firebase-SDK-Livelogin.

**Befunde:** [G-030](gaps.md#g-030). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/firebase.js](../../../static/firebase.js)
- [static/js/auth-bootstrap.js](../../../static/js/auth-bootstrap.js)
- [static/js/auth-session-state.js](../../../static/js/auth-session-state.js)
- [static/js/email-verify.js](../../../static/js/email-verify.js)
- [static/js/run-registry.js](../../../static/js/run-registry.js)

**Testdateien:**

- [tests/e2e/test_browser_failure_recovery.py](../../../tests/e2e/test_browser_failure_recovery.py)
- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py)
- [tests/js/attachment-draft-generation.test.mjs](../../../tests/js/attachment-draft-generation.test.mjs)
- [tests/js/bookmark-write-queue.test.mjs](../../../tests/js/bookmark-write-queue.test.mjs)
- [tests/js/memory-edit-auth.test.mjs](../../../tests/js/memory-edit-auth.test.mjs)
- [tests/js/skeleton-lifecycle.test.mjs](../../../tests/js/skeleton-lifecycle.test.mjs)
- [tests/js/source-verification-watch.test.mjs](../../../tests/js/source-verification-watch.test.mjs)

</details>

**Konkrete Teilbelege:**

- [serializes the same account resource across rapid auth generations](../../../tests/js/bookmark-write-queue.test.mjs#L59) — Ausgeführter Firebase-Funktionsausschnitt in Node. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 75](../../../tests/js/bookmark-write-queue.test.mjs#L75): ` expect(events).toEqual(["old:start"]); `
  - [Zeile 78](../../../tests/js/bookmark-write-queue.test.mjs#L78): ` expect(events).toEqual(["old:start", "old:end", "new"]); `
- [test_j05_delete_during_agent_work_fences_late_writes_and_owner_switch](../../../tests/e2e/test_persisted_journeys.py#L308) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 318](../../../tests/e2e/test_persisted_journeys.py#L318): ` assert memory.ok, memory.text() `
  - [Zeile 324](../../../tests/e2e/test_persisted_journeys.py#L324): ` expect(j.page.locator('#agentAnswerBody')).to_contain_text('Saved partial answer', timeout=30000) `
  - [Zeile 326](../../../tests/e2e/test_persisted_journeys.py#L326): ` assert deleted.status == 200, deleted.text() `
  - [Zeile 327](../../../tests/e2e/test_persisted_journeys.py#L327): ` assert deleted.json()['status'] == 'deleted' `
  - [Zeile 328](../../../tests/e2e/test_persisted_journeys.py#L328): ` assert j.control('state')['streams'] == [{'lease': 'running', 'response_ended': False}] `
  - [Zeile 333](../../../tests/e2e/test_persisted_journeys.py#L333): ` assert j.producer_finished() == [{'lease': 'released', 'response_ended': True}] `
- [test_phase4_server_reuses_its_child_and_rejects_an_unowned_listener](../../../tests/e2e/test_phase4_frontend.py#L143) — Chromium und ein gemeinsam gestarteter lokaler Testserver. **Datei**status vom 2026-10-02: passed=29.
  - [Zeile 150](../../../tests/e2e/test_phase4_frontend.py#L150): ` assert next(imported_fixture) == phase4_server `
  - [Zeile 151](../../../tests/e2e/test_phase4_frontend.py#L151): ` with pytest.raises(StopIteration): `
  - [Zeile 153](../../../tests/e2e/test_phase4_frontend.py#L153): ` assert request.config._phase4_server_url == phase4_server `
  - [Zeile 156](../../../tests/e2e/test_phase4_frontend.py#L156): ` with pytest.raises(RuntimeError, match='already in use'): `

<a id="quota-01"></a>

## QUOTA-01 · Ein regulärer Lauf, eine Belastung

Prepare/Fanout/Consensus teilen einen owner-/payloadgebundenen Run-Key und ein Tokenkonto. Admission hält eine Modusschätzung; einzelne Provider-/Judgeoperationen buchen idempotent, Final/Release löst Restholds. Der Admissiontag bleibt über UTC-Mitternacht gebunden; alte Runzählquoten entfallen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Native SDK-Admission/Buchung/Freigabe ohne lokalen Accountlock sowie Atomaritätsmutationen; keine produktive Lastgarantie.

**Befunde:** [G-002](gaps.md#g-002). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/chat.py](../../../app/api/routers/chat.py)
- [app/api/routers/users.py](../../../app/api/routers/users.py)
- [app/services/usage_repository.py](../../../app/services/usage_repository.py)

**Testdateien:**

- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/e2e/test_usage_transactions.py](../../../tests/e2e/test_usage_transactions.py)
- [tests/test_api_run_billing_identity.py](../../../tests/test_api_run_billing_identity.py)
- [tests/test_api_run_recovery.py](../../../tests/test_api_run_recovery.py)
- [tests/test_run_usage_endpoints.py](../../../tests/test_run_usage_endpoints.py)
- [tests/test_run_usage_repository.py](../../../tests/test_run_usage_repository.py)
- [tests/test_usage_authorization.py](../../../tests/test_usage_authorization.py)

</details>

**Konkrete Teilbelege:**

- [test_prepare_admits_once_and_answers_book_their_measured_tokens](../../../tests/test_run_usage_endpoints.py#L100) — Router-Integration mit FakeFirestore und Provider-/Engine-Doubles. **Datei**status vom 2026-10-02: passed=14.
  - [Zeile 105](../../../tests/test_run_usage_endpoints.py#L105): ` assert prepared.status_code == 200 `
  - [Zeile 107](../../../tests/test_run_usage_endpoints.py#L107): ` assert body["usage_run_status"] == "consumed" `
  - [Zeile 108](../../../tests/test_run_usage_endpoints.py#L108): ` assert body["run_estimate"] == FREE_RUN["consensus"] `
  - [Zeile 109](../../../tests/test_run_usage_endpoints.py#L109): ` assert body["token_budget"]["used"] == 0 `
  - [Zeile 110](../../../tests/test_run_usage_endpoints.py#L110): ` assert body["token_budget"]["reserved"] == FREE_RUN["consensus"] `
  - [Zeile 111](../../../tests/test_run_usage_endpoints.py#L111): ` assert body["token_budget"]["run_estimates"] == FREE_RUN `
- [test_same_operation_race_has_exactly_one_authorization](../../../tests/test_usage_authorization.py#L78) — Atomare Autorisierungslogik mit FakeFirestore und Threads. **Datei**status vom 2026-10-02: passed=15.
  - [Zeile 82](../../../tests/test_usage_authorization.py#L82): ` assert sum(not claim.idempotent for _, claim in results) == 1 `
  - [Zeile 83](../../../tests/test_usage_authorization.py#L83): ` assert db.documents[LEDGER]["pipeline_runs"] == 1 `
  - [Zeile 86](../../../tests/test_usage_authorization.py#L86): ` assert repeated.idempotent `
  - [Zeile 87](../../../tests/test_usage_authorization.py#L87): ` assert db.documents == before `
- [test_native_identical_key_and_booking_are_exactly_once](../../../tests/e2e/test_usage_transactions.py#L26) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 32](../../../tests/e2e/test_usage_transactions.py#L32): ` assert sorted(result.idempotent for result in results) == [False, True] `
  - [Zeile 39](../../../tests/e2e/test_usage_transactions.py#L39): ` assert ledger["used"] == 25 and ledger["pipeline_estimated"] == 5 and ledger["pipeline_holds"] == {} `
  - [Zeile 40](../../../tests/e2e/test_usage_transactions.py#L40): ` assert not agent_quota.quota_ref(db, other, admission(now).period).get().exists `
- [test_restart_requeues_only_pre_provider_work_and_deduplicates_schedule](../../../tests/test_api_run_recovery.py#L104) — Recoveryorchestrierung mit echten Run-/Quota-/Cleanup-Repositories. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 118](../../../tests/test_api_run_recovery.py#L118): ` assert runner.recover_persisted_runs() == 2 `
  - [Zeile 119](../../../tests/test_api_run_recovery.py#L119): ` assert ( `
  - [Zeile 122](../../../tests/test_api_run_recovery.py#L122): ` assert len(h.tasks) == 2 `
  - [Zeile 123](../../../tests/test_api_run_recovery.py#L123): ` assert {args[0] for _, args in h.tasks} == {accepted["run_id"], reserved["run_id"]} `
  - [Zeile 124](../../../tests/test_api_run_recovery.py#L124): ` assert h.runs.get(live["run_id"])["status"] == "running" `
  - [Zeile 125](../../../tests/test_api_run_recovery.py#L125): ` assert h.runs.get(stale["run_id"])["error"]["code"] == "worker_interrupted" `
- [test_j01_saved_consensus_reload_followup_keeps_native_identity_and_context](../../../tests/e2e/test_persisted_journeys.py#L150) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 155](../../../tests/e2e/test_persisted_journeys.py#L155): ` assert saved.ok, saved.text() `
  - [Zeile 156](../../../tests/e2e/test_persisted_journeys.py#L156): ` assert j.request('GET', '/bookmarks/' + first['bookmark'], uid='journey-'+'f'*32).status == 404 `
  - [Zeile 158](../../../tests/e2e/test_persisted_journeys.py#L158): ` j.page.wait_for_function('() => typeof window.openBookmark === "function" && window.__consensioAuthState?.known') `
  - [Zeile 160](../../../tests/e2e/test_persisted_journeys.py#L160): ` expect(j.page.locator('#consensusResponse')).to_contain_text('Mock consensus', timeout=15000) `
  - [Zeile 161](../../../tests/e2e/test_persisted_journeys.py#L161): ` expect(j.page.locator('#questionInput')).to_have_attribute('placeholder', 'Ask a follow-up question') `
  - [Zeile 163](../../../tests/e2e/test_persisted_journeys.py#L163): ` assert second['chat'] == first['chat'] and second['turn'] != first['turn'] `

<a id="quota-02"></a>

## QUOTA-02 · Rate-Limits und Kontostufen

Rechte und Kosten ergeben sich aus serverseitiger Stufe/Modellwahl; Own-Key umgeht keine Login-/Premiumrechte. UID-Limits bleiben beim Keywechsel erhalten; getrennte IP-/Key-Buckets schützen den Eingang.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Reale main-Rate-/Kapazitätsablehnung und user_status-Tarifmatrix; kein verteilter Proxy-/Mehrinstanz-Limiternachweis.

**Befunde:** [G-012](gaps.md#g-012). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/users.py](../../../app/api/routers/users.py)
- [app/core/entitlements.py](../../../app/core/entitlements.py)
- [app/core/rate_limit.py](../../../app/core/rate_limit.py)
- [app/services/account_tier.py](../../../app/services/account_tier.py)
- [static/js/feature-access.js](../../../static/js/feature-access.js)
- [static/js/usage-limit.js](../../../static/js/usage-limit.js)
- [static/js/user-tier.js](../../../static/js/user-tier.js)

**Testdateien:**

- [tests/js/account-tier-mark.test.mjs](../../../tests/js/account-tier-mark.test.mjs)
- [tests/js/plus-tier-gates.test.mjs](../../../tests/js/plus-tier-gates.test.mjs)
- [tests/test_agent_http_contract.py](../../../tests/test_agent_http_contract.py)
- [tests/test_onboarding_gates.py](../../../tests/test_onboarding_gates.py)
- [tests/test_plus_tier.py](../../../tests/test_plus_tier.py)
- [tests/test_pro_beta_and_copy.py](../../../tests/test_pro_beta_and_copy.py)
- [tests/test_rate_limit.py](../../../tests/test_rate_limit.py)
- [tests/test_usage_limit_ui.py](../../../tests/test_usage_limit_ui.py)

</details>

**Konkrete Teilbelege:**

- [test_plus_gets_the_features_but_not_the_expensive_models](../../../tests/test_plus_tier.py#L67) — Entitlements-/Konfigurationslogik und Security mit DB-Double. **Datei**status vom 2026-10-02: passed=34.
  - [Zeile 69](../../../tests/test_plus_tier.py#L69): ` assert plus.attachments is True `
  - [Zeile 70](../../../tests/test_plus_tier.py#L70): ` assert plus.resolve is True `
  - [Zeile 72](../../../tests/test_plus_tier.py#L72): ` assert plus.is_pro is False `
  - [Zeile 73](../../../tests/test_plus_tier.py#L73): ` assert plus.premium_models is False `
  - [Zeile 74](../../../tests/test_plus_tier.py#L74): ` assert plus.deep_think is False `
- [test_detail_pages_are_owner_bound_and_never_start_provider](../../../tests/test_agent_http_contract.py#L56) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=9.
  - [Zeile 67](../../../tests/test_agent_http_contract.py#L67): ` assert response.status_code == 200, response.text `
  - [Zeile 68](../../../tests/test_agent_http_contract.py#L68): ` assert response.headers["cache-control"] == "private, no-store" `
  - [Zeile 70](../../../tests/test_agent_http_contract.py#L70): ` assert data["agent"]["id"] == h.agent_id `
  - [Zeile 71](../../../tests/test_agent_http_contract.py#L71): ` assert data["agent"]["assignment"]["goal"] == "Owner private assignment" `
  - [Zeile 72](../../../tests/test_agent_http_contract.py#L72): ` assert 1 <= len(data["messages"]) <= 3 `
  - [Zeile 77](../../../tests/test_agent_http_contract.py#L77): ` assert [m["text"] for m in messages] == ["Message " + str(i) for i in range(7)] `

<a id="chat-01"></a>

## CHAT-01 · Chats, Turns und Cursor

Ownergebundene Chats/Turns verwenden stabile Request-IDs, monotone Positionen und begrenzte signierte Pagination; bewegte Seitengrenzen dürfen keine fremden oder doppelten Inhalte erzeugen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Native Limits und Chatlebenszyklus ergänzen lokale Cursor-/Paginationtests; keine unbegrenzte Last-/Cursorvollständigkeitsgarantie.

**Befunde:** [G-003](gaps.md#g-003). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/chat_history.py](../../../app/api/routers/chat_history.py)
- [app/services/chat_store.py](../../../app/services/chat_store.py)

**Testdateien:**

- [tests/e2e/test_chat_lifecycle_transactions.py](../../../tests/e2e/test_chat_lifecycle_transactions.py)
- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)
- [tests/test_chat_history.py](../../../tests/test_chat_history.py)

</details>

**Konkrete Teilbelege:**

- [test_chat_cursor_keeps_original_boundary_when_boundary_chat_moves](../../../tests/test_chat_history.py#L511) — Router und ChatStore mit speicherbasiertem Transaktionsmodell. **Datei**status vom 2026-10-02: passed=77.
  - [Zeile 528](../../../tests/test_chat_history.py#L528): ` assert delivered_ids == [chats[3]["id"], chats[2]["id"]] `
  - [Zeile 529](../../../tests/test_chat_history.py#L529): ` assert second_ids == [chats[1]["id"], chats[0]["id"]] `
  - [Zeile 530](../../../tests/test_chat_history.py#L530): ` assert set(delivered_ids).isdisjoint(second_ids) `
- [test_native_chat_completion_and_delete_never_resurrect_children](../../../tests/e2e/test_chat_lifecycle_transactions.py#L23) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=5.
  - [Zeile 35](../../../tests/e2e/test_chat_lifecycle_transactions.py#L35): ` assert ChatStore(db).delete_chat(uid, chat) `
  - [Zeile 41](../../../tests/e2e/test_chat_lifecycle_transactions.py#L41): ` assert ready.wait(20) `
  - [Zeile 43](../../../tests/e2e/test_chat_lifecycle_transactions.py#L43): ` with pytest.raises(ChatNotFound): `
  - [Zeile 46](../../../tests/e2e/test_chat_lifecycle_transactions.py#L46): ` assert ChatStore(db).delete_chat(uid, chat) `
  - [Zeile 51](../../../tests/e2e/test_chat_lifecycle_transactions.py#L51): ` with pytest.raises(ChatNotFound): `
  - [Zeile 53](../../../tests/e2e/test_chat_lifecycle_transactions.py#L53): ` assert tree(store._chat_ref(uid, chat)) == {} `
- [test_two_workers_cannot_exceed_owner_watch_limit](../../../tests/e2e/test_phase2_transactions.py#L29) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 71](../../../tests/e2e/test_phase2_transactions.py#L71): ` assert sorted(code for code, _watch_id in outcomes) == [ `
  - [Zeile 78](../../../tests/e2e/test_phase2_transactions.py#L78): ` assert len(watches) == 1 `
  - [Zeile 83](../../../tests/e2e/test_phase2_transactions.py#L83): ` assert state["active_count"] == 1 `
- [test_j01_saved_consensus_reload_followup_keeps_native_identity_and_context](../../../tests/e2e/test_persisted_journeys.py#L150) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 155](../../../tests/e2e/test_persisted_journeys.py#L155): ` assert saved.ok, saved.text() `
  - [Zeile 156](../../../tests/e2e/test_persisted_journeys.py#L156): ` assert j.request('GET', '/bookmarks/' + first['bookmark'], uid='journey-'+'f'*32).status == 404 `
  - [Zeile 158](../../../tests/e2e/test_persisted_journeys.py#L158): ` j.page.wait_for_function('() => typeof window.openBookmark === "function" && window.__consensioAuthState?.known') `
  - [Zeile 160](../../../tests/e2e/test_persisted_journeys.py#L160): ` expect(j.page.locator('#consensusResponse')).to_contain_text('Mock consensus', timeout=15000) `
  - [Zeile 161](../../../tests/e2e/test_persisted_journeys.py#L161): ` expect(j.page.locator('#questionInput')).to_have_attribute('placeholder', 'Ask a follow-up question') `
  - [Zeile 163](../../../tests/e2e/test_persisted_journeys.py#L163): ` assert second['chat'] == first['chat'] and second['turn'] != first['turn'] `

<a id="chat-02"></a>

## CHAT-02 · Abschluss und Löschsperre

Completion persistiert erlaubte Turn-/Antwortdaten atomar, ist bei identischem Payload idempotent und lehnt Konflikte ab. Nach deleting/Tombstone sind verspätete Completion/Fail-Writes gesperrt.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Native Löschung/Completion in beiden Reihenfolgen und während committed deleting vor Purge; vollständige eigene Kaskade und unveränderte Fremddaten belegt.

**Befunde:** [G-003](gaps.md#g-003). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/chat.py](../../../app/api/routers/chat.py)
- [app/services/chat_store.py](../../../app/services/chat_store.py)

**Testdateien:**

- [tests/e2e/test_account_deletion_transactions.py](../../../tests/e2e/test_account_deletion_transactions.py)
- [tests/e2e/test_chat_lifecycle_transactions.py](../../../tests/e2e/test_chat_lifecycle_transactions.py)
- [tests/e2e/test_file_storage_transactions.py](../../../tests/e2e/test_file_storage_transactions.py)
- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/test_agent_chat_integrity.py](../../../tests/test_agent_chat_integrity.py)
- [tests/test_chat_history.py](../../../tests/test_chat_history.py)
- [tests/test_consensus_chat_history.py](../../../tests/test_consensus_chat_history.py)

</details>

**Konkrete Teilbelege:**

- [test_complete_turn_atomically_persists_six_separate_answer_documents](../../../tests/test_chat_history.py#L831) — Router und ChatStore mit speicherbasiertem Transaktionsmodell. **Datei**status vom 2026-10-02: passed=77.
  - [Zeile 845](../../../tests/test_chat_history.py#L845): ` assert completed["status"] == "completed" `
  - [Zeile 846](../../../tests/test_chat_history.py#L846): ` assert completed["answer_count"] == 6 `
  - [Zeile 847](../../../tests/test_chat_history.py#L847): ` assert completed["agreement_score"] == 83 `
  - [Zeile 848](../../../tests/test_chat_history.py#L848): ` assert completed["included_models"] == list(PROVIDERS) `
  - [Zeile 849](../../../tests/test_chat_history.py#L849): ` assert set(completed["model_answers"]) == set(PROVIDERS) `
  - [Zeile 850](../../../tests/test_chat_history.py#L850): ` assert set(stored_answers) == { `
- [test_deleting_chat_state_rejects_late_completion_and_failure_writes](../../../tests/test_chat_history.py#L1491) — Router und ChatStore mit speicherbasiertem Transaktionsmodell. **Datei**status vom 2026-10-02: passed=77.
  - [Zeile 1500](../../../tests/test_chat_history.py#L1500): ` with pytest.raises(chat_store.ChatNotFound): `
  - [Zeile 1504](../../../tests/test_chat_history.py#L1504): ` with pytest.raises(chat_store.ChatNotFound): `
  - [Zeile 1512](../../../tests/test_chat_history.py#L1512): ` assert database.documents == before `
  - [Zeile 1513](../../../tests/test_chat_history.py#L1513): ` assert database.model_answers("owner-uid", chat["id"], turn["id"]) == {} `
- [test_native_chat_completion_and_delete_never_resurrect_children](../../../tests/e2e/test_chat_lifecycle_transactions.py#L23) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=5.
  - [Zeile 35](../../../tests/e2e/test_chat_lifecycle_transactions.py#L35): ` assert ChatStore(db).delete_chat(uid, chat) `
  - [Zeile 41](../../../tests/e2e/test_chat_lifecycle_transactions.py#L41): ` assert ready.wait(20) `
  - [Zeile 43](../../../tests/e2e/test_chat_lifecycle_transactions.py#L43): ` with pytest.raises(ChatNotFound): `
  - [Zeile 46](../../../tests/e2e/test_chat_lifecycle_transactions.py#L46): ` assert ChatStore(db).delete_chat(uid, chat) `
  - [Zeile 51](../../../tests/e2e/test_chat_lifecycle_transactions.py#L51): ` with pytest.raises(ChatNotFound): `
  - [Zeile 53](../../../tests/e2e/test_chat_lifecycle_transactions.py#L53): ` assert tree(store._chat_ref(uid, chat)) == {} `
- [test_native_cloud_upload_quota_foreign_download_and_delete_retry](../../../tests/e2e/test_file_storage_transactions.py#L50) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator, echter Cloudadapter und DOCX-/PDF-Renderer. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 62](../../../tests/e2e/test_file_storage_transactions.py#L62): ` assert sum(value is not None for value in outcomes) == 1 `
  - [Zeile 63](../../../tests/e2e/test_file_storage_transactions.py#L63): ` assert files.quota_ref(uid).get().to_dict() == {"count": 1, "bytes": 15} `
  - [Zeile 64](../../../tests/e2e/test_file_storage_transactions.py#L64): ` assert files.download(uid, chat, saved["id"])[1] == b"private fixture" `
  - [Zeile 66](../../../tests/e2e/test_file_storage_transactions.py#L66): ` with pytest.raises(ChatNotFound): `
  - [Zeile 68](../../../tests/e2e/test_file_storage_transactions.py#L68): ` assert bucket.calls == before_calls `
  - [Zeile 70](../../../tests/e2e/test_file_storage_transactions.py#L70): ` with pytest.raises(OSError, match="Retryable"): `
- [test_native_account_cascade_resumes_failed_objects_without_foreign_loss](../../../tests/e2e/test_account_deletion_transactions.py#L60) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter Cloudadapter. **Datei**status vom 2026-10-02: passed=2.
  - [Zeile 76](../../../tests/e2e/test_account_deletion_transactions.py#L76): ` assert service.cleanup_uid(uid) == ["chats"] `
  - [Zeile 78](../../../tests/e2e/test_account_deletion_transactions.py#L78): ` assert job["status"] == "pending" and "chats" not in job["completed_areas"] `
  - [Zeile 79](../../../tests/e2e/test_account_deletion_transactions.py#L79): ` assert set(job["completed_areas"]) == AREAS - {"chats"} `
  - [Zeile 80](../../../tests/e2e/test_account_deletion_transactions.py#L80): ` with pytest.raises(persistence_guard.AccountDeletionInProgress): `
  - [Zeile 83](../../../tests/e2e/test_account_deletion_transactions.py#L83): ` assert account_deletion.FirestoreAccountDeletion(db).cleanup_uid(uid) == [] `
  - [Zeile 85](../../../tests/e2e/test_account_deletion_transactions.py#L85): ` assert final["status"] == "completed" and set(final["completed_areas"]) == AREAS `
- [test_j01_saved_consensus_reload_followup_keeps_native_identity_and_context](../../../tests/e2e/test_persisted_journeys.py#L150) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 155](../../../tests/e2e/test_persisted_journeys.py#L155): ` assert saved.ok, saved.text() `
  - [Zeile 156](../../../tests/e2e/test_persisted_journeys.py#L156): ` assert j.request('GET', '/bookmarks/' + first['bookmark'], uid='journey-'+'f'*32).status == 404 `
  - [Zeile 158](../../../tests/e2e/test_persisted_journeys.py#L158): ` j.page.wait_for_function('() => typeof window.openBookmark === "function" && window.__consensioAuthState?.known') `
  - [Zeile 160](../../../tests/e2e/test_persisted_journeys.py#L160): ` expect(j.page.locator('#consensusResponse')).to_contain_text('Mock consensus', timeout=15000) `
  - [Zeile 161](../../../tests/e2e/test_persisted_journeys.py#L161): ` expect(j.page.locator('#questionInput')).to_have_attribute('placeholder', 'Ask a follow-up question') `
  - [Zeile 163](../../../tests/e2e/test_persisted_journeys.py#L163): ` assert second['chat'] == first['chat'] and second['turn'] != first['turn'] `

<a id="chat-03"></a>

## CHAT-03 · Kontext und Nutzergedächtnis im Lauf

Ein autoritativer Kontext ist an Owner/Turn/Frage/Version gebunden, einmalig gebaut und begrenzt. Jede Modellfamilie erhält nur ihre eigene vorherige Antwort; Gedächtnis bleibt Datenkontext ohne ungefragte Persistenz.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Compressor/Judge synthetisch; Signaltests beweisen keine semantische Gedächtnisqualität oder Prompt-Injection-Resistenz.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/chat_history.py](../../../app/api/routers/chat_history.py)
- [app/services/chat_context.py](../../../app/services/chat_context.py)
- [app/services/user_memory.py](../../../app/services/user_memory.py)

**Testdateien:**

- [tests/e2e/test_chat_lifecycle_transactions.py](../../../tests/e2e/test_chat_lifecycle_transactions.py)
- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/test_chat_context.py](../../../tests/test_chat_context.py)
- [tests/test_followup_context.py](../../../tests/test_followup_context.py)
- [tests/test_prompt_date_context.py](../../../tests/test_prompt_date_context.py)
- [tests/test_user_memory.py](../../../tests/test_user_memory.py)
- [tests/test_user_memory_run_cache.py](../../../tests/test_user_memory_run_cache.py)

</details>

**Konkrete Teilbelege:**

- [test_each_model_sees_only_its_own_previous_answer](../../../tests/test_chat_context.py#L1043) — Service/Repository/Router mit FakeChatDatabase und künstlichem Compressor. **Datei**status vom 2026-10-02: passed=41.
  - [Zeile 1074](../../../tests/test_chat_context.py#L1074): ` assert "My earlier reading of the site." in claude `
  - [Zeile 1075](../../../tests/test_chat_context.py#L1075): ` assert "A different earlier reading." not in claude `
  - [Zeile 1076](../../../tests/test_chat_context.py#L1076): ` assert "A different earlier reading." in grok `
  - [Zeile 1077](../../../tests/test_chat_context.py#L1077): ` assert "My earlier reading of the site." not in grok `
  - [Zeile 1079](../../../tests/test_chat_context.py#L1079): ` assert "Anthropic" not in claude and "Grok" not in grok `
  - [Zeile 1081](../../../tests/test_chat_context.py#L1081): ` assert "the answer you yourself gave" not in mistral.casefold() `
- [test_native_chat_completion_and_delete_never_resurrect_children](../../../tests/e2e/test_chat_lifecycle_transactions.py#L23) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=5.
  - [Zeile 35](../../../tests/e2e/test_chat_lifecycle_transactions.py#L35): ` assert ChatStore(db).delete_chat(uid, chat) `
  - [Zeile 41](../../../tests/e2e/test_chat_lifecycle_transactions.py#L41): ` assert ready.wait(20) `
  - [Zeile 43](../../../tests/e2e/test_chat_lifecycle_transactions.py#L43): ` with pytest.raises(ChatNotFound): `
  - [Zeile 46](../../../tests/e2e/test_chat_lifecycle_transactions.py#L46): ` assert ChatStore(db).delete_chat(uid, chat) `
  - [Zeile 51](../../../tests/e2e/test_chat_lifecycle_transactions.py#L51): ` with pytest.raises(ChatNotFound): `
  - [Zeile 53](../../../tests/e2e/test_chat_lifecycle_transactions.py#L53): ` assert tree(store._chat_ref(uid, chat)) == {} `
- [test_j01_saved_consensus_reload_followup_keeps_native_identity_and_context](../../../tests/e2e/test_persisted_journeys.py#L150) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 155](../../../tests/e2e/test_persisted_journeys.py#L155): ` assert saved.ok, saved.text() `
  - [Zeile 156](../../../tests/e2e/test_persisted_journeys.py#L156): ` assert j.request('GET', '/bookmarks/' + first['bookmark'], uid='journey-'+'f'*32).status == 404 `
  - [Zeile 158](../../../tests/e2e/test_persisted_journeys.py#L158): ` j.page.wait_for_function('() => typeof window.openBookmark === "function" && window.__consensioAuthState?.known') `
  - [Zeile 160](../../../tests/e2e/test_persisted_journeys.py#L160): ` expect(j.page.locator('#consensusResponse')).to_contain_text('Mock consensus', timeout=15000) `
  - [Zeile 161](../../../tests/e2e/test_persisted_journeys.py#L161): ` expect(j.page.locator('#questionInput')).to_have_attribute('placeholder', 'Ask a follow-up question') `
  - [Zeile 163](../../../tests/e2e/test_persisted_journeys.py#L163): ` assert second['chat'] == first['chat'] and second['turn'] != first['turn'] `

<a id="chat-04"></a>

## CHAT-04 · Bookmarks und vollständiger Verlauf

Speichern materialisiert den autoritativen Run/Turn statt Clientkopien; stabile Bookmark-ID erhält alle Turns, Listen bleiben kompakt. Rehydration ist owner-/versionsgebunden, Quoten begrenzen Count/Bytes.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Browser-SDK/API ersetzt, viele JS-Tests Quellausschnitte; keine durchgehende Browser→Bookmark→Firestore-Kaskade.

**Befunde:** [G-030](gaps.md#g-030). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/bookmarks.py](../../../app/api/routers/bookmarks.py)
- [app/services/persistence_guard.py](../../../app/services/persistence_guard.py)
- [static/firebase.js](../../../static/firebase.js)

**Testdateien:**

- [tests/e2e/test_bookmark_lifecycle_frontend.py](../../../tests/e2e/test_bookmark_lifecycle_frontend.py)
- [tests/e2e/test_chat_scroll_frontend.py](../../../tests/e2e/test_chat_scroll_frontend.py)
- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/js/bookmark-attachments.test.mjs](../../../tests/js/bookmark-attachments.test.mjs)
- [tests/js/bookmark-pending-state.test.mjs](../../../tests/js/bookmark-pending-state.test.mjs)
- [tests/js/bookmark-source-check.test.mjs](../../../tests/js/bookmark-source-check.test.mjs)
- [tests/js/bookmark-write-queue.test.mjs](../../../tests/js/bookmark-write-queue.test.mjs)
- [tests/js/stored-turn-markers.test.mjs](../../../tests/js/stored-turn-markers.test.mjs)
- [tests/test_bookmarks.py](../../../tests/test_bookmarks.py)
- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)

</details>

**Konkrete Teilbelege:**

- [test_chat_bookmark_conversation_falls_back_without_losing_middle_turns](../../../tests/test_bookmarks.py#L881) — Router/Service mit Firestore-Doubles und Quelltextverträgen. **Datei**status vom 2026-10-02: passed=40.
  - [Zeile 894](../../../tests/test_bookmarks.py#L894): ` assert (uid, requested_chat_id, cursor, limit) == ( `
  - [Zeile 931](../../../tests/test_bookmarks.py#L931): ` assert response.status_code == 200 `
  - [Zeile 932](../../../tests/test_bookmarks.py#L932): ` assert [turn["question"] for turn in response.json()["turns"]] == [ `
- [test_j01_saved_consensus_reload_followup_keeps_native_identity_and_context](../../../tests/e2e/test_persisted_journeys.py#L150) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 155](../../../tests/e2e/test_persisted_journeys.py#L155): ` assert saved.ok, saved.text() `
  - [Zeile 156](../../../tests/e2e/test_persisted_journeys.py#L156): ` assert j.request('GET', '/bookmarks/' + first['bookmark'], uid='journey-'+'f'*32).status == 404 `
  - [Zeile 158](../../../tests/e2e/test_persisted_journeys.py#L158): ` j.page.wait_for_function('() => typeof window.openBookmark === "function" && window.__consensioAuthState?.known') `
  - [Zeile 160](../../../tests/e2e/test_persisted_journeys.py#L160): ` expect(j.page.locator('#consensusResponse')).to_contain_text('Mock consensus', timeout=15000) `
  - [Zeile 161](../../../tests/e2e/test_persisted_journeys.py#L161): ` expect(j.page.locator('#questionInput')).to_have_attribute('placeholder', 'Ask a follow-up question') `
  - [Zeile 163](../../../tests/e2e/test_persisted_journeys.py#L163): ` assert second['chat'] == first['chat'] and second['turn'] != first['turn'] `
- [stays disabled until both the run and its persistence write finish](../../../tests/js/bookmark-pending-state.test.mjs#L45) — Originale Bookmarkhelfer und Markup im jsdom mit kontrolliertem Speichern. **Datei**status vom 2026-10-02: passed=5.
  - [Zeile 54](../../../tests/js/bookmark-pending-state.test.mjs#L54): ` expect(session.pending).not.toBeNull(); `
  - [Zeile 55](../../../tests/js/bookmark-pending-state.test.mjs#L55): ` expect(ready).toEqual([]); `
  - [Zeile 59](../../../tests/js/bookmark-pending-state.test.mjs#L59): ` expect(session.pending).toBeNull(); `
  - [Zeile 60](../../../tests/js/bookmark-pending-state.test.mjs#L60): ` expect(ready).toEqual([{ id: "pending_id", title: "How does this work?" }]); `
  - [Zeile 61](../../../tests/js/bookmark-pending-state.test.mjs#L61): ` expect(rendered.length).toBeGreaterThanOrEqual(2); `
- [keeps the contradiction line on the disputed sentence](../../../tests/js/stored-turn-markers.test.mjs#L92) — Echte DOMrenderfunktionen im jsdom. **Datei**status vom 2026-10-02: passed=8.
  - [Zeile 95](../../../tests/js/stored-turn-markers.test.mjs#L95): ` expect(marks.length).toBeGreaterThan(0); `
  - [Zeile 96](../../../tests/js/stored-turn-markers.test.mjs#L96): ` expect(marks[0].textContent).toContain("ticket costs 29 euros"); `
- [test_agent_review_and_completion_keep_visible_answer_still](../../../tests/e2e/test_chat_scroll_frontend.py#L13) — Chromium mit echten Appskripten und kontrollierten Antworten. **Datei**status vom 2026-10-02: passed=11.
  - [Zeile 39](../../../tests/e2e/test_chat_scroll_frontend.py#L39): ` expect(page.locator('#agentAnswerBody p')).to_have_count(45) `
  - [Zeile 45](../../../tests/e2e/test_chat_scroll_frontend.py#L45): ` page.wait_for_function('() => document.documentElement.scrollHeight - innerHeight - scrollY < 3') `
  - [Zeile 62](../../../tests/e2e/test_chat_scroll_frontend.py#L62): ` assert page.locator('#agentAnswerActivity').bounding_box()['y'] + page.locator('#agentAnswerActivity').bounding_box()['height'] < 0 `
  - [Zeile 86](../../../tests/e2e/test_chat_scroll_frontend.py#L86): ` assert max(samples) - min(samples) < 3, (stage, samples) `
  - [Zeile 87](../../../tests/e2e/test_chat_scroll_frontend.py#L87): ` expect(page.locator('#agentAnswerActivity details')).not_to_have_attribute('open', '') `
  - [Zeile 88](../../../tests/e2e/test_chat_scroll_frontend.py#L88): ` expect(page.locator('#agentAnswerActivity .agent-progress')).not_to_be_visible() `

<a id="mem-01"></a>

## MEM-01 · Memory lesen und manuell speichern

Manuelles Memory-PUT benötigt expected_revision. Stale oder revisionslose Writes erhalten 409 ohne Datenverlust; die UI bewahrt Entwürfe und verlangt bewussten Reload/Overwrite.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Repos/Endpoints/DOM separat; reale Cross-Tab-Persistenz nicht durch diese Tests bewiesen.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/users.py](../../../app/api/routers/users.py)
- [app/services/user_memory.py](../../../app/services/user_memory.py)
- [static/js/user-memory.js](../../../static/js/user-memory.js)

**Testdateien:**

- [tests/e2e/test_memory_edit_transactions.py](../../../tests/e2e/test_memory_edit_transactions.py)
- [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py)
- [tests/js/user-memory.test.mjs](../../../tests/js/user-memory.test.mjs)
- [tests/test_memory_http_contract.py](../../../tests/test_memory_http_contract.py)
- [tests/test_user_memory.py](../../../tests/test_user_memory.py)
- [tests/test_user_memory_run_cache.py](../../../tests/test_user_memory_run_cache.py)

</details>

**Konkrete Teilbelege:**

- [test_legacy_save_without_notes_preserves_an_existing_long_note](../../../tests/test_user_memory.py#L234) — Sanitizer-/Repository-/Router-/Prompt-Integration mit Doubles und einem Sourcevertrag. **Datei**status vom 2026-10-02: passed=34.
  - [Zeile 237](../../../tests/test_user_memory.py#L237): ` assert saved["role"] == "Senior doctor" `
  - [Zeile 238](../../../tests/test_user_memory.py#L238): ` assert saved["notes"] == "Keep this imported memory" `
  - [Zeile 241](../../../tests/test_user_memory.py#L241): ` assert cleared["notes"] == "" `
- [test_native_patch_and_manual_save_have_one_revision_winner](../../../tests/e2e/test_memory_edit_transactions.py#L44) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter main-HTTP-Adapter. **Datei**status vom 2026-10-02: passed=7.
  - [Zeile 51](../../../tests/e2e/test_memory_edit_transactions.py#L51): ` assert exc.code == "revision_conflict" `
  - [Zeile 68](../../../tests/e2e/test_memory_edit_transactions.py#L68): ` assert sorted(value for value in results if value is not None) == [5] `
  - [Zeile 70](../../../tests/e2e/test_memory_edit_transactions.py#L70): ` assert stored["revision"] == 5 `
  - [Zeile 71](../../../tests/e2e/test_memory_edit_transactions.py#L71): ` assert (stored["role"], stored["notes"]) in { `
- [test_main_undo_errors_preserve_all_state_and_never_call_provider](../../../tests/test_memory_http_contract.py#L75) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=12.
  - [Zeile 109](../../../tests/test_memory_http_contract.py#L109): ` assert response.status_code == status, response.text `
  - [Zeile 110](../../../tests/test_memory_http_contract.py#L110): ` assert "error" in response.json() `
  - [Zeile 112](../../../tests/test_memory_http_contract.py#L112): ` assert response.json()["error"]["error_code"] == code `
  - [Zeile 113](../../../tests/test_memory_http_contract.py#L113): ` assert response.json()["error"]["message"] `
  - [Zeile 114](../../../tests/test_memory_http_contract.py#L114): ` assert "private database diagnostic" not in response.text `
  - [Zeile 115](../../../tests/test_memory_http_contract.py#L115): ` assert h.db.documents == before and len(h.db.write_log) == writes `
- [test_phase4_server_reuses_its_child_and_rejects_an_unowned_listener](../../../tests/e2e/test_phase4_frontend.py#L143) — Chromium und ein gemeinsam gestarteter lokaler Testserver. **Datei**status vom 2026-10-02: passed=29.
  - [Zeile 150](../../../tests/e2e/test_phase4_frontend.py#L150): ` assert next(imported_fixture) == phase4_server `
  - [Zeile 151](../../../tests/e2e/test_phase4_frontend.py#L151): ` with pytest.raises(StopIteration): `
  - [Zeile 153](../../../tests/e2e/test_phase4_frontend.py#L153): ` assert request.config._phase4_server_url == phase4_server `
  - [Zeile 156](../../../tests/e2e/test_phase4_frontend.py#L156): ` with pytest.raises(RuntimeError, match='already in use'): `

<a id="mem-02"></a>

## MEM-02 · Expliziter KI-Patch und sicheres Undo

Expliziter KI-Patch und Undo sind owner-/revisions-/leasegebunden. Ein Vorprofil über dem aktuellen Limit wird strukturiert ohne Writes abgelehnt; erfolgreiche Rücknahme darf keine Notizen kürzen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Repository-, native SDK- und registrierte main-HTTP-Nachweise für Revision, Lease, Owner, Expiry, Replay und Limitabsenkung vorhanden. Providerqualität und kostenpflichtige Live-Edits sind keine Testziele.

**Befunde:** [G-007](gaps.md#g-007), [G-008](gaps.md#g-008), [G-038](gaps.md#g-038). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/users.py](../../../app/api/routers/users.py)
- [app/services/memory_edit.py](../../../app/services/memory_edit.py)
- [static/js/memory-edit.js](../../../static/js/memory-edit.js)

**Testdateien:**

- [tests/e2e/test_memory_edit_transactions.py](../../../tests/e2e/test_memory_edit_transactions.py)
- [tests/e2e/test_reader_review_regressions.py](../../../tests/e2e/test_reader_review_regressions.py)
- [tests/js/memory-edit-auth.test.mjs](../../../tests/js/memory-edit-auth.test.mjs)
- [tests/js/memory-edit-sources.test.mjs](../../../tests/js/memory-edit-sources.test.mjs)
- [tests/test_memory_edit.py](../../../tests/test_memory_edit.py)
- [tests/test_memory_http_contract.py](../../../tests/test_memory_http_contract.py)

</details>

**Konkrete Teilbelege:**

- [test_replace_is_revision_checked_and_undo_restores_exact_content](../../../tests/test_memory_edit.py#L178) — Memory-Repository mit Transaktionsdouble. **Datei**status vom 2026-10-02: passed=22.
  - [Zeile 189](../../../tests/test_memory_edit.py#L189): ` assert reserved["baseline_revision"] == 4 `
  - [Zeile 204](../../../tests/test_memory_edit.py#L204): ` assert result["status"] == "applied" `
  - [Zeile 208](../../../tests/test_memory_edit.py#L208): ` assert profile["role"] == "Works at Firma Y." `
  - [Zeile 209](../../../tests/test_memory_edit.py#L209): ` assert revision == 5 `
  - [Zeile 220](../../../tests/test_memory_edit.py#L220): ` assert undone["status"] == "undone" `
  - [Zeile 221](../../../tests/test_memory_edit.py#L221): ` assert restored["role"] == "Works at Firma X." `
- [test_native_patch_and_manual_save_have_one_revision_winner](../../../tests/e2e/test_memory_edit_transactions.py#L44) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter main-HTTP-Adapter. **Datei**status vom 2026-10-02: passed=7.
  - [Zeile 51](../../../tests/e2e/test_memory_edit_transactions.py#L51): ` assert exc.code == "revision_conflict" `
  - [Zeile 68](../../../tests/e2e/test_memory_edit_transactions.py#L68): ` assert sorted(value for value in results if value is not None) == [5] `
  - [Zeile 70](../../../tests/e2e/test_memory_edit_transactions.py#L70): ` assert stored["revision"] == 5 `
  - [Zeile 71](../../../tests/e2e/test_memory_edit_transactions.py#L71): ` assert (stored["role"], stored["notes"]) in { `
- [test_main_undo_errors_preserve_all_state_and_never_call_provider](../../../tests/test_memory_http_contract.py#L75) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=12.
  - [Zeile 109](../../../tests/test_memory_http_contract.py#L109): ` assert response.status_code == status, response.text `
  - [Zeile 110](../../../tests/test_memory_http_contract.py#L110): ` assert "error" in response.json() `
  - [Zeile 112](../../../tests/test_memory_http_contract.py#L112): ` assert response.json()["error"]["error_code"] == code `
  - [Zeile 113](../../../tests/test_memory_http_contract.py#L113): ` assert response.json()["error"]["message"] `
  - [Zeile 114](../../../tests/test_memory_http_contract.py#L114): ` assert "private database diagnostic" not in response.text `
  - [Zeile 115](../../../tests/test_memory_http_contract.py#L115): ` assert h.db.documents == before and len(h.db.write_log) == writes `

<a id="api-01"></a>

## API-01 · API-Schlüssel und Scopes

Nur aktive verifizierte Konten bekommen Schlüssel; Klartext wird einmal ausgegeben und nicht gespeichert. Ownerbindung, Widerruf und Scopes begrenzen Run/Share/Indexing.

**Anforderungsbasis:** [docs/consensus-api.md](../../consensus-api.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Hash-/Scope-/Authvertrag lokal; native Kontokaskade umfasst echte API-Key-/Runbereiche. Kein produktiver Credentialtest.

**Befunde:** [G-037](gaps.md#g-037). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/admin.py](../../../app/api/routers/admin.py)
- [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py)
- [app/services/api_account_cleanup.py](../../../app/services/api_account_cleanup.py)
- [app/services/api_key_repository.py](../../../app/services/api_key_repository.py)

**Testdateien:**

- [tests/e2e/test_account_deletion_transactions.py](../../../tests/e2e/test_account_deletion_transactions.py)
- [tests/test_api_account_cleanup.py](../../../tests/test_api_account_cleanup.py)
- [tests/test_api_key_repository.py](../../../tests/test_api_key_repository.py)
- [tests/test_consensus_api.py](../../../tests/test_consensus_api.py)

</details>

**Konkrete Teilbelege:**

- [test_plaintext_key_is_returned_once_but_never_persisted](../../../tests/test_api_key_repository.py#L71) — Repository mit Firestore-Fake. **Datei**status vom 2026-10-02: passed=5.
  - [Zeile 76](../../../tests/test_api_key_repository.py#L76): ` assert issued["api_key"].startswith("cns_live_") `
  - [Zeile 77](../../../tests/test_api_key_repository.py#L77): ` assert issued["key_id"] in db.documents `
  - [Zeile 78](../../../tests/test_api_key_repository.py#L78): ` assert issued["api_key"] not in repr(db.documents) `
  - [Zeile 79](../../../tests/test_api_key_repository.py#L79): ` assert "api_key" not in db.documents[issued["key_id"]] `
  - [Zeile 81](../../../tests/test_api_key_repository.py#L81): ` assert identity.uid == "user-1" `
  - [Zeile 82](../../../tests/test_api_key_repository.py#L82): ` assert identity.key_id == issued["key_id"] `
- [test_native_account_cascade_resumes_failed_objects_without_foreign_loss](../../../tests/e2e/test_account_deletion_transactions.py#L60) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter Cloudadapter. **Datei**status vom 2026-10-02: passed=2.
  - [Zeile 76](../../../tests/e2e/test_account_deletion_transactions.py#L76): ` assert service.cleanup_uid(uid) == ["chats"] `
  - [Zeile 78](../../../tests/e2e/test_account_deletion_transactions.py#L78): ` assert job["status"] == "pending" and "chats" not in job["completed_areas"] `
  - [Zeile 79](../../../tests/e2e/test_account_deletion_transactions.py#L79): ` assert set(job["completed_areas"]) == AREAS - {"chats"} `
  - [Zeile 80](../../../tests/e2e/test_account_deletion_transactions.py#L80): ` with pytest.raises(persistence_guard.AccountDeletionInProgress): `
  - [Zeile 83](../../../tests/e2e/test_account_deletion_transactions.py#L83): ` assert account_deletion.FirestoreAccountDeletion(db).cleanup_uid(uid) == [] `
  - [Zeile 85](../../../tests/e2e/test_account_deletion_transactions.py#L85): ` assert final["status"] == "completed" and set(final["completed_areas"]) == AREAS `

<a id="api-02"></a>

## API-02 · Dauerhafte API-Runs

Idempotenzschlüssel und Payload bestimmen einen Run mit eigenem nicht wiederverwendbarem Usagebeleg. Löschen hinterlässt einen begrenzten Tombstone und Wiederholung liefert 410; neue Schlüssel starten neue bezahlte Arbeit. Verwaiste accepted/reserved-Runs werden konservativ abgeschlossen, running wird nicht blind neu generiert.

**Anforderungsbasis:** [docs/consensus-api.md](../../consensus-api.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Echte Recoveryorchestrierung mit DB-Doubles sowie native Retention-/Mappingtransaktionen. Keine produktive Restart-/Last- oder Providerverfügbarkeitsgarantie.

**Befunde:** [G-005](gaps.md#g-005). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py)
- [app/services/api_consensus_runner.py](../../../app/services/api_consensus_runner.py)
- [app/services/api_run_repository.py](../../../app/services/api_run_repository.py)

**Testdateien:**

- [tests/e2e/test_account_deletion_transactions.py](../../../tests/e2e/test_account_deletion_transactions.py)
- [tests/e2e/test_api_retention_transactions.py](../../../tests/e2e/test_api_retention_transactions.py)
- [tests/test_api_run_billing_identity.py](../../../tests/test_api_run_billing_identity.py)
- [tests/test_api_run_recovery.py](../../../tests/test_api_run_recovery.py)
- [tests/test_api_run_repository.py](../../../tests/test_api_run_repository.py)
- [tests/test_consensus_api.py](../../../tests/test_consensus_api.py)

</details>

**Konkrete Teilbelege:**

- [test_expired_running_lease_fails_without_requeueing](../../../tests/test_api_run_repository.py#L200) — Repository mit synchronisiertem Firestore-Fake. **Datei**status vom 2026-10-02: passed=8.
  - [Zeile 211](../../../tests/test_api_run_repository.py#L211): ` assert changed is True `
  - [Zeile 212](../../../tests/test_api_run_repository.py#L212): ` assert failed["status"] == "failed" `
  - [Zeile 213](../../../tests/test_api_run_repository.py#L213): ` assert failed["error"]["code"] == "worker_interrupted" `
  - [Zeile 214](../../../tests/test_api_run_repository.py#L214): ` assert repo.fail_if_lease_expired(run["run_id"]) is False `
- [test_native_account_cascade_resumes_failed_objects_without_foreign_loss](../../../tests/e2e/test_account_deletion_transactions.py#L60) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter Cloudadapter. **Datei**status vom 2026-10-02: passed=2.
  - [Zeile 76](../../../tests/e2e/test_account_deletion_transactions.py#L76): ` assert service.cleanup_uid(uid) == ["chats"] `
  - [Zeile 78](../../../tests/e2e/test_account_deletion_transactions.py#L78): ` assert job["status"] == "pending" and "chats" not in job["completed_areas"] `
  - [Zeile 79](../../../tests/e2e/test_account_deletion_transactions.py#L79): ` assert set(job["completed_areas"]) == AREAS - {"chats"} `
  - [Zeile 80](../../../tests/e2e/test_account_deletion_transactions.py#L80): ` with pytest.raises(persistence_guard.AccountDeletionInProgress): `
  - [Zeile 83](../../../tests/e2e/test_account_deletion_transactions.py#L83): ` assert account_deletion.FirestoreAccountDeletion(db).cleanup_uid(uid) == [] `
  - [Zeile 85](../../../tests/e2e/test_account_deletion_transactions.py#L85): ` assert final["status"] == "completed" and set(final["completed_areas"]) == AREAS `
- [test_restart_requeues_only_pre_provider_work_and_deduplicates_schedule](../../../tests/test_api_run_recovery.py#L104) — Recoveryorchestrierung mit echten Run-/Quota-/Cleanup-Repositories. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 118](../../../tests/test_api_run_recovery.py#L118): ` assert runner.recover_persisted_runs() == 2 `
  - [Zeile 119](../../../tests/test_api_run_recovery.py#L119): ` assert ( `
  - [Zeile 122](../../../tests/test_api_run_recovery.py#L122): ` assert len(h.tasks) == 2 `
  - [Zeile 123](../../../tests/test_api_run_recovery.py#L123): ` assert {args[0] for _, args in h.tasks} == {accepted["run_id"], reserved["run_id"]} `
  - [Zeile 124](../../../tests/test_api_run_recovery.py#L124): ` assert h.runs.get(live["run_id"])["status"] == "running" `
  - [Zeile 125](../../../tests/test_api_run_recovery.py#L125): ` assert h.runs.get(stale["run_id"])["error"]["code"] == "worker_interrupted" `
- [test_retention_backfill_is_atomic_and_does_not_renew_another_run](../../../tests/e2e/test_api_retention_transactions.py#L8) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=2.
  - [Zeile 21](../../../tests/e2e/test_api_retention_transactions.py#L21): ` assert sorted(race(repo.backfill_retention, repo.backfill_retention)) == [0, 1] `
  - [Zeile 22](../../../tests/e2e/test_api_retention_transactions.py#L22): ` assert ref.get().to_dict()["expires_at"] == stamp + timedelta(days=30) `
  - [Zeile 23](../../../tests/e2e/test_api_retention_transactions.py#L23): ` assert mapping.get().to_dict() == before `
  - [Zeile 27](../../../tests/e2e/test_api_retention_transactions.py#L27): ` assert repo.backfill_retention() == 0 `
  - [Zeile 28](../../../tests/e2e/test_api_retention_transactions.py#L28): ` assert not repo._idempotency_ref(owner, "unknown").get().exists `

<a id="api-03"></a>

## API-03 · Historische Source-Checks der API

Historische API-Prüfberichte bleiben owner-, run- und antwortversionsgebunden lesbar; neue Nicht-Chat-Runs starten keine Source-Check-Jobs.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Registrierter historischer API-v1-Source-GET und echte Repositorygrenzen geprüft; Daten/SDKidentität kontrolliert, keine neue Job-Erzeugung.

**Befunde:** [G-010](gaps.md#g-010). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py)
- [app/api/routers/source_checks.py](../../../app/api/routers/source_checks.py)
- [app/services/source_check_jobs.py](../../../app/services/source_check_jobs.py)

**Testdateien:**

- [tests/test_api_source_history.py](../../../tests/test_api_source_history.py)
- [tests/test_source_check_api.py](../../../tests/test_source_check_api.py)
- [tests/test_source_check_scope.py](../../../tests/test_source_check_scope.py)

</details>

**Konkrete Teilbelege:**

- [test_product_runs_keep_consensus_and_differences_without_source_work](../../../tests/test_source_check_scope.py#L20) — Produkt-Pipeline-Integration im Mock-LLM-Modus mit verbotenen Source-Hooks. **Datei**status vom 2026-10-02: passed=12.
  - [Zeile 41](../../../tests/test_source_check_scope.py#L41): ` assert result.get('consensus') or result.get('consensus_response') `
  - [Zeile 42](../../../tests/test_source_check_scope.py#L42): ` assert isinstance(result['differences_data']['agreement']['score'], int) `
  - [Zeile 43](../../../tests/test_source_check_scope.py#L43): ` assert result.get('source_verification') is None `
  - [Zeile 45](../../../tests/test_source_check_scope.py#L45): ` assert len(result['included_models']) == 2 `
  - [Zeile 46](../../../tests/test_source_check_scope.py#L46): ` assert 'sources' in result `
  - [Zeile 47](../../../tests/test_source_check_scope.py#L47): ` assert 'opinion_map' in result `
- [test_historic_api_source_pages_owner_cursor_revision_and_cache](../../../tests/test_api_source_history.py#L43) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=9.
  - [Zeile 52](../../../tests/test_api_source_history.py#L52): ` assert response.status_code == 200, response.text `
  - [Zeile 53](../../../tests/test_api_source_history.py#L53): ` assert set(map(str.strip, response.headers["cache-control"].split(","))) == { `
  - [Zeile 60](../../../tests/test_api_source_history.py#L60): ` assert len(found) == 9 `
  - [Zeile 61](../../../tests/test_api_source_history.py#L61): ` assert h.client.get(h.url).status_code == 401 `
  - [Zeile 62](../../../tests/test_api_source_history.py#L62): ` assert h.client.get(h.url, headers={"X-API-Key": h.other_key}).status_code == 404 `
  - [Zeile 64](../../../tests/test_api_source_history.py#L64): ` assert ( `

<a id="api-04"></a>

## API-04 · API-Publish und Publisher-Watch

Nur eigene erfolgreiche Runs werden publiziert; Indexing verlangt Scope und aktuelle Adminrolle. Publisher-Konfiguration und Watch-Capacity liefern stabile Skip-/Erfolgsverträge.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** API/Repository/Dienst separat mit Fakes. Aktuelle Providerpläne den Tests/Config entnehmen; veraltete DeepSeek-Ausschlussbeschreibung nicht als Soll verwenden.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py)
- [app/services/publisher_config.py](../../../app/services/publisher_config.py)
- [app/services/share_snapshots.py](../../../app/services/share_snapshots.py)

**Testdateien:**

- [tests/test_consensus_api.py](../../../tests/test_consensus_api.py)
- [tests/test_publisher_config.py](../../../tests/test_publisher_config.py)
- [tests/test_share_feature.py](../../../tests/test_share_feature.py)

</details>

**Konkrete Teilbelege:**

- [test_direct_indexing_requires_scope_admin_and_returns_indexed_state](../../../tests/test_consensus_api.py#L937) — Main-App-API und Runner mit Repository-/LLM-/Scheduler-Doubles; einzelne Quelltextverträge. **Datei**status vom 2026-10-02: passed=27.
  - [Zeile 974](../../../tests/test_consensus_api.py#L974): ` assert response.status_code == 200 `
  - [Zeile 975](../../../tests/test_consensus_api.py#L975): ` assert response.json()["indexing_status"] == "indexed" `
  - [Zeile 976](../../../tests/test_consensus_api.py#L976): ` assert response.json()["robots"] == "index, follow" `
  - [Zeile 977](../../../tests/test_consensus_api.py#L977): ` assert response.json()["in_sitemap"] is True `
  - [Zeile 985](../../../tests/test_consensus_api.py#L985): ` assert denied_scope.status_code == 403 `
  - [Zeile 994](../../../tests/test_consensus_api.py#L994): ` assert denied_admin.status_code == 403 `

<a id="llm-01"></a>

## LLM-01 · Registry, Credentials und Payload

Angebotene Modelle, Fähigkeiten, Reasoning und Suchoptionen folgen der Registry; nur der passende OpenRouter-Key wird verwendet, Own-Key hat keinen Developer-Fallback.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Konfiguration/Payloads des Snapshots; keine Live-Verfügbarkeits-, Preis- oder Capability-Bestätigung.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/core/config.py](../../../app/core/config.py)
- [app/core/openrouter_contract.py](../../../app/core/openrouter_contract.py)
- [app/services/llm/agent_model_catalog.json](../../../app/services/llm/agent_model_catalog.json)
- [app/services/llm/agent_model_metadata.py](../../../app/services/llm/agent_model_metadata.py)
- [app/services/llm/base.py](../../../app/services/llm/base.py)
- [app/services/llm/credentials.py](../../../app/services/llm/credentials.py)
- [app/services/llm/engines.py](../../../app/services/llm/engines.py)
- [app/services/llm/provider_transport.py](../../../app/services/llm/provider_transport.py)
- [app/services/llm/task_transport.py](../../../app/services/llm/task_transport.py)

**Testdateien:**

- [tests/test_agent_model_catalog.py](../../../tests/test_agent_model_catalog.py)
- [tests/test_ask_endpoints.py](../../../tests/test_ask_endpoints.py)
- [tests/test_deepseek_web_search.py](../../../tests/test_deepseek_web_search.py)
- [tests/test_model_configuration.py](../../../tests/test_model_configuration.py)
- [tests/test_model_configuration_regressions.py](../../../tests/test_model_configuration_regressions.py)
- [tests/test_provider_registry.py](../../../tests/test_provider_registry.py)
- [tests/test_reasoning_policy.py](../../../tests/test_reasoning_policy.py)

</details>

**Konkrete Teilbelege:**

- [test_own_keys_flag_without_openrouter_key_is_rejected](../../../tests/test_ask_endpoints.py#L79) — Router und Usage-Repository mit Auth-/Provider-Doubles. **Datei**status vom 2026-10-02: passed=14.
  - [Zeile 92](../../../tests/test_ask_endpoints.py#L92): ` assert response.status_code == 400 `
  - [Zeile 93](../../../tests/test_ask_endpoints.py#L93): ` assert response.json()["detail"] == "Missing user OpenRouter API key." `

<a id="llm-02"></a>

## LLM-02 · Providerstream, Fehler und Ressourcen

Timeouts sind begrenzt, HTTP-200-Fehlerbodies werden als Fehler erkannt, Ressourcen schließen bei normalem Ende und Cancel. Kein versteckter kostenpflichtiger SDK-Retry.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** HTTPX-/SSE-Doubles plus reale Loopback-TCP-/TLS-Abbrüche und SDKdeadline; kein Provider-/Proxyverfügbarkeitsnachweis.

**Befunde:** [G-032](gaps.md#g-032). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/llm/agent_client.py](../../../app/services/llm/agent_client.py)
- [app/services/llm/mock_llm.py](../../../app/services/llm/mock_llm.py)
- [app/services/llm/provider_runtime.py](../../../app/services/llm/provider_runtime.py)
- [app/services/llm/streaming.py](../../../app/services/llm/streaming.py)

**Testdateien:**

- [tests/test_agent_capacity.py](../../../tests/test_agent_capacity.py)
- [tests/test_agent_reasoning_continuation.py](../../../tests/test_agent_reasoning_continuation.py)
- [tests/test_agent_reliability.py](../../../tests/test_agent_reliability.py)
- [tests/test_benchmark_protocol.py](../../../tests/test_benchmark_protocol.py)
- [tests/test_benchmark_transport.py](../../../tests/test_benchmark_transport.py)
- [tests/test_local_transport.py](../../../tests/test_local_transport.py)
- [tests/test_provider_response_errors.py](../../../tests/test_provider_response_errors.py)
- [tests/test_provider_timeouts.py](../../../tests/test_provider_timeouts.py)
- [tests/test_stream_backpressure.py](../../../tests/test_stream_backpressure.py)
- [tests/test_streaming.py](../../../tests/test_streaming.py)

</details>

**Konkrete Teilbelege:**

- [test_body_error_preserves_status_without_content_or_retry](../../../tests/test_provider_response_errors.py#L55) — Adapter/Fan-out mit HTTP-Response-Doubles. **Datei**status vom 2026-10-02: passed=38.
  - [Zeile 64](../../../tests/test_provider_response_errors.py#L64): ` assert result["error_code"] == expected `
  - [Zeile 65](../../../tests/test_provider_response_errors.py#L65): ` assert result["text"] == "" `
  - [Zeile 66](../../../tests/test_provider_response_errors.py#L66): ` assert result["sources"] == [] `
  - [Zeile 67](../../../tests/test_provider_response_errors.py#L67): ` assert f"_ProviderResponseError:{code}" in caplog.text `
  - [Zeile 68](../../../tests/test_provider_response_errors.py#L68): ` assert secret not in caplog.text + json.dumps(result) `
- [test_protocol_failures_are_not_successful_abstentions](../../../tests/test_benchmark_protocol.py#L46) — Transport-, Record-, Resume- und Statistikpipeline mit HTTP-Response-Double. **Datei**status vom 2026-10-02: passed=15.
  - [Zeile 49](../../../tests/test_benchmark_protocol.py#L49): ` assert response.closed `
  - [Zeile 50](../../../tests/test_benchmark_protocol.py#L50): ` assert outcome["error_code"] == code `
  - [Zeile 51](../../../tests/test_benchmark_protocol.py#L51): ` assert outcome["error"] `
  - [Zeile 52](../../../tests/test_benchmark_protocol.py#L52): ` assert outcome["raw"] is None `
  - [Zeile 54](../../../tests/test_benchmark_protocol.py#L54): ` assert row["abstain"] is False `
  - [Zeile 55](../../../tests/test_benchmark_protocol.py#L55): ` assert row["extracted_letter"] is None `
- [test_cancellation_closes_real_idle_provider_socket_without_retry](../../../tests/test_local_transport.py#L64) — Echte lokale TCP-/TLS-Server durch HTTP-/SDK-Adapter. **Datei**status vom 2026-10-02: passed=10.
  - [Zeile 85](../../../tests/test_local_transport.py#L85): ` assert state.seen.wait(3), 'request never reached local server' `
  - [Zeile 88](../../../tests/test_local_transport.py#L88): ` assert not thread.is_alive(), 'producer survived cancellation' `
  - [Zeile 89](../../../tests/test_local_transport.py#L89): ` assert len(errors) == 1 and isinstance(errors[0], runtime.ProviderCancelled) `
  - [Zeile 90](../../../tests/test_local_transport.py#L90): ` assert state.closed.wait(3), 'server socket stayed open' `
  - [Zeile 91](../../../tests/test_local_transport.py#L91): ` assert len(state.requests) == 1 `
- [test_all_model_families_use_one_openrouter_transport](../../../tests/test_benchmark_transport.py#L53) — Benchmarktransport mit HTTP-Doubles. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 59](../../../tests/test_benchmark_transport.py#L59): ` assert result["error"] is None `
  - [Zeile 60](../../../tests/test_benchmark_transport.py#L60): ` assert result["text"] == "The [S1] answer is (C)." `
  - [Zeile 61](../../../tests/test_benchmark_transport.py#L61): ` assert result["usage"] == {"prompt": 100, "completion": 20, "total": 120} `
  - [Zeile 62](../../../tests/test_benchmark_transport.py#L62): ` assert result["raw"] is OPENROUTER_RESPONSE `
  - [Zeile 63](../../../tests/test_benchmark_transport.py#L63): ` assert captured["url"] == OPENROUTER_CHAT_COMPLETIONS_URL `
  - [Zeile 64](../../../tests/test_benchmark_transport.py#L64): ` assert captured["params"] is None `
- [test_disconnect_preserves_generator_exit_when_deleted_account_blocks_cleanup](../../../tests/test_agent_capacity.py#L16) — Agentkapazität, Routerstream und lokale Worker mit kontrolliertem Loop. **Datei**status vom 2026-10-02: passed=7.
  - [Zeile 35](../../../tests/test_agent_capacity.py#L35): ` assert "event: accepted" in next(stream) `
  - [Zeile 36](../../../tests/test_agent_capacity.py#L36): ` assert "event: delta" in next(stream) `
  - [Zeile 38](../../../tests/test_agent_capacity.py#L38): ` assert closed == [True] and not calls `
  - [Zeile 39](../../../tests/test_agent_capacity.py#L39): ` assert "Agent completion failed" not in caplog.text `
  - [Zeile 40](../../../tests/test_agent_capacity.py#L40): ` assert "Agent stream cleanup unavailable" in caplog.text `
  - [Zeile 41](../../../tests/test_agent_capacity.py#L41): ` assert list(stream) == [] `

<a id="cons-01"></a>

## CONS-01 · Neutrale Pipeline und Teilergebnisse

Fan-out sammelt gültige Antworten, synthetisiert Consensus und analysiert Unterschiede; gescheiterte Einzelmodelle werden ehrlich behandelt. Watch/Topic/API verwenden denselben neutralen Kern.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Feste Engine-/Judge-Ergebnisse prüfen Orchestrierung, keine fachliche Überlegenheit der Synthese.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/chat.py](../../../app/api/routers/chat.py)
- [app/services/consensus_pipeline.py](../../../app/services/consensus_pipeline.py)
- [app/services/llm/consensus_engine.py](../../../app/services/llm/consensus_engine.py)

**Testdateien:**

- [tests/test_consensus_answer_contract.py](../../../tests/test_consensus_answer_contract.py)
- [tests/test_consensus_chat_history.py](../../../tests/test_consensus_chat_history.py)
- [tests/test_consensus_engine.py](../../../tests/test_consensus_engine.py)
- [tests/test_consensus_input_caps.py](../../../tests/test_consensus_input_caps.py)
- [tests/test_phase6_architecture.py](../../../tests/test_phase6_architecture.py)

</details>

**Konkrete Teilbelege:**

- [test_neutral_pipeline_can_select_the_first_successful_provider_as_engine](../../../tests/test_phase6_architecture.py#L76) — Statische Architektur-, Routing- und Assetverträge. **Datei**status vom 2026-10-02: passed=8.
  - [Zeile 83](../../../tests/test_phase6_architecture.py#L83): ` assert args[3] == "Mistral" `
  - [Zeile 102](../../../tests/test_phase6_architecture.py#L102): ` assert [item["provider"] for item in result["model_answers"]] == ["Mistral", "Gemini"] `

<a id="cons-02"></a>

## CONS-02 · Strukturierte Differences und Agreement

Parser/Scorer akzeptieren nur zulässige Modelle, Claims, Anchors und bounded Werte; fehlende Analyse bleibt unbewertet statt Nullbeweis. Agreement und Claim-Coverage bleiben verschiedene Aussagen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Synthetische JSON-/Textantworten; Validierung sichert Form/Provenienz, nicht Wahrheit oder Kalibrierung.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/llm/consensus_engine.py](../../../app/services/llm/consensus_engine.py)
- [app/services/llm/consensus_parsing.py](../../../app/services/llm/consensus_parsing.py)
- [app/services/llm/consensus_scoring.py](../../../app/services/llm/consensus_scoring.py)
- [app/services/llm/coverage_judge.py](../../../app/services/llm/coverage_judge.py)

**Testdateien:**

- [tests/test_analysis_quality_budget.py](../../../tests/test_analysis_quality_budget.py)
- [tests/test_consensus_answer_contract.py](../../../tests/test_consensus_answer_contract.py)
- [tests/test_consensus_engine.py](../../../tests/test_consensus_engine.py)
- [tests/test_coverage_judge.py](../../../tests/test_coverage_judge.py)
- [tests/test_differences_schema.py](../../../tests/test_differences_schema.py)

</details>

**Konkrete Teilbelege:**

- [test_empty_or_sparse_evidence_does_not_create_a_numeric_score](../../../tests/test_analysis_quality_budget.py#L28) — Scoring-/Snapshot-/Budgetlogik und HTTPX-MockTransport. **Datei**status vom 2026-10-02: passed=14.
  - [Zeile 31](../../../tests/test_analysis_quality_budget.py#L31): ` assert result["score"] is None `
  - [Zeile 32](../../../tests/test_analysis_quality_budget.py#L32): ` assert result["level"] == "insufficient" `
  - [Zeile 33](../../../tests/test_analysis_quality_budget.py#L33): ` assert result["coverage_status"] == "insufficient" `
  - [Zeile 34](../../../tests/test_analysis_quality_budget.py#L34): ` assert score([claim()] + [claim(()) for _ in range(19)])["coverage_percent"] == 5 `

<a id="cons-03"></a>

## CONS-03 · Quellenkatalog und Zitatprovenienz

Quellen werden normalisiert, nummeriert und an den richtigen Run/Antworttext gebunden; unbekannte IDs und falsche Zitatzuordnung werden nicht als verifiziert dargestellt.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Formaler Parser/DOM-Vertrag; keine externe Quellenwahrheit.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/llm/citations.py](../../../app/services/llm/citations.py)
- [app/services/llm/consensus_citations.py](../../../app/services/llm/consensus_citations.py)
- [app/services/source_catalog.py](../../../app/services/source_catalog.py)
- [static/js/sources.js](../../../static/js/sources.js)

**Testdateien:**

- [tests/e2e/test_agent_comparison_frontend.py](../../../tests/e2e/test_agent_comparison_frontend.py)
- [tests/js/agent-citations.test.mjs](../../../tests/js/agent-citations.test.mjs)
- [tests/js/claim-mark-joins.test.mjs](../../../tests/js/claim-mark-joins.test.mjs)
- [tests/js/source-catalog-refs.test.mjs](../../../tests/js/source-catalog-refs.test.mjs)
- [tests/js/source-url-identity.test.mjs](../../../tests/js/source-url-identity.test.mjs)
- [tests/test_citations.py](../../../tests/test_citations.py)
- [tests/test_consensus_citations.py](../../../tests/test_consensus_citations.py)
- [tests/test_source_catalog.py](../../../tests/test_source_catalog.py)

</details>

**Konkrete Teilbelege:**

- [resolves sparse IDs by identity and leaves missing citations unresolved](../../../tests/js/source-catalog-refs.test.mjs#L14) — JavaScript-Modultest mit jsdom. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 18](../../../tests/js/source-catalog-refs.test.mjs#L18): ` expect(refs.map(item => item.src?.url || null)).toEqual([null, 'https://two.example', 'https://seven.example']); `
- [test_comparison_selection_blocks_send_before_losing_draft](../../../tests/e2e/test_agent_comparison_frontend.py#L13) — Chromium mit echten Vergleichs-/Drawerkomponenten. **Datei**status vom 2026-10-02: passed=15.
  - [Zeile 25](../../../tests/e2e/test_agent_comparison_frontend.py#L25): ` expect(page.locator('#sendButton')).to_be_enabled() `
  - [Zeile 27](../../../tests/e2e/test_agent_comparison_frontend.py#L27): ` expect(page.locator('.consensus-model-inline')).to_be_hidden() `
  - [Zeile 33](../../../tests/e2e/test_agent_comparison_frontend.py#L33): ` expect(page.locator('#sendButton')).to_be_disabled() `
  - [Zeile 35](../../../tests/e2e/test_agent_comparison_frontend.py#L35): ` expect(page.locator('#sendButton')).to_be_disabled() `
  - [Zeile 37](../../../tests/e2e/test_agent_comparison_frontend.py#L37): ` expect(page.locator('#agentComposerNotice')).to_be_visible() `
  - [Zeile 38](../../../tests/e2e/test_agent_comparison_frontend.py#L38): ` expect(page.locator('#agentComposerMessage')).to_contain_text('comparison models') `

<a id="cons-04"></a>

## CONS-04 · Resolve als eigener Lauf

Resolve verwendet vorhandene Konflikte/Kontext, bleibt tier-/ownergebunden und nutzt eigenen Usage-Key. Ein abgeschlossener Resolve wird korrekt gespeichert und angezeigt.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Backend lokal; Browseraktionen teils nur Fixture-UI. Durchgehender Resolve→Persistenz-Vertrag nicht ausgeführt.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/chat.py](../../../app/api/routers/chat.py)
- [app/services/llm/resolve_engine.py](../../../app/services/llm/resolve_engine.py)
- [static/js/consensus-actions.js](../../../static/js/consensus-actions.js)

**Testdateien:**

- [tests/e2e/test_inspector_polish.py](../../../tests/e2e/test_inspector_polish.py)
- [tests/e2e/test_smoke.py](../../../tests/e2e/test_smoke.py)
- [tests/test_resolve_round.py](../../../tests/test_resolve_round.py)

</details>

**Konkrete Teilbelege:**

- [test_resolve_does_not_persist_after_the_bookmark_revision_advanced](../../../tests/test_resolve_round.py#L394) — Resolve-Unit-/Routertests mit Engine-/DB-Doubles. **Datei**status vom 2026-10-02: passed=23.
  - [Zeile 432](../../../tests/test_resolve_round.py#L432): ` assert persisted is False `
  - [Zeile 433](../../../tests/test_resolve_round.py#L433): ` assert "resolution" not in bookmark_ref.data["responses"]["differences_data"]["differences"][0] `

<a id="cons-05"></a>

## CONS-05 · Finalisierung, Replay und Browser-Recovery

Vor dem abschließenden Ergebnis werden angeforderte Turn-/Bookmarkwrites versucht; Antworterfolg und Persistenzerfolg bleiben getrennt. Ein Speicherfehler erhält die erfolgreiche Antwort und wird über chat_persisted/bookmark_persisted sowie den Turnstatus kenntlich. Completed-Replay ruft weder Engine noch Usage erneut auf. Ein unklarer Streamabbruch wird am Turnstatus abgeglichen, ein Analysefehler vernichtet keine bereits gelieferte Antwort.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante. Zusätzlich belegt test_completion_storage_failure_never_replaces_successful_consensus in tests/test_consensus_chat_history.py für JSON und SSE: Antwort bleibt erhalten, chat_persisted=false und chat_turn_state=pending. Ein terminales final-Event allein garantiert keinen DB-Commit.

**Testgrenze:** SSE-Schnipsel/TestClient/Fake-Requests; keine durchgehende Socket→Server→DB→Reload-Prüfung.

**Befunde:** [G-030](gaps.md#g-030). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/chat.py](../../../app/api/routers/chat.py)
- [static/js/chat-session.js](../../../static/js/chat-session.js)
- [static/js/consensus-lifecycle.js](../../../static/js/consensus-lifecycle.js)
- [static/js/consensus-run.js](../../../static/js/consensus-run.js)
- [static/js/query-send.js](../../../static/js/query-send.js)

**Testdateien:**

- [tests/e2e/test_agreement_verdict.py](../../../tests/e2e/test_agreement_verdict.py)
- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/e2e/test_run_cancel_and_progress.py](../../../tests/e2e/test_run_cancel_and_progress.py)
- [tests/js/bookmark-pending-state.test.mjs](../../../tests/js/bookmark-pending-state.test.mjs)
- [tests/js/consensus-recovery.test.mjs](../../../tests/js/consensus-recovery.test.mjs)
- [tests/js/judge-stream-events.test.mjs](../../../tests/js/judge-stream-events.test.mjs)
- [tests/js/sse-completion.test.mjs](../../../tests/js/sse-completion.test.mjs)
- [tests/test_consensus_chat_history.py](../../../tests/test_consensus_chat_history.py)
- [tests/test_consensus_progress_ui.py](../../../tests/test_consensus_progress_ui.py)

</details>

**Konkrete Teilbelege:**

- [recovers a committed turn through GET without another generation, vote or save](../../../tests/js/consensus-recovery.test.mjs#L40) — JavaScript-Modulintegration mit Request-/Stream-Doubles. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 43](../../../tests/js/consensus-recovery.test.mjs#L43): ` expect(context.status, context.consensus.error?.message).toBe('succeeded'); `
  - [Zeile 44](../../../tests/js/consensus-recovery.test.mjs#L44): ` expect(context.consensus.text).toBe('Stored answer'); `
  - [Zeile 45](../../../tests/js/consensus-recovery.test.mjs#L45): ` expect(context.consensus.resultId).toBe('stored-result'); `
  - [Zeile 46](../../../tests/js/consensus-recovery.test.mjs#L46): ` expect(context.chatSession.handleConsensusResult).toHaveBeenCalledWith(expect.objectContaining({ chatTurnState: 'completed' })); `
  - [Zeile 47](../../../tests/js/consensus-recovery.test.mjs#L47): ` expect(window.streamSSERequest).toHaveBeenCalledOnce(); `
  - [Zeile 48](../../../tests/js/consensus-recovery.test.mjs#L48): `` expect(window.fetch).toHaveBeenCalledWith(`/chats/${'a'.repeat(32)}/turns/${'b'.repeat(32)}`, expect.objectContaining({ cache: 'no-store', headers: { Authorization: 'Bearer token' } })); ``
- [test_consensus_persists_requested_bookmark_before_successful_final_event](../../../tests/test_consensus_chat_history.py#L251) — Router/SSE-Verträge mit RecordingStore und Engine-Doubles. **Datei**status vom 2026-10-02: passed=52.
  - [Zeile 306](../../../tests/test_consensus_chat_history.py#L306): ` assert response.status_code == 200 `
  - [Zeile 307](../../../tests/test_consensus_chat_history.py#L307): ` assert body["bookmark_persisted"] is True `
  - [Zeile 308](../../../tests/test_consensus_chat_history.py#L308): ` assert body["bookmark_meta"]["id"] == "stable_bookmark" `
  - [Zeile 309](../../../tests/test_consensus_chat_history.py#L309): ` assert len(writes) == 1 `
  - [Zeile 311](../../../tests/test_consensus_chat_history.py#L311): ` assert uid == UID `
  - [Zeile 312](../../../tests/test_consensus_chat_history.py#L312): ` assert data["chatId"] == CHAT_ID `
- [test_low_score_without_contradictions_is_not_green_or_high](../../../tests/e2e/test_agreement_verdict.py#L4) — Chromium mit echtem App-Frontend und direkt aufgerufenem Verdict-Renderer. **Datei**status vom 2026-10-02: passed=1.
  - [Zeile 23](../../../tests/e2e/test_agreement_verdict.py#L23): ` expect(verdict).to_have_class("consensus-verdict is-alert") `
  - [Zeile 24](../../../tests/e2e/test_agreement_verdict.py#L24): ` expect(verdict.locator(".verdict-headline")).to_have_text("Low agreement") `
  - [Zeile 25](../../../tests/e2e/test_agreement_verdict.py#L25): ` expect(verdict.locator(".verdict-detail")).to_contain_text("no contradictions") `
  - [Zeile 33](../../../tests/e2e/test_agreement_verdict.py#L33): ` assert palette["--verdict-ring"] == palette["--dispute"] `
  - [Zeile 34](../../../tests/e2e/test_agreement_verdict.py#L34): ` assert palette["--verdict-ring"] != palette["--agree"] `
- [test_send_button_stays_cancelable_until_consensus_is_done](../../../tests/e2e/test_run_cancel_and_progress.py#L47) — Chromium mit echten Registry- und DOMereignissen. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 78](../../../tests/e2e/test_run_cancel_and_progress.py#L78): ` app_page.wait_for_function( `
  - [Zeile 86](../../../tests/e2e/test_run_cancel_and_progress.py#L86): ` assert any(sample["status"] == "pending" for sample in samples), samples `
  - [Zeile 87](../../../tests/e2e/test_run_cancel_and_progress.py#L87): ` assert any(sample["status"] in {"streaming", "differences"} for sample in samples), samples `
  - [Zeile 88](../../../tests/e2e/test_run_cancel_and_progress.py#L88): ` assert all(sample["cancelable"] for sample in samples), samples `
  - [Zeile 89](../../../tests/e2e/test_run_cancel_and_progress.py#L89): ` expect(app_page.locator("#sendButton")).not_to_have_class( `
- [test_j01_saved_consensus_reload_followup_keeps_native_identity_and_context](../../../tests/e2e/test_persisted_journeys.py#L150) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 155](../../../tests/e2e/test_persisted_journeys.py#L155): ` assert saved.ok, saved.text() `
  - [Zeile 156](../../../tests/e2e/test_persisted_journeys.py#L156): ` assert j.request('GET', '/bookmarks/' + first['bookmark'], uid='journey-'+'f'*32).status == 404 `
  - [Zeile 158](../../../tests/e2e/test_persisted_journeys.py#L158): ` j.page.wait_for_function('() => typeof window.openBookmark === "function" && window.__consensioAuthState?.known') `
  - [Zeile 160](../../../tests/e2e/test_persisted_journeys.py#L160): ` expect(j.page.locator('#consensusResponse')).to_contain_text('Mock consensus', timeout=15000) `
  - [Zeile 161](../../../tests/e2e/test_persisted_journeys.py#L161): ` expect(j.page.locator('#questionInput')).to_have_attribute('placeholder', 'Ask a follow-up question') `
  - [Zeile 163](../../../tests/e2e/test_persisted_journeys.py#L163): ` assert second['chat'] == first['chat'] and second['turn'] != first['turn'] `
- [stays disabled until both the run and its persistence write finish](../../../tests/js/bookmark-pending-state.test.mjs#L45) — Originale Bookmarkhelfer und Markup im jsdom mit kontrolliertem Speichern. **Datei**status vom 2026-10-02: passed=5.
  - [Zeile 54](../../../tests/js/bookmark-pending-state.test.mjs#L54): ` expect(session.pending).not.toBeNull(); `
  - [Zeile 55](../../../tests/js/bookmark-pending-state.test.mjs#L55): ` expect(ready).toEqual([]); `
  - [Zeile 59](../../../tests/js/bookmark-pending-state.test.mjs#L59): ` expect(session.pending).toBeNull(); `
  - [Zeile 60](../../../tests/js/bookmark-pending-state.test.mjs#L60): ` expect(ready).toEqual([{ id: "pending_id", title: "How does this work?" }]); `
  - [Zeile 61](../../../tests/js/bookmark-pending-state.test.mjs#L61): ` expect(rendered.length).toBeGreaterThanOrEqual(2); `
- [test_consensus_result_precedes_model_answers_and_run_block_is_loaded](../../../tests/test_consensus_progress_ui.py#L12) — Statische DOM-/CSS-/JS-Verträge. **Datei**status vom 2026-10-02: passed=18.
  - [Zeile 15](../../../tests/test_consensus_progress_ui.py#L15): ` assert template.index('class="consensus-section"') < template.index( `
  - [Zeile 18](../../../tests/test_consensus_progress_ui.py#L18): ` assert 'id="consensusRun"' in template `
  - [Zeile 19](../../../tests/test_consensus_progress_ui.py#L19): ` assert 'id="runStatus"' in template `
  - [Zeile 20](../../../tests/test_consensus_progress_ui.py#L20): ` assert loads_before("agent-mode.js", "consensus-progress.js") `
  - [Zeile 21](../../../tests/test_consensus_progress_ui.py#L21): ` assert loads_before("consensus-progress.js", "consensus-lifecycle.js") `

<a id="agent-01"></a>

## AGENT-01 · Admission und Token-/Kostenledger

Modellaufrufe benötigen atomare Admission; Tokens, Kosten, Reserven und unbekannte Messungen bleiben getrennt. Settlement pro tatsächlichem Schritt ist idempotent, UTC-/Reset-Versionen ordnen Budgetstände.

**Anforderungsbasis:** [docs/agent-accounting-audit.md](../../agent-accounting-audit.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Reale Emulatorbelege für ausgewählte Rennen vorhanden; kein vollständiger produktiver Mehrprozess-/Providerablauf.

**Befunde:** [G-037](gaps.md#g-037). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/agent_budget_config.py](../../../app/services/agent_budget_config.py)
- [app/services/agent_costs.py](../../../app/services/agent_costs.py)
- [app/services/agent_provider_limits.py](../../../app/services/agent_provider_limits.py)
- [app/services/agent_quota.py](../../../app/services/agent_quota.py)
- [app/services/agent_runs.py](../../../app/services/agent_runs.py)
- [app/services/agent_sessions.py](../../../app/services/agent_sessions.py)
- [app/services/agent_tokens.py](../../../app/services/agent_tokens.py)

**Testdateien:**

- [tests/e2e/test_agent_transactions.py](../../../tests/e2e/test_agent_transactions.py)
- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/e2e/test_usage_transactions.py](../../../tests/e2e/test_usage_transactions.py)
- [tests/test_agent_accounting_audit.py](../../../tests/test_agent_accounting_audit.py)
- [tests/test_agent_admission.py](../../../tests/test_agent_admission.py)
- [tests/test_agent_budget_config.py](../../../tests/test_agent_budget_config.py)
- [tests/test_agent_capacity.py](../../../tests/test_agent_capacity.py)
- [tests/test_agent_quota_recovery.py](../../../tests/test_agent_quota_recovery.py)
- [tests/test_agent_root_compaction.py](../../../tests/test_agent_root_compaction.py)

</details>

**Konkrete Teilbelege:**

- [test_final_usage_replaces_cumulative_values_and_releases_reservation](../../../tests/test_agent_accounting_audit.py#L85) — Abrechnung über realen Agent-Loop und geskripteten Transport. **Datei**status vom 2026-10-02: passed=58.
  - [Zeile 91](../../../tests/test_agent_accounting_audit.py#L91): ` assert budget['used'] == 130 and budget['reserved'] == budget['unknown'] == 0 `
  - [Zeile 92](../../../tests/test_agent_accounting_audit.py#L92): ` assert loop.completion.usage['complete'] `
- [test_native_identical_key_and_booking_are_exactly_once](../../../tests/e2e/test_usage_transactions.py#L26) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 32](../../../tests/e2e/test_usage_transactions.py#L32): ` assert sorted(result.idempotent for result in results) == [False, True] `
  - [Zeile 39](../../../tests/e2e/test_usage_transactions.py#L39): ` assert ledger["used"] == 25 and ledger["pipeline_estimated"] == 5 and ledger["pipeline_holds"] == {} `
  - [Zeile 40](../../../tests/e2e/test_usage_transactions.py#L40): ` assert not agent_quota.quota_ref(db, other, admission(now).period).get().exists `
- [test_j02_stop_reload_recover_preserves_partial_and_charges_only_started_step](../../../tests/e2e/test_persisted_journeys.py#L186) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 196](../../../tests/e2e/test_persisted_journeys.py#L196): ` expect(j.page.locator('#agentAnswerBody')).to_contain_text('Saved partial answer', timeout=30000) `
  - [Zeile 199](../../../tests/e2e/test_persisted_journeys.py#L199): ` j.page.wait_for_function('() => Date.now() - App.runRegistry.visible().startedAt > 800') `
  - [Zeile 201](../../../tests/e2e/test_persisted_journeys.py#L201): ` j.page.wait_for_function('() => App.runRegistry.visible()?.status === "canceled"') `
  - [Zeile 205](../../../tests/e2e/test_persisted_journeys.py#L205): ` assert len(state['calls']) == 8  # orchestrator + six comparison providers + partial synthesis `
  - [Zeile 208](../../../tests/e2e/test_persisted_journeys.py#L208): ` assert turn['data']['status'] == 'failed' `
  - [Zeile 209](../../../tests/e2e/test_persisted_journeys.py#L209): ` assert turn['data']['agent_failure']['code'] == 'cancelled' `
- [test_disconnect_preserves_generator_exit_when_deleted_account_blocks_cleanup](../../../tests/test_agent_capacity.py#L16) — Agentkapazität, Routerstream und lokale Worker mit kontrolliertem Loop. **Datei**status vom 2026-10-02: passed=7.
  - [Zeile 35](../../../tests/test_agent_capacity.py#L35): ` assert "event: accepted" in next(stream) `
  - [Zeile 36](../../../tests/test_agent_capacity.py#L36): ` assert "event: delta" in next(stream) `
  - [Zeile 38](../../../tests/test_agent_capacity.py#L38): ` assert closed == [True] and not calls `
  - [Zeile 39](../../../tests/test_agent_capacity.py#L39): ` assert "Agent completion failed" not in caplog.text `
  - [Zeile 40](../../../tests/test_agent_capacity.py#L40): ` assert "Agent stream cleanup unavailable" in caplog.text `
  - [Zeile 41](../../../tests/test_agent_capacity.py#L41): ` assert list(stream) == [] `

<a id="agent-02"></a>

## AGENT-02 · Chatpolicy und Legacy-Toolloop

Aktive Chats verwenden das Kontotokenbudget, keine alten Gesamtlauf-/Calllimits. Parallele Vergleiche unterstützen Quorum oder alle Modelle, Tiefe und Antwortbeginn; eine Suchkonfiguration gilt für alle Modelle, Judges suchen nicht. Unfertige Vergleichstexte bleiben markiert, Reasoningsignaturen korrekt fortsetzbar.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Gesteuerte Tool-/Providerantworten; richtige Aufgabenverteilung/Urteilsqualität ist damit nicht gemessen.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/agent.py](../../../app/api/routers/agent.py)
- [app/services/agent_comparison.py](../../../app/services/agent_comparison.py)
- [app/services/agent_contradictions.py](../../../app/services/agent_contradictions.py)
- [app/services/agent_loop.py](../../../app/services/agent_loop.py)
- [app/services/agent_policy.py](../../../app/services/agent_policy.py)
- [app/services/agent_tools.py](../../../app/services/agent_tools.py)
- [app/services/llm/agent_client.py](../../../app/services/llm/agent_client.py)

**Testdateien:**

- [tests/test_agent_comparison.py](../../../tests/test_agent_comparison.py)
- [tests/test_agent_continuation.py](../../../tests/test_agent_continuation.py)
- [tests/test_agent_contradictions.py](../../../tests/test_agent_contradictions.py)
- [tests/test_agent_loop.py](../../../tests/test_agent_loop.py)
- [tests/test_agent_reasoning_continuation.py](../../../tests/test_agent_reasoning_continuation.py)
- [tests/test_agent_reliability.py](../../../tests/test_agent_reliability.py)
- [tests/test_agent_search.py](../../../tests/test_agent_search.py)
- [tests/test_agent_synthesis_context.py](../../../tests/test_agent_synthesis_context.py)

</details>

**Konkrete Teilbelege:**

- [test_more_than_one_hundred_steps_and_seventeen_minutes_complete_with_live_lease](../../../tests/test_agent_continuation.py#L45) — Langlauf-/Recovery-Verträge mit Fake-Uhr, Store und Providern. **Datei**status vom 2026-10-02: passed=13.
  - [Zeile 65](../../../tests/test_agent_continuation.py#L65): ` assert loop.budget.deadline == float("inf") `
  - [Zeile 69](../../../tests/test_agent_continuation.py#L69): ` assert saved["status"] == "completed" and saved["consensus"] == "Finished after many rounds." `
  - [Zeile 70](../../../tests/test_agent_continuation.py#L70): ` assert timer.stamp - started == timedelta(minutes=17) `
  - [Zeile 71](../../../tests/test_agent_continuation.py#L71): ` assert root["step_states"]["completion:101"] == "succeeded" `
  - [Zeile 72](../../../tests/test_agent_continuation.py#L72): ` assert root["policy"]["seconds"] is None and root["policy"]["max_calls"] is None `
  - [Zeile 73](../../../tests/test_agent_continuation.py#L73): ` assert loop.tools_used == 101 and loop.budget.calls == 102 `
- [test_consensus_and_legacy_analysis_budgets_remain_bounded](../../../tests/test_agent_continuation.py#L154) — Langlauf-/Recovery-Verträge mit Fake-Uhr, Store und Providern. **Datei**status vom 2026-10-02: passed=13.
  - [Zeile 156](../../../tests/test_agent_continuation.py#L156): ` with pytest.raises(AnalysisBudgetExceeded, match="deadline"): `
  - [Zeile 158](../../../tests/test_agent_continuation.py#L158): ` assert not AgentPolicy.from_config(defaults()).account_budget_only `

<a id="agent-03"></a>

## AGENT-03 · Delegierte Sitzungen und Kommunikation

Orchestrator und Worker besitzen eigene Identitäten/Verläufe, geordnete deduplizierte Nachrichten und gemeinsames Budget. Stop und verspätete Workerergebnisse dürfen keine neuen bezahlten Schritte oder falschen Turnwrites verursachen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Lokale Threads und Emulatorbudget, Browser-API ersetzt. Historische Delegation-Spezifikation ist teilweise überholt.

**Befunde:** [G-039](gaps.md#g-039). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/agent_delegation.py](../../../app/services/agent_delegation.py)
- [app/services/agent_delegation_config.py](../../../app/services/agent_delegation_config.py)
- [app/services/agent_sessions.py](../../../app/services/agent_sessions.py)
- [static/js/agent-delegation.js](../../../static/js/agent-delegation.js)

**Testdateien:**

- [tests/e2e/test_agent_delegation_frontend.py](../../../tests/e2e/test_agent_delegation_frontend.py)
- [tests/e2e/test_agent_transactions.py](../../../tests/e2e/test_agent_transactions.py)
- [tests/js/agent-delegation.test.mjs](../../../tests/js/agent-delegation.test.mjs)
- [tests/test_agent_delegation.py](../../../tests/test_agent_delegation.py)
- [tests/test_agent_reliability.py](../../../tests/test_agent_reliability.py)
- [tests/test_agent_root_compaction.py](../../../tests/test_agent_root_compaction.py)

</details>

**Konkrete Teilbelege:**

- [test_parallel_question_answer_rework_and_review_persist_same_session_and_total_costs](../../../tests/test_agent_delegation.py#L102) — Echte Workerthreads/Mailboxen mit Store- und Provider-Doubles. **Datei**status vom 2026-10-02: passed=16.
  - [Zeile 106](../../../tests/test_agent_delegation.py#L106): ` assert loop.completion.text == "Product 6; sum 5." `
  - [Zeile 107](../../../tests/test_agent_delegation.py#L107): ` assert len(loop.workers) == 2 `
  - [Zeile 108](../../../tests/test_agent_delegation.py#L108): ` assert script.actions.count("start_agent") == 2 and script.actions.count("send_agent") == 2 `
  - [Zeile 109](../../../tests/test_agent_delegation.py#L109): ` assert all(w.reviewed and not w.thread.is_alive() for w in loop.workers.values()) `
  - [Zeile 113](../../../tests/test_agent_delegation.py#L113): ` assert [m["kind"] for m in messages] == ["question", "answer", "result", "rework", "result", "review"] `
  - [Zeile 114](../../../tests/test_agent_delegation.py#L114): ` assert [m["text"] for m in messages if m["kind"] == "result"] == ["5", "6"] `

<a id="agent-04"></a>

## AGENT-04 · Agent-Recovery und Eigentümerbindung

Run-/Turn-/Agentdetails sind ownergebunden; recover_only startet nie Modelle. Abgelaufene Leases werden ohne Doppelverbrauch beendet, bestätigte Antworten und Usage bleiben lesbar.

**Anforderungsbasis:** [docs/agent-reliability-audit-2026-09-20.md](../../agent-reliability-audit-2026-09-20.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Echte main-Detail-/Stopadapter inklusive Zustand, Bindung, Pagination und no-store; Prozesscrash über persistierte Zustände kontrolliert, Providertransport separat lokal geprüft.

**Befunde:** [G-030](gaps.md#g-030), [G-039](gaps.md#g-039). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/agent.py](../../../app/api/routers/agent.py)
- [app/services/agent_runs.py](../../../app/services/agent_runs.py)
- [app/services/agent_runtime.py](../../../app/services/agent_runtime.py)
- [app/services/agent_sessions.py](../../../app/services/agent_sessions.py)

**Testdateien:**

- [tests/e2e/test_agent_chat_frontend.py](../../../tests/e2e/test_agent_chat_frontend.py)
- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/e2e/test_run_cancel_and_progress.py](../../../tests/e2e/test_run_cancel_and_progress.py)
- [tests/test_agent_answer_lifecycle.py](../../../tests/test_agent_answer_lifecycle.py)
- [tests/test_agent_capacity.py](../../../tests/test_agent_capacity.py)
- [tests/test_agent_chat_integrity.py](../../../tests/test_agent_chat_integrity.py)
- [tests/test_agent_http_contract.py](../../../tests/test_agent_http_contract.py)
- [tests/test_agent_quota_recovery.py](../../../tests/test_agent_quota_recovery.py)
- [tests/test_agent_reliability.py](../../../tests/test_agent_reliability.py)
- [tests/test_agent_runs.py](../../../tests/test_agent_runs.py)

</details>

**Konkrete Teilbelege:**

- [test_recovery_never_starts_a_new_call](../../../tests/test_agent_runs.py#L278) — Store-/API-Verträge mit Auth-/Transport-Doubles. **Datei**status vom 2026-10-02: passed=38.
  - [Zeile 283](../../../tests/test_agent_runs.py#L283): ` assert response.status_code == 404 `
  - [Zeile 284](../../../tests/test_agent_runs.py#L284): ` assert calls == [] `
  - [Zeile 285](../../../tests/test_agent_runs.py#L285): ` assert store.get_chat(UID, chat_id)["turn_count"] == 0 `
- [test_detail_pages_are_owner_bound_and_never_start_provider](../../../tests/test_agent_http_contract.py#L56) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=9.
  - [Zeile 67](../../../tests/test_agent_http_contract.py#L67): ` assert response.status_code == 200, response.text `
  - [Zeile 68](../../../tests/test_agent_http_contract.py#L68): ` assert response.headers["cache-control"] == "private, no-store" `
  - [Zeile 70](../../../tests/test_agent_http_contract.py#L70): ` assert data["agent"]["id"] == h.agent_id `
  - [Zeile 71](../../../tests/test_agent_http_contract.py#L71): ` assert data["agent"]["assignment"]["goal"] == "Owner private assignment" `
  - [Zeile 72](../../../tests/test_agent_http_contract.py#L72): ` assert 1 <= len(data["messages"]) <= 3 `
  - [Zeile 77](../../../tests/test_agent_http_contract.py#L77): ` assert [m["text"] for m in messages] == ["Message " + str(i) for i in range(7)] `
- [test_send_button_stays_cancelable_until_consensus_is_done](../../../tests/e2e/test_run_cancel_and_progress.py#L47) — Chromium mit echten Registry- und DOMereignissen. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 78](../../../tests/e2e/test_run_cancel_and_progress.py#L78): ` app_page.wait_for_function( `
  - [Zeile 86](../../../tests/e2e/test_run_cancel_and_progress.py#L86): ` assert any(sample["status"] == "pending" for sample in samples), samples `
  - [Zeile 87](../../../tests/e2e/test_run_cancel_and_progress.py#L87): ` assert any(sample["status"] in {"streaming", "differences"} for sample in samples), samples `
  - [Zeile 88](../../../tests/e2e/test_run_cancel_and_progress.py#L88): ` assert all(sample["cancelable"] for sample in samples), samples `
  - [Zeile 89](../../../tests/e2e/test_run_cancel_and_progress.py#L89): ` expect(app_page.locator("#sendButton")).not_to_have_class( `
- [test_j02_stop_reload_recover_preserves_partial_and_charges_only_started_step](../../../tests/e2e/test_persisted_journeys.py#L186) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 196](../../../tests/e2e/test_persisted_journeys.py#L196): ` expect(j.page.locator('#agentAnswerBody')).to_contain_text('Saved partial answer', timeout=30000) `
  - [Zeile 199](../../../tests/e2e/test_persisted_journeys.py#L199): ` j.page.wait_for_function('() => Date.now() - App.runRegistry.visible().startedAt > 800') `
  - [Zeile 201](../../../tests/e2e/test_persisted_journeys.py#L201): ` j.page.wait_for_function('() => App.runRegistry.visible()?.status === "canceled"') `
  - [Zeile 205](../../../tests/e2e/test_persisted_journeys.py#L205): ` assert len(state['calls']) == 8  # orchestrator + six comparison providers + partial synthesis `
  - [Zeile 208](../../../tests/e2e/test_persisted_journeys.py#L208): ` assert turn['data']['status'] == 'failed' `
  - [Zeile 209](../../../tests/e2e/test_persisted_journeys.py#L209): ` assert turn['data']['agent_failure']['code'] == 'cancelled' `
- [test_disconnect_preserves_generator_exit_when_deleted_account_blocks_cleanup](../../../tests/test_agent_capacity.py#L16) — Agentkapazität, Routerstream und lokale Worker mit kontrolliertem Loop. **Datei**status vom 2026-10-02: passed=7.
  - [Zeile 35](../../../tests/test_agent_capacity.py#L35): ` assert "event: accepted" in next(stream) `
  - [Zeile 36](../../../tests/test_agent_capacity.py#L36): ` assert "event: delta" in next(stream) `
  - [Zeile 38](../../../tests/test_agent_capacity.py#L38): ` assert closed == [True] and not calls `
  - [Zeile 39](../../../tests/test_agent_capacity.py#L39): ` assert "Agent completion failed" not in caplog.text `
  - [Zeile 40](../../../tests/test_agent_capacity.py#L40): ` assert "Agent stream cleanup unavailable" in caplog.text `
  - [Zeile 41](../../../tests/test_agent_capacity.py#L41): ` assert list(stream) == [] `
- [test_all_pro_chat_models_are_grouped_by_provider](../../../tests/e2e/test_agent_chat_frontend.py#L71) — Chromium mit echtem App-Frontend und kontrollierten Agent-APIantworten. **Datei**status vom 2026-10-02: passed=31.
  - [Zeile 77](../../../tests/e2e/test_agent_chat_frontend.py#L77): ` assert cfg.PREMIUM_MODELS <= {model['id'] for model in catalog['models']} `
  - [Zeile 86](../../../tests/e2e/test_agent_chat_frontend.py#L86): ` expect(page.locator('#agentModelDropdown')).to_be_enabled() `
  - [Zeile 87](../../../tests/e2e/test_agent_chat_frontend.py#L87): ` expect(page.locator('#agentModelDropdown option')).to_have_count(len(catalog['models'])) `
  - [Zeile 91](../../../tests/e2e/test_agent_chat_frontend.py#L91): ` assert menu['x'] >= 0 and menu['x'] + menu['width'] <= width `
  - [Zeile 92](../../../tests/e2e/test_agent_chat_frontend.py#L92): ` assert menu['y'] >= 0 and menu['y'] + menu['height'] <= 900 `
  - [Zeile 93](../../../tests/e2e/test_agent_chat_frontend.py#L93): ` expect(page.locator('.agent-model-picker button[data-model-group]')).to_have_count(len(cfg.PROVIDERS)) `

<a id="agent-05"></a>

## AGENT-05 · Agent-Ansicht und bestätigter Fortschritt

Sidebar/Antworten zeigen echte Ereignisse, Reasoning getrennt vom Antworttext, bekannte Kosten versus pending; historische Laufzeiten frieren ein. View-/Authwechsel unterdrücken verspätete Projektionen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** jsdom führt Ereignis-/Darstellungslogik und logische Fokusfälle aus, etwa activeElement und Clipboard-Fallback in agent-answer-actions.test.mjs. Tatsächliche Geometrie, native Auswahl und Browserfokus benötigen den nicht ausgeführten Browserbestand.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/agent_progress.py](../../../app/services/agent_progress.py)
- [static/js/agent-activity.js](../../../static/js/agent-activity.js)
- [static/js/agent-answer-actions.js](../../../static/js/agent-answer-actions.js)
- [static/js/agent-chat.js](../../../static/js/agent-chat.js)
- [static/js/agent-preferences.js](../../../static/js/agent-preferences.js)
- [static/js/agent-review.js](../../../static/js/agent-review.js)
- [static/js/sidebar-quota.js](../../../static/js/sidebar-quota.js)

**Testdateien:**

- [tests/e2e/test_agent_chat_frontend.py](../../../tests/e2e/test_agent_chat_frontend.py)
- [tests/e2e/test_agent_comparison_frontend.py](../../../tests/e2e/test_agent_comparison_frontend.py)
- [tests/e2e/test_agent_delegation_frontend.py](../../../tests/e2e/test_agent_delegation_frontend.py)
- [tests/e2e/test_agent_gmail_frontend.py](../../../tests/e2e/test_agent_gmail_frontend.py)
- [tests/e2e/test_agent_status_frontend.py](../../../tests/e2e/test_agent_status_frontend.py)
- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/e2e/test_run_mode_selector.py](../../../tests/e2e/test_run_mode_selector.py)
- [tests/js/agent-answer-actions.test.mjs](../../../tests/js/agent-answer-actions.test.mjs)
- [tests/js/agent-chat.test.mjs](../../../tests/js/agent-chat.test.mjs)
- [tests/js/agent-preferences.test.mjs](../../../tests/js/agent-preferences.test.mjs)
- [tests/js/agent-review.test.mjs](../../../tests/js/agent-review.test.mjs)
- [tests/js/sidebar-quota.test.mjs](../../../tests/js/sidebar-quota.test.mjs)
- [tests/test_agent_progress.py](../../../tests/test_agent_progress.py)

</details>

**Konkrete Teilbelege:**

- [test_short_highlights_update_at_boundaries_and_remain_bounded](../../../tests/test_agent_progress.py#L14) — Fortschrittsfunktionen und Loop mit kontrollierter Uhr/Providern. **Datei**status vom 2026-10-02: passed=10.
  - [Zeile 16](../../../tests/test_agent_progress.py#L16): ` assert progress.update(event("Checking the ")) is None `
  - [Zeile 18](../../../tests/test_agent_progress.py#L18): ` assert first["text"] == "Checking the available evidence." `
  - [Zeile 19](../../../tests/test_agent_progress.py#L19): ` assert first["summary_source"] == "excerpt" and first["append"] is False `
  - [Zeile 20](../../../tests/test_agent_progress.py#L20): ` assert progress.update(event(" Next")) is None `
  - [Zeile 24](../../../tests/test_agent_progress.py#L24): ` assert len(value["text"]) <= 542 `
  - [Zeile 25](../../../tests/test_agent_progress.py#L25): ` assert len(value["text"].splitlines()) <= 3 `
- [test_j02_stop_reload_recover_preserves_partial_and_charges_only_started_step](../../../tests/e2e/test_persisted_journeys.py#L186) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 196](../../../tests/e2e/test_persisted_journeys.py#L196): ` expect(j.page.locator('#agentAnswerBody')).to_contain_text('Saved partial answer', timeout=30000) `
  - [Zeile 199](../../../tests/e2e/test_persisted_journeys.py#L199): ` j.page.wait_for_function('() => Date.now() - App.runRegistry.visible().startedAt > 800') `
  - [Zeile 201](../../../tests/e2e/test_persisted_journeys.py#L201): ` j.page.wait_for_function('() => App.runRegistry.visible()?.status === "canceled"') `
  - [Zeile 205](../../../tests/e2e/test_persisted_journeys.py#L205): ` assert len(state['calls']) == 8  # orchestrator + six comparison providers + partial synthesis `
  - [Zeile 208](../../../tests/e2e/test_persisted_journeys.py#L208): ` assert turn['data']['status'] == 'failed' `
  - [Zeile 209](../../../tests/e2e/test_persisted_journeys.py#L209): ` assert turn['data']['agent_failure']['code'] == 'cancelled' `
- [test_all_pro_chat_models_are_grouped_by_provider](../../../tests/e2e/test_agent_chat_frontend.py#L71) — Chromium mit echtem App-Frontend und kontrollierten Agent-APIantworten. **Datei**status vom 2026-10-02: passed=31.
  - [Zeile 77](../../../tests/e2e/test_agent_chat_frontend.py#L77): ` assert cfg.PREMIUM_MODELS <= {model['id'] for model in catalog['models']} `
  - [Zeile 86](../../../tests/e2e/test_agent_chat_frontend.py#L86): ` expect(page.locator('#agentModelDropdown')).to_be_enabled() `
  - [Zeile 87](../../../tests/e2e/test_agent_chat_frontend.py#L87): ` expect(page.locator('#agentModelDropdown option')).to_have_count(len(catalog['models'])) `
  - [Zeile 91](../../../tests/e2e/test_agent_chat_frontend.py#L91): ` assert menu['x'] >= 0 and menu['x'] + menu['width'] <= width `
  - [Zeile 92](../../../tests/e2e/test_agent_chat_frontend.py#L92): ` assert menu['y'] >= 0 and menu['y'] + menu['height'] <= 900 `
  - [Zeile 93](../../../tests/e2e/test_agent_chat_frontend.py#L93): ` expect(page.locator('.agent-model-picker button[data-model-group]')).to_have_count(len(cfg.PROVIDERS)) `
- [test_comparison_selection_blocks_send_before_losing_draft](../../../tests/e2e/test_agent_comparison_frontend.py#L13) — Chromium mit echten Vergleichs-/Drawerkomponenten. **Datei**status vom 2026-10-02: passed=15.
  - [Zeile 25](../../../tests/e2e/test_agent_comparison_frontend.py#L25): ` expect(page.locator('#sendButton')).to_be_enabled() `
  - [Zeile 27](../../../tests/e2e/test_agent_comparison_frontend.py#L27): ` expect(page.locator('.consensus-model-inline')).to_be_hidden() `
  - [Zeile 33](../../../tests/e2e/test_agent_comparison_frontend.py#L33): ` expect(page.locator('#sendButton')).to_be_disabled() `
  - [Zeile 35](../../../tests/e2e/test_agent_comparison_frontend.py#L35): ` expect(page.locator('#sendButton')).to_be_disabled() `
  - [Zeile 37](../../../tests/e2e/test_agent_comparison_frontend.py#L37): ` expect(page.locator('#agentComposerNotice')).to_be_visible() `
  - [Zeile 38](../../../tests/e2e/test_agent_comparison_frontend.py#L38): ` expect(page.locator('#agentComposerMessage')).to_contain_text('comparison models') `
- [test_gmail_draft_revision_document_download_and_restoration](../../../tests/e2e/test_agent_gmail_frontend.py#L12) — Chromium mit kontrollierten Verbindungen und Gmailaktionsantworten. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 26](../../../tests/e2e/test_agent_gmail_frontend.py#L26): ` assert route.request.headers.get('authorization','').startswith('Bearer ') `
  - [Zeile 52](../../../tests/e2e/test_agent_gmail_frontend.py#L52): ` expect(page.locator('#agentGoogleChips')).to_contain_text('Gmail · owner@example.org') `
  - [Zeile 55](../../../tests/e2e/test_agent_gmail_frontend.py#L55): ` expect(page.locator('#agentGoogleActions')).to_contain_text('Decision-v1.pdf') `
  - [Zeile 56](../../../tests/e2e/test_agent_gmail_frontend.py#L56): ` assert requests[0]['google_selection']['gmail'] is True and requests[0]['google_selection']['calendar'] is False `
  - [Zeile 57](../../../tests/e2e/test_agent_gmail_frontend.py#L57): ` expect(consent).not_to_be_checked();assert not confirmed `
  - [Zeile 57](../../../tests/e2e/test_agent_gmail_frontend.py#L57): ` expect(consent).not_to_be_checked();assert not confirmed `
- [test_progress_paragraphs_collapse_at_final_and_reopen_with_keyboard](../../../tests/e2e/test_agent_status_frontend.py#L11) — Chromium mit kontrollierten gestreamten Fortschrittsereignissen. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 28](../../../tests/e2e/test_agent_status_frontend.py#L28): ` expect(page.locator("#agentModelDropdown")).to_be_enabled() `
  - [Zeile 73](../../../tests/e2e/test_agent_status_frontend.py#L73): ` expect(preview.locator('.agent-current-status')).to_have_text('Thinking…') `
  - [Zeile 76](../../../tests/e2e/test_agent_status_frontend.py#L76): ` expect(thinking_details.locator('.agent-activity-run-details')).to_be_visible() `
  - [Zeile 77](../../../tests/e2e/test_agent_status_frontend.py#L77): ` expect(thinking_details.locator('.agent-activity-run-details')).to_contain_text('DeepSeek V4.1 Flash') `
  - [Zeile 78](../../../tests/e2e/test_agent_status_frontend.py#L78): ` expect(thinking_details.locator('.agent-activity-run-details')).to_contain_text('Thinking…') `
  - [Zeile 79](../../../tests/e2e/test_agent_status_frontend.py#L79): ` expect(thinking_details.locator('.agent-activity-run-details')).to_contain_text('Model default') `

<a id="src-01"></a>

## SRC-01 · Sicherer begrenzter Quellenabruf

Abruf validiert URL, DNS, Redirects und Ziel-IP, erhält Host/SNI und begrenzt Bytes/Zeit; Fehler-/Singleflight-Caches dürfen Ownerdaten nicht vermischen.

**Anforderungsbasis:** [docs/source-verification.md](../../source-verification.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Realer lokaler TLS-/Redirect-/gzip-Pfad mit Host/SNI und neu validierten Redirectzielen; Zielpinning für eigene Server kontrolliert, keine Internetmessung.

**Befunde:** [G-032](gaps.md#g-032). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/source_documents.py](../../../app/services/source_documents.py)
- [app/services/source_verification.py](../../../app/services/source_verification.py)

**Testdateien:**

- [tests/test_local_transport.py](../../../tests/test_local_transport.py)
- [tests/test_source_verification.py](../../../tests/test_source_verification.py)

</details>

**Konkrete Teilbelege:**

- [test_fetch_pins_ip_and_checks_redirect_again](../../../tests/test_source_verification.py#L436) — Verifikations-/Dokument-/Pipeline-Integration mit Fetch/Judge/HTTPX-Doubles und Threads. **Datei**status vom 2026-10-02: passed=122.
  - [Zeile 443](../../../tests/test_source_verification.py#L443): ` assert request.url.host == '93.184.216.34' `
  - [Zeile 444](../../../tests/test_source_verification.py#L444): ` assert request.headers['host'] == 'example.com' `
  - [Zeile 445](../../../tests/test_source_verification.py#L445): ` assert request.extensions['sni_hostname'] == 'example.com' `
  - [Zeile 449](../../../tests/test_source_verification.py#L449): ` with pytest.raises(ValueError, match='unsafe_address'): `
  - [Zeile 451](../../../tests/test_source_verification.py#L451): ` assert len(calls) == 1 `
- [test_cancellation_closes_real_idle_provider_socket_without_retry](../../../tests/test_local_transport.py#L64) — Echte lokale TCP-/TLS-Server durch HTTP-/SDK-Adapter. **Datei**status vom 2026-10-02: passed=10.
  - [Zeile 85](../../../tests/test_local_transport.py#L85): ` assert state.seen.wait(3), 'request never reached local server' `
  - [Zeile 88](../../../tests/test_local_transport.py#L88): ` assert not thread.is_alive(), 'producer survived cancellation' `
  - [Zeile 89](../../../tests/test_local_transport.py#L89): ` assert len(errors) == 1 and isinstance(errors[0], runtime.ProviderCancelled) `
  - [Zeile 90](../../../tests/test_local_transport.py#L90): ` assert state.closed.wait(3), 'server socket stayed open' `
  - [Zeile 91](../../../tests/test_local_transport.py#L91): ` assert len(state.requests) == 1 `

<a id="src-02"></a>

## SRC-02 · Prüfplan und konservative Urteile

Nur geeignete Widersprüche werden anhand vorhandener Quellen geprüft; beide Positionen, Originalzitate und Run-/Antwortbindung sind erforderlich. Disabled/skipped/unavailable/unresolved sind unterschiedliche Zustände.

**Anforderungsbasis:** [docs/source-judge-spec.md](../../source-judge-spec.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Synthetische Belege und Judgeantworten; kein fachlicher Evaluationsnachweis.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/contradiction_verification.py](../../../app/services/contradiction_verification.py)
- [app/services/llm/coverage_judge.py](../../../app/services/llm/coverage_judge.py)
- [app/services/source_verification.py](../../../app/services/source_verification.py)

**Testdateien:**

- [tests/test_analysis_quality_budget.py](../../../tests/test_analysis_quality_budget.py)
- [tests/test_contradiction_verification.py](../../../tests/test_contradiction_verification.py)
- [tests/test_source_judge_fallback.py](../../../tests/test_source_judge_fallback.py)
- [tests/test_source_verification.py](../../../tests/test_source_verification.py)

</details>

**Konkrete Teilbelege:**

- [test_original_evidence_validation_rejects_invented_or_incomplete_verdicts](../../../tests/test_contradiction_verification.py#L208) — Deterministische Planungs-/Validierungs- und Ausführungstests mit injizierten Fetch/Judge-Funktionen. **Datei**status vom 2026-10-02: passed=67.
  - [Zeile 224](../../../tests/test_contradiction_verification.py#L224): ` assert not result['findings'][0]['checked'] `
  - [Zeile 225](../../../tests/test_contradiction_verification.py#L225): ` assert result['findings'][0]['reason_code'] in ('evidence_mismatch', 'invalid_output') `

<a id="src-03"></a>

## SRC-03 · Dauerhafte Jobqueue und Credentials

Claims/Resultwrites sind lease-/revisionsgebunden; eigene Keys bleiben im Prozessspeicher, kein Developer-Fallback. Stale Writes/Ownerlöschung/Versionswechsel dürfen alte Ergebnisse nicht an neue Antworten hängen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Native SDK-Queueclaims, Takeover, Paketabschluss und Deletefencing; Providerdaten synthetisch, transiente ABORTED können neuen Workeraufruf erfordern.

**Befunde:** [G-006](gaps.md#g-006). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/source_check_jobs.py](../../../app/services/source_check_jobs.py)
- [app/services/source_check_repository.py](../../../app/services/source_check_repository.py)

**Testdateien:**

- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/e2e/test_source_check_transactions.py](../../../tests/e2e/test_source_check_transactions.py)
- [tests/test_contradiction_jobs.py](../../../tests/test_contradiction_jobs.py)
- [tests/test_source_check_jobs.py](../../../tests/test_source_check_jobs.py)
- [tests/test_source_check_repository.py](../../../tests/test_source_check_repository.py)
- [tests/test_source_check_scope.py](../../../tests/test_source_check_scope.py)

</details>

**Konkrete Teilbelege:**

- [test_expired_lease_reclaims_unfinished_package_and_rejects_stale_worker](../../../tests/test_source_check_repository.py#L214) — Repository mit lockbasiertem FakeDb und Threads. **Datei**status vom 2026-10-02: passed=36.
  - [Zeile 219](../../../tests/test_source_check_repository.py#L219): ` assert repo.claim(job["job_id"], now=now + timedelta(seconds=LEASE_SECONDS - 1)) is None `
  - [Zeile 221](../../../tests/test_source_check_repository.py#L221): ` assert second["lease_token"] != first["lease_token"] `
  - [Zeile 222](../../../tests/test_source_check_repository.py#L222): ` assert second["completed_packages"] == 0 `
  - [Zeile 224](../../../tests/test_source_check_repository.py#L224): ` assert not repo.finish_package(first, result) `
  - [Zeile 225](../../../tests/test_source_check_repository.py#L225): ` assert not repo.retry(first) `
  - [Zeile 226](../../../tests/test_source_check_repository.py#L226): ` assert repo.finish_package(second, result) `
- [test_restart_pauses_own_key_work_without_developer_fallback_then_owner_resumes](../../../tests/test_source_check_jobs.py#L80) — Job-Worker mit FakeDb/Fetch/Judge und simulierten Workeridentitäten. **Datei**status vom 2026-10-02: passed=23.
  - [Zeile 89](../../../tests/test_source_check_jobs.py#L89): ` assert jobs.process_one(repo) `
  - [Zeile 90](../../../tests/test_source_check_jobs.py#L90): ` assert repo.get(snapshot['job_id'])['status'] == 'awaiting_credentials' `
  - [Zeile 91](../../../tests/test_source_check_jobs.py#L91): ` assert used == [] `
  - [Zeile 93](../../../tests/test_source_check_jobs.py#L93): ` assert resumed['job_id'] == snapshot['job_id'] and resumed['status'] == 'queued' `
  - [Zeile 94](../../../tests/test_source_check_jobs.py#L94): ` assert jobs.process_one(repo) `
  - [Zeile 95](../../../tests/test_source_check_jobs.py#L95): ` assert used == [{'OpenRouter': 'replacement-secret'}] `
- [test_native_source_claim_takeover_and_exactly_once_package](../../../tests/e2e/test_source_check_transactions.py#L15) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 27](../../../tests/e2e/test_source_check_transactions.py#L27): ` assert sum(claim is not None for claim in claims) == 1 `
  - [Zeile 31](../../../tests/e2e/test_source_check_transactions.py#L31): ` assert current["lease_token"] != old["lease_token"] `
  - [Zeile 33](../../../tests/e2e/test_source_check_transactions.py#L33): ` assert repos[0].finish_package(old, package_result(plan, 0)) is False `
  - [Zeile 34](../../../tests/e2e/test_source_check_transactions.py#L34): ` assert tree(ref) == before `
  - [Zeile 42](../../../tests/e2e/test_source_check_transactions.py#L42): ` assert sorted(results) == [False, True] `
  - [Zeile 43](../../../tests/e2e/test_source_check_transactions.py#L43): ` assert ref.get().to_dict()["completed_packages"] == 1 `
- [test_j03_historical_source_job_resumes_and_pages_a_native_revision](../../../tests/e2e/test_persisted_journeys.py#L227) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 235](../../../tests/e2e/test_persisted_journeys.py#L235): ` j.page.wait_for_function('() => window.__consensioAuthState?.known && window.openBookmark') `
  - [Zeile 238](../../../tests/e2e/test_persisted_journeys.py#L238): ` assert resumed.value.ok, resumed.value.text() `
  - [Zeile 239](../../../tests/e2e/test_persisted_journeys.py#L239): ` assert j.request('GET', f'/api/source-checks/{job_id}', uid='journey-'+'f'*32).status == 404 `
  - [Zeile 242](../../../tests/e2e/test_persisted_journeys.py#L242): ` assert completion['worker'] == {'provider_calls': 9, 'fetch_calls': 1, `
  - [Zeile 245](../../../tests/e2e/test_persisted_journeys.py#L245): ` assert finished['status'] == 'complete' and finished['scope']['checked_pairs'] == 9 `
  - [Zeile 246](../../../tests/e2e/test_persisted_journeys.py#L246): ` assert finished['runtime']['calls'] == 9 `

<a id="src-04"></a>

## SRC-04 · Private und öffentliche Jobseiten

Jede Seite prüft Owner oder aktive öffentliche Ressource sowie Run/Antwort/Revision; Pagination darf bei geändertem Stand nicht mischen, eigene Keys dürfen nicht persistieren.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Private/öffentliche Adapter und historischer API-v1-Source-GET sowie native Pagination; Auth-SDK/Providerdaten kontrolliert.

**Befunde:** [G-010](gaps.md#g-010). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py)
- [app/api/routers/source_checks.py](../../../app/api/routers/source_checks.py)

**Testdateien:**

- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/e2e/test_source_check_transactions.py](../../../tests/e2e/test_source_check_transactions.py)
- [tests/test_api_source_history.py](../../../tests/test_api_source_history.py)
- [tests/test_source_check_api.py](../../../tests/test_source_check_api.py)
- [tests/test_source_check_scope.py](../../../tests/test_source_check_scope.py)

</details>

**Konkrete Teilbelege:**

- [test_v4_public_share_rejects_wrong_job_version_on_every_page](../../../tests/test_source_check_api.py#L125) — Router mit SourceCheckRepository/FakeDb und Share-/Topic-Doubles. **Datei**status vom 2026-10-02: passed=14.
  - [Zeile 138](../../../tests/test_source_check_api.py#L138): ` assert client.get(url, params=params).status_code == 200 `
  - [Zeile 140](../../../tests/test_source_check_api.py#L140): ` assert client.get(url, params=params).status_code == 404 `
- [test_native_source_claim_takeover_and_exactly_once_package](../../../tests/e2e/test_source_check_transactions.py#L15) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 27](../../../tests/e2e/test_source_check_transactions.py#L27): ` assert sum(claim is not None for claim in claims) == 1 `
  - [Zeile 31](../../../tests/e2e/test_source_check_transactions.py#L31): ` assert current["lease_token"] != old["lease_token"] `
  - [Zeile 33](../../../tests/e2e/test_source_check_transactions.py#L33): ` assert repos[0].finish_package(old, package_result(plan, 0)) is False `
  - [Zeile 34](../../../tests/e2e/test_source_check_transactions.py#L34): ` assert tree(ref) == before `
  - [Zeile 42](../../../tests/e2e/test_source_check_transactions.py#L42): ` assert sorted(results) == [False, True] `
  - [Zeile 43](../../../tests/e2e/test_source_check_transactions.py#L43): ` assert ref.get().to_dict()["completed_packages"] == 1 `
- [test_historic_api_source_pages_owner_cursor_revision_and_cache](../../../tests/test_api_source_history.py#L43) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=9.
  - [Zeile 52](../../../tests/test_api_source_history.py#L52): ` assert response.status_code == 200, response.text `
  - [Zeile 53](../../../tests/test_api_source_history.py#L53): ` assert set(map(str.strip, response.headers["cache-control"].split(","))) == { `
  - [Zeile 60](../../../tests/test_api_source_history.py#L60): ` assert len(found) == 9 `
  - [Zeile 61](../../../tests/test_api_source_history.py#L61): ` assert h.client.get(h.url).status_code == 401 `
  - [Zeile 62](../../../tests/test_api_source_history.py#L62): ` assert h.client.get(h.url, headers={"X-API-Key": h.other_key}).status_code == 404 `
  - [Zeile 64](../../../tests/test_api_source_history.py#L64): ` assert ( `
- [test_j03_historical_source_job_resumes_and_pages_a_native_revision](../../../tests/e2e/test_persisted_journeys.py#L227) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 235](../../../tests/e2e/test_persisted_journeys.py#L235): ` j.page.wait_for_function('() => window.__consensioAuthState?.known && window.openBookmark') `
  - [Zeile 238](../../../tests/e2e/test_persisted_journeys.py#L238): ` assert resumed.value.ok, resumed.value.text() `
  - [Zeile 239](../../../tests/e2e/test_persisted_journeys.py#L239): ` assert j.request('GET', f'/api/source-checks/{job_id}', uid='journey-'+'f'*32).status == 404 `
  - [Zeile 242](../../../tests/e2e/test_persisted_journeys.py#L242): ` assert completion['worker'] == {'provider_calls': 9, 'fetch_calls': 1, `
  - [Zeile 245](../../../tests/e2e/test_persisted_journeys.py#L245): ` assert finished['status'] == 'complete' and finished['scope']['checked_pairs'] == 9 `
  - [Zeile 246](../../../tests/e2e/test_persisted_journeys.py#L246): ` assert finished['runtime']['calls'] == 9 `

<a id="src-05"></a>

## SRC-05 · Sources-/Differences-UI und Nachladen

UI unterscheidet alle Prüfzustände, zeigt Originalpassagen und bindet verspätete Seiten an Run/Ansicht/Auth. Legacyberichte bleiben lesbar; Filter entfernen unsichtbare Interaktionen ohne Befunde zu verlieren.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Fixture-Daten/DOM, Browser nicht ausgeführt; keine Qualitätsbehauptung über den Judge.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/js/consensus-insights.js](../../../static/js/consensus-insights.js)
- [static/js/source-verification.js](../../../static/js/source-verification.js)
- [static/js/sources.js](../../../static/js/sources.js)

**Testdateien:**

- [tests/e2e/test_contradiction_source_ui.py](../../../tests/e2e/test_contradiction_source_ui.py)
- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py)
- [tests/js/admin-source-model.test.mjs](../../../tests/js/admin-source-model.test.mjs)
- [tests/js/bookmark-source-check.test.mjs](../../../tests/js/bookmark-source-check.test.mjs)
- [tests/js/claim-coverage-states.test.mjs](../../../tests/js/claim-coverage-states.test.mjs)
- [tests/js/contradiction-source-verification.test.mjs](../../../tests/js/contradiction-source-verification.test.mjs)
- [tests/js/memory-edit-sources.test.mjs](../../../tests/js/memory-edit-sources.test.mjs)
- [tests/js/source-catalog-refs.test.mjs](../../../tests/js/source-catalog-refs.test.mjs)
- [tests/js/source-teaser-check.test.mjs](../../../tests/js/source-teaser-check.test.mjs)
- [tests/js/source-url-identity.test.mjs](../../../tests/js/source-url-identity.test.mjs)
- [tests/js/source-verification-watch.test.mjs](../../../tests/js/source-verification-watch.test.mjs)
- [tests/js/source-verification.test.mjs](../../../tests/js/source-verification.test.mjs)
- [tests/test_source_pills_ui.py](../../../tests/test_source_pills_ui.py)

</details>

**Konkrete Teilbelege:**

- [keeps the compact Sources verdict honest across result and run changes](../../../tests/js/source-verification.test.mjs#L16) — JavaScript-Modulintegration mit jsdom. **Datei**status vom 2026-10-02: passed=21.
  - [Zeile 37](../../../tests/js/source-verification.test.mjs#L37): ` expect(tab.dataset.checkState).toBe(state); `
  - [Zeile 38](../../../tests/js/source-verification.test.mjs#L38): ` expect(tab.querySelectorAll('.consensus-source-check-icon')).toHaveLength(1); `
  - [Zeile 39](../../../tests/js/source-verification.test.mjs#L39): ` expect(tab.querySelector('.consensus-source-check-icon').textContent).toBe(icon); `
  - [Zeile 40](../../../tests/js/source-verification.test.mjs#L40): ` expect(tab.querySelector('.consensus-source-check-icon').getAttribute('aria-hidden')).toBe('true'); `
  - [Zeile 42](../../../tests/js/source-verification.test.mjs#L42): ` expect(tab.title).toBe('View sources'); `
- [test_j03_historical_source_job_resumes_and_pages_a_native_revision](../../../tests/e2e/test_persisted_journeys.py#L227) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 235](../../../tests/e2e/test_persisted_journeys.py#L235): ` j.page.wait_for_function('() => window.__consensioAuthState?.known && window.openBookmark') `
  - [Zeile 238](../../../tests/e2e/test_persisted_journeys.py#L238): ` assert resumed.value.ok, resumed.value.text() `
  - [Zeile 239](../../../tests/e2e/test_persisted_journeys.py#L239): ` assert j.request('GET', f'/api/source-checks/{job_id}', uid='journey-'+'f'*32).status == 404 `
  - [Zeile 242](../../../tests/e2e/test_persisted_journeys.py#L242): ` assert completion['worker'] == {'provider_calls': 9, 'fetch_calls': 1, `
  - [Zeile 245](../../../tests/e2e/test_persisted_journeys.py#L245): ` assert finished['status'] == 'complete' and finished['scope']['checked_pairs'] == 9 `
  - [Zeile 246](../../../tests/e2e/test_persisted_journeys.py#L246): ` assert finished['runtime']['calls'] == 9 `

<a id="share-01"></a>

## SHARE-01 · Autoritative Share-Erstellung

Ein gültiger eigener Pending-Run wird idempotent veröffentlicht; Sichtbarkeit, Quota und Snapshot werden gemeinsam entschieden. Clientinhalt darf kein fremdes oder erfundenes Resultat materialisieren.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Echter App-POST mit autoritativem Pending und native Shareidempotenz; SDKauth ersetzt, kein Produktpublish.

**Befunde:** [G-011](gaps.md#g-011), [G-027](gaps.md#g-027). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/share.py](../../../app/api/routers/share.py)
- [app/services/share_snapshots.py](../../../app/services/share_snapshots.py)
- [static/js/share-dialog.js](../../../static/js/share-dialog.js)

**Testdateien:**

- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)
- [tests/test_consensus_api.py](../../../tests/test_consensus_api.py)
- [tests/test_share_feature.py](../../../tests/test_share_feature.py)
- [tests/test_share_http_contract.py](../../../tests/test_share_http_contract.py)

</details>

**Konkrete Teilbelege:**

- [ShareFlowTests::test_create_share_is_idempotent](../../../tests/test_share_feature.py#L780) — Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads. **Datei**status vom 2026-10-02: passed=156.
  - [Zeile 790](../../../tests/test_share_feature.py#L790): ` self.assertEqual(first["share_id"], second["share_id"]) `
  - [Zeile 791](../../../tests/test_share_feature.py#L791): ` self.assertFalse(second["created"]) `
  - [Zeile 792](../../../tests/test_share_feature.py#L792): ` self.assertEqual(len(quota_calls), 1) `
- [test_two_workers_cannot_exceed_owner_watch_limit](../../../tests/e2e/test_phase2_transactions.py#L29) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 71](../../../tests/e2e/test_phase2_transactions.py#L71): ` assert sorted(code for code, _watch_id in outcomes) == [ `
  - [Zeile 78](../../../tests/e2e/test_phase2_transactions.py#L78): ` assert len(watches) == 1 `
  - [Zeile 83](../../../tests/e2e/test_phase2_transactions.py#L83): ` assert state["active_count"] == 1 `
- [test_app_share_publishes_authoritative_content_and_retry_does_not_charge_twice](../../../tests/test_share_http_contract.py#L36) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=7.
  - [Zeile 48](../../../tests/test_share_http_contract.py#L48): ` assert first.status_code == 200, first.text `
  - [Zeile 51](../../../tests/test_share_http_contract.py#L51): ` assert stored["owner_uid"] == "owner" and stored["visibility"] == "public" `
  - [Zeile 52](../../../tests/test_share_http_contract.py#L52): ` assert stored["question"] == "Unique public question?" and "FORGED" not in str( `
  - [Zeile 55](../../../tests/test_share_http_contract.py#L55): ` assert data["path"] == snapshots.share_path(stored["slug"], data["share_id"]) `
  - [Zeile 56](../../../tests/test_share_http_contract.py#L56): ` assert data["url"].endswith(data["path"]) and data["created"] is True `
  - [Zeile 59](../../../tests/test_share_http_contract.py#L59): ` assert second.status_code == 200 and second.json()["created"] is False `
- [test_j04_app_share_follow_watch_versions_bind_to_saved_native_result](../../../tests/e2e/test_persisted_journeys.py#L261) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 268](../../../tests/e2e/test_persisted_journeys.py#L268): ` j.page.wait_for_function('() => window.__consensioAuthState?.known && window.openBookmark') `
  - [Zeile 274](../../../tests/e2e/test_persisted_journeys.py#L274): ` assert published.value.ok, published.value.text() `
  - [Zeile 278](../../../tests/e2e/test_persisted_journeys.py#L278): ` assert pending['owner_uid'] == j.uid and 'Mock consensus' in pending['consensus_md'] `
  - [Zeile 279](../../../tests/e2e/test_persisted_journeys.py#L279): ` assert native['global_owned']['shares'][share['share_id']]['data']['owner_uid'] == j.uid `
  - [Zeile 282](../../../tests/e2e/test_persisted_journeys.py#L282): ` assert wid_response.ok, wid_response.text() `
  - [Zeile 284](../../../tests/e2e/test_persisted_journeys.py#L284): ` assert j.request('DELETE', '/api/share/' + share['share_id'], {}, uid='journey-'+'f'*32).status == 403 `

<a id="share-02"></a>

## SHARE-02 · Öffentliche und private Darstellung

Status/Sichtbarkeit und gewählte Version bestimmen Inhalt, Quellen, Canonical und noindex; Legacy-Citations und Markdown werden sicher dargestellt. Private Inhalte erscheinen nicht in öffentlichen Hubs/Sitemaps.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** SSR mit Fake-Daten; nicht automatisch als Browser-Sanitizer-/CSP-Nachweis zu werten.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/share.py](../../../app/api/routers/share.py)
- [app/services/history_view.py](../../../app/services/history_view.py)
- [app/services/public_markdown.py](../../../app/services/public_markdown.py)
- [templates/questions.html](../../../templates/questions.html)
- [templates/share.html](../../../templates/share.html)
- [templates/share_unavailable.html](../../../templates/share_unavailable.html)

**Testdateien:**

- [tests/test_public_citation_cleanup.py](../../../tests/test_public_citation_cleanup.py)
- [tests/test_public_markdown.py](../../../tests/test_public_markdown.py)
- [tests/test_seo_basics.py](../../../tests/test_seo_basics.py)
- [tests/test_share_feature.py](../../../tests/test_share_feature.py)
- [tests/test_unscored_history.py](../../../tests/test_unscored_history.py)

</details>

**Konkrete Teilbelege:**

- [SharePageRouteTests::test_private_share_requires_owner_and_is_never_publicly_cached](../../../tests/test_share_feature.py#L1515) — Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads. **Datei**status vom 2026-10-02: passed=156.
  - [Zeile 1521](../../../tests/test_share_feature.py#L1521): ` self.assertEqual(denied.status_code, 403) `
  - [Zeile 1522](../../../tests/test_share_feature.py#L1522): ` self.assertNotIn("Photosynthese wandelt", denied.text) `
  - [Zeile 1528](../../../tests/test_share_feature.py#L1528): ` self.assertEqual(allowed.status_code, 200) `
  - [Zeile 1529](../../../tests/test_share_feature.py#L1529): ` self.assertEqual(allowed.headers["Cache-Control"], "private, no-store") `
  - [Zeile 1530](../../../tests/test_share_feature.py#L1530): ` self.assertIn("· Private", allowed.text) `
  - [Zeile 1531](../../../tests/test_share_feature.py#L1531): ` self.assertNotIn("Report this page", allowed.text) `

<a id="share-03"></a>

## SHARE-03 · Reports, Moderation und Kaskade

Reports zählen ohne verlorene Inkremente; Schwellwerte und Adminentscheidungen steuern Index/Sichtbarkeit. Ownerlöschung entfernt abhängige Daten idempotent.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Native Reportinkremente mit sichtbar erfassten SDK-Abbrüchen; Indexstatus bleibt nach aktuellem Vertrag unverändert. Keine Lastverfügbarkeitsgarantie.

**Befunde:** [G-029](gaps.md#g-029). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/admin.py](../../../app/api/routers/admin.py)
- [app/api/routers/share.py](../../../app/api/routers/share.py)
- [app/services/share_snapshots.py](../../../app/services/share_snapshots.py)

**Testdateien:**

- [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)
- [tests/test_share_feature.py](../../../tests/test_share_feature.py)

</details>

**Konkrete Teilbelege:**

- [test_two_workers_cannot_exceed_owner_watch_limit](../../../tests/e2e/test_phase2_transactions.py#L29) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 71](../../../tests/e2e/test_phase2_transactions.py#L71): ` assert sorted(code for code, _watch_id in outcomes) == [ `
  - [Zeile 78](../../../tests/e2e/test_phase2_transactions.py#L78): ` assert len(watches) == 1 `
  - [Zeile 83](../../../tests/e2e/test_phase2_transactions.py#L83): ` assert state["active_count"] == 1 `

<a id="share-04"></a>

## SHARE-04 · Open-Graph-Karte

Aktive öffentliche Shares liefern eine PNG-Karte aus dem neuesten gültigen öffentlichen Antwortstand der OG-Route; private/inaktive Ressourcen bleiben verborgen, Frage und Kennzahlen müssen tatsächlich im Bild ankommen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_and_inferred_rendering_invariant `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Pillowinhalt, verschiedene Bildregionen und Cacheinputs geprüft, weißes gültiges PNG erkannt; keine plattformabhängigen Pixelhashes.

**Befunde:** [G-020](gaps.md#g-020). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/share.py](../../../app/api/routers/share.py)
- [app/services/og_image.py](../../../app/services/og_image.py)

**Testdateien:**

- [tests/test_og_image.py](../../../tests/test_og_image.py)
- [tests/test_share_feature.py](../../../tests/test_share_feature.py)
- [tests/test_share_http_contract.py](../../../tests/test_share_http_contract.py)

</details>

**Konkrete Teilbelege:**

- [ShareSeoEnhancementTests::test_og_card_route_and_meta](../../../tests/test_share_feature.py#L2597) — Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads. **Datei**status vom 2026-10-02: passed=156.
  - [Zeile 2604](../../../tests/test_share_feature.py#L2604): ` self.assertIn("/og.png", page.text) `
  - [Zeile 2605](../../../tests/test_share_feature.py#L2605): ` self.assertIn("summary_large_image", page.text) `
  - [Zeile 2606](../../../tests/test_share_feature.py#L2606): ` self.assertEqual(og.status_code, 200) `
  - [Zeile 2607](../../../tests/test_share_feature.py#L2607): ` self.assertEqual(og.headers["content-type"], "image/png") `
  - [Zeile 2608](../../../tests/test_share_feature.py#L2608): ` self.assertTrue(og.content.startswith(b"\x89PNG")) `
  - [Zeile 2609](../../../tests/test_share_feature.py#L2609): ` self.assertEqual(og.headers["Cache-Control"], share_router.SHARE_CACHE_CONTROL) `
- [test_app_share_publishes_authoritative_content_and_retry_does_not_charge_twice](../../../tests/test_share_http_contract.py#L36) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=7.
  - [Zeile 48](../../../tests/test_share_http_contract.py#L48): ` assert first.status_code == 200, first.text `
  - [Zeile 51](../../../tests/test_share_http_contract.py#L51): ` assert stored["owner_uid"] == "owner" and stored["visibility"] == "public" `
  - [Zeile 52](../../../tests/test_share_http_contract.py#L52): ` assert stored["question"] == "Unique public question?" and "FORGED" not in str( `
  - [Zeile 55](../../../tests/test_share_http_contract.py#L55): ` assert data["path"] == snapshots.share_path(stored["slug"], data["share_id"]) `
  - [Zeile 56](../../../tests/test_share_http_contract.py#L56): ` assert data["url"].endswith(data["path"]) and data["created"] is True `
  - [Zeile 59](../../../tests/test_share_http_contract.py#L59): ` assert second.status_code == 200 and second.json()["created"] is False `
- [test_renderer_draws_question_score_and_model_facts](../../../tests/test_og_image.py#L31) — Echter Pillowrenderer und kontrollierter Imagecache. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 41](../../../tests/test_og_image.py#L41): ` assert "Is this the distinctive test question?" in " ".join(texts) `
  - [Zeile 42](../../../tests/test_og_image.py#L42): ` assert "71" in texts and "/100 agreement" in texts `
  - [Zeile 43](../../../tests/test_og_image.py#L43): ` assert any("3 AI models" in text for text in texts) `
  - [Zeile 44](../../../tests/test_og_image.py#L44): ` assert any("2 contradictions" in text for text in texts) `
  - [Zeile 47](../../../tests/test_og_image.py#L47): ` assert len(image.crop(box).getcolors(1_000_000)) > 20 `
  - [Zeile 53](../../../tests/test_og_image.py#L53): ` assert ImageChops.difference( `

<a id="watch-01"></a>

## WATCH-01 · Watch-Erstellung und Planrechte

Watches sind ownergebunden, quota-/tierbegrenzt und verwenden konsistente Baseline-/Publisherlineage. Updates/Löschen dürfen fremde Watches und quittierte Löschbereiche nicht verändern.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Native Ownerlimits und echte HTTP-PATCH/DELETE-Guards; äußere Auth-/Providergrenzen kontrolliert.

**Befunde:** [G-013](gaps.md#g-013), [G-027](gaps.md#g-027). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/watch.py](../../../app/api/routers/watch.py)
- [app/services/watch_service.py](../../../app/services/watch_service.py)

**Testdateien:**

- [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)
- [tests/test_plus_tier.py](../../../tests/test_plus_tier.py)
- [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)
- [tests/test_watch_http_contract.py](../../../tests/test_watch_http_contract.py)

</details>

**Konkrete Teilbelege:**

- [WatchCrudTests::test_pause_delete_and_resume_keep_owner_counter_consistent](../../../tests/test_watch_feature.py#L413) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. **Datei**status vom 2026-10-02: passed=157.
  - [Zeile 423](../../../tests/test_watch_feature.py#L423): ` self.assertEqual(state_store["quota"]["active_count"], 2) `
  - [Zeile 428](../../../tests/test_watch_feature.py#L428): ` self.assertEqual(state_store["quota"]["active_count"], 1) `
  - [Zeile 432](../../../tests/test_watch_feature.py#L432): ` self.assertEqual(state_store["quota"]["active_count"], 2) `
  - [Zeile 434](../../../tests/test_watch_feature.py#L434): ` self.assertEqual(state_store["quota"]["active_count"], 1) `
- [test_two_workers_cannot_exceed_owner_watch_limit](../../../tests/e2e/test_phase2_transactions.py#L29) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 71](../../../tests/e2e/test_phase2_transactions.py#L71): ` assert sorted(code for code, _watch_id in outcomes) == [ `
  - [Zeile 78](../../../tests/e2e/test_phase2_transactions.py#L78): ` assert len(watches) == 1 `
  - [Zeile 83](../../../tests/e2e/test_phase2_transactions.py#L83): ` assert state["active_count"] == 1 `
- [test_watch_patch_delete_entitlement_owner_and_allowlist](../../../tests/test_watch_http_contract.py#L42) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=13.
  - [Zeile 52](../../../tests/test_watch_http_contract.py#L52): ` assert response.status_code == status, response.text `
  - [Zeile 53](../../../tests/test_watch_http_contract.py#L53): ` assert ( `
  - [Zeile 60](../../../tests/test_watch_http_contract.py#L60): ` assert response.status_code == 200, response.text `
  - [Zeile 62](../../../tests/test_watch_http_contract.py#L62): ` assert stored["status"] == response.json()["watch"]["status"] == "paused" `
  - [Zeile 63](../../../tests/test_watch_http_contract.py#L63): ` assert stored["interval"] == "monthly" `
  - [Zeile 64](../../../tests/test_watch_http_contract.py#L64): ` assert h.client.delete(h.url, headers=login("stranger")).status_code == 403 `

<a id="watch-02"></a>

## WATCH-02 · Zeitplan, Claim und Ausführung

Slots, ownergebundene Workerleases und Konfigurationsgenerationen schützen Pause/Resume/Terminwechsel vor späten Ergebnissen. Aktueller Tarif/Modellplan, Fehlerstatus und belegbasierte Ergebnisannahme bestimmen Lauf und nächste Prüfung; Outbox hält die Zustellabsicht fest.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Native Duequery/Claim-/Budget-/Stale-Fences und echte Schedulerabläufe; Uhrwartepunkt und kostenpflichtige Pipelinegrenze kontrolliert, keine produktive Lastgarantie.

**Befunde:** [G-031](gaps.md#g-031). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/drift_signal.py](../../../app/services/drift_signal.py)
- [app/services/opinion_map.py](../../../app/services/opinion_map.py)
- [app/services/watch_scheduler.py](../../../app/services/watch_scheduler.py)
- [app/services/watch_service.py](../../../app/services/watch_service.py)

**Testdateien:**

- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/e2e/test_scheduler_transactions.py](../../../tests/e2e/test_scheduler_transactions.py)
- [tests/e2e/test_watch_delivery_transactions.py](../../../tests/e2e/test_watch_delivery_transactions.py)
- [tests/test_drift_signal.py](../../../tests/test_drift_signal.py)
- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)
- [tests/test_unscored_history.py](../../../tests/test_unscored_history.py)
- [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

</details>

**Konkrete Teilbelege:**

- [SchedulerSafetyTests::test_stale_run_cannot_complete_or_fail_newer_claim](../../../tests/test_watch_feature.py#L1124) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. **Datei**status vom 2026-10-02: passed=157.
  - [Zeile 1148](../../../tests/test_watch_feature.py#L1148): ` self.assertIsNone( `
  - [Zeile 1151](../../../tests/test_watch_feature.py#L1151): ` self.assertIsNone(watch_service.fail_watch_run("w1", claimed, db=db)) `
  - [Zeile 1152](../../../tests/test_watch_feature.py#L1152): ` self.assertEqual(db.stores["watches"]["w1"]["current_run_id"], "new-run") `
  - [Zeile 1153](../../../tests/test_watch_feature.py#L1153): ` self.assertEqual(db.stores[f"shares/{share_id}/watch_history"], {}) `
- [test_native_due_queries_and_topic_claim_fence](../../../tests/e2e/test_scheduler_transactions.py#L21) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 33](../../../tests/e2e/test_scheduler_transactions.py#L33): ` assert group[0].id in result and all(ref.id not in result for ref in group[1:]) `
  - [Zeile 39](../../../tests/e2e/test_scheduler_transactions.py#L39): ` assert exc.code == "conflict" `
  - [Zeile 42](../../../tests/e2e/test_scheduler_transactions.py#L42): ` assert sum(value is not None for value in values) == 1 `
  - [Zeile 46](../../../tests/e2e/test_scheduler_transactions.py#L46): ` assert not topics.fail_topic_run(ref.id, "late failure", now=later, db=db, expected_claim_id=old["current_run_id"]) `
  - [Zeile 47](../../../tests/e2e/test_scheduler_transactions.py#L47): ` assert ref.get().to_dict() == before `
  - [Zeile 48](../../../tests/e2e/test_scheduler_transactions.py#L48): ` assert fresh["current_run_id"] != old["current_run_id"] `
- [test_native_outbox_claim_takeover_rejects_stale_ack_and_terminal_replay](../../../tests/e2e/test_watch_delivery_transactions.py#L8) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 15](../../../tests/e2e/test_watch_delivery_transactions.py#L15): ` assert sum(claim is not None for claim in claims) == 1 `
  - [Zeile 20](../../../tests/e2e/test_watch_delivery_transactions.py#L20): ` assert current["lease_owner"] != old["lease_owner"] `
  - [Zeile 21](../../../tests/e2e/test_watch_delivery_transactions.py#L21): ` assert not outbox.finish(ref.id, old["lease_owner"], outbox.SENT, now=later, db=db) `
  - [Zeile 22](../../../tests/e2e/test_watch_delivery_transactions.py#L22): ` assert ref.get().to_dict() == before `
  - [Zeile 23](../../../tests/e2e/test_watch_delivery_transactions.py#L23): ` assert outbox.finish(ref.id, current["lease_owner"], outbox.SENT, now=later, db=db) `
  - [Zeile 24](../../../tests/e2e/test_watch_delivery_transactions.py#L24): ` assert outbox.claim(ref.id, now=later + timedelta(days=1), db=db) is None `
- [test_j04_app_share_follow_watch_versions_bind_to_saved_native_result](../../../tests/e2e/test_persisted_journeys.py#L261) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 268](../../../tests/e2e/test_persisted_journeys.py#L268): ` j.page.wait_for_function('() => window.__consensioAuthState?.known && window.openBookmark') `
  - [Zeile 274](../../../tests/e2e/test_persisted_journeys.py#L274): ` assert published.value.ok, published.value.text() `
  - [Zeile 278](../../../tests/e2e/test_persisted_journeys.py#L278): ` assert pending['owner_uid'] == j.uid and 'Mock consensus' in pending['consensus_md'] `
  - [Zeile 279](../../../tests/e2e/test_persisted_journeys.py#L279): ` assert native['global_owned']['shares'][share['share_id']]['data']['owner_uid'] == j.uid `
  - [Zeile 282](../../../tests/e2e/test_persisted_journeys.py#L282): ` assert wid_response.ok, wid_response.text() `
  - [Zeile 284](../../../tests/e2e/test_persisted_journeys.py#L284): ` assert j.request('DELETE', '/api/share/' + share['share_id'], {}, uid='journey-'+'f'*32).status == 403 `

<a id="watch-03"></a>

## WATCH-03 · E-Mail-Follow mit Einwilligungsnachweis

Follow wird erst nach atomar konsumierter Challenge aktiv; Rate-/Resendlimits, Delivery-ID und signierte Unsubscribe verhindern Duplikate und fremde Abmeldung. Löschung invalidiert alte Challenges.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Mailtransport ersetzt, kein echter Zustellnachweis; Challenge- und Send-Effekt getrennt.

**Befunde:** [G-013](gaps.md#g-013). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/watch.py](../../../app/api/routers/watch.py)
- [app/services/follow_challenges.py](../../../app/services/follow_challenges.py)
- [app/services/mailer.py](../../../app/services/mailer.py)
- [app/services/watch_followers.py](../../../app/services/watch_followers.py)

**Testdateien:**

- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)
- [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)
- [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)
- [tests/test_watch_http_contract.py](../../../tests/test_watch_http_contract.py)

</details>

**Konkrete Teilbelege:**

- [FollowerTests::test_cleanup_or_removed_watch_invalidates_outstanding_confirm_link](../../../tests/test_watch_feature.py#L2967) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. **Datei**status vom 2026-10-02: passed=157.
  - [Zeile 2970](../../../tests/test_watch_feature.py#L2970): ` self.assertTrue(pending["token"]) `
  - [Zeile 2975](../../../tests/test_watch_feature.py#L2975): ` with self.assertRaisesRegex(WatchError, "invalid or expired"): `
  - [Zeile 2977](../../../tests/test_watch_feature.py#L2977): ` self.assertEqual(self.db.stores[watch_followers.FOLLOWERS_COLLECTION], {}) `
  - [Zeile 2981](../../../tests/test_watch_feature.py#L2981): ` with self.assertRaisesRegex(WatchError, "no Consensus Watch"): `
  - [Zeile 2983](../../../tests/test_watch_feature.py#L2983): ` self.assertEqual(self.db.stores[watch_followers.FOLLOWERS_COLLECTION], {}) `
- [test_watch_patch_delete_entitlement_owner_and_allowlist](../../../tests/test_watch_http_contract.py#L42) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=13.
  - [Zeile 52](../../../tests/test_watch_http_contract.py#L52): ` assert response.status_code == status, response.text `
  - [Zeile 53](../../../tests/test_watch_http_contract.py#L53): ` assert ( `
  - [Zeile 60](../../../tests/test_watch_http_contract.py#L60): ` assert response.status_code == 200, response.text `
  - [Zeile 62](../../../tests/test_watch_http_contract.py#L62): ` assert stored["status"] == response.json()["watch"]["status"] == "paused" `
  - [Zeile 63](../../../tests/test_watch_http_contract.py#L63): ` assert stored["interval"] == "monthly" `
  - [Zeile 64](../../../tests/test_watch_http_contract.py#L64): ` assert h.client.delete(h.url, headers=login("stranger")).status_code == 403 `
- [test_j04_app_share_follow_watch_versions_bind_to_saved_native_result](../../../tests/e2e/test_persisted_journeys.py#L261) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 268](../../../tests/e2e/test_persisted_journeys.py#L268): ` j.page.wait_for_function('() => window.__consensioAuthState?.known && window.openBookmark') `
  - [Zeile 274](../../../tests/e2e/test_persisted_journeys.py#L274): ` assert published.value.ok, published.value.text() `
  - [Zeile 278](../../../tests/e2e/test_persisted_journeys.py#L278): ` assert pending['owner_uid'] == j.uid and 'Mock consensus' in pending['consensus_md'] `
  - [Zeile 279](../../../tests/e2e/test_persisted_journeys.py#L279): ` assert native['global_owned']['shares'][share['share_id']]['data']['owner_uid'] == j.uid `
  - [Zeile 282](../../../tests/e2e/test_persisted_journeys.py#L282): ` assert wid_response.ok, wid_response.text() `
  - [Zeile 284](../../../tests/e2e/test_persisted_journeys.py#L284): ` assert j.request('DELETE', '/api/share/' + share['share_id'], {}, uid='journey-'+'f'*32).status == 403 `

<a id="watch-04"></a>

## WATCH-04 · Telegram-Link und Zustellung

Secret-Webhook, einmaliger Linktoken und Ownerbindung schützen Verbindung/Aktionen; wiederholte Updates/Sendversuche erzeugen keine Doppelaktionen, Löschung entfernt Verknüpfungen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Registrierte Link/Test/Disconnectadapter einschließlich Fremdowner und Nichtversand ohne Verbindung; Telegramtransport kontrolliert.

**Befunde:** [G-013](gaps.md#g-013). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/watch.py](../../../app/api/routers/watch.py)
- [app/services/mailer.py](../../../app/services/mailer.py)
- [app/services/telegram_watch.py](../../../app/services/telegram_watch.py)

**Testdateien:**

- [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)
- [tests/test_watch_http_contract.py](../../../tests/test_watch_http_contract.py)

</details>

**Konkrete Teilbelege:**

- [WatchCrudTests::test_free_create_list_update_pause_delete](../../../tests/test_watch_feature.py#L177) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. **Datei**status vom 2026-10-02: passed=157.
  - [Zeile 179](../../../tests/test_watch_feature.py#L179): ` self.assertEqual(created["status"], "active") `
  - [Zeile 180](../../../tests/test_watch_feature.py#L180): ` self.assertEqual(created["email_mode"], "changes_only") `
  - [Zeile 181](../../../tests/test_watch_feature.py#L181): ` self.assertTrue(created["email_enabled"]) `
  - [Zeile 182](../../../tests/test_watch_feature.py#L182): ` self.assertFalse(created["telegram_enabled"]) `
  - [Zeile 183](../../../tests/test_watch_feature.py#L183): ` self.assertEqual(created["last_agreement_score"], 60) `
  - [Zeile 184](../../../tests/test_watch_feature.py#L184): ` self.assertEqual(created["baseline_agreement_score"], 60) `
- [test_watch_patch_delete_entitlement_owner_and_allowlist](../../../tests/test_watch_http_contract.py#L42) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=13.
  - [Zeile 52](../../../tests/test_watch_http_contract.py#L52): ` assert response.status_code == status, response.text `
  - [Zeile 53](../../../tests/test_watch_http_contract.py#L53): ` assert ( `
  - [Zeile 60](../../../tests/test_watch_http_contract.py#L60): ` assert response.status_code == 200, response.text `
  - [Zeile 62](../../../tests/test_watch_http_contract.py#L62): ` assert stored["status"] == response.json()["watch"]["status"] == "paused" `
  - [Zeile 63](../../../tests/test_watch_http_contract.py#L63): ` assert stored["interval"] == "monthly" `
  - [Zeile 64](../../../tests/test_watch_http_contract.py#L64): ` assert h.client.delete(h.url, headers=login("stranger")).status_code == 403 `

<a id="watch-05"></a>

## WATCH-05 · Morning Brief

Brief bündelt fällige Inhalte nach lokaler Zeit. Der persistente Claim rückt den Zeitplan vor dem Versand vor (At-most-once-Versuch); eine separate deduplizierte Versand-ID existiert in diesem Pfad nicht. Unsubscribe deaktiviert den passenden Brief.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Claim-/Mailerfakes, kein realer Zustellnachweis. Ein Crash nach dem Vorabclaim kann einen Brief auslassen; keine atomare Garantie über Datenbank und externen Mailversand (D-03).

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/watch.py](../../../app/api/routers/watch.py)
- [app/services/mailer.py](../../../app/services/mailer.py)
- [app/services/watch_brief.py](../../../app/services/watch_brief.py)
- [app/services/watch_scheduler.py](../../../app/services/watch_scheduler.py)

**Testdateien:**

- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)
- [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

</details>

**Konkrete Teilbelege:**

- [BriefClaimTests::test_claim_advances_before_sending_and_prevents_double_send](../../../tests/test_watch_feature.py#L2433) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. **Datei**status vom 2026-10-02: passed=157.
  - [Zeile 2435](../../../tests/test_watch_feature.py#L2435): ` self.assertIsNotNone(claimed) `
  - [Zeile 2436](../../../tests/test_watch_feature.py#L2436): ` self.assertEqual(claimed["baseline"], self.now - timedelta(days=3)) `
  - [Zeile 2437](../../../tests/test_watch_feature.py#L2437): ` self.assertGreater(self.store["u1"]["next_send_at"], self.now) `
  - [Zeile 2438](../../../tests/test_watch_feature.py#L2438): ` self.assertEqual(self.store["u1"]["last_evaluated_at"], self.now) `
  - [Zeile 2439](../../../tests/test_watch_feature.py#L2439): ` self.assertIsNone(watch_brief._claim_in_transaction(FakeTransaction(), self.ref, self.now)) `

<a id="watch-06"></a>

## WATCH-06 · Watch-Frontend

Dashboard lädt eigene Metadaten/History und autoritative Limitwerte, Modals erhalten Fokus/Scrollzustand, Konto-/Ansichtswechsel verwirft verspätete Daten. Driftanzeige folgt derselben Regel wie Backend.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** JS teils ausgeschnittene Funktionen, Browser-APIs ersetzt; zentrale Create/Update/Delete-Verkabelung nicht Ende-zu-Ende belegt.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/js/share-dialog.js](../../../static/js/share-dialog.js)
- [static/js/watch-state.js](../../../static/js/watch-state.js)
- [static/js/watch.js](../../../static/js/watch.js)

**Testdateien:**

- [tests/e2e/test_mobile_navigation.py](../../../tests/e2e/test_mobile_navigation.py)
- [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py)
- [tests/js/source-verification-watch.test.mjs](../../../tests/js/source-verification-watch.test.mjs)
- [tests/js/watch-feature-nudge.test.mjs](../../../tests/js/watch-feature-nudge.test.mjs)
- [tests/test_phase4_frontend.py](../../../tests/test_phase4_frontend.py)

</details>

**Konkrete Teilbelege:**

- [test_usage_countdown_tracks_utc_midnight_and_refreshes_server_state](../../../tests/test_phase4_frontend.py#L27) — Quelltextverträge. **Datei**status vom 2026-10-02: passed=14.
  - [Zeile 31](../../../tests/test_phase4_frontend.py#L31): ` assert "getUTCFullYear()" in countdown `
  - [Zeile 32](../../../tests/test_phase4_frontend.py#L32): ` assert "Date.UTC(" in countdown `
  - [Zeile 33](../../../tests/test_phase4_frontend.py#L33): ` assert "window.refreshUsageData?.()" in countdown `
  - [Zeile 34](../../../tests/test_phase4_frontend.py#L34): ` assert "usageRefreshTargetUtcDay" in countdown `
  - [Zeile 35](../../../tests/test_phase4_frontend.py#L35): ` assert "refreshed === true" in countdown `
  - [Zeile 36](../../../tests/test_phase4_frontend.py#L36): ` assert "location.reload()" not in countdown `

<a id="topic-01"></a>

## TOPIC-01 · Topic-Administration und versionierte Runs

Adminrechte, Slugreservierung, Archive/Indexing und unveränderliche Runversionen schützen Topics; atomare Pointerwrites akzeptieren nur den aktuellen Claim.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Echte Adminmethoden/Revocation/Tierfehler und native Claims ergänzen lokale Versionstests; kostenpflichtige Pipelineantworten ersetzt.

**Befunde:** [G-014](gaps.md#g-014), [G-031](gaps.md#g-031), [G-041](gaps.md#g-041). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/topics.py](../../../app/api/routers/topics.py)
- [app/services/topics.py](../../../app/services/topics.py)

**Testdateien:**

- [tests/e2e/test_scheduler_transactions.py](../../../tests/e2e/test_scheduler_transactions.py)
- [tests/js/admin-topic-editor.test.mjs](../../../tests/js/admin-topic-editor.test.mjs)
- [tests/test_http_adapter_auth.py](../../../tests/test_http_adapter_auth.py)
- [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

</details>

**Konkrete Teilbelege:**

- [test_topic_run_and_latest_pointer_commit_or_fail_together](../../../tests/test_topics_feature.py#L421) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. **Datei**status vom 2026-10-02: passed=65.
  - [Zeile 427](../../../tests/test_topics_feature.py#L427): ` with pytest.raises(RuntimeError, match="injected transaction failure"): `
  - [Zeile 432](../../../tests/test_topics_feature.py#L432): ` assert db.documents[("topics", topic["id"])] == before `
  - [Zeile 433](../../../tests/test_topics_feature.py#L433): ` assert not any( `
- [test_native_due_queries_and_topic_claim_fence](../../../tests/e2e/test_scheduler_transactions.py#L21) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 33](../../../tests/e2e/test_scheduler_transactions.py#L33): ` assert group[0].id in result and all(ref.id not in result for ref in group[1:]) `
  - [Zeile 39](../../../tests/e2e/test_scheduler_transactions.py#L39): ` assert exc.code == "conflict" `
  - [Zeile 42](../../../tests/e2e/test_scheduler_transactions.py#L42): ` assert sum(value is not None for value in values) == 1 `
  - [Zeile 46](../../../tests/e2e/test_scheduler_transactions.py#L46): ` assert not topics.fail_topic_run(ref.id, "late failure", now=later, db=db, expected_claim_id=old["current_run_id"]) `
  - [Zeile 47](../../../tests/e2e/test_scheduler_transactions.py#L47): ` assert ref.get().to_dict() == before `
  - [Zeile 48](../../../tests/e2e/test_scheduler_transactions.py#L48): ` assert fresh["current_run_id"] != old["current_run_id"] `
- [test_every_topic_admin_method_enforces_real_policy_before_service](../../../tests/test_http_adapter_auth.py#L29) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=38.
  - [Zeile 43](../../../tests/test_http_adapter_auth.py#L43): ` assert response.status_code == expected, response.text `
  - [Zeile 44](../../../tests/test_http_adapter_auth.py#L44): ` assert "error" in response.json() and "private" not in response.text `
  - [Zeile 45](../../../tests/test_http_adapter_auth.py#L45): ` assert database.documents == {} and database.query_reads == [] `
  - [Zeile 47](../../../tests/test_http_adapter_auth.py#L47): ` assert h.checks[-1][1]["check_revoked"] is True `

<a id="topic-02"></a>

## TOPIC-02 · Topic-Pipeline und Identitätsjudge

Die neutrale Pipeline erzeugt neue Topicruns, vorhandene Claimidentitäten werden nur aus erlaubten Keys/Indices übernommen; ein fehlerhafter Identity-Judge darf den Run nicht verhindern.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Echter Identityparser und begrenzter Retryplan mit synthetischen Modellantworten; JSON-Integer strikt, keine Liveclaim-Qualitätsmessung.

**Befunde:** [G-016](gaps.md#g-016). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/llm/consensus_engine.py](../../../app/services/llm/consensus_engine.py)
- [app/services/topic_pipeline.py](../../../app/services/topic_pipeline.py)
- [app/services/topic_runner.py](../../../app/services/topic_runner.py)

**Testdateien:**

- [tests/test_claim_identity_judge.py](../../../tests/test_claim_identity_judge.py)
- [tests/test_maintenance_scripts.py](../../../tests/test_maintenance_scripts.py)
- [tests/test_source_check_scope.py](../../../tests/test_source_check_scope.py)
- [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

</details>

**Konkrete Teilbelege:**

- [test_claim_identity_falls_back_to_fresh_keys_when_the_judge_is_unavailable](../../../tests/test_topics_feature.py#L1098) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. **Datei**status vom 2026-10-02: passed=65.
  - [Zeile 1116](../../../tests/test_topics_feature.py#L1116): ` assert [item["key"] for item in position_map["dimensions"]] == ["run-7-0", "run-7-1"] `
- [test_repair_inspect_does_not_apply_but_selected_account_recovery_does](../../../tests/test_maintenance_scripts.py#L114) — Echte Entry-Points in isolierten Subprozessen. **Datei**status vom 2026-10-02: passed=13.
  - [Zeile 116](../../../tests/test_maintenance_scripts.py#L116): ` assert inspected['codes'] == [0] `
  - [Zeile 117](../../../tests/test_maintenance_scripts.py#L117): ` assert inspected['events'] == [['lookup','selected@example.invalid'], ['read','selected-account'], ['close']] `
  - [Zeile 119](../../../tests/test_maintenance_scripts.py#L119): ` assert applied['codes'] == [0] `
  - [Zeile 120](../../../tests/test_maintenance_scripts.py#L120): ` assert [e for e in applied['events'] if e[0] == 'recover'] == [['recover','selected-account']] `
- [test_known_unique_bindings_only](../../../tests/test_claim_identity_judge.py#L19) — Echter Identityhelper, Parser und Retryplan mit Transportdouble. **Datei**status vom 2026-10-02: passed=14.
  - [Zeile 33](../../../tests/test_claim_identity_judge.py#L33): ` assert result == {0: "k1", 1: "k2"} `
  - [Zeile 34](../../../tests/test_claim_identity_judge.py#L34): ` assert call.call_count == 1 `

<a id="topic-03"></a>

## TOPIC-03 · Zeitlicher Claim-/Quellenverlauf

Neue Belege, reine Wiederbewertung, Modellwechsel und fehlende Messung bleiben getrennt. Held-Runs widerrufen keine stehenden Claims; historische Ansichten verwenden nur damals vorhandene Daten und begrenzte Versionsfenster werden sichtbar ausgewiesen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Synthetische Identitäten und Claims; ein korrektes Ledger macht falsche LLM-Identitäten nicht fachlich richtig.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/claim_ledger.py](../../../app/services/claim_ledger.py)
- [app/services/drift_signal.py](../../../app/services/drift_signal.py)
- [app/services/history_view.py](../../../app/services/history_view.py)
- [app/services/opinion_map.py](../../../app/services/opinion_map.py)
- [app/services/topic_finding.py](../../../app/services/topic_finding.py)

**Testdateien:**

- [tests/test_claim_ledger.py](../../../tests/test_claim_ledger.py)
- [tests/test_drift_signal.py](../../../tests/test_drift_signal.py)
- [tests/test_topic_finding.py](../../../tests/test_topic_finding.py)
- [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)
- [tests/test_unscored_history.py](../../../tests/test_unscored_history.py)

</details>

**Konkrete Teilbelege:**

- [test_a_check_without_a_claim_list_is_a_gap_not_a_retirement](../../../tests/test_claim_ledger.py#L85) — Deterministische Unit-Tests. **Datei**status vom 2026-10-02: passed=21.
  - [Zeile 98](../../../tests/test_claim_ledger.py#L98): ` assert ledger["thin"] == 1 `
  - [Zeile 99](../../../tests/test_claim_ledger.py#L99): ` assert ledger["enumerated"] == 2 `
  - [Zeile 101](../../../tests/test_claim_ledger.py#L101): ` assert claim["streak"] == 2, "the gap must not break the streak" `
  - [Zeile 102](../../../tests/test_claim_ledger.py#L102): ` assert claim["appearances"] == 2 `
  - [Zeile 103](../../../tests/test_claim_ledger.py#L103): ` assert [tick["state"] for tick in claim["lifeline"]] == ["on", "gap", "on"] `
  - [Zeile 104](../../../tests/test_claim_ledger.py#L104): ` assert ledger["retired"] == [] `

<a id="topic-04"></a>

## TOPIC-04 · Öffentliche Topic-Seiten und Follow

Der öffentliche Hub enthält aktive oder pausierte Topics mit veröffentlichtem latest_run_id, auch bei noindex. Die Sitemap schließt noindex zusätzlich aus; archivierte oder unveröffentlichte Topics fehlen in beiden Listen. Versionsseiten und Evidenz-Links respektieren den jeweiligen Publikationsstand; Follow benötigt Double-opt-in, Faviconabruf ist begrenzt und prüft fremde Netzwerkziele.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** SSR und Helper belegt; Hub/Sitemap/Follow-Adapter und echter Favicon-Transport haben Ausführungsgrenzen.

**Befunde:** [G-014](gaps.md#g-014). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/topics.py](../../../app/api/routers/topics.py)
- [app/services/favicons.py](../../../app/services/favicons.py)
- [app/services/topics.py](../../../app/services/topics.py)
- [static/js/public-theme.js](../../../static/js/public-theme.js)
- [templates/topic.html](../../../templates/topic.html)
- [templates/topics.html](../../../templates/topics.html)

**Testdateien:**

- [tests/e2e/test_topic_frontend.py](../../../tests/e2e/test_topic_frontend.py)
- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)
- [tests/test_public_markdown.py](../../../tests/test_public_markdown.py)
- [tests/test_seo_basics.py](../../../tests/test_seo_basics.py)
- [tests/test_topic_public_http.py](../../../tests/test_topic_public_http.py)
- [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

</details>

**Konkrete Teilbelege:**

- [test_public_topic_history_is_ssr_and_historical_version_is_noindex](../../../tests/test_topics_feature.py#L1440) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. **Datei**status vom 2026-10-02: passed=65.
  - [Zeile 1467](../../../tests/test_topics_feature.py#L1467): ` assert current.status_code == 200 `
  - [Zeile 1468](../../../tests/test_topics_feature.py#L1468): ` assert "The <strong>current</strong> consensus moved." in current.text `
  - [Zeile 1469](../../../tests/test_topics_feature.py#L1469): ` assert current.headers["x-robots-tag"] == "index, follow" `
  - [Zeile 1470](../../../tests/test_topics_feature.py#L1470): ` assert historical.status_code == 200 `
  - [Zeile 1471](../../../tests/test_topics_feature.py#L1471): ` assert "No confirmed release date exists." in historical.text `
  - [Zeile 1472](../../../tests/test_topics_feature.py#L1472): ` assert historical.headers["x-robots-tag"] == "noindex, follow" `
- [test_hub_and_sitemap_distinguish_noindex_from_archive_or_unpublished](../../../tests/test_topic_public_http.py#L34) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=10.
  - [Zeile 52](../../../tests/test_topic_public_http.py#L52): ` assert hub.status_code == sitemap.status_code == 200 `
  - [Zeile 54](../../../tests/test_topic_public_http.py#L54): ` assert "/topics/" + slug in hub.text `
  - [Zeile 56](../../../tests/test_topic_public_http.py#L56): ` assert "/topics/" + slug in sitemap.text `
  - [Zeile 58](../../../tests/test_topic_public_http.py#L58): ` assert "/topics/" + slug not in hub.text + sitemap.text `
  - [Zeile 59](../../../tests/test_topic_public_http.py#L59): ` assert "/topics/noindex-topic" not in sitemap.text `
  - [Zeile 61](../../../tests/test_topic_public_http.py#L61): ` assert "<img src=x onerror=" not in body and "&lt;img" in body `
- [test_topic_markup_stays_text_and_preview_preserves_navigation](../../../tests/e2e/test_topic_frontend.py#L33) — Chromium mit Originalskript und kontrollierter SSR-Minimalfixture. **Datei**status vom 2026-10-02: passed=5.
  - [Zeile 39](../../../tests/e2e/test_topic_frontend.py#L39): ` assert '?' not in page.url  # first touch previews rather than navigating `
  - [Zeile 42](../../../tests/e2e/test_topic_frontend.py#L42): ` expect(page.locator('#topicStripRead')).to_contain_text(HOSTILE) `
  - [Zeile 43](../../../tests/e2e/test_topic_frontend.py#L43): ` expect(page.locator('#topicStripRead .topic-strip-score')).to_have_text('72/100 agreement') `
  - [Zeile 44](../../../tests/e2e/test_topic_frontend.py#L44): ` expect(page.locator('#injected, #topicStripRead img')).to_have_count(0) `
  - [Zeile 45](../../../tests/e2e/test_topic_frontend.py#L45): ` assert page.evaluate('window.__injected') is None `
  - [Zeile 50](../../../tests/e2e/test_topic_frontend.py#L50): ` expect(page).to_have_url('https://topics.test/topics/example?version=new') `

<a id="topic-05"></a>

## TOPIC-05 · Interaktiver Check-Strip

Hover/Fokus zeigt den gewählten historischen Check, Touch trennt Vorschau und Navigation. Wiederkehrende Leser sehen neue Checks; historische Versionen markieren neuere Checks nicht als gelesen. Notiztext bleibt Text.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_and_inferred_rendering_invariant `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Tests prüfen SSR-Marker und vorbereitete Daten; keine Ausführung des Topic-Frontendmoduls.

**Befunde:** [G-018](gaps.md#g-018). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/claim_ledger.py](../../../app/services/claim_ledger.py)
- [static/js/topic-page.js](../../../static/js/topic-page.js)
- [templates/topic.html](../../../templates/topic.html)

**Testdateien:**

- [tests/e2e/test_topic_frontend.py](../../../tests/e2e/test_topic_frontend.py)
- [tests/js/topic-page.test.mjs](../../../tests/js/topic-page.test.mjs)
- [tests/test_claim_ledger.py](../../../tests/test_claim_ledger.py)
- [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

</details>

**Konkrete Teilbelege:**

- [test_the_check_strip_gives_every_check_one_cell_and_a_reason](../../../tests/test_claim_ledger.py#L395) — Deterministische Unit-Tests. **Datei**status vom 2026-10-02: passed=21.
  - [Zeile 409](../../../tests/test_claim_ledger.py#L409): ` assert [cell["kind"] for cell in strip] == ["first", "stable", "material", "event"] `
  - [Zeile 410](../../../tests/test_claim_ledger.py#L410): ` assert strip[0]["note"] == "First check. The record starts here." `
  - [Zeile 411](../../../tests/test_claim_ledger.py#L411): ` assert strip[2]["note"] == "A rumoured window entered the answer." `
  - [Zeile 413](../../../tests/test_claim_ledger.py#L413): ` assert "entered" in strip[3]["note"] and "dropped out" in strip[3]["note"] `
  - [Zeile 414](../../../tests/test_claim_ledger.py#L414): ` assert strip[-1]["is_latest"] is True `
  - [Zeile 415](../../../tests/test_claim_ledger.py#L415): ` assert [cell["is_latest"] for cell in strip[:-1]] == [False, False, False] `
- [test_topic_markup_stays_text_and_preview_preserves_navigation](../../../tests/e2e/test_topic_frontend.py#L33) — Chromium mit Originalskript und kontrollierter SSR-Minimalfixture. **Datei**status vom 2026-10-02: passed=5.
  - [Zeile 39](../../../tests/e2e/test_topic_frontend.py#L39): ` assert '?' not in page.url  # first touch previews rather than navigating `
  - [Zeile 42](../../../tests/e2e/test_topic_frontend.py#L42): ` expect(page.locator('#topicStripRead')).to_contain_text(HOSTILE) `
  - [Zeile 43](../../../tests/e2e/test_topic_frontend.py#L43): ` expect(page.locator('#topicStripRead .topic-strip-score')).to_have_text('72/100 agreement') `
  - [Zeile 44](../../../tests/e2e/test_topic_frontend.py#L44): ` expect(page.locator('#injected, #topicStripRead img')).to_have_count(0) `
  - [Zeile 45](../../../tests/e2e/test_topic_frontend.py#L45): ` assert page.evaluate('window.__injected') is None `
  - [Zeile 50](../../../tests/e2e/test_topic_frontend.py#L50): ` expect(page).to_have_url('https://topics.test/topics/example?version=new') `

<a id="seo-01"></a>

## SEO-01 · Search-Console-Erfassung

Read-only Credentials und begrenzte paginierte Erfassung liefern finale Zeiträume; Truncation/fehlende Daten werden nicht als echte Nullen gespeichert, wiederholte Tage bleiben idempotent.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Keine GSC-Integration; Erfassung gegen Repository-Double, Entdeckung der tatsächlich indexierbaren Ressourcen separat.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/google_search_console.py](../../../app/services/google_search_console.py)
- [app/services/seo_data.py](../../../app/services/seo_data.py)

**Testdateien:**

- [tests/test_seo_data.py](../../../tests/test_seo_data.py)

</details>

**Konkrete Teilbelege:**

- [test_truncated_ranges_do_not_persist_omitted_rows_as_zeroes](../../../tests/test_seo_data.py#L251) — GSC-/Repository-/Recommendation-/Router-Integration mit Service-/HTTP-/DB-Doubles; UI-Sourceverträge. **Datei**status vom 2026-10-02: passed=39.
  - [Zeile 269](../../../tests/test_seo_data.py#L269): ` assert result["status"] == "partial" `
  - [Zeile 270](../../../tests/test_seo_data.py#L270): ` assert result["days_requested"] == 90 `
  - [Zeile 271](../../../tests/test_seo_data.py#L271): ` assert result["days_collected"] == 0 `
  - [Zeile 273](../../../tests/test_seo_data.py#L273): ` assert len(metric_paths) == 1 `
  - [Zeile 274](../../../tests/test_seo_data.py#L274): ` assert metric_paths[0][-1] == "2026-07-17" `

<a id="seo-02"></a>

## SEO-02 · SEO-Repository und Dossiers

Seitengruppen, Zeiträume und neueste Läufe werden deterministisch, begrenzt und ohne sensible Querydetails gelesen; Dossiers trennen beobachtete Kennzahlen von Empfehlungen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** BatchGet-/Queryadapter mit ungeordneten/fehlenden Snapshots sowie echten nativen Rückgaben; keine Search-Console-Livemessung.

**Befunde:** [G-017](gaps.md#g-017). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/seo_data.py](../../../app/services/seo_data.py)
- [app/services/seo_dossier.py](../../../app/services/seo_dossier.py)
- [app/services/seo_repository.py](../../../app/services/seo_repository.py)

**Testdateien:**

- [tests/e2e/test_seo_repository_queries.py](../../../tests/e2e/test_seo_repository_queries.py)
- [tests/test_seo_data.py](../../../tests/test_seo_data.py)
- [tests/test_seo_repository.py](../../../tests/test_seo_repository.py)
- [tests/test_seo_weekly_review.py](../../../tests/test_seo_weekly_review.py)

</details>

**Konkrete Teilbelege:**

- [test_share_dossier_keeps_only_a_bounded_representation](../../../tests/test_seo_data.py#L774) — GSC-/Repository-/Recommendation-/Router-Integration mit Service-/HTTP-/DB-Doubles; UI-Sourceverträge. **Datei**status vom 2026-10-02: passed=39.
  - [Zeile 798](../../../tests/test_seo_data.py#L798): ` assert len(dossier["content_representation"]) <= seo_dossier.MAX_SHARE_CONTENT_REPRESENTATION_CHARS `
  - [Zeile 799](../../../tests/test_seo_data.py#L799): ` assert dossier["source_freshness"]["source_count"] == 1 `
  - [Zeile 800](../../../tests/test_seo_data.py#L800): ` assert dossier["watch_freshness"]["last_checked_at"] == checked.isoformat() `
  - [Zeile 801](../../../tests/test_seo_data.py#L801): ` assert dossier["last_content_change_at"] == changed.isoformat() `
  - [Zeile 802](../../../tests/test_seo_data.py#L802): ` assert dossier["technical_uncertainties"] == [] `
- [test_batch_get_binds_document_identity_and_dates_not_position_or_payload](../../../tests/test_seo_repository.py#L9) — Echter Repositoryadapter mit kontrollierten SDK-Snapshots. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 26](../../../tests/test_seo_repository.py#L26): ` assert db.get_all_calls == [400, 215] `
  - [Zeile 27](../../../tests/test_seo_repository.py#L27): ` assert ( `
  - [Zeile 30](../../../tests/test_seo_repository.py#L30): ` assert result["a"][0] == {"clicks": 1, "page_id": "a", "date": "2026-01-02"} `
  - [Zeile 31](../../../tests/test_seo_repository.py#L31): ` assert result["b"][-1] == {"clicks": 1204, "page_id": "b", "date": "2026-07-24"} `
  - [Zeile 32](../../../tests/test_seo_repository.py#L32): ` assert FirestoreSeoRepository(db).list_metrics_for_pages([], start, start) == {} `
  - [Zeile 33](../../../tests/test_seo_repository.py#L33): ` assert db.get_all_calls == [400, 215] `
- [test_seo_native_latest_judgments_and_unordered_batch_identity](../../../tests/e2e/test_seo_repository_queries.py#L8) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=1.
  - [Zeile 30](../../../tests/e2e/test_seo_repository_queries.py#L30): ` assert data == { `
  - [Zeile 35](../../../tests/e2e/test_seo_repository_queries.py#L35): ` assert repo.last_run() is None `
  - [Zeile 45](../../../tests/e2e/test_seo_repository_queries.py#L45): ` assert repo.last_run()["run_id"] == "3" `
  - [Zeile 46](../../../tests/e2e/test_seo_repository_queries.py#L46): ` assert repo.latest_query_snapshot("a")["snapshot_id"] == "3" `
  - [Zeile 47](../../../tests/e2e/test_seo_repository_queries.py#L47): ` assert [ `

<a id="seo-03"></a>

## SEO-03 · Konservative Empfehlungen und Aktionen

Deterministische Evidenzgates schützen Gewinner/Graceperiod; Content-Judge umgeht keine Regeln. Preview und Apply unterscheiden sich, Teilfehler bleiben sichtbar und Briefannahme prüft Konflikte.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** LLM/Indexing/Watch-Aktionen ersetzt; reale SEO-Wirkung nicht messbar durch diese Suite.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/admin.py](../../../app/api/routers/admin.py)
- [app/services/seo_recommendation.py](../../../app/services/seo_recommendation.py)
- [app/services/seo_weekly_review.py](../../../app/services/seo_weekly_review.py)

**Testdateien:**

- [tests/js/seo-admin-alerts.test.mjs](../../../tests/js/seo-admin-alerts.test.mjs)
- [tests/test_seo_data.py](../../../tests/test_seo_data.py)
- [tests/test_seo_weekly_review.py](../../../tests/test_seo_weekly_review.py)

</details>

**Konkrete Teilbelege:**

- [test_apply_all_never_includes_delete_and_delete_requires_publisher_lineage](../../../tests/test_seo_weekly_review.py#L575) — Review-Service mit Repository-/Judge-/Action-Doubles. **Datei**status vom 2026-10-02: passed=20.
  - [Zeile 578](../../../tests/test_seo_weekly_review.py#L578): ` assert service.apply(RUN_ID, admin_uid="admin", apply_all=True)["results"] == [] `
  - [Zeile 579](../../../tests/test_seo_weekly_review.py#L579): ` assert deleted == [] `
  - [Zeile 584](../../../tests/test_seo_weekly_review.py#L584): ` assert result["results"][0]["status"] == "error" `
  - [Zeile 585](../../../tests/test_seo_weekly_review.py#L585): ` assert deleted == [] `
  - [Zeile 589](../../../tests/test_seo_weekly_review.py#L589): ` assert result["results"][0]["status"] == "success" `
  - [Zeile 590](../../../tests/test_seo_weekly_review.py#L590): ` assert deleted == ["S" * 16] `

<a id="seo-04"></a>

## SEO-04 · Wöchentlicher Review und Publikationsdaten

Reviews folgen dem konfigurierten Intervall von 1–90 Tagen (Default 7) samt lokaler Uhrzeit/Zeitzone; eine persistente Lease schützt vor konkurrierenden Läufen. Manuell erzwungene Läufe umgehen die Fälligkeitsprüfung, nicht die Lease. Datenportfolio und Prompt sind begrenzt; Benachrichtigung und manuelle Entscheidungen sind nachvollziehbar und wiederholbar.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Echter SEOloop mit nativer Lease, persistiertem externem Collectionfehler/Benachrichtigungsstatus und Cancellation; Collector/Notifier außen kontrolliert, kein Live-Search-Console-Nachweis.

**Befunde:** [G-017](gaps.md#g-017), [G-031](gaps.md#g-031). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/publisher_config.py](../../../app/services/publisher_config.py)
- [app/services/seo_data.py](../../../app/services/seo_data.py)
- [app/services/seo_weekly_review.py](../../../app/services/seo_weekly_review.py)

**Testdateien:**

- [tests/e2e/test_scheduler_transactions.py](../../../tests/e2e/test_scheduler_transactions.py)
- [tests/test_seo_weekly_review.py](../../../tests/test_seo_weekly_review.py)

</details>

**Konkrete Teilbelege:**

- [test_review_uses_at_most_one_portfolio_judge_call](../../../tests/test_seo_weekly_review.py#L181) — Review-Service mit Repository-/Judge-/Action-Doubles. **Datei**status vom 2026-10-02: passed=20.
  - [Zeile 184](../../../tests/test_seo_weekly_review.py#L184): ` assert result["status"] == "completed" `
  - [Zeile 185](../../../tests/test_seo_weekly_review.py#L185): ` assert judge.calls == 1 `
  - [Zeile 186](../../../tests/test_seo_weekly_review.py#L186): ` assert result["judge_called"] is True `
- [test_native_due_queries_and_topic_claim_fence](../../../tests/e2e/test_scheduler_transactions.py#L21) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 33](../../../tests/e2e/test_scheduler_transactions.py#L33): ` assert group[0].id in result and all(ref.id not in result for ref in group[1:]) `
  - [Zeile 39](../../../tests/e2e/test_scheduler_transactions.py#L39): ` assert exc.code == "conflict" `
  - [Zeile 42](../../../tests/e2e/test_scheduler_transactions.py#L42): ` assert sum(value is not None for value in values) == 1 `
  - [Zeile 46](../../../tests/e2e/test_scheduler_transactions.py#L46): ` assert not topics.fail_topic_run(ref.id, "late failure", now=later, db=db, expected_claim_id=old["current_run_id"]) `
  - [Zeile 47](../../../tests/e2e/test_scheduler_transactions.py#L47): ` assert ref.get().to_dict() == before `
  - [Zeile 48](../../../tests/e2e/test_scheduler_transactions.py#L48): ` assert fresh["current_run_id"] != old["current_run_id"] `

<a id="seo-05"></a>

## SEO-05 · Öffentliche Navigation und Suchmetadaten

SSR liefert Canonical, Robots/Sitemaps und konsistente Entität; App/Privat/Admin sind angemessen noindex. Model-Pulse zeigt dieselben Counts wie API und erhält letzten Stand bei Fehlern.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** SSR-/String-/DOM-Belege; keine tatsächliche Google-Indexierung oder semantische Richtigkeit von Rechtstexten.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/pages.py](../../../app/api/routers/pages.py)
- [app/core/seo_entity.py](../../../app/core/seo_entity.py)
- [app/core/site.py](../../../app/core/site.py)
- [static/js/model-pulse.js](../../../static/js/model-pulse.js)
- [templates/about.html](../../../templates/about.html)
- [templates/admin.html](../../../templates/admin.html)
- [templates/admin_benchmark.html](../../../templates/admin_benchmark.html)
- [templates/ai-model-comparison.html](../../../templates/ai-model-comparison.html)
- [templates/benchmark.html](../../../templates/benchmark.html)
- [templates/consensus-engine.html](../../../templates/consensus-engine.html)
- [templates/imprint.html](../../../templates/imprint.html)
- [templates/index.html](../../../templates/index.html)
- [templates/landing.html](../../../templates/landing.html)
- [templates/model-pulse.html](../../../templates/model-pulse.html)
- [templates/partials/admin_prompt_config.html](../../../templates/partials/admin_prompt_config.html)
- [templates/partials/analytics.html](../../../templates/partials/analytics.html)
- [templates/partials/composer_toolbar_mockup.html](../../../templates/partials/composer_toolbar_mockup.html)
- [templates/partials/product_result_mockup.html](../../../templates/partials/product_result_mockup.html)
- [templates/partials/public_footer.html](../../../templates/partials/public_footer.html)
- [templates/partials/public_nav.html](../../../templates/partials/public_nav.html)
- [templates/privacy.html](../../../templates/privacy.html)
- [templates/questions.html](../../../templates/questions.html)
- [templates/share.html](../../../templates/share.html)
- [templates/share_unavailable.html](../../../templates/share_unavailable.html)
- [templates/terms.html](../../../templates/terms.html)
- [templates/topic.html](../../../templates/topic.html)
- [templates/topics.html](../../../templates/topics.html)

**Testdateien:**

- [tests/js/model-pulse.test.mjs](../../../tests/js/model-pulse.test.mjs)
- [tests/test_model_leaderboard.py](../../../tests/test_model_leaderboard.py)
- [tests/test_public_design_system.py](../../../tests/test_public_design_system.py)
- [tests/test_seo_basics.py](../../../tests/test_seo_basics.py)
- [tests/test_seo_entity.py](../../../tests/test_seo_entity.py)
- [tests/test_topic_public_http.py](../../../tests/test_topic_public_http.py)

</details>

**Konkrete Teilbelege:**

- [test_pulse_failure_is_retryable_not_a_fake_zero_ranking](../../../tests/test_model_leaderboard.py#L60) — Pages/API mit FakeDb und echten lokalen Threads. **Datei**status vom 2026-10-02: passed=18.
  - [Zeile 68](../../../tests/test_model_leaderboard.py#L68): ` assert page.status_code == 503 `
  - [Zeile 69](../../../tests/test_model_leaderboard.py#L69): ` assert page.headers["cache-control"] == "no-store" `
  - [Zeile 70](../../../tests/test_model_leaderboard.py#L70): ` assert page.headers["retry-after"] == "60" `
  - [Zeile 71](../../../tests/test_model_leaderboard.py#L71): ` assert "temporarily unavailable" in page.text `
  - [Zeile 72](../../../tests/test_model_leaderboard.py#L72): ` assert 'role="listitem"' not in page.text `
  - [Zeile 73](../../../tests/test_model_leaderboard.py#L73): ` assert "0 judge selections" not in page.text `
- [test_hub_and_sitemap_distinguish_noindex_from_archive_or_unpublished](../../../tests/test_topic_public_http.py#L34) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=10.
  - [Zeile 52](../../../tests/test_topic_public_http.py#L52): ` assert hub.status_code == sitemap.status_code == 200 `
  - [Zeile 54](../../../tests/test_topic_public_http.py#L54): ` assert "/topics/" + slug in hub.text `
  - [Zeile 56](../../../tests/test_topic_public_http.py#L56): ` assert "/topics/" + slug in sitemap.text `
  - [Zeile 58](../../../tests/test_topic_public_http.py#L58): ` assert "/topics/" + slug not in hub.text + sitemap.text `
  - [Zeile 59](../../../tests/test_topic_public_http.py#L59): ` assert "/topics/noindex-topic" not in sitemap.text `
  - [Zeile 61](../../../tests/test_topic_public_http.py#L61): ` assert "<img src=x onerror=" not in body and "&lt;img" in body `

<a id="admin-01"></a>

## ADMIN-01 · Konfiguration: Revisionen und Aktivierungsrollback

Modellkonfiguration verwendet CAS-Revisionssave und eigenen revisionsgebundenen Rollback; andere Prozesse übernehmen neuere veröffentlichte Revisionen. Prompt-/Budgetkonfiguration bleiben revisioniert; Publisher hat einen separaten Savepfad. Keine gemeinsame atomare DB-/Runtimeaktivierung aller Prozesse.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Eigener Revisionsrollback gegen unabhängigen nativen Writer mit und ohne Vorgängerdokument belegt; lokale Aktivierungsfehler zusätzlich getestet. Keine globale DB-/Runtimeatomizität aller Server. Native Rollback-RPCfehler sind zusätzlich injiziert: gespeicherte neue Revision und alter Runtime-Snapshot werden ehrlich getrennt ausgewiesen.

**Befunde:** [G-040](gaps.md#g-040). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/admin.py](../../../app/api/routers/admin.py)
- [app/core/config.py](../../../app/core/config.py)
- [app/services/agent_budget_config.py](../../../app/services/agent_budget_config.py)
- [app/services/prompt_config.py](../../../app/services/prompt_config.py)
- [app/services/prompt_defaults.py](../../../app/services/prompt_defaults.py)
- [app/services/publisher_config.py](../../../app/services/publisher_config.py)

**Testdateien:**

- [tests/e2e/test_model_configuration_transactions.py](../../../tests/e2e/test_model_configuration_transactions.py)
- [tests/e2e/test_prompt_config_transactions.py](../../../tests/e2e/test_prompt_config_transactions.py)
- [tests/js/admin-prompt-config.test.mjs](../../../tests/js/admin-prompt-config.test.mjs)
- [tests/test_agent_budget_config.py](../../../tests/test_agent_budget_config.py)
- [tests/test_model_configuration.py](../../../tests/test_model_configuration.py)
- [tests/test_model_configuration_regressions.py](../../../tests/test_model_configuration_regressions.py)
- [tests/test_prompt_config.py](../../../tests/test_prompt_config.py)
- [tests/test_publisher_config.py](../../../tests/test_publisher_config.py)
- [tests/test_source_model_configuration.py](../../../tests/test_source_model_configuration.py)

</details>

**Konkrete Teilbelege:**

- [test_admin_read_is_write_free_and_save_is_versioned_and_audited](../../../tests/test_prompt_config.py#L94) — Router/Store und Runtime-Prompt-Integration mit Fake-DB. **Datei**status vom 2026-10-02: passed=19.
  - [Zeile 96](../../../tests/test_prompt_config.py#L96): ` assert response.status_code == 200 `
  - [Zeile 97](../../../tests/test_prompt_config.py#L97): ` assert response.json()["config"]["revision"] == 0 `
  - [Zeile 98](../../../tests/test_prompt_config.py#L98): ` assert response.json()["defaults"] == prompt_config.defaults() `
  - [Zeile 99](../../../tests/test_prompt_config.py#L99): ` assert config_store.db.documents == {} `
  - [Zeile 101](../../../tests/test_prompt_config.py#L101): ` assert response.status_code == 200 `
  - [Zeile 103](../../../tests/test_prompt_config.py#L103): ` assert saved["revision"] == 1 and saved["updated_by"] == "admin" `
- [test_native_failed_model_activation_preserves_other_writer](../../../tests/e2e/test_model_configuration_transactions.py#L11) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator mit zwei durch Events koordinierten Writern. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 20](../../../tests/e2e/test_model_configuration_transactions.py#L20): ` assert finished.wait(20) `
  - [Zeile 24](../../../tests/e2e/test_model_configuration_transactions.py#L24): ` with pytest.raises(RuntimeError, match="activation failure"): `
  - [Zeile 27](../../../tests/e2e/test_model_configuration_transactions.py#L27): ` assert entered.wait(20) `
  - [Zeile 34](../../../tests/e2e/test_model_configuration_transactions.py#L34): ` assert current["revision"] == initial_revision + 1 `
  - [Zeile 43](../../../tests/e2e/test_model_configuration_transactions.py#L43): ` assert ref.get().to_dict() == {"revision": initial_revision + 2, "label": "B"} `
  - [Zeile 44](../../../tests/e2e/test_model_configuration_transactions.py#L44): ` with pytest.raises(admin.ModelConfigConflict): `
- [ModelConfigurationTests::test_rejected_admin_document_cannot_mutate_runtime_limits](../../../tests/test_model_configuration.py#L101) — Modellkonfiguration mit Repository-/Aktivierungsdoubles und statischen UIverträgen. **Datei**status vom 2026-10-02: passed=31.
  - [Zeile 113](../../../tests/test_model_configuration.py#L113): ` self.assertRaises(HTTPException) as exc_info, `
  - [Zeile 117](../../../tests/test_model_configuration.py#L117): ` self.assertEqual(exc_info.exception.status_code, 400) `
  - [Zeile 118](../../../tests/test_model_configuration.py#L118): ` self.assertEqual(cfg.get_limits_config(), before) `
  - [Zeile 119](../../../tests/test_model_configuration.py#L119): ` fake_document.set.assert_not_called() `
- [shows the real main error envelope while retaining a conflicting draft without a second write](../../../tests/js/admin-prompt-config.test.mjs#L31) — Prompteditor im jsdom mit echtem Adminclient. **Datei**status vom 2026-10-02: passed=11.
  - [Zeile 40](../../../tests/js/admin-prompt-config.test.mjs#L40): ` await vi.waitFor(() => expect(doc.getElementById('promptConfigStatus').textContent).toContain('Configuration changed in another session.')); `
  - [Zeile 41](../../../tests/js/admin-prompt-config.test.mjs#L41): ` expect(doc.getElementById('promptConfigStatus').textContent).not.toContain('[object Object]'); `
  - [Zeile 42](../../../tests/js/admin-prompt-config.test.mjs#L42): ` expect(doc.getElementById('prompt-agent').value).toBe('My unsaved draft'); `
  - [Zeile 43](../../../tests/js/admin-prompt-config.test.mjs#L43): ` expect(doc.getElementById('promptConfigDirty').hidden).toBe(false); `
  - [Zeile 44](../../../tests/js/admin-prompt-config.test.mjs#L44): ` expect(fetch.mock.calls.filter(([, options]) => options.method === 'PUT')).toHaveLength(1); `

<a id="admin-02"></a>

## ADMIN-02 · Adminoberfläche und HTTP-Adapter

Adminaktionen tragen den aktuellen Token, lesen/speichern die passende Ressource und zeigen verständliche Fehler; Bei revisionierten Editoren: Revisionkonflikte erhalten lokale Eingaben und fordern Reload statt stiller Überschreibung.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Tatsächlicher main-Fehlerumschlag plus originaler Adminclient/Editor/Viewer im jsdom; HTTP/Authgrenzen kontrolliert, kein globaler Browser-/DB-Atomaritätsvertrag.

**Befunde:** [G-019](gaps.md#g-019). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/js/admin-agent-budget.js](../../../static/js/admin-agent-budget.js)
- [static/js/admin-api.js](../../../static/js/admin-api.js)
- [static/js/admin-benchmark.js](../../../static/js/admin-benchmark.js)
- [static/js/admin-config.js](../../../static/js/admin-config.js)
- [static/js/admin-prompt-config.js](../../../static/js/admin-prompt-config.js)
- [static/js/admin.js](../../../static/js/admin.js)
- [templates/admin.html](../../../templates/admin.html)
- [templates/admin_benchmark.html](../../../templates/admin_benchmark.html)
- [templates/partials/admin_prompt_config.html](../../../templates/partials/admin_prompt_config.html)

**Testdateien:**

- [tests/e2e/test_admin_agent_budget.py](../../../tests/e2e/test_admin_agent_budget.py)
- [tests/e2e/test_admin_prompt_config.py](../../../tests/e2e/test_admin_prompt_config.py)
- [tests/js/admin-agent-budget.test.mjs](../../../tests/js/admin-agent-budget.test.mjs)
- [tests/js/admin-api.test.mjs](../../../tests/js/admin-api.test.mjs)
- [tests/js/admin-benchmark.test.mjs](../../../tests/js/admin-benchmark.test.mjs)
- [tests/js/admin-prompt-config.test.mjs](../../../tests/js/admin-prompt-config.test.mjs)
- [tests/js/admin-reasoning-policy.test.mjs](../../../tests/js/admin-reasoning-policy.test.mjs)
- [tests/js/admin-source-model.test.mjs](../../../tests/js/admin-source-model.test.mjs)
- [tests/js/admin-topic-editor.test.mjs](../../../tests/js/admin-topic-editor.test.mjs)
- [tests/js/admin-watch-effective-run.test.mjs](../../../tests/js/admin-watch-effective-run.test.mjs)
- [tests/test_account_tier_admin.py](../../../tests/test_account_tier_admin.py)
- [tests/test_http_adapter_auth.py](../../../tests/test_http_adapter_auth.py)
- [tests/test_phase6_architecture.py](../../../tests/test_phase6_architecture.py)

</details>

**Konkrete Teilbelege:**

- [keeps the draft after conflict or failure and allows explicit reload](../../../tests/js/admin-prompt-config.test.mjs#L86) — Prompteditor im jsdom mit echtem Adminclient. **Datei**status vom 2026-10-02: passed=11.
  - [Zeile 92](../../../tests/js/admin-prompt-config.test.mjs#L92): ` await vi.waitFor(() => expect(doc.getElementById('promptConfigStatus').textContent).toContain('another session')); `
  - [Zeile 93](../../../tests/js/admin-prompt-config.test.mjs#L93): ` expect(doc.getElementById('prompt-agent').value).toBe('My unsaved draft'); `
  - [Zeile 94](../../../tests/js/admin-prompt-config.test.mjs#L94): ` expect(doc.getElementById('promptConfigDirty').hidden).toBe(false); `
  - [Zeile 96](../../../tests/js/admin-prompt-config.test.mjs#L96): ` await vi.waitFor(() => expect(doc.getElementById('prompt-agent').value).toBe(config.prompts.agent)); `
  - [Zeile 97](../../../tests/js/admin-prompt-config.test.mjs#L97): ` expect(doc.getElementById('promptConfigDirty').hidden).toBe(true); `
- [test_every_topic_admin_method_enforces_real_policy_before_service](../../../tests/test_http_adapter_auth.py#L29) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=38.
  - [Zeile 43](../../../tests/test_http_adapter_auth.py#L43): ` assert response.status_code == expected, response.text `
  - [Zeile 44](../../../tests/test_http_adapter_auth.py#L44): ` assert "error" in response.json() and "private" not in response.text `
  - [Zeile 45](../../../tests/test_http_adapter_auth.py#L45): ` assert database.documents == {} and database.query_reads == [] `
  - [Zeile 47](../../../tests/test_http_adapter_auth.py#L47): ` assert h.checks[-1][1]["check_revoked"] is True `
- [test_set_tier_writes_the_field_audits_it_and_drops_the_cache](../../../tests/test_account_tier_admin.py#L144) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=13.
  - [Zeile 149](../../../tests/test_account_tier_admin.py#L149): ` assert db.stores["users"]["uid-1"]["tier"] == "plus" `
  - [Zeile 150](../../../tests/test_account_tier_admin.py#L150): ` assert db.stores["users"]["uid-1"]["tier_updated_by"] == "admin-uid" `
  - [Zeile 151](../../../tests/test_account_tier_admin.py#L151): ` assert isinstance(db.stores["users"]["uid-1"]["tier_updated_at"], datetime) `
  - [Zeile 152](../../../tests/test_account_tier_admin.py#L152): ` invalidate.assert_called_once_with("uid-1") `
  - [Zeile 155](../../../tests/test_account_tier_admin.py#L155): ` assert len(entries) == 1 `
  - [Zeile 156](../../../tests/test_account_tier_admin.py#L156): ` assert entries[0]["from_tier"] == "free" `
- [unpacks only allowed strings from %j](../../../tests/js/admin-api.test.mjs#L8) — Originaler Adminclient mit kontrolliertem Fetch. **Datei**status vom 2026-10-02: passed=9.
  - [Zeile 20](../../../tests/js/admin-api.test.mjs#L20): ` await expect(request('PUT', '/api/admin/account-tier', { tier: 'plus' })).rejects.toThrow(expected); `
  - [Zeile 21](../../../tests/js/admin-api.test.mjs#L21): ` expect(fetch).toHaveBeenCalledTimes(1); `
  - [Zeile 22](../../../tests/js/admin-api.test.mjs#L22): ` expect(fetch.mock.calls[0][1]).toMatchObject({ method: 'PUT', headers: { Authorization: 'Bearer test-token' }, body: '{"tier":"plus"}' }); `
- [renders compact data, safely quotes labels and excludes raw prompts/answers](../../../tests/js/admin-benchmark.test.mjs#L25) — Originaler Viewer und Adminclient im jsdom. **Datei**status vom 2026-10-02: passed=7.
  - [Zeile 33](../../../tests/js/admin-benchmark.test.mjs#L33): ` await vi.waitFor(() => expect(doc.getElementById('runDetail').textContent).toContain('Run · run-a')); `
  - [Zeile 34](../../../tests/js/admin-benchmark.test.mjs#L34): ` expect(doc.getElementById('runDetail').textContent).toContain('50.0%'); `
  - [Zeile 35](../../../tests/js/admin-benchmark.test.mjs#L35): ` expect(doc.getElementById('runDetail').textContent).toContain('<img src=x onerror=alert(1)>'); `
  - [Zeile 36](../../../tests/js/admin-benchmark.test.mjs#L36): ` expect(doc.querySelector('img')).toBeNull(); `
  - [Zeile 37](../../../tests/js/admin-benchmark.test.mjs#L37): ` expect(doc.body.textContent).not.toContain('PRIVATE'); `

<a id="ui-01"></a>

## UI-01 · Run-State und getrennte Ansichten

RunRegistry besitzt Ausführung/Abbruch; visibleRunId bestimmt nur Rendering. Hintergrundruns speichern weiter, gespeicherte Ansichten und Authgeneration verhindern fremde Projektionen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Reale Modulzustände mit Fake-Netzwerk; Browser nicht ausgeführt.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/js/app-state.js](../../../static/js/app-state.js)
- [static/js/chat-session.js](../../../static/js/chat-session.js)
- [static/js/run-registry.js](../../../static/js/run-registry.js)
- [static/js/run-view.js](../../../static/js/run-view.js)

**Testdateien:**

- [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py)
- [tests/js/app-state.test.mjs](../../../tests/js/app-state.test.mjs)
- [tests/js/multi-run-view.test.mjs](../../../tests/js/multi-run-view.test.mjs)
- [tests/js/run-registry.test.mjs](../../../tests/js/run-registry.test.mjs)
- [tests/test_chat_session_ui.py](../../../tests/test_chat_session_ui.py)
- [tests/test_multi_run_architecture.py](../../../tests/test_multi_run_architecture.py)

</details>

**Konkrete Teilbelege:**

- [rejects a write from any other module and leaves the value alone](../../../tests/js/app-state.test.mjs#L36) — JavaScript-Modultest mit jsdom. **Datei**status vom 2026-10-02: passed=8.
  - [Zeile 40](../../../tests/js/app-state.test.mjs#L40): ` expect(() => `
  - [Zeile 43](../../../tests/js/app-state.test.mjs#L43): ` expect(window.App.state.get("lastQuestion")).toBe("original"); `

<a id="ui-02"></a>

## UI-02 · Senden, Presets und Moduswechsel

Ein Compare/Consensus/Agent-Modusselektor migriert Legacywerte und synchronisiert Settings. Chatfamilie, Accountzugriff und ausstehende Autorisierung bestimmen effektiven Modus; laufende Konfiguration bleibt eingefroren. Ein Agentpicker verbindet Chatmodell und Vergleiche.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Statische und jsdom-Verträge; tatsächliche Provider-/Persistenzverkabelung gesondert.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/css/send-glow.css](../../../static/css/send-glow.css)
- [static/js/agent-mode.js](../../../static/js/agent-mode.js)
- [static/js/app-core.js](../../../static/js/app-core.js)
- [static/js/app-init.js](../../../static/js/app-init.js)
- [static/js/composer-autosize.js](../../../static/js/composer-autosize.js)
- [static/js/feature-access.js](../../../static/js/feature-access.js)
- [static/js/model-picker.js](../../../static/js/model-picker.js)
- [static/js/query-send.js](../../../static/js/query-send.js)
- [static/js/run-mode.js](../../../static/js/run-mode.js)

**Testdateien:**

- [tests/e2e/test_direct_comparison_preview.py](../../../tests/e2e/test_direct_comparison_preview.py)
- [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py)
- [tests/e2e/test_run_mode_selector.py](../../../tests/e2e/test_run_mode_selector.py)
- [tests/e2e/test_smoke.py](../../../tests/e2e/test_smoke.py)
- [tests/js/agent-mode-projection.test.mjs](../../../tests/js/agent-mode-projection.test.mjs)
- [tests/js/agent-preferences.test.mjs](../../../tests/js/agent-preferences.test.mjs)
- [tests/js/composer-autosize.test.mjs](../../../tests/js/composer-autosize.test.mjs)
- [tests/js/model-attachment-capability.test.mjs](../../../tests/js/model-attachment-capability.test.mjs)
- [tests/js/model-family-cap.test.mjs](../../../tests/js/model-family-cap.test.mjs)
- [tests/js/plus-tier-gates.test.mjs](../../../tests/js/plus-tier-gates.test.mjs)
- [tests/js/run-mode.test.mjs](../../../tests/js/run-mode.test.mjs)
- [tests/js/send-button.test.mjs](../../../tests/js/send-button.test.mjs)
- [tests/test_agent_mode_ui.py](../../../tests/test_agent_mode_ui.py)
- [tests/test_navigation_settings_ui.py](../../../tests/test_navigation_settings_ui.py)
- [tests/test_usage_limit_ui.py](../../../tests/test_usage_limit_ui.py)

</details>

**Konkrete Teilbelege:**

- [persists source checks for agent runs and locks every control for direct comparisons](../../../tests/js/agent-mode-projection.test.mjs#L114) — JavaScript-Modultest mit jsdom. **Datei**status vom 2026-10-02: passed=10.
  - [Zeile 118](../../../tests/js/agent-mode-projection.test.mjs#L118): ` expect(window.App.isSourceCheckEnabled()).toBe(true); `
  - [Zeile 119](../../../tests/js/agent-mode-projection.test.mjs#L119): ` expect(toggle.getAttribute('aria-checked')).toBe('true'); `
  - [Zeile 121](../../../tests/js/agent-mode-projection.test.mjs#L121): ` expect(window.App.isSourceCheckEnabled()).toBe(false); `
  - [Zeile 122](../../../tests/js/agent-mode-projection.test.mjs#L122): ` expect(window.localStorage.getItem('checkSources')).toBe('false'); `
  - [Zeile 123](../../../tests/js/agent-mode-projection.test.mjs#L123): ` expect(document.getElementById('sourceCheckMenuSwitch').checked).toBe(false); `
  - [Zeile 124](../../../tests/js/agent-mode-projection.test.mjs#L124): ` expect(document.getElementById('sourceCheckSwitch').checked).toBe(false); `
- [shrinks a wrapped placeholder when the actual width finishes changing without another viewport event](../../../tests/js/composer-autosize.test.mjs#L31) — Originales Autosize-Modul in jsdom mit kontrollierter Geometrie und Frames. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 34](../../../tests/js/composer-autosize.test.mjs#L34): ` expect(app.field.style.height).toBe('180px'); `
  - [Zeile 35](../../../tests/js/composer-autosize.test.mjs#L35): ` expect(app.field.style.overflowY).toBe('auto'); `
  - [Zeile 37](../../../tests/js/composer-autosize.test.mjs#L37): ` expect(app.field.style.height).toBe('180px'); `
  - [Zeile 39](../../../tests/js/composer-autosize.test.mjs#L39): ` expect(app.field.style.height).toBe('52px'); `
  - [Zeile 40](../../../tests/js/composer-autosize.test.mjs#L40): ` expect(app.field.style.overflowY).toBe('hidden'); `
- [test_chat_textarea_grows_until_responsive_height_limit](../../../tests/test_navigation_settings_ui.py#L280) — Quelltextverträge. **Datei**status vom 2026-10-02: passed=27.
  - [Zeile 285](../../../tests/test_navigation_settings_ui.py#L285): ` assert 'id="questionInput" rows="1"' in template `
  - [Zeile 286](../../../tests/test_navigation_settings_ui.py#L286): ` assert "resize: none;" in input_css `
  - [Zeile 287](../../../tests/test_navigation_settings_ui.py#L287): ` assert "overflow-y: hidden;" in input_css `
  - [Zeile 288](../../../tests/test_navigation_settings_ui.py#L288): ` assert "max-height: 220px;" in input_css `
  - [Zeile 289](../../../tests/test_navigation_settings_ui.py#L289): ` assert "@media (max-width: 1099px)" in input_css `
  - [Zeile 290](../../../tests/test_navigation_settings_ui.py#L290): ` assert "max-height: 180px;" in input_css `
- [test_question_input_grows_and_caps_on_desktop_and_mobile](../../../tests/e2e/test_smoke.py#L176) — Chromium gegen echte App-Routen und Demo-Firestore mit kontrollierter Identität/Modellen; ergänzend direkte Rendererfälle. **Datei**status vom 2026-10-02: passed=43.
  - [Zeile 184](../../../tests/e2e/test_smoke.py#L184): ` assert grown_height > base_height `
  - [Zeile 185](../../../tests/e2e/test_smoke.py#L185): ` assert grown_height < 220 `
  - [Zeile 196](../../../tests/e2e/test_smoke.py#L196): ` assert desktop["height"] == 220 `
  - [Zeile 197](../../../tests/e2e/test_smoke.py#L197): ` assert desktop["scrollHeight"] > desktop["clientHeight"] `
  - [Zeile 198](../../../tests/e2e/test_smoke.py#L198): ` assert desktop["overflowY"] == "auto" `
  - [Zeile 207](../../../tests/e2e/test_smoke.py#L207): ` assert round(mobile["height"]) == 180 `
- [test_phase4_server_reuses_its_child_and_rejects_an_unowned_listener](../../../tests/e2e/test_phase4_frontend.py#L143) — Chromium und ein gemeinsam gestarteter lokaler Testserver. **Datei**status vom 2026-10-02: passed=29.
  - [Zeile 150](../../../tests/e2e/test_phase4_frontend.py#L150): ` assert next(imported_fixture) == phase4_server `
  - [Zeile 151](../../../tests/e2e/test_phase4_frontend.py#L151): ` with pytest.raises(StopIteration): `
  - [Zeile 153](../../../tests/e2e/test_phase4_frontend.py#L153): ` assert request.config._phase4_server_url == phase4_server `
  - [Zeile 156](../../../tests/e2e/test_phase4_frontend.py#L156): ` with pytest.raises(RuntimeError, match='already in use'): `

<a id="ui-03"></a>

## UI-03 · Streaming, Deadlines und Fortschritt

Parser verarbeitet geteilte SSE-Chunks, genau ein finales Ergebnis und verständliche Fehler. Steueranfragen haben Fristen; Stream-Liveness und Provider-Fortschrittswatchdog bleiben von Gesamtlaufzeit getrennt. Progress zählt echte Daten und endet pro Run.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Fake-Uhr/Streams; Geometrie/Animation im Browserbestand noch nicht ausgeführt.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/js/consensus-lifecycle.js](../../../static/js/consensus-lifecycle.js)
- [static/js/consensus-progress.js](../../../static/js/consensus-progress.js)
- [static/js/markdown-stream.js](../../../static/js/markdown-stream.js)
- [static/js/request-deadline.js](../../../static/js/request-deadline.js)

**Testdateien:**

- [tests/e2e/test_agent_status_frontend.py](../../../tests/e2e/test_agent_status_frontend.py)
- [tests/e2e/test_agreement_verdict.py](../../../tests/e2e/test_agreement_verdict.py)
- [tests/e2e/test_chat_scroll_frontend.py](../../../tests/e2e/test_chat_scroll_frontend.py)
- [tests/e2e/test_consensus_live_progress.py](../../../tests/e2e/test_consensus_live_progress.py)
- [tests/e2e/test_run_cancel_and_progress.py](../../../tests/e2e/test_run_cancel_and_progress.py)
- [tests/js/chat-scroll.test.mjs](../../../tests/js/chat-scroll.test.mjs)
- [tests/js/judge-stream-events.test.mjs](../../../tests/js/judge-stream-events.test.mjs)
- [tests/js/markdown-stream-incremental.test.mjs](../../../tests/js/markdown-stream-incremental.test.mjs)
- [tests/js/request-deadline.test.mjs](../../../tests/js/request-deadline.test.mjs)
- [tests/js/run-progress-scope.test.mjs](../../../tests/js/run-progress-scope.test.mjs)
- [tests/js/sse-completion.test.mjs](../../../tests/js/sse-completion.test.mjs)
- [tests/test_consensus_progress_ui.py](../../../tests/test_consensus_progress_ui.py)

</details>

**Konkrete Teilbelege:**

- [renews streaming liveness and removes timers after completion](../../../tests/js/request-deadline.test.mjs#L22) — JavaScript-Modultest mit jsdom. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 29](../../../tests/js/request-deadline.test.mjs#L29): ` for (let i = 0; i < 10; i++) { progress(); expect(timers.size).toBe(1); } `
  - [Zeile 32](../../../tests/js/request-deadline.test.mjs#L32): ` expect(result).toBe('done'); expect(timers.size).toBe(0); `
  - [Zeile 33](../../../tests/js/request-deadline.test.mjs#L33): ` touch(); expect(timers.size).toBe(0); `
- [test_low_score_without_contradictions_is_not_green_or_high](../../../tests/e2e/test_agreement_verdict.py#L4) — Chromium mit echtem App-Frontend und direkt aufgerufenem Verdict-Renderer. **Datei**status vom 2026-10-02: passed=1.
  - [Zeile 23](../../../tests/e2e/test_agreement_verdict.py#L23): ` expect(verdict).to_have_class("consensus-verdict is-alert") `
  - [Zeile 24](../../../tests/e2e/test_agreement_verdict.py#L24): ` expect(verdict.locator(".verdict-headline")).to_have_text("Low agreement") `
  - [Zeile 25](../../../tests/e2e/test_agreement_verdict.py#L25): ` expect(verdict.locator(".verdict-detail")).to_contain_text("no contradictions") `
  - [Zeile 33](../../../tests/e2e/test_agreement_verdict.py#L33): ` assert palette["--verdict-ring"] == palette["--dispute"] `
  - [Zeile 34](../../../tests/e2e/test_agreement_verdict.py#L34): ` assert palette["--verdict-ring"] != palette["--agree"] `
- [test_send_button_stays_cancelable_until_consensus_is_done](../../../tests/e2e/test_run_cancel_and_progress.py#L47) — Chromium mit echten Registry- und DOMereignissen. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 78](../../../tests/e2e/test_run_cancel_and_progress.py#L78): ` app_page.wait_for_function( `
  - [Zeile 86](../../../tests/e2e/test_run_cancel_and_progress.py#L86): ` assert any(sample["status"] == "pending" for sample in samples), samples `
  - [Zeile 87](../../../tests/e2e/test_run_cancel_and_progress.py#L87): ` assert any(sample["status"] in {"streaming", "differences"} for sample in samples), samples `
  - [Zeile 88](../../../tests/e2e/test_run_cancel_and_progress.py#L88): ` assert all(sample["cancelable"] for sample in samples), samples `
  - [Zeile 89](../../../tests/e2e/test_run_cancel_and_progress.py#L89): ` expect(app_page.locator("#sendButton")).not_to_have_class( `
- [keeps the reading position when offscreen activity shrinks, including native anchoring](../../../tests/js/chat-scroll.test.mjs#L37) — Originale Scrollsteuerung mit kontrollierten DOMmaßen und Frames. **Datei**status vom 2026-10-02: passed=16.
  - [Zeile 46](../../../tests/js/chat-scroll.test.mjs#L46): ` expect(app.window.scrollY).toBe(960); `
  - [Zeile 52](../../../tests/js/chat-scroll.test.mjs#L52): ` expect(app.window.scrollY).toBe(780); `
  - [Zeile 53](../../../tests/js/chat-scroll.test.mjs#L53): ` expect(app.window.scrollTo).not.toHaveBeenCalled(); `
  - [Zeile 55](../../../tests/js/chat-scroll.test.mjs#L55): ` expect(app.window.App.chatScroll.preserveAbove(activity)).toBeNull(); `
- [test_consensus_result_precedes_model_answers_and_run_block_is_loaded](../../../tests/test_consensus_progress_ui.py#L12) — Statische DOM-/CSS-/JS-Verträge. **Datei**status vom 2026-10-02: passed=18.
  - [Zeile 15](../../../tests/test_consensus_progress_ui.py#L15): ` assert template.index('class="consensus-section"') < template.index( `
  - [Zeile 18](../../../tests/test_consensus_progress_ui.py#L18): ` assert 'id="consensusRun"' in template `
  - [Zeile 19](../../../tests/test_consensus_progress_ui.py#L19): ` assert 'id="runStatus"' in template `
  - [Zeile 20](../../../tests/test_consensus_progress_ui.py#L20): ` assert loads_before("agent-mode.js", "consensus-progress.js") `
  - [Zeile 21](../../../tests/test_consensus_progress_ui.py#L21): ` assert loads_before("consensus-progress.js", "consensus-lifecycle.js") `
- [test_agent_review_and_completion_keep_visible_answer_still](../../../tests/e2e/test_chat_scroll_frontend.py#L13) — Chromium mit echten Appskripten und kontrollierten Antworten. **Datei**status vom 2026-10-02: passed=11.
  - [Zeile 39](../../../tests/e2e/test_chat_scroll_frontend.py#L39): ` expect(page.locator('#agentAnswerBody p')).to_have_count(45) `
  - [Zeile 45](../../../tests/e2e/test_chat_scroll_frontend.py#L45): ` page.wait_for_function('() => document.documentElement.scrollHeight - innerHeight - scrollY < 3') `
  - [Zeile 62](../../../tests/e2e/test_chat_scroll_frontend.py#L62): ` assert page.locator('#agentAnswerActivity').bounding_box()['y'] + page.locator('#agentAnswerActivity').bounding_box()['height'] < 0 `
  - [Zeile 86](../../../tests/e2e/test_chat_scroll_frontend.py#L86): ` assert max(samples) - min(samples) < 3, (stage, samples) `
  - [Zeile 87](../../../tests/e2e/test_chat_scroll_frontend.py#L87): ` expect(page.locator('#agentAnswerActivity details')).not_to_have_attribute('open', '') `
  - [Zeile 88](../../../tests/e2e/test_chat_scroll_frontend.py#L88): ` expect(page.locator('#agentAnswerActivity .agent-progress')).not_to_be_visible() `
- [test_progress_paragraphs_collapse_at_final_and_reopen_with_keyboard](../../../tests/e2e/test_agent_status_frontend.py#L11) — Chromium mit kontrollierten gestreamten Fortschrittsereignissen. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 28](../../../tests/e2e/test_agent_status_frontend.py#L28): ` expect(page.locator("#agentModelDropdown")).to_be_enabled() `
  - [Zeile 73](../../../tests/e2e/test_agent_status_frontend.py#L73): ` expect(preview.locator('.agent-current-status')).to_have_text('Thinking…') `
  - [Zeile 76](../../../tests/e2e/test_agent_status_frontend.py#L76): ` expect(thinking_details.locator('.agent-activity-run-details')).to_be_visible() `
  - [Zeile 77](../../../tests/e2e/test_agent_status_frontend.py#L77): ` expect(thinking_details.locator('.agent-activity-run-details')).to_contain_text('DeepSeek V4.1 Flash') `
  - [Zeile 78](../../../tests/e2e/test_agent_status_frontend.py#L78): ` expect(thinking_details.locator('.agent-activity-run-details')).to_contain_text('Thinking…') `
  - [Zeile 79](../../../tests/e2e/test_agent_status_frontend.py#L79): ` expect(thinking_details.locator('.agent-activity-run-details')).to_contain_text('Model default') `

<a id="ui-04"></a>

## UI-04 · Antworten, Markdown und zugängliche Details

Sanitisierte Markdown-/Mathematik-/Antwortansichten bewahren Quellenidentität und gespeicherte Turns. Quellen erscheinen als gruppierbare Faviconpillen, Differences werden nach Schweregrad angezeigt; inkrementelles Streaming erhält fertige Blöcke und vermeidet Remote-Medien.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Konkrete DOM-/CSS- und Chromiumverträge, archivierte Drawer und inerte Notizen; keine flächige Accessibility-/visuelle Baseline.

**Befunde:** [G-028](gaps.md#g-028). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/js/consensus-anchor.js](../../../static/js/consensus-anchor.js)
- [static/js/consensus-insights.js](../../../static/js/consensus-insights.js)
- [static/js/consensus-run.js](../../../static/js/consensus-run.js)
- [static/js/markdown-stream.js](../../../static/js/markdown-stream.js)
- [static/js/math-render.js](../../../static/js/math-render.js)
- [static/js/model-answer-reader.js](../../../static/js/model-answer-reader.js)

**Testdateien:**

- [tests/e2e/test_agent_chat_frontend.py](../../../tests/e2e/test_agent_chat_frontend.py)
- [tests/e2e/test_agent_comparison_frontend.py](../../../tests/e2e/test_agent_comparison_frontend.py)
- [tests/e2e/test_agent_status_frontend.py](../../../tests/e2e/test_agent_status_frontend.py)
- [tests/e2e/test_agreement_verdict.py](../../../tests/e2e/test_agreement_verdict.py)
- [tests/e2e/test_model_answer_reader.py](../../../tests/e2e/test_model_answer_reader.py)
- [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py)
- [tests/e2e/test_reader_density.py](../../../tests/e2e/test_reader_density.py)
- [tests/e2e/test_reader_review_regressions.py](../../../tests/e2e/test_reader_review_regressions.py)
- [tests/e2e/test_run_cancel_and_progress.py](../../../tests/e2e/test_run_cancel_and_progress.py)
- [tests/e2e/test_smoke.py](../../../tests/e2e/test_smoke.py)
- [tests/e2e/test_topic_frontend.py](../../../tests/e2e/test_topic_frontend.py)
- [tests/js/bookmark-pending-state.test.mjs](../../../tests/js/bookmark-pending-state.test.mjs)
- [tests/js/claim-mark-joins.test.mjs](../../../tests/js/claim-mark-joins.test.mjs)
- [tests/js/consensus-anchor.test.mjs](../../../tests/js/consensus-anchor.test.mjs)
- [tests/js/consensus-coverage-verdict.test.mjs](../../../tests/js/consensus-coverage-verdict.test.mjs)
- [tests/js/consensus-marker-visibility.test.mjs](../../../tests/js/consensus-marker-visibility.test.mjs)
- [tests/js/consensus-recovery.test.mjs](../../../tests/js/consensus-recovery.test.mjs)
- [tests/js/dompurify-vendor.test.mjs](../../../tests/js/dompurify-vendor.test.mjs)
- [tests/js/markdown-remote-media.test.mjs](../../../tests/js/markdown-remote-media.test.mjs)
- [tests/js/markdown-stream-incremental.test.mjs](../../../tests/js/markdown-stream-incremental.test.mjs)
- [tests/js/markdown-table.test.mjs](../../../tests/js/markdown-table.test.mjs)
- [tests/js/math-render.test.mjs](../../../tests/js/math-render.test.mjs)
- [tests/js/model-answer-reader.test.mjs](../../../tests/js/model-answer-reader.test.mjs)
- [tests/js/stored-turn-markers.test.mjs](../../../tests/js/stored-turn-markers.test.mjs)
- [tests/js/thread-question-disclosure.test.mjs](../../../tests/js/thread-question-disclosure.test.mjs)
- [tests/test_agreement_verdict_ui.py](../../../tests/test_agreement_verdict_ui.py)
- [tests/test_consensus_progress_ui.py](../../../tests/test_consensus_progress_ui.py)
- [tests/test_source_pills_ui.py](../../../tests/test_source_pills_ui.py)

</details>

**Konkrete Teilbelege:**

- [keeps measured agreement and coverage separate](../../../tests/js/consensus-coverage-verdict.test.mjs#L24) — JavaScript-Modulintegration mit jsdom. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 26](../../../tests/js/consensus-coverage-verdict.test.mjs#L26): ` expect(verdict.querySelector(".verdict-score-num").textContent).toContain("64"); `
  - [Zeile 27](../../../tests/js/consensus-coverage-verdict.test.mjs#L27): ` expect(verdict.textContent).toContain("Coverage: 2/4 claims (50%)"); `
  - [Zeile 28](../../../tests/js/consensus-coverage-verdict.test.mjs#L28): ` expect(verdict.textContent).toContain("evidence incomplete"); `
- [test_consensus_renders_differences_and_agreement_score](../../../tests/e2e/test_smoke.py#L852) — Chromium gegen echte App-Routen und Demo-Firestore mit kontrollierter Identität/Modellen; ergänzend direkte Rendererfälle. **Datei**status vom 2026-10-02: passed=43.
  - [Zeile 887](../../../tests/e2e/test_smoke.py#L887): ` expect(pipeline).to_be_visible(timeout=10000) `
  - [Zeile 888](../../../tests/e2e/test_smoke.py#L888): ` expect(pipeline).to_have_attribute("data-stage", "answers") `
  - [Zeile 898](../../../tests/e2e/test_smoke.py#L898): ` assert metrics["height"] <= 34 `
  - [Zeile 899](../../../tests/e2e/test_smoke.py#L899): ` assert metrics["clipped"] is False `
  - [Zeile 902](../../../tests/e2e/test_smoke.py#L902): ` expect(pipeline).to_have_attribute("data-stage", "consensus", timeout=20000) `
  - [Zeile 904](../../../tests/e2e/test_smoke.py#L904): ` expect(app_page.locator("#consensusResponse")).to_contain_text("Mock consensus", timeout=30000) `
- [test_low_score_without_contradictions_is_not_green_or_high](../../../tests/e2e/test_agreement_verdict.py#L4) — Chromium mit echtem App-Frontend und direkt aufgerufenem Verdict-Renderer. **Datei**status vom 2026-10-02: passed=1.
  - [Zeile 23](../../../tests/e2e/test_agreement_verdict.py#L23): ` expect(verdict).to_have_class("consensus-verdict is-alert") `
  - [Zeile 24](../../../tests/e2e/test_agreement_verdict.py#L24): ` expect(verdict.locator(".verdict-headline")).to_have_text("Low agreement") `
  - [Zeile 25](../../../tests/e2e/test_agreement_verdict.py#L25): ` expect(verdict.locator(".verdict-detail")).to_contain_text("no contradictions") `
  - [Zeile 33](../../../tests/e2e/test_agreement_verdict.py#L33): ` assert palette["--verdict-ring"] == palette["--dispute"] `
  - [Zeile 34](../../../tests/e2e/test_agreement_verdict.py#L34): ` assert palette["--verdict-ring"] != palette["--agree"] `
- [test_send_button_stays_cancelable_until_consensus_is_done](../../../tests/e2e/test_run_cancel_and_progress.py#L47) — Chromium mit echten Registry- und DOMereignissen. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 78](../../../tests/e2e/test_run_cancel_and_progress.py#L78): ` app_page.wait_for_function( `
  - [Zeile 86](../../../tests/e2e/test_run_cancel_and_progress.py#L86): ` assert any(sample["status"] == "pending" for sample in samples), samples `
  - [Zeile 87](../../../tests/e2e/test_run_cancel_and_progress.py#L87): ` assert any(sample["status"] in {"streaming", "differences"} for sample in samples), samples `
  - [Zeile 88](../../../tests/e2e/test_run_cancel_and_progress.py#L88): ` assert all(sample["cancelable"] for sample in samples), samples `
  - [Zeile 89](../../../tests/e2e/test_run_cancel_and_progress.py#L89): ` expect(app_page.locator("#sendButton")).not_to_have_class( `
- [stays disabled until both the run and its persistence write finish](../../../tests/js/bookmark-pending-state.test.mjs#L45) — Originale Bookmarkhelfer und Markup im jsdom mit kontrolliertem Speichern. **Datei**status vom 2026-10-02: passed=5.
  - [Zeile 54](../../../tests/js/bookmark-pending-state.test.mjs#L54): ` expect(session.pending).not.toBeNull(); `
  - [Zeile 55](../../../tests/js/bookmark-pending-state.test.mjs#L55): ` expect(ready).toEqual([]); `
  - [Zeile 59](../../../tests/js/bookmark-pending-state.test.mjs#L59): ` expect(session.pending).toBeNull(); `
  - [Zeile 60](../../../tests/js/bookmark-pending-state.test.mjs#L60): ` expect(ready).toEqual([{ id: "pending_id", title: "How does this work?" }]); `
  - [Zeile 61](../../../tests/js/bookmark-pending-state.test.mjs#L61): ` expect(rendered.length).toBeGreaterThanOrEqual(2); `
- [keeps the contradiction line on the disputed sentence](../../../tests/js/stored-turn-markers.test.mjs#L92) — Echte DOMrenderfunktionen im jsdom. **Datei**status vom 2026-10-02: passed=8.
  - [Zeile 95](../../../tests/js/stored-turn-markers.test.mjs#L95): ` expect(marks.length).toBeGreaterThan(0); `
  - [Zeile 96](../../../tests/js/stored-turn-markers.test.mjs#L96): ` expect(marks[0].textContent).toContain("ticket costs 29 euros"); `
- [test_topic_markup_stays_text_and_preview_preserves_navigation](../../../tests/e2e/test_topic_frontend.py#L33) — Chromium mit Originalskript und kontrollierter SSR-Minimalfixture. **Datei**status vom 2026-10-02: passed=5.
  - [Zeile 39](../../../tests/e2e/test_topic_frontend.py#L39): ` assert '?' not in page.url  # first touch previews rather than navigating `
  - [Zeile 42](../../../tests/e2e/test_topic_frontend.py#L42): ` expect(page.locator('#topicStripRead')).to_contain_text(HOSTILE) `
  - [Zeile 43](../../../tests/e2e/test_topic_frontend.py#L43): ` expect(page.locator('#topicStripRead .topic-strip-score')).to_have_text('72/100 agreement') `
  - [Zeile 44](../../../tests/e2e/test_topic_frontend.py#L44): ` expect(page.locator('#injected, #topicStripRead img')).to_have_count(0) `
  - [Zeile 45](../../../tests/e2e/test_topic_frontend.py#L45): ` assert page.evaluate('window.__injected') is None `
  - [Zeile 50](../../../tests/e2e/test_topic_frontend.py#L50): ` expect(page).to_have_url('https://topics.test/topics/example?version=new') `
- [test_consensus_result_precedes_model_answers_and_run_block_is_loaded](../../../tests/test_consensus_progress_ui.py#L12) — Statische DOM-/CSS-/JS-Verträge. **Datei**status vom 2026-10-02: passed=18.
  - [Zeile 15](../../../tests/test_consensus_progress_ui.py#L15): ` assert template.index('class="consensus-section"') < template.index( `
  - [Zeile 18](../../../tests/test_consensus_progress_ui.py#L18): ` assert 'id="consensusRun"' in template `
  - [Zeile 19](../../../tests/test_consensus_progress_ui.py#L19): ` assert 'id="runStatus"' in template `
  - [Zeile 20](../../../tests/test_consensus_progress_ui.py#L20): ` assert loads_before("agent-mode.js", "consensus-progress.js") `
  - [Zeile 21](../../../tests/test_consensus_progress_ui.py#L21): ` assert loads_before("consensus-progress.js", "consensus-lifecycle.js") `
- [test_all_pro_chat_models_are_grouped_by_provider](../../../tests/e2e/test_agent_chat_frontend.py#L71) — Chromium mit echtem App-Frontend und kontrollierten Agent-APIantworten. **Datei**status vom 2026-10-02: passed=31.
  - [Zeile 77](../../../tests/e2e/test_agent_chat_frontend.py#L77): ` assert cfg.PREMIUM_MODELS <= {model['id'] for model in catalog['models']} `
  - [Zeile 86](../../../tests/e2e/test_agent_chat_frontend.py#L86): ` expect(page.locator('#agentModelDropdown')).to_be_enabled() `
  - [Zeile 87](../../../tests/e2e/test_agent_chat_frontend.py#L87): ` expect(page.locator('#agentModelDropdown option')).to_have_count(len(catalog['models'])) `
  - [Zeile 91](../../../tests/e2e/test_agent_chat_frontend.py#L91): ` assert menu['x'] >= 0 and menu['x'] + menu['width'] <= width `
  - [Zeile 92](../../../tests/e2e/test_agent_chat_frontend.py#L92): ` assert menu['y'] >= 0 and menu['y'] + menu['height'] <= 900 `
  - [Zeile 93](../../../tests/e2e/test_agent_chat_frontend.py#L93): ` expect(page.locator('.agent-model-picker button[data-model-group]')).to_have_count(len(cfg.PROVIDERS)) `
- [test_comparison_selection_blocks_send_before_losing_draft](../../../tests/e2e/test_agent_comparison_frontend.py#L13) — Chromium mit echten Vergleichs-/Drawerkomponenten. **Datei**status vom 2026-10-02: passed=15.
  - [Zeile 25](../../../tests/e2e/test_agent_comparison_frontend.py#L25): ` expect(page.locator('#sendButton')).to_be_enabled() `
  - [Zeile 27](../../../tests/e2e/test_agent_comparison_frontend.py#L27): ` expect(page.locator('.consensus-model-inline')).to_be_hidden() `
  - [Zeile 33](../../../tests/e2e/test_agent_comparison_frontend.py#L33): ` expect(page.locator('#sendButton')).to_be_disabled() `
  - [Zeile 35](../../../tests/e2e/test_agent_comparison_frontend.py#L35): ` expect(page.locator('#sendButton')).to_be_disabled() `
  - [Zeile 37](../../../tests/e2e/test_agent_comparison_frontend.py#L37): ` expect(page.locator('#agentComposerNotice')).to_be_visible() `
  - [Zeile 38](../../../tests/e2e/test_agent_comparison_frontend.py#L38): ` expect(page.locator('#agentComposerMessage')).to_contain_text('comparison models') `
- [test_progress_paragraphs_collapse_at_final_and_reopen_with_keyboard](../../../tests/e2e/test_agent_status_frontend.py#L11) — Chromium mit kontrollierten gestreamten Fortschrittsereignissen. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 28](../../../tests/e2e/test_agent_status_frontend.py#L28): ` expect(page.locator("#agentModelDropdown")).to_be_enabled() `
  - [Zeile 73](../../../tests/e2e/test_agent_status_frontend.py#L73): ` expect(preview.locator('.agent-current-status')).to_have_text('Thinking…') `
  - [Zeile 76](../../../tests/e2e/test_agent_status_frontend.py#L76): ` expect(thinking_details.locator('.agent-activity-run-details')).to_be_visible() `
  - [Zeile 77](../../../tests/e2e/test_agent_status_frontend.py#L77): ` expect(thinking_details.locator('.agent-activity-run-details')).to_contain_text('DeepSeek V4.1 Flash') `
  - [Zeile 78](../../../tests/e2e/test_agent_status_frontend.py#L78): ` expect(thinking_details.locator('.agent-activity-run-details')).to_contain_text('Thinking…') `
  - [Zeile 79](../../../tests/e2e/test_agent_status_frontend.py#L79): ` expect(thinking_details.locator('.agent-activity-run-details')).to_contain_text('Model default') `
- [test_phase4_server_reuses_its_child_and_rejects_an_unowned_listener](../../../tests/e2e/test_phase4_frontend.py#L143) — Chromium und ein gemeinsam gestarteter lokaler Testserver. **Datei**status vom 2026-10-02: passed=29.
  - [Zeile 150](../../../tests/e2e/test_phase4_frontend.py#L150): ` assert next(imported_fixture) == phase4_server `
  - [Zeile 151](../../../tests/e2e/test_phase4_frontend.py#L151): ` with pytest.raises(StopIteration): `
  - [Zeile 153](../../../tests/e2e/test_phase4_frontend.py#L153): ` assert request.config._phase4_server_url == phase4_server `
  - [Zeile 156](../../../tests/e2e/test_phase4_frontend.py#L156): ` with pytest.raises(RuntimeError, match='already in use'): `
- [test_six_answers_leave_room_to_read_and_keep_touch_targets](../../../tests/e2e/test_reader_density.py#L10) — Chromium mit echten Readerkomponenten und gemessener Geometrie. **Datei**status vom 2026-10-02: passed=2.
  - [Zeile 41](../../../tests/e2e/test_reader_density.py#L41): ` expect(page.locator('#answerReaderModels button')).to_have_count(6) `
  - [Zeile 53](../../../tests/e2e/test_reader_density.py#L53): ` assert 520 <= round(metrics['width']) <= 720 `
  - [Zeile 54](../../../tests/e2e/test_reader_density.py#L54): ` assert metrics['chatWidth'] >= 550 `
  - [Zeile 55](../../../tests/e2e/test_reader_density.py#L55): ` assert metrics['chatRight'] < metrics['readerLeft'] `
  - [Zeile 56](../../../tests/e2e/test_reader_density.py#L56): ` assert metrics['headerHeight'] <= 36 `
  - [Zeile 57](../../../tests/e2e/test_reader_density.py#L57): ` assert metrics['bodyTop'] < 340 `

<a id="ui-05"></a>

## UI-05 · Anhänge und Composer

Ab Plus akzeptierte Dateien werden validiert, komprimiert und pro Turn eingefroren; Vorschau/Entfernen und Moduswechsel erhalten korrekte Metadaten. Persistenz enthält keine Dateibytes.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Codec/Blob/Canvas teilweise ersetzt; kein umfassender Dateiformat-Fuzz-/realer Browsercodec-Nachweis.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/llm/attachments.py](../../../app/services/llm/attachments.py)
- [static/css/composer.css](../../../static/css/composer.css)
- [static/js/attachments.js](../../../static/js/attachments.js)
- [static/js/composer-collapse.js](../../../static/js/composer-collapse.js)
- [static/js/composer-quote.js](../../../static/js/composer-quote.js)

**Testdateien:**

- [tests/e2e/test_composer_mode_bar.py](../../../tests/e2e/test_composer_mode_bar.py)
- [tests/js/attachment-compression.test.mjs](../../../tests/js/attachment-compression.test.mjs)
- [tests/js/attachment-draft-generation.test.mjs](../../../tests/js/attachment-draft-generation.test.mjs)
- [tests/js/bookmark-attachments.test.mjs](../../../tests/js/bookmark-attachments.test.mjs)
- [tests/js/composer-attachments.test.mjs](../../../tests/js/composer-attachments.test.mjs)
- [tests/js/composer-quote.test.mjs](../../../tests/js/composer-quote.test.mjs)
- [tests/js/model-attachment-capability.test.mjs](../../../tests/js/model-attachment-capability.test.mjs)
- [tests/test_attachments.py](../../../tests/test_attachments.py)
- [tests/test_chat_history.py](../../../tests/test_chat_history.py)

</details>

**Konkrete Teilbelege:**

- [shrinks an oversized photo before it is encoded](../../../tests/js/attachment-compression.test.mjs#L106) — JavaScript-Modulintegration mit simuliertem Bild-/Canvasverhalten. **Datei**status vom 2026-10-02: passed=5.
  - [Zeile 114](../../../tests/js/attachment-compression.test.mjs#L114): ` expect(attachments).toHaveLength(1); `
  - [Zeile 115](../../../tests/js/attachment-compression.test.mjs#L115): ` expect(attachments[0].mime).toBe("image/jpeg"); `
  - [Zeile 117](../../../tests/js/attachment-compression.test.mjs#L117): ` expect(attachments[0].name).toBe("photo.jpg"); `
  - [Zeile 118](../../../tests/js/attachment-compression.test.mjs#L118): ` expect(attachments[0].size).toBe(ENCODED_BYTES); `
  - [Zeile 120](../../../tests/js/attachment-compression.test.mjs#L120): ` expect(harness.drawn).toEqual([[1568, 1045]]); `

<a id="ui-06"></a>

## UI-06 · Navigation, Scroll und Modals

Sidebar, Settings, Login und Shared-Modal sind erreichbar, geben Fokus zurück und erhalten korrekten Scroll-/Runzustand; mobile Größen und Reduced Motion folgen denselben Aktionen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Ausgeführte Chromiumfälle und präzise jsdom-Framekontrollen; Auswahl an Viewports/Flows, keine vollständige visuelle Baseline.

**Befunde:** [G-025](gaps.md#g-025). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/app-ui.js](../../../static/app-ui.js)
- [static/js/app-dom-events.js](../../../static/js/app-dom-events.js)
- [static/js/app-init.js](../../../static/js/app-init.js)
- [static/js/chat-scroll.js](../../../static/js/chat-scroll.js)
- [static/js/composer-autosize.js](../../../static/js/composer-autosize.js)
- [static/js/composer-collapse.js](../../../static/js/composer-collapse.js)
- [static/js/mobile-header.js](../../../static/js/mobile-header.js)
- [static/js/share-dialog.js](../../../static/js/share-dialog.js)

**Testdateien:**

- [tests/e2e/test_browser_failure_recovery.py](../../../tests/e2e/test_browser_failure_recovery.py)
- [tests/e2e/test_chat_scroll_frontend.py](../../../tests/e2e/test_chat_scroll_frontend.py)
- [tests/e2e/test_mobile_navigation.py](../../../tests/e2e/test_mobile_navigation.py)
- [tests/e2e/test_reader_density.py](../../../tests/e2e/test_reader_density.py)
- [tests/e2e/test_smoke.py](../../../tests/e2e/test_smoke.py)
- [tests/js/chat-scroll.test.mjs](../../../tests/js/chat-scroll.test.mjs)
- [tests/js/composer-autosize.test.mjs](../../../tests/js/composer-autosize.test.mjs)
- [tests/js/mobile-header.test.mjs](../../../tests/js/mobile-header.test.mjs)
- [tests/test_navigation_settings_ui.py](../../../tests/test_navigation_settings_ui.py)

</details>

**Konkrete Teilbelege:**

- [moves the actual controls and restores their exact desktop slots without duplicates](../../../tests/js/mobile-header.test.mjs#L24) — JavaScript-Modultest mit jsdom. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 30](../../../tests/js/mobile-header.test.mjs#L30): ` expect(actions.parentElement.id).toBe('mobileConversationActions'); `
  - [Zeile 31](../../../tests/js/mobile-header.test.mjs#L31): ` expect(views.parentElement.id).toBe('mobileSidebarViews'); `
  - [Zeile 32](../../../tests/js/mobile-header.test.mjs#L32): ` document.getElementById('action').click();expect(listener).toHaveBeenCalledOnce(); `
  - [Zeile 34](../../../tests/js/mobile-header.test.mjs#L34): ` expect(actions.previousElementSibling.id).toBe('before'); `
  - [Zeile 35](../../../tests/js/mobile-header.test.mjs#L35): ` expect(actions.nextElementSibling.id).toBe('after'); `
  - [Zeile 36](../../../tests/js/mobile-header.test.mjs#L36): ` expect(views.parentElement.tagName).toBe('HEADER'); `
- [shrinks a wrapped placeholder when the actual width finishes changing without another viewport event](../../../tests/js/composer-autosize.test.mjs#L31) — Originales Autosize-Modul in jsdom mit kontrollierter Geometrie und Frames. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 34](../../../tests/js/composer-autosize.test.mjs#L34): ` expect(app.field.style.height).toBe('180px'); `
  - [Zeile 35](../../../tests/js/composer-autosize.test.mjs#L35): ` expect(app.field.style.overflowY).toBe('auto'); `
  - [Zeile 37](../../../tests/js/composer-autosize.test.mjs#L37): ` expect(app.field.style.height).toBe('180px'); `
  - [Zeile 39](../../../tests/js/composer-autosize.test.mjs#L39): ` expect(app.field.style.height).toBe('52px'); `
  - [Zeile 40](../../../tests/js/composer-autosize.test.mjs#L40): ` expect(app.field.style.overflowY).toBe('hidden'); `
- [test_chat_textarea_grows_until_responsive_height_limit](../../../tests/test_navigation_settings_ui.py#L280) — Quelltextverträge. **Datei**status vom 2026-10-02: passed=27.
  - [Zeile 285](../../../tests/test_navigation_settings_ui.py#L285): ` assert 'id="questionInput" rows="1"' in template `
  - [Zeile 286](../../../tests/test_navigation_settings_ui.py#L286): ` assert "resize: none;" in input_css `
  - [Zeile 287](../../../tests/test_navigation_settings_ui.py#L287): ` assert "overflow-y: hidden;" in input_css `
  - [Zeile 288](../../../tests/test_navigation_settings_ui.py#L288): ` assert "max-height: 220px;" in input_css `
  - [Zeile 289](../../../tests/test_navigation_settings_ui.py#L289): ` assert "@media (max-width: 1099px)" in input_css `
  - [Zeile 290](../../../tests/test_navigation_settings_ui.py#L290): ` assert "max-height: 180px;" in input_css `
- [test_question_input_grows_and_caps_on_desktop_and_mobile](../../../tests/e2e/test_smoke.py#L176) — Chromium gegen echte App-Routen und Demo-Firestore mit kontrollierter Identität/Modellen; ergänzend direkte Rendererfälle. **Datei**status vom 2026-10-02: passed=43.
  - [Zeile 184](../../../tests/e2e/test_smoke.py#L184): ` assert grown_height > base_height `
  - [Zeile 185](../../../tests/e2e/test_smoke.py#L185): ` assert grown_height < 220 `
  - [Zeile 196](../../../tests/e2e/test_smoke.py#L196): ` assert desktop["height"] == 220 `
  - [Zeile 197](../../../tests/e2e/test_smoke.py#L197): ` assert desktop["scrollHeight"] > desktop["clientHeight"] `
  - [Zeile 198](../../../tests/e2e/test_smoke.py#L198): ` assert desktop["overflowY"] == "auto" `
  - [Zeile 207](../../../tests/e2e/test_smoke.py#L207): ` assert round(mobile["height"]) == 180 `
- [keeps the reading position when offscreen activity shrinks, including native anchoring](../../../tests/js/chat-scroll.test.mjs#L37) — Originale Scrollsteuerung mit kontrollierten DOMmaßen und Frames. **Datei**status vom 2026-10-02: passed=16.
  - [Zeile 46](../../../tests/js/chat-scroll.test.mjs#L46): ` expect(app.window.scrollY).toBe(960); `
  - [Zeile 52](../../../tests/js/chat-scroll.test.mjs#L52): ` expect(app.window.scrollY).toBe(780); `
  - [Zeile 53](../../../tests/js/chat-scroll.test.mjs#L53): ` expect(app.window.scrollTo).not.toHaveBeenCalled(); `
  - [Zeile 55](../../../tests/js/chat-scroll.test.mjs#L55): ` expect(app.window.App.chatScroll.preserveAbove(activity)).toBeNull(); `
- [test_agent_review_and_completion_keep_visible_answer_still](../../../tests/e2e/test_chat_scroll_frontend.py#L13) — Chromium mit echten Appskripten und kontrollierten Antworten. **Datei**status vom 2026-10-02: passed=11.
  - [Zeile 39](../../../tests/e2e/test_chat_scroll_frontend.py#L39): ` expect(page.locator('#agentAnswerBody p')).to_have_count(45) `
  - [Zeile 45](../../../tests/e2e/test_chat_scroll_frontend.py#L45): ` page.wait_for_function('() => document.documentElement.scrollHeight - innerHeight - scrollY < 3') `
  - [Zeile 62](../../../tests/e2e/test_chat_scroll_frontend.py#L62): ` assert page.locator('#agentAnswerActivity').bounding_box()['y'] + page.locator('#agentAnswerActivity').bounding_box()['height'] < 0 `
  - [Zeile 86](../../../tests/e2e/test_chat_scroll_frontend.py#L86): ` assert max(samples) - min(samples) < 3, (stage, samples) `
  - [Zeile 87](../../../tests/e2e/test_chat_scroll_frontend.py#L87): ` expect(page.locator('#agentAnswerActivity details')).not_to_have_attribute('open', '') `
  - [Zeile 88](../../../tests/e2e/test_chat_scroll_frontend.py#L88): ` expect(page.locator('#agentAnswerActivity .agent-progress')).not_to_be_visible() `
- [test_six_answers_leave_room_to_read_and_keep_touch_targets](../../../tests/e2e/test_reader_density.py#L10) — Chromium mit echten Readerkomponenten und gemessener Geometrie. **Datei**status vom 2026-10-02: passed=2.
  - [Zeile 41](../../../tests/e2e/test_reader_density.py#L41): ` expect(page.locator('#answerReaderModels button')).to_have_count(6) `
  - [Zeile 53](../../../tests/e2e/test_reader_density.py#L53): ` assert 520 <= round(metrics['width']) <= 720 `
  - [Zeile 54](../../../tests/e2e/test_reader_density.py#L54): ` assert metrics['chatWidth'] >= 550 `
  - [Zeile 55](../../../tests/e2e/test_reader_density.py#L55): ` assert metrics['chatRight'] < metrics['readerLeft'] `
  - [Zeile 56](../../../tests/e2e/test_reader_density.py#L56): ` assert metrics['headerHeight'] <= 36 `
  - [Zeile 57](../../../tests/e2e/test_reader_density.py#L57): ` assert metrics['bodyTop'] < 340 `

<a id="ui-07"></a>

## UI-07 · Bootstrap, Skript-Reihenfolge und Styles

Serverkonfiguration wird escaped über Bootstrap-Daten übergeben; klassische Skripte laden in Vertragsreihenfolge, Globals haben eindeutige Owner und Styles konsistente Tokens.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Datei-/Source-Verträge sichern keine vollständige visuelle Darstellung.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/app-ui.js](../../../static/app-ui.js)
- [static/css/admin-benchmark.css](../../../static/css/admin-benchmark.css)
- [static/css/admin.css](../../../static/css/admin.css)
- [static/css/agent-chat.css](../../../static/css/agent-chat.css)
- [static/css/base.css](../../../static/css/base.css)
- [static/css/benchmark.css](../../../static/css/benchmark.css)
- [static/css/chat-scroll.css](../../../static/css/chat-scroll.css)
- [static/css/components-attachment-viewer.css](../../../static/css/components-attachment-viewer.css)
- [static/css/components-consensus-insights.css](../../../static/css/components-consensus-insights.css)
- [static/css/components-consensus-visuals.css](../../../static/css/components-consensus-visuals.css)
- [static/css/components-consensus.css](../../../static/css/components-consensus.css)
- [static/css/components-controls.css](../../../static/css/components-controls.css)
- [static/css/components-feedback.css](../../../static/css/components-feedback.css)
- [static/css/components-input.css](../../../static/css/components-input.css)
- [static/css/components-memory-edit.css](../../../static/css/components-memory-edit.css)
- [static/css/components-misc.css](../../../static/css/components-misc.css)
- [static/css/components-modals.css](../../../static/css/components-modals.css)
- [static/css/components-model-picker.css](../../../static/css/components-model-picker.css)
- [static/css/components-watch.css](../../../static/css/components-watch.css)
- [static/css/composer-attachments.css](../../../static/css/composer-attachments.css)
- [static/css/consensus-engine.css](../../../static/css/consensus-engine.css)
- [static/css/demo-action.css](../../../static/css/demo-action.css)
- [static/css/landing.css](../../../static/css/landing.css)
- [static/css/layout.css](../../../static/css/layout.css)
- [static/css/model-answer-reader.css](../../../static/css/model-answer-reader.css)
- [static/css/model-pulse.css](../../../static/css/model-pulse.css)
- [static/css/public-pages.css](../../../static/css/public-pages.css)
- [static/css/public-shell.css](../../../static/css/public-shell.css)
- [static/css/public-tokens.css](../../../static/css/public-tokens.css)
- [static/css/shell.css](../../../static/css/shell.css)
- [static/css/skeleton.css](../../../static/css/skeleton.css)
- [static/css/source-verification.css](../../../static/css/source-verification.css)
- [static/css/status-palette.css](../../../static/css/status-palette.css)
- [static/css/topics.css](../../../static/css/topics.css)
- [static/css/typography.css](../../../static/css/typography.css)
- [static/css/variables.css](../../../static/css/variables.css)
- [static/js/app-bootstrap.js](../../../static/js/app-bootstrap.js)
- [static/js/app-core.js](../../../static/js/app-core.js)
- [static/js/app-dom-events.js](../../../static/js/app-dom-events.js)
- [static/js/bundles.json](../../../static/js/bundles.json)
- [static/js/composer-autosize.js](../../../static/js/composer-autosize.js)
- [static/style.css](../../../static/style.css)
- [templates/index.html](../../../templates/index.html)

**Testdateien:**

- [tests/js/composer-autosize.test.mjs](../../../tests/js/composer-autosize.test.mjs)
- [tests/test_frontend_assets.py](../../../tests/test_frontend_assets.py)
- [tests/test_frontend_build.py](../../../tests/test_frontend_build.py)
- [tests/test_frontend_resilience.py](../../../tests/test_frontend_resilience.py)
- [tests/test_navigation_settings_ui.py](../../../tests/test_navigation_settings_ui.py)
- [tests/test_phase6_architecture.py](../../../tests/test_phase6_architecture.py)
- [tests/test_public_design_system.py](../../../tests/test_public_design_system.py)

</details>

**Konkrete Teilbelege:**

- [test_source_mode_serves_every_file_in_declared_order](../../../tests/test_frontend_assets.py#L55) — Asset-Funktionen, Dateisystem und isolierte Pages-Routen. **Datei**status vom 2026-10-02: passed=14.
  - [Zeile 67](../../../tests/test_frontend_assets.py#L67): ` assert served == expected `
- [shrinks a wrapped placeholder when the actual width finishes changing without another viewport event](../../../tests/js/composer-autosize.test.mjs#L31) — Originales Autosize-Modul in jsdom mit kontrollierter Geometrie und Frames. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 34](../../../tests/js/composer-autosize.test.mjs#L34): ` expect(app.field.style.height).toBe('180px'); `
  - [Zeile 35](../../../tests/js/composer-autosize.test.mjs#L35): ` expect(app.field.style.overflowY).toBe('auto'); `
  - [Zeile 37](../../../tests/js/composer-autosize.test.mjs#L37): ` expect(app.field.style.height).toBe('180px'); `
  - [Zeile 39](../../../tests/js/composer-autosize.test.mjs#L39): ` expect(app.field.style.height).toBe('52px'); `
  - [Zeile 40](../../../tests/js/composer-autosize.test.mjs#L40): ` expect(app.field.style.overflowY).toBe('hidden'); `
- [test_chat_textarea_grows_until_responsive_height_limit](../../../tests/test_navigation_settings_ui.py#L280) — Quelltextverträge. **Datei**status vom 2026-10-02: passed=27.
  - [Zeile 285](../../../tests/test_navigation_settings_ui.py#L285): ` assert 'id="questionInput" rows="1"' in template `
  - [Zeile 286](../../../tests/test_navigation_settings_ui.py#L286): ` assert "resize: none;" in input_css `
  - [Zeile 287](../../../tests/test_navigation_settings_ui.py#L287): ` assert "overflow-y: hidden;" in input_css `
  - [Zeile 288](../../../tests/test_navigation_settings_ui.py#L288): ` assert "max-height: 220px;" in input_css `
  - [Zeile 289](../../../tests/test_navigation_settings_ui.py#L289): ` assert "@media (max-width: 1099px)" in input_css `
  - [Zeile 290](../../../tests/test_navigation_settings_ui.py#L290): ` assert "max-height: 180px;" in input_css `
- [test_public_site_origin_is_neutral_validated_core_configuration](../../../tests/test_phase6_architecture.py#L27) — Statische Architektur-, Routing- und Assetverträge. **Datei**status vom 2026-10-02: passed=8.
  - [Zeile 28](../../../tests/test_phase6_architecture.py#L28): ` assert normalize_public_site_url(None) == "https://www.consens.io" `
  - [Zeile 29](../../../tests/test_phase6_architecture.py#L29): ` assert normalize_public_site_url("https://preview.example/") == "https://preview.example" `
  - [Zeile 31](../../../tests/test_phase6_architecture.py#L31): ` with pytest.raises(RuntimeError): `
  - [Zeile 37](../../../tests/test_phase6_architecture.py#L37): ` assert "from app.api.routers.pages import SITE_URL" not in service_sources `

<a id="ui-08"></a>

## UI-08 · Demo und Landing-Interaktionen

Demo bleibt lokal, startet auf bewusste Aktion, zeigt konsistente Beispielantworten und führt zum Login; Landing-Animationen dürfen Inhalt/Navigation nicht blockieren.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Demo-Teilfälle belegt. test_public_composer_mockups.py enthält dynamische Scroll-/--sp-/Toolbar-/Reduced-Motion-Prüfungen der Landinganimation, wurde aber nicht im Browser ausgeführt. Für die separate landing-insights.js-Logik gibt es keinen gezielten dynamischen Beleg; nicht den gesamten Landingbereich als ungetestet bezeichnen.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/demo.js](../../../static/demo.js)
- [static/js/landing-insights.js](../../../static/js/landing-insights.js)
- [static/js/landing-scenes.js](../../../static/js/landing-scenes.js)
- [templates/consensus-engine.html](../../../templates/consensus-engine.html)
- [templates/landing.html](../../../templates/landing.html)
- [templates/partials/composer_toolbar_mockup.html](../../../templates/partials/composer_toolbar_mockup.html)
- [templates/partials/product_result_mockup.html](../../../templates/partials/product_result_mockup.html)

**Testdateien:**

- [tests/e2e/test_public_composer_mockups.py](../../../tests/e2e/test_public_composer_mockups.py)
- [tests/e2e/test_smoke.py](../../../tests/e2e/test_smoke.py)
- [tests/js/demo-claim-coverage.test.mjs](../../../tests/js/demo-claim-coverage.test.mjs)
- [tests/test_demo_login_prompt.py](../../../tests/test_demo_login_prompt.py)

</details>

**Konkrete Teilbelege:**

- [marks every checkable consensus passage with the current coverage contract](../../../tests/js/demo-claim-coverage.test.mjs#L33) — JavaScript-Daten-/Modulintegration mit VM und jsdom. **Datei**status vom 2026-10-02: passed=2.
  - [Zeile 60](../../../tests/js/demo-claim-coverage.test.mjs#L60): ` expect(body.querySelectorAll(".cx-claim").length).toBe(19); `
  - [Zeile 61](../../../tests/js/demo-claim-coverage.test.mjs#L61): ` expect(fallback.hidden).toBe(true); `
  - [Zeile 71](../../../tests/js/demo-claim-coverage.test.mjs#L71): ` expect(unmarkedWords, passage.textContent).toBe(""); `

<a id="ui-09"></a>

## UI-09 · Analytics-Selbstausschluss

notrack=1 deaktiviert Tracking vor Trackerstart, notrack=0 hebt den Ausschluss auf; blockierter Storage darf Seitenstart nicht abbrechen. Adminseiten werden nicht getrackt.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Originalskript dynamisch vor Seiten-/Trackerstartmarker für Query- und Storagefehler ausgeführt; kein echter Trackerversand.

**Befunde:** [G-021](gaps.md#g-021). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/js/analytics-opt-out.js](../../../static/js/analytics-opt-out.js)
- [templates/partials/analytics.html](../../../templates/partials/analytics.html)

**Testdateien:**

- [tests/js/analytics-opt-out.test.mjs](../../../tests/js/analytics-opt-out.test.mjs)
- [tests/test_analytics_partial.py](../../../tests/test_analytics_partial.py)

</details>

**Konkrete Teilbelege:**

- [test_partial_ships_the_self_exclusion_switch](../../../tests/test_analytics_partial.py#L59) — Quelltextverträge. **Datei**status vom 2026-10-02: passed=5.
  - [Zeile 67](../../../tests/test_analytics_partial.py#L67): ` assert 'localStorage.setItem("umami.disabled", "1")' in opt_out `
  - [Zeile 68](../../../tests/test_analytics_partial.py#L68): ` assert 'localStorage.removeItem("umami.disabled")' in opt_out `
  - [Zeile 69](../../../tests/test_analytics_partial.py#L69): ` assert partial.index("analytics-opt-out.js") < partial.index("cloud.umami.is"), ( `
- [applies %s to %s before the next script runs](../../../tests/js/analytics-opt-out.test.mjs#L9) — Originales Skript in frischem jsdom vor instrumentiertem Trackerstart. **Datei**status vom 2026-10-02: passed=9.
  - [Zeile 19](../../../tests/js/analytics-opt-out.test.mjs#L19): ` expect(w.trackerDisabled).toBe(expected); `
  - [Zeile 20](../../../tests/js/analytics-opt-out.test.mjs#L20): ` expect(w.trackerStarted).toBe(true); `

<a id="data-01"></a>

## DATA-01 · Votes, Feedback und Modellstatistik

Feedback ist UID-begrenzt, Votes sind owner-/resultgebunden und zählen einmal. Aggregierte Statistik enthält keine Inhalte; öffentliche Counts kommen aus konsistentem gecachtem Snapshot.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Reale main-Feedback- und Statistikpersistenzpfade; Auth-/DBgrenzen kontrolliert, eingegebener Feedbacktext bewusst erlaubt.

**Befunde:** [G-034](gaps.md#g-034). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/pages.py](../../../app/api/routers/pages.py)
- [app/services/differences_stats.py](../../../app/services/differences_stats.py)
- [app/services/persistence_guard.py](../../../app/services/persistence_guard.py)

**Testdateien:**

- [tests/test_differences_stats.py](../../../tests/test_differences_stats.py)
- [tests/test_feedback.py](../../../tests/test_feedback.py)
- [tests/test_firestore_read_contracts.py](../../../tests/test_firestore_read_contracts.py)
- [tests/test_model_leaderboard.py](../../../tests/test_model_leaderboard.py)
- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)

</details>

**Konkrete Teilbelege:**

- [BuildDifferencesStatsDocTests::test_no_content_leaks_into_doc](../../../tests/test_differences_stats.py#L134) — Unit-Tests für Statistikprojektion. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 147](../../../tests/test_differences_stats.py#L147): ` self.assertNotIn(forbidden, flat) `
- [test_feedback_auth_payload_and_persisted_cooldown](../../../tests/test_feedback.py#L23) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=8.
  - [Zeile 33](../../../tests/test_feedback.py#L33): ` assert response.status_code == 401 `
  - [Zeile 34](../../../tests/test_feedback.py#L34): ` assert h.feedback_db.data == {} `
  - [Zeile 36](../../../tests/test_feedback.py#L36): ` assert response.status_code == 200, response.text `
  - [Zeile 38](../../../tests/test_feedback.py#L38): ` assert len(saved) == 1 `
  - [Zeile 39](../../../tests/test_feedback.py#L39): ` assert set(saved[0]) == {"uid", "email", "message", "timestamp"} `
  - [Zeile 40](../../../tests/test_feedback.py#L40): ` assert saved[0]["uid"] == "owner" and saved[0]["email"] == "me@example.test" `

<a id="bench-01"></a>

## BENCH-01 · Dataset, Budget und Closed-book-Vertrag

Stichproben sind deterministisch und Pilot/Final disjunkt; Parser bewertet nur explizite Antwortmarker, Payloads haben keine Webtools, Budgetstop erfolgt vor weiteren Calls.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Kleine synthetische Daten und Provider-Doubles; keine Repräsentativität oder Live-Modellqualität.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [benchmark/audit.py](../../../benchmark/audit.py)
- [benchmark/cli_validation.py](../../../benchmark/cli_validation.py)
- [benchmark/config.py](../../../benchmark/config.py)
- [benchmark/cost.py](../../../benchmark/cost.py)
- [benchmark/dataset.py](../../../benchmark/dataset.py)
- [benchmark/parse.py](../../../benchmark/parse.py)
- [benchmark/prompt.py](../../../benchmark/prompt.py)
- [benchmark/transport.py](../../../benchmark/transport.py)

**Testdateien:**

- [tests/test_auxiliary_cli.py](../../../tests/test_auxiliary_cli.py)
- [tests/test_benchmark_audits.py](../../../tests/test_benchmark_audits.py)
- [tests/test_benchmark_budget.py](../../../tests/test_benchmark_budget.py)
- [tests/test_benchmark_credentials.py](../../../tests/test_benchmark_credentials.py)
- [tests/test_benchmark_dataset.py](../../../tests/test_benchmark_dataset.py)
- [tests/test_benchmark_mode.py](../../../tests/test_benchmark_mode.py)
- [tests/test_benchmark_parse.py](../../../tests/test_benchmark_parse.py)
- [tests/test_benchmark_transport.py](../../../tests/test_benchmark_transport.py)

</details>

**Konkrete Teilbelege:**

- [ExtractLetterTests::test_final_answer_marker_on_last_line](../../../tests/test_benchmark_parse.py#L9) — Reine Parser-/Auswertungsfunktionen. **Datei**status vom 2026-10-02: passed=12.
  - [Zeile 10](../../../tests/test_benchmark_parse.py#L10): ` self.assertEqual( `
  - [Zeile 14](../../../tests/test_benchmark_parse.py#L14): ` self.assertEqual( `
- [test_invalid_execution_args_stop_before_dataset_or_provider](../../../tests/test_auxiliary_cli.py#L77) — Echte CLIs und Runner in netzwerkgesperrten Subprozessen. **Datei**status vom 2026-10-02: passed=21.
  - [Zeile 79](../../../tests/test_auxiliary_cli.py#L79): ` assert value == {'codes':[2], 'events':[]} `
  - [Zeile 80](../../../tests/test_auxiliary_cli.py#L80): ` assert not (tmp_path/'runs').exists() `
- [BenchmarkBudgetTests::test_tight_budget_stops_before_the_first_uncovered_audit_call](../../../tests/test_benchmark_budget.py#L53) — Benchmarkrunner mit deterministischem Transport und temporären Artefakten. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 60](../../../tests/test_benchmark_budget.py#L60): ` self.assertFalse(main.stopped) `
  - [Zeile 65](../../../tests/test_benchmark_budget.py#L65): ` self.assertTrue(result.stopped) `
  - [Zeile 66](../../../tests/test_benchmark_budget.py#L66): ` self.assertIn("audit", result.stop_reason) `
  - [Zeile 67](../../../tests/test_benchmark_budget.py#L67): ` self.assertIsNone(audits) `
  - [Zeile 68](../../../tests/test_benchmark_budget.py#L68): ` self.assertIsNone(summary) `
  - [Zeile 69](../../../tests/test_benchmark_budget.py#L69): ` self.assertEqual(transport.calls, []) `

<a id="bench-02"></a>

## BENCH-02 · Runner, Resume und Artefakte

Runs speichern effektive Konfiguration und getrennte Modell-/Consensus-/Synthesezellen; Resume dedupliziert, Retry bleibt explizit, Rohkeys werden redigiert. Große Modi bleiben hinter Budget-/Freigabegates.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Alle unterstützten CLI-Einstiege in isolierten Prozessen; Protokollfehler bleiben Fehler, gültige nichtauswertbare Antworten Enthaltung. Kein Livebenchmark.

**Befunde:** [G-035](gaps.md#g-035), [G-042](gaps.md#g-042). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [benchmark/__init__.py](../../../benchmark/__init__.py)
- [benchmark/__main__.py](../../../benchmark/__main__.py)
- [benchmark/run_experiment.py](../../../benchmark/run_experiment.py)
- [benchmark/run_sample.py](../../../benchmark/run_sample.py)
- [benchmark/runner.py](../../../benchmark/runner.py)

**Testdateien:**

- [tests/test_auxiliary_cli.py](../../../tests/test_auxiliary_cli.py)
- [tests/test_benchmark_audits.py](../../../tests/test_benchmark_audits.py)
- [tests/test_benchmark_budget.py](../../../tests/test_benchmark_budget.py)
- [tests/test_benchmark_cli.py](../../../tests/test_benchmark_cli.py)
- [tests/test_benchmark_manifest_clock.py](../../../tests/test_benchmark_manifest_clock.py)
- [tests/test_benchmark_protocol.py](../../../tests/test_benchmark_protocol.py)
- [tests/test_benchmark_redaction.py](../../../tests/test_benchmark_redaction.py)
- [tests/test_benchmark_run.py](../../../tests/test_benchmark_run.py)
- [tests/test_benchmark_runner.py](../../../tests/test_benchmark_runner.py)
- [tests/test_benchmark_transport.py](../../../tests/test_benchmark_transport.py)

</details>

**Konkrete Teilbelege:**

- [test_dry_run_creates_run_dir_and_manifest_without_http](../../../tests/test_benchmark_cli.py#L54) — CLI-Funktionen mit Dataset-/Runner-/Publisher-Doubles. **Datei**status vom 2026-10-02: passed=20.
  - [Zeile 56](../../../tests/test_benchmark_cli.py#L56): ` assert rc == 0 `
  - [Zeile 58](../../../tests/test_benchmark_cli.py#L58): ` assert (run_dir / "manifest.json").exists() `
  - [Zeile 59](../../../tests/test_benchmark_cli.py#L59): ` assert not (run_dir / "calls.jsonl").exists() `
  - [Zeile 60](../../../tests/test_benchmark_cli.py#L60): ` assert "Dry-Run" in capsys.readouterr().out `
- [test_invalid_execution_args_stop_before_dataset_or_provider](../../../tests/test_auxiliary_cli.py#L77) — Echte CLIs und Runner in netzwerkgesperrten Subprozessen. **Datei**status vom 2026-10-02: passed=21.
  - [Zeile 79](../../../tests/test_auxiliary_cli.py#L79): ` assert value == {'codes':[2], 'events':[]} `
  - [Zeile 80](../../../tests/test_auxiliary_cli.py#L80): ` assert not (tmp_path/'runs').exists() `
- [test_resume_across_seconds_days_and_dst_keeps_manifest](../../../tests/test_benchmark_manifest_clock.py#L15) — Echter Manifestvergleich mit kontrollierter Uhr. **Datei**status vom 2026-10-02: passed=5.
  - [Zeile 22](../../../tests/test_benchmark_manifest_clock.py#L22): ` assert (tmp_path / "manifest.json").read_bytes() == original `
- [test_protocol_failures_are_not_successful_abstentions](../../../tests/test_benchmark_protocol.py#L46) — Transport-, Record-, Resume- und Statistikpipeline mit HTTP-Response-Double. **Datei**status vom 2026-10-02: passed=15.
  - [Zeile 49](../../../tests/test_benchmark_protocol.py#L49): ` assert response.closed `
  - [Zeile 50](../../../tests/test_benchmark_protocol.py#L50): ` assert outcome["error_code"] == code `
  - [Zeile 51](../../../tests/test_benchmark_protocol.py#L51): ` assert outcome["error"] `
  - [Zeile 52](../../../tests/test_benchmark_protocol.py#L52): ` assert outcome["raw"] is None `
  - [Zeile 54](../../../tests/test_benchmark_protocol.py#L54): ` assert row["abstain"] is False `
  - [Zeile 55](../../../tests/test_benchmark_protocol.py#L55): ` assert row["extracted_letter"] is None `
- [test_all_model_families_use_one_openrouter_transport](../../../tests/test_benchmark_transport.py#L53) — Benchmarktransport mit HTTP-Doubles. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 59](../../../tests/test_benchmark_transport.py#L59): ` assert result["error"] is None `
  - [Zeile 60](../../../tests/test_benchmark_transport.py#L60): ` assert result["text"] == "The [S1] answer is (C)." `
  - [Zeile 61](../../../tests/test_benchmark_transport.py#L61): ` assert result["usage"] == {"prompt": 100, "completion": 20, "total": 120} `
  - [Zeile 62](../../../tests/test_benchmark_transport.py#L62): ` assert result["raw"] is OPENROUTER_RESPONSE `
  - [Zeile 63](../../../tests/test_benchmark_transport.py#L63): ` assert captured["url"] == OPENROUTER_CHAT_COMPLETIONS_URL `
  - [Zeile 64](../../../tests/test_benchmark_transport.py#L64): ` assert captured["params"] is None `
- [BenchmarkBudgetTests::test_tight_budget_stops_before_the_first_uncovered_audit_call](../../../tests/test_benchmark_budget.py#L53) — Benchmarkrunner mit deterministischem Transport und temporären Artefakten. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 60](../../../tests/test_benchmark_budget.py#L60): ` self.assertFalse(main.stopped) `
  - [Zeile 65](../../../tests/test_benchmark_budget.py#L65): ` self.assertTrue(result.stopped) `
  - [Zeile 66](../../../tests/test_benchmark_budget.py#L66): ` self.assertIn("audit", result.stop_reason) `
  - [Zeile 67](../../../tests/test_benchmark_budget.py#L67): ` self.assertIsNone(audits) `
  - [Zeile 68](../../../tests/test_benchmark_budget.py#L68): ` self.assertIsNone(summary) `
  - [Zeile 69](../../../tests/test_benchmark_budget.py#L69): ` self.assertEqual(transport.calls, []) `

<a id="bench-03"></a>

## BENCH-03 · Ergebnisberechnung und Adminberichte

Deduplizierte Zellen bestimmen Accuracy/Kosten/Fehler; Publish speichert kompakte Reports ohne Rohprompts, Reader verhindert Traversal und bevorzugt Firestore bei Duplikaten.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Echte Adminrollen-/Reportadapter mit kompakten lokalen Reports; Reportdarstellung zusätzlich dynamisch geprüft. Keine privaten Rohprompt-/Antwortdaten.

**Befunde:** [G-015](gaps.md#g-015), [G-042](gaps.md#g-042). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/benchmark_reports.py](../../../app/services/benchmark_reports.py)
- [benchmark/report_reader.py](../../../benchmark/report_reader.py)
- [benchmark/results.py](../../../benchmark/results.py)
- [static/js/admin-benchmark.js](../../../static/js/admin-benchmark.js)

**Testdateien:**

- [tests/js/admin-benchmark.test.mjs](../../../tests/js/admin-benchmark.test.mjs)
- [tests/test_benchmark_report_reader.py](../../../tests/test_benchmark_report_reader.py)
- [tests/test_benchmark_reports.py](../../../tests/test_benchmark_reports.py)
- [tests/test_benchmark_results.py](../../../tests/test_benchmark_results.py)
- [tests/test_http_adapter_auth.py](../../../tests/test_http_adapter_auth.py)

</details>

**Konkrete Teilbelege:**

- [test_publish_run_dir_stores_compact_report_only](../../../tests/test_benchmark_reports.py#L76) — Report-Publisher mit FakeCollection. **Datei**status vom 2026-10-02: passed=2.
  - [Zeile 83](../../../tests/test_benchmark_reports.py#L83): ` assert summary["run_id"] == "pilot_v1" `
  - [Zeile 86](../../../tests/test_benchmark_reports.py#L86): ` assert stored["storage_version"] == benchmark_reports.STORAGE_VERSION `
  - [Zeile 87](../../../tests/test_benchmark_reports.py#L87): ` assert stored["report"]["questions"][0]["models"]["openai"]["letter"] == "C" `
  - [Zeile 88](../../../tests/test_benchmark_reports.py#L88): ` assert "SECRET_RAW_ANSWER" not in stored_json `
  - [Zeile 89](../../../tests/test_benchmark_reports.py#L89): ` assert "SECRET_RAW_PROMPT" not in stored_json `
  - [Zeile 90](../../../tests/test_benchmark_reports.py#L90): ` assert "SECRET_RAW_PAYLOAD" not in stored_json `
- [test_every_topic_admin_method_enforces_real_policy_before_service](../../../tests/test_http_adapter_auth.py#L29) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. **Datei**status vom 2026-10-02: passed=38.
  - [Zeile 43](../../../tests/test_http_adapter_auth.py#L43): ` assert response.status_code == expected, response.text `
  - [Zeile 44](../../../tests/test_http_adapter_auth.py#L44): ` assert "error" in response.json() and "private" not in response.text `
  - [Zeile 45](../../../tests/test_http_adapter_auth.py#L45): ` assert database.documents == {} and database.query_reads == [] `
  - [Zeile 47](../../../tests/test_http_adapter_auth.py#L47): ` assert h.checks[-1][1]["check_revoked"] is True `
- [renders compact data, safely quotes labels and excludes raw prompts/answers](../../../tests/js/admin-benchmark.test.mjs#L25) — Originaler Viewer und Adminclient im jsdom. **Datei**status vom 2026-10-02: passed=7.
  - [Zeile 33](../../../tests/js/admin-benchmark.test.mjs#L33): ` await vi.waitFor(() => expect(doc.getElementById('runDetail').textContent).toContain('Run · run-a')); `
  - [Zeile 34](../../../tests/js/admin-benchmark.test.mjs#L34): ` expect(doc.getElementById('runDetail').textContent).toContain('50.0%'); `
  - [Zeile 35](../../../tests/js/admin-benchmark.test.mjs#L35): ` expect(doc.getElementById('runDetail').textContent).toContain('<img src=x onerror=alert(1)>'); `
  - [Zeile 36](../../../tests/js/admin-benchmark.test.mjs#L36): ` expect(doc.querySelector('img')).toBeNull(); `
  - [Zeile 37](../../../tests/js/admin-benchmark.test.mjs#L37): ` expect(doc.body.textContent).not.toContain('PRIVATE'); `

<a id="build-01"></a>

## BUILD-01 · Reproduzierbare Frontendartefakte

Manifest/Fingerprint und Inhaltsnamen passen zu aktuellen Quellen; alter Output wird sicher bereinigt, öffentliche Assets haben konsistente Cachekeys und vendorte Libraries definierte Eingänge.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Build-/Dateisystem- und direkter Vendorhelpernachweis mit synthetischen Paketen; echter Gitcheckout mit core.autocrlf=true schützt dist-Hash-/Byteidentität. Browserausführung nicht jedes erzeugten Bundles einzeln garantiert.

**Befunde:** [G-036](gaps.md#g-036). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/core/assets.py](../../../app/core/assets.py)
- [app/core/version.py](../../../app/core/version.py)
- [package.json](../../../package.json)
- [scripts/build_frontend.mjs](../../../scripts/build_frontend.mjs)
- [scripts/frontend-output.mjs](../../../scripts/frontend-output.mjs)
- [scripts/vendor_frontend.mjs](../../../scripts/vendor_frontend.mjs)

**Testdateien:**

- [tests/js/dompurify-vendor.test.mjs](../../../tests/js/dompurify-vendor.test.mjs)
- [tests/js/frontend-output.test.mjs](../../../tests/js/frontend-output.test.mjs)
- [tests/js/vendor-frontend.test.mjs](../../../tests/js/vendor-frontend.test.mjs)
- [tests/test_frontend_assets.py](../../../tests/test_frontend_assets.py)
- [tests/test_frontend_build.py](../../../tests/test_frontend_build.py)
- [tests/test_phase6_architecture.py](../../../tests/test_phase6_architecture.py)

</details>

**Konkrete Teilbelege:**

- [leaves the old manifest and assets readable when publication fails](../../../tests/js/frontend-output.test.mjs#L99) — Echter Buildoutput und temporärer Gitcheckout. **Datei**status vom 2026-10-02: passed=5.
  - [Zeile 102](../../../tests/js/frontend-output.test.mjs#L102): ` await expect(publishBuild(dir, new Map([["invalid.js", "bad"]]), {})).rejects.toThrow(); `
  - [Zeile 103](../../../tests/js/frontend-output.test.mjs#L103): ` expect(JSON.parse(await fs.readFile(path.join(dir, "manifest.json"), "utf8"))).toEqual(first.manifest); `
  - [Zeile 104](../../../tests/js/frontend-output.test.mjs#L104): ` expect(await fs.readFile(path.join(dir, first.name), "utf8")).toBe("/* version 1 */"); `
- [test_public_site_origin_is_neutral_validated_core_configuration](../../../tests/test_phase6_architecture.py#L27) — Statische Architektur-, Routing- und Assetverträge. **Datei**status vom 2026-10-02: passed=8.
  - [Zeile 28](../../../tests/test_phase6_architecture.py#L28): ` assert normalize_public_site_url(None) == "https://www.consens.io" `
  - [Zeile 29](../../../tests/test_phase6_architecture.py#L29): ` assert normalize_public_site_url("https://preview.example/") == "https://preview.example" `
  - [Zeile 31](../../../tests/test_phase6_architecture.py#L31): ` with pytest.raises(RuntimeError): `
  - [Zeile 37](../../../tests/test_phase6_architecture.py#L37): ` assert "from app.api.routers.pages import SITE_URL" not in service_sources `
- [copies every pinned library, license and font byte and retains unrelated old versions](../../../tests/js/vendor-frontend.test.mjs#L25) — Echter Vendorhelper mit temporärem Dateisystem und synthetischen Paketen. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 29](../../../tests/js/vendor-frontend.test.mjs#L29): ` expect(inputs).toHaveLength(10); `
  - [Zeile 30](../../../tests/js/vendor-frontend.test.mjs#L30): ` expect(inputs.slice(-2)).toEqual(['static/vendor/katex/1.0.0/dist/fonts/A.ttf', 'static/vendor/katex/1.0.0/dist/fonts/Z.woff2']); `
  - [Zeile 32](../../../tests/js/vendor-frontend.test.mjs#L32): `` expect(await fs.readFile(path.join(root, `static/vendor/${name}/1.0.0/${file}`))).toEqual(await fs.readFile(path.join(root, `node_modules/${name}/${file}`))); ``
  - [Zeile 34](../../../tests/js/vendor-frontend.test.mjs#L34): ` expect(await fs.readFile(path.join(root, 'static/vendor/marked/0.9.0/keep.js'), 'utf8')).toBe('old'); `
  - [Zeile 38](../../../tests/js/vendor-frontend.test.mjs#L38): ` for (const relative of inputs) expect((await fs.stat(path.join(root, relative))).mtimeMs).toBe(old.getTime()); `

<a id="build-02"></a>

## BUILD-02 · Test- und Emulator-Einstieg

Backend/Frontend/Browser sind reproduzierbar auswählbar; Browser nutzt ausschließlich lokales Demo-Firestore, niemals produktive Credentials. Toolfehler müssen als Fehler sichtbar bleiben.

**Anforderungsbasis:** [docs/testing.md](../../testing.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Reale Windows-PowerShell-/pwsh-Einstiege und getrennte Python-/JS-/Chromium-/Emulator-/Rules-Gates. Nutzerentscheidung: schnelle Push-/PR-Prüfungen, schwere Jobs bei ReadyForReview oder manueller Auswahl, docs-only ausgenommen. Bewusste Auswahl-Skips beweisen keinen Volltest; tatsächliche CI-Läufe stehen separat im Laufbericht.

**Befunde:** [G-024](gaps.md#g-024), [G-025](gaps.md#g-025), [G-026](gaps.md#g-026), [G-046](gaps.md#g-046). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [.github/workflows/tests.yml](../../../.github/workflows/tests.yml)
- [dev.ps1](../../../dev.ps1)
- [firebase.json](../../../firebase.json)
- [firestore.indexes.json](../../../firestore.indexes.json)
- [vitest.config.mjs](../../../vitest.config.mjs)

**Testdateien:**

- [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py)
- [tests/rules/firestore.rules.test.mjs](../../../tests/rules/firestore.rules.test.mjs)
- [tests/test_dev_cli.py](../../../tests/test_dev_cli.py)
- [tests/test_e2e_safety.py](../../../tests/test_e2e_safety.py)
- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)

</details>

**Konkrete Teilbelege:**

- [test_frontend_preserves_failure_and_stops](../../../tests/test_dev_cli.py#L164) — Windows-PowerShell-/pwsh-Subprozesse mit instrumentierten Runnern. **Datei**status vom 2026-10-02: passed=28.
  - [Zeile 167](../../../tests/test_dev_cli.py#L167): ` assert result.returncode == 23, result.stdout + result.stderr `
  - [Zeile 168](../../../tests/test_dev_cli.py#L168): ` assert len(calls) == expected_calls `
  - [Zeile 169](../../../tests/test_dev_cli.py#L169): ` assert "[dev] OK" not in result.stdout `
- [`${identity}: no client read/write/query/delete of ${path.replace(owner, '{uid}').split('/').slice(0, -1).join('/')}`](../../../tests/rules/firestore.rules.test.mjs#L49) — Echte Firebase-Clientoperationen gegen Firestore-Emulator. **Datei**status vom 2026-10-02: passed=49.
  - [Zeile 54](../../../tests/rules/firestore.rules.test.mjs#L54): ` await assertFails(getDoc(ref)); `
  - [Zeile 55](../../../tests/rules/firestore.rules.test.mjs#L55): ` await assertFails(getDocs(collection(db, path.split('/').slice(0, -1).join('/')))); `
  - [Zeile 56](../../../tests/rules/firestore.rules.test.mjs#L56): ` await assertFails(setDoc(ref, { role: 'admin', tier: 'pro' })); `
  - [Zeile 57](../../../tests/rules/firestore.rules.test.mjs#L57): ` await assertFails(updateDoc(ref, { role: 'admin', tier: 'pro' })); `
  - [Zeile 58](../../../tests/rules/firestore.rules.test.mjs#L58): ` await assertFails(deleteDoc(ref)); `
- [test_phase4_server_reuses_its_child_and_rejects_an_unowned_listener](../../../tests/e2e/test_phase4_frontend.py#L143) — Chromium und ein gemeinsam gestarteter lokaler Testserver. **Datei**status vom 2026-10-02: passed=29.
  - [Zeile 150](../../../tests/e2e/test_phase4_frontend.py#L150): ` assert next(imported_fixture) == phase4_server `
  - [Zeile 151](../../../tests/e2e/test_phase4_frontend.py#L151): ` with pytest.raises(StopIteration): `
  - [Zeile 153](../../../tests/e2e/test_phase4_frontend.py#L153): ` assert request.config._phase4_server_url == phase4_server `
  - [Zeile 156](../../../tests/e2e/test_phase4_frontend.py#L156): ` with pytest.raises(RuntimeError, match='already in use'): `

<a id="build-03"></a>

## BUILD-03 · Scheduled Publisher und Workflows

Standalone-Publisher funktioniert ohne Backendabhängigkeiten, verwendet stabiles Idempotency-Key und behandelt Publish/Skip/Disabled nachvollziehbar; Konfiguration/Indexing/Watch sind explizite Schritte.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Subprozess mit Netzwerkverbot und HTTP-Doubles; kein realer Scheduler-/Render-/Publishlauf.

**Befunde:** [G-024](gaps.md#g-024). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [.github/workflows/publish-consensus.yml](../../../.github/workflows/publish-consensus.yml)
- [.github/workflows/publisher-tests.yml](../../../.github/workflows/publisher-tests.yml)
- [.github/workflows/restart-render.yml](../../../.github/workflows/restart-render.yml)
- [scripts/publish_consensus.py](../../../scripts/publish_consensus.py)

**Testdateien:**

- [tests/test_publish_consensus_script.py](../../../tests/test_publish_consensus_script.py)
- [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py)

</details>

**Konkrete Teilbelege:**

- [PublisherStandaloneTests::test_scheduled_flow_without_packages_or_external_services](../../../tests/test_publisher_standalone.py#L98) — Isolierter Python-Subprozess ohne optionale Pakete oder externe Services. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 156](../../../tests/test_publisher_standalone.py#L156): ` self.assert_success(self.run_python(["-c", code], env={ `

<a id="tools-01"></a>

## TOOLS-01 · Wartungs- und Reparaturwerkzeuge

Repair betrifft nur explizit gewähltes Konto/Projekt, Inspect schreibt nicht. Claim-Key-Backfill erhält fremde Felder, überspringt fertige Runs, Dry-run schreibt nicht und Force ist explizit.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_cli_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Echte Entry-Points in netzwerkgesperrten Subprozessen; SDK/Recovery/Judge ersetzt. Dry-run kann außerhalb der Tests Judgekosten verursachen.

**Befunde:** [G-022](gaps.md#g-022), [G-023](gaps.md#g-023). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [scripts/backfill_claim_keys.py](../../../scripts/backfill_claim_keys.py)
- [scripts/repair_agent_allowance.py](../../../scripts/repair_agent_allowance.py)

**Testdateien:**

- [tests/test_maintenance_scripts.py](../../../tests/test_maintenance_scripts.py)

</details>

**Konkrete Teilbelege:**

- [test_repair_inspect_does_not_apply_but_selected_account_recovery_does](../../../tests/test_maintenance_scripts.py#L114) — Echte Entry-Points in isolierten Subprozessen. **Datei**status vom 2026-10-02: passed=13.
  - [Zeile 116](../../../tests/test_maintenance_scripts.py#L116): ` assert inspected['codes'] == [0] `
  - [Zeile 117](../../../tests/test_maintenance_scripts.py#L117): ` assert inspected['events'] == [['lookup','selected@example.invalid'], ['read','selected-account'], ['close']] `
  - [Zeile 119](../../../tests/test_maintenance_scripts.py#L119): ` assert applied['codes'] == [0] `
  - [Zeile 120](../../../tests/test_maintenance_scripts.py#L120): ` assert [e for e in applied['events'] if e[0] == 'recover'] == [['recover','selected-account']] `

<a id="tools-02"></a>

## TOOLS-02 · Evaluations-/Vorschauwerkzeuge

Evaluationen haben begrenzte Inputs/Modelle/Budgets und nachvollziehbare Ergebnisse; lokale Vorschauen schreiben ausschließlich gewünschte Artefakte, keine Produktdaten.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_cli_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Unterstützte sample/experiment-CLIs durch reale Runner mit synthetischem Transport; keine bezahlte Modellqualität.

**Befunde:** [G-035](gaps.md#g-035). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [benchmark/cli_validation.py](../../../benchmark/cli_validation.py)
- [scripts/evaluate_agent_delegation.py](../../../scripts/evaluate_agent_delegation.py)
- [scripts/evaluate_source_verification.py](../../../scripts/evaluate_source_verification.py)
- [scripts/probe_agent_delegation.py](../../../scripts/probe_agent_delegation.py)
- [scripts/render_watch_preview.py](../../../scripts/render_watch_preview.py)

**Testdateien:**

- [tests/test_agent_delegation.py](../../../tests/test_agent_delegation.py)
- [tests/test_auxiliary_cli.py](../../../tests/test_auxiliary_cli.py)
- [tests/test_source_verification.py](../../../tests/test_source_verification.py)

</details>

**Konkrete Teilbelege:**

- [test_evaluation_dataset_has_complete_v3_expected_verdicts](../../../tests/test_source_verification.py#L753) — Verifikations-/Dokument-/Pipeline-Integration mit Fetch/Judge/HTTPX-Doubles und Threads. **Datei**status vom 2026-10-02: passed=122.
  - [Zeile 755](../../../tests/test_source_verification.py#L755): ` assert all(len(case) == 7 for case in CASES) `
  - [Zeile 757](../../../tests/test_source_verification.py#L757): ` assert expected['contradiction'] == expected['untrusted_instructions'] == 'contradicted' `
  - [Zeile 758](../../../tests/test_source_verification.py#L758): ` assert expected['missing_condition'] == 'partial' `
- [test_quality_gate_rejects_cheap_bad_unknown_unpaired_or_unused_delegation](../../../tests/test_agent_delegation.py#L299) — Echte Workerthreads/Mailboxen mit Store- und Provider-Doubles. **Datei**status vom 2026-10-02: passed=16.
  - [Zeile 305](../../../tests/test_agent_delegation.py#L305): ` assert gate(rows)["approved"] is True `
  - [Zeile 310](../../../tests/test_agent_delegation.py#L310): ` assert gate(candidate)["approved"] is False `
  - [Zeile 311](../../../tests/test_agent_delegation.py#L311): ` assert not gate([r for r in rows if r["task"] == "parallel_ledgers"])["approved"] `
  - [Zeile 312](../../../tests/test_agent_delegation.py#L312): ` assert not gate([{**r, "agents": 0} for r in rows])["approved"] `
- [test_invalid_execution_args_stop_before_dataset_or_provider](../../../tests/test_auxiliary_cli.py#L77) — Echte CLIs und Runner in netzwerkgesperrten Subprozessen. **Datei**status vom 2026-10-02: passed=21.
  - [Zeile 79](../../../tests/test_auxiliary_cli.py#L79): ` assert value == {'codes':[2], 'events':[]} `
  - [Zeile 80](../../../tests/test_auxiliary_cli.py#L80): ` assert not (tmp_path/'runs').exists() `

<a id="auth-05"></a>

## AUTH-05 · Direkte Firestore-Clients bleiben gesperrt

Browser-/REST-Clients dürfen weder fremde noch eigene Firestore-Dokumente lesen/schreiben; insbesondere dürfen Nutzer ihren tier/role nicht selbst ändern. Backend-Admin-SDK ist eine getrennte Autorisierungsgrenze.

**Anforderungsbasis:** [firestore.rules](../../../firestore.rules) · ` documented_security_invariant `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Echte Firebaseclient-Denials mit vier Identitäten und permissiver Negativkontrolle; AdminSDK dient nur Seed/Cleanup eigener IDs. Keine produktive IAMfreigabe.

**Befunde:** [G-001](gaps.md#g-001). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [firebase.json](../../../firebase.json)
- [firestore.rules](../../../firestore.rules)

**Testdateien:**

- [tests/rules/firestore.rules.test.mjs](../../../tests/rules/firestore.rules.test.mjs)

</details>

**Konkrete Teilbelege:**

- [`${identity}: no client read/write/query/delete of ${path.replace(owner, '{uid}').split('/').slice(0, -1).join('/')}`](../../../tests/rules/firestore.rules.test.mjs#L49) — Echte Firebase-Clientoperationen gegen Firestore-Emulator. **Datei**status vom 2026-10-02: passed=49.
  - [Zeile 54](../../../tests/rules/firestore.rules.test.mjs#L54): ` await assertFails(getDoc(ref)); `
  - [Zeile 55](../../../tests/rules/firestore.rules.test.mjs#L55): ` await assertFails(getDocs(collection(db, path.split('/').slice(0, -1).join('/')))); `
  - [Zeile 56](../../../tests/rules/firestore.rules.test.mjs#L56): ` await assertFails(setDoc(ref, { role: 'admin', tier: 'pro' })); `
  - [Zeile 57](../../../tests/rules/firestore.rules.test.mjs#L57): ` await assertFails(updateDoc(ref, { role: 'admin', tier: 'pro' })); `
  - [Zeile 58](../../../tests/rules/firestore.rules.test.mjs#L58): ` await assertFails(deleteDoc(ref)); `

<a id="agent-06"></a>

## AGENT-06 · Private Dateien und Nachrichtenzuordnung

Agentdateien sind owner-/chatgebunden, privat gespeichert, begrenzt extrahiert und an ihrem Turn wiederauffindbar. Löschen und Kontosperren verhindern spätere Neuerstellung.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Aktualisierung 02.10.2026: Assertions und ersetzte Grenzen im aktuellen Dateikatalog beschrieben.

**Testgrenze:** Native Quoten/Metadaten, echter Cloudadapter an strengem Bucketdouble und Retrykaskade; keine produktive Bucket-IAM oder globale Objekt-/DBatomizität.

**Befunde:** [G-044](gaps.md#g-044). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/agent_files.py](../../../app/api/routers/agent_files.py)
- [app/services/agent_file_extract.py](../../../app/services/agent_file_extract.py)
- [app/services/agent_files.py](../../../app/services/agent_files.py)
- [static/css/agent-workspace.css](../../../static/css/agent-workspace.css)
- [static/js/agent-workspace.js](../../../static/js/agent-workspace.js)

**Testdateien:**

- [tests/e2e/test_account_deletion_transactions.py](../../../tests/e2e/test_account_deletion_transactions.py)
- [tests/e2e/test_agent_chat_frontend.py](../../../tests/e2e/test_agent_chat_frontend.py)
- [tests/e2e/test_agent_workspace_frontend.py](../../../tests/e2e/test_agent_workspace_frontend.py)
- [tests/e2e/test_file_storage_transactions.py](../../../tests/e2e/test_file_storage_transactions.py)
- [tests/js/agent-workspace.test.mjs](../../../tests/js/agent-workspace.test.mjs)
- [tests/test_agent_files.py](../../../tests/test_agent_files.py)
- [tests/test_attachment_meta.py](../../../tests/test_attachment_meta.py)
- [tests/test_pdf_extraction_isolation.py](../../../tests/test_pdf_extraction_isolation.py)

</details>

**Konkrete Teilbelege:**

- [test_real_extraction_storage_download_and_owner_isolation](../../../tests/test_agent_files.py#L28) — Datei-Service, echte Extraktion und isolierte HTTP-Adapter. **Datei**status vom 2026-10-02: passed=24.
  - [Zeile 32](../../../tests/test_agent_files.py#L32): ` assert raw.startswith(b'Price: 42') `
  - [Zeile 33](../../../tests/test_agent_files.py#L33): ` assert data['parts'][0]['locator'] == 'lines 1-2' `
  - [Zeile 34](../../../tests/test_agent_files.py#L34): ` assert 'object_key' not in meta and 'parts' not in meta `
  - [Zeile 35](../../../tests/test_agent_files.py#L35): ` assert all(not isinstance(v, bytes) for doc in files.db.documents.values() for v in doc.values()) `
  - [Zeile 38](../../../tests/test_agent_files.py#L38): ` with pytest.raises(ChatNotFound): action() `
  - [Zeile 39](../../../tests/test_agent_files.py#L39): ` assert files.download('owner', chat, meta['id'])[1] == raw `
- [test_native_cloud_upload_quota_foreign_download_and_delete_retry](../../../tests/e2e/test_file_storage_transactions.py#L50) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator, echter Cloudadapter und DOCX-/PDF-Renderer. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 62](../../../tests/e2e/test_file_storage_transactions.py#L62): ` assert sum(value is not None for value in outcomes) == 1 `
  - [Zeile 63](../../../tests/e2e/test_file_storage_transactions.py#L63): ` assert files.quota_ref(uid).get().to_dict() == {"count": 1, "bytes": 15} `
  - [Zeile 64](../../../tests/e2e/test_file_storage_transactions.py#L64): ` assert files.download(uid, chat, saved["id"])[1] == b"private fixture" `
  - [Zeile 66](../../../tests/e2e/test_file_storage_transactions.py#L66): ` with pytest.raises(ChatNotFound): `
  - [Zeile 68](../../../tests/e2e/test_file_storage_transactions.py#L68): ` assert bucket.calls == before_calls `
  - [Zeile 70](../../../tests/e2e/test_file_storage_transactions.py#L70): ` with pytest.raises(OSError, match="Retryable"): `
- [test_native_account_cascade_resumes_failed_objects_without_foreign_loss](../../../tests/e2e/test_account_deletion_transactions.py#L60) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter Cloudadapter. **Datei**status vom 2026-10-02: passed=2.
  - [Zeile 76](../../../tests/e2e/test_account_deletion_transactions.py#L76): ` assert service.cleanup_uid(uid) == ["chats"] `
  - [Zeile 78](../../../tests/e2e/test_account_deletion_transactions.py#L78): ` assert job["status"] == "pending" and "chats" not in job["completed_areas"] `
  - [Zeile 79](../../../tests/e2e/test_account_deletion_transactions.py#L79): ` assert set(job["completed_areas"]) == AREAS - {"chats"} `
  - [Zeile 80](../../../tests/e2e/test_account_deletion_transactions.py#L80): ` with pytest.raises(persistence_guard.AccountDeletionInProgress): `
  - [Zeile 83](../../../tests/e2e/test_account_deletion_transactions.py#L83): ` assert account_deletion.FirestoreAccountDeletion(db).cleanup_uid(uid) == [] `
  - [Zeile 85](../../../tests/e2e/test_account_deletion_transactions.py#L85): ` assert final["status"] == "completed" and set(final["completed_areas"]) == AREAS `
- [test_all_pro_chat_models_are_grouped_by_provider](../../../tests/e2e/test_agent_chat_frontend.py#L71) — Chromium mit echtem App-Frontend und kontrollierten Agent-APIantworten. **Datei**status vom 2026-10-02: passed=31.
  - [Zeile 77](../../../tests/e2e/test_agent_chat_frontend.py#L77): ` assert cfg.PREMIUM_MODELS <= {model['id'] for model in catalog['models']} `
  - [Zeile 86](../../../tests/e2e/test_agent_chat_frontend.py#L86): ` expect(page.locator('#agentModelDropdown')).to_be_enabled() `
  - [Zeile 87](../../../tests/e2e/test_agent_chat_frontend.py#L87): ` expect(page.locator('#agentModelDropdown option')).to_have_count(len(catalog['models'])) `
  - [Zeile 91](../../../tests/e2e/test_agent_chat_frontend.py#L91): ` assert menu['x'] >= 0 and menu['x'] + menu['width'] <= width `
  - [Zeile 92](../../../tests/e2e/test_agent_chat_frontend.py#L92): ` assert menu['y'] >= 0 and menu['y'] + menu['height'] <= 900 `
  - [Zeile 93](../../../tests/e2e/test_agent_chat_frontend.py#L93): ` expect(page.locator('.agent-model-picker button[data-model-group]')).to_have_count(len(cfg.PROVIDERS)) `

<a id="agent-07"></a>

## AGENT-07 · Versionierte DOCX-/PDF-Dokumente

Versionierte private DOCX-/PDF-Dokumente bewahren Quellenhashes und Vorversionen. Firestore-Speicherschema2 codiert Tabellenzeilen als Maps mit cells, Lesecodec stellt die DocumentSpec verlustfrei wieder her.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Aktualisierung 02.10.2026: Assertions und ersetzte Grenzen im aktuellen Dateikatalog beschrieben.

**Testgrenze:** Echte Renderer und native Metadaten-/Quotatransaktionen mit strengem Bucket-Double. Keine vollständige visuelle Seiten- oder produktive Bucket-IAM-Prüfung.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/agent_document_render.py](../../../app/services/agent_document_render.py)
- [app/services/agent_document_spec.py](../../../app/services/agent_document_spec.py)
- [app/services/agent_documents.py](../../../app/services/agent_documents.py)

**Testdateien:**

- [tests/e2e/test_account_deletion_transactions.py](../../../tests/e2e/test_account_deletion_transactions.py)
- [tests/e2e/test_agent_gmail_frontend.py](../../../tests/e2e/test_agent_gmail_frontend.py)
- [tests/e2e/test_agent_workspace_frontend.py](../../../tests/e2e/test_agent_workspace_frontend.py)
- [tests/e2e/test_file_storage_transactions.py](../../../tests/e2e/test_file_storage_transactions.py)
- [tests/js/agent-workspace.test.mjs](../../../tests/js/agent-workspace.test.mjs)
- [tests/test_agent_documents.py](../../../tests/test_agent_documents.py)
- [tests/test_agent_gmail.py](../../../tests/test_agent_gmail.py)

</details>

**Konkrete Teilbelege:**

- [test_real_docx_pdf_version_and_saved_provenance](../../../tests/test_agent_documents.py#L24) — Dokument-Service mit echten DOCX-/PDF-Renderern und temporärem Speicher. **Datei**status vom 2026-10-02: passed=12.
  - [Zeile 30](../../../tests/test_agent_documents.py#L30): ` assert len(created["files"]) == 2 `
  - [Zeile 33](../../../tests/test_agent_documents.py#L33): ` assert meta["turn_id"] == "first" and meta["source_file_ids"] == [source["id"]] `
  - [Zeile 37](../../../tests/test_agent_documents.py#L37): ` assert "Tax treatment" in text and "Model B prioritizes" in text and "42 EUR" in text `
  - [Zeile 40](../../../tests/test_agent_documents.py#L40): ` assert document.tables[0].cell(1, 1).text == "42 EUR" `
  - [Zeile 42](../../../tests/test_agent_documents.py#L42): ` assert saved["sources"][0]["sha256"] == source["sha256"] `
  - [Zeile 43](../../../tests/test_agent_documents.py#L43): ` assert saved["content_hash"] == created["content_hash"] `
- [test_native_cloud_upload_quota_foreign_download_and_delete_retry](../../../tests/e2e/test_file_storage_transactions.py#L50) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator, echter Cloudadapter und DOCX-/PDF-Renderer. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 62](../../../tests/e2e/test_file_storage_transactions.py#L62): ` assert sum(value is not None for value in outcomes) == 1 `
  - [Zeile 63](../../../tests/e2e/test_file_storage_transactions.py#L63): ` assert files.quota_ref(uid).get().to_dict() == {"count": 1, "bytes": 15} `
  - [Zeile 64](../../../tests/e2e/test_file_storage_transactions.py#L64): ` assert files.download(uid, chat, saved["id"])[1] == b"private fixture" `
  - [Zeile 66](../../../tests/e2e/test_file_storage_transactions.py#L66): ` with pytest.raises(ChatNotFound): `
  - [Zeile 68](../../../tests/e2e/test_file_storage_transactions.py#L68): ` assert bucket.calls == before_calls `
  - [Zeile 70](../../../tests/e2e/test_file_storage_transactions.py#L70): ` with pytest.raises(OSError, match="Retryable"): `
- [test_native_account_cascade_resumes_failed_objects_without_foreign_loss](../../../tests/e2e/test_account_deletion_transactions.py#L60) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter Cloudadapter. **Datei**status vom 2026-10-02: passed=2.
  - [Zeile 76](../../../tests/e2e/test_account_deletion_transactions.py#L76): ` assert service.cleanup_uid(uid) == ["chats"] `
  - [Zeile 78](../../../tests/e2e/test_account_deletion_transactions.py#L78): ` assert job["status"] == "pending" and "chats" not in job["completed_areas"] `
  - [Zeile 79](../../../tests/e2e/test_account_deletion_transactions.py#L79): ` assert set(job["completed_areas"]) == AREAS - {"chats"} `
  - [Zeile 80](../../../tests/e2e/test_account_deletion_transactions.py#L80): ` with pytest.raises(persistence_guard.AccountDeletionInProgress): `
  - [Zeile 83](../../../tests/e2e/test_account_deletion_transactions.py#L83): ` assert account_deletion.FirestoreAccountDeletion(db).cleanup_uid(uid) == [] `
  - [Zeile 85](../../../tests/e2e/test_account_deletion_transactions.py#L85): ` assert final["status"] == "completed" and set(final["completed_areas"]) == AREAS `
- [test_gmail_draft_revision_document_download_and_restoration](../../../tests/e2e/test_agent_gmail_frontend.py#L12) — Chromium mit kontrollierten Verbindungen und Gmailaktionsantworten. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 26](../../../tests/e2e/test_agent_gmail_frontend.py#L26): ` assert route.request.headers.get('authorization','').startswith('Bearer ') `
  - [Zeile 52](../../../tests/e2e/test_agent_gmail_frontend.py#L52): ` expect(page.locator('#agentGoogleChips')).to_contain_text('Gmail · owner@example.org') `
  - [Zeile 55](../../../tests/e2e/test_agent_gmail_frontend.py#L55): ` expect(page.locator('#agentGoogleActions')).to_contain_text('Decision-v1.pdf') `
  - [Zeile 56](../../../tests/e2e/test_agent_gmail_frontend.py#L56): ` assert requests[0]['google_selection']['gmail'] is True and requests[0]['google_selection']['calendar'] is False `
  - [Zeile 57](../../../tests/e2e/test_agent_gmail_frontend.py#L57): ` expect(consent).not_to_be_checked();assert not confirmed `
  - [Zeile 57](../../../tests/e2e/test_agent_gmail_frontend.py#L57): ` expect(consent).not_to_be_checked();assert not confirmed `

<a id="google-01"></a>

## GOOGLE-01 · Google-Verbindung und Datenfreigabe

OAuth bindet State/PKCE an Browser und Owner; Scopes werden getrennt gewährt, Tokens verschlüsselt gespeichert und nach Widerruf/Disconnect nicht wiederbelebt. Google-Daten dürfen nur mit expliziter Nachrichtenzustimmung und zugelassenem Modellhosting verarbeitet werden.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Aktualisierung 02.10.2026: Assertions und ersetzte Grenzen im aktuellen Dateikatalog beschrieben.

**Testgrenze:** Signierte synthetische Identität, Google-/DB-/Auth-Doubles. Browser testet echten Callback/CSP mit gemocktem OAuth-Finish, keinen Live-OAuth.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/agent_google.py](../../../app/api/routers/agent_google.py)
- [app/services/google_connections.py](../../../app/services/google_connections.py)
- [static/css/agent-google.css](../../../static/css/agent-google.css)
- [static/js/agent-google.js](../../../static/js/agent-google.js)

**Testdateien:**

- [tests/e2e/test_account_deletion_transactions.py](../../../tests/e2e/test_account_deletion_transactions.py)
- [tests/e2e/test_agent_google_frontend.py](../../../tests/e2e/test_agent_google_frontend.py)
- [tests/js/agent-google.test.mjs](../../../tests/js/agent-google.test.mjs)
- [tests/test_google_connections.py](../../../tests/test_google_connections.py)

</details>

**Konkrete Teilbelege:**

- [test_oauth_state_pkce_browser_owner_and_incremental_scopes](../../../tests/test_google_connections.py#L35) — OAuth-/Connectiondienste, signierte Testidentität und HTTP-Adapter. **Datei**status vom 2026-10-02: passed=15.
  - [Zeile 38](../../../tests/test_google_connections.py#L38): ` assert query["include_granted_scopes"]==["true"] and query["code_challenge_method"]==["S256"] `
  - [Zeile 39](../../../tests/test_google_connections.py#L39): ` assert "gmail" not in query["scope"][0] and "calendar.events" not in query["scope"][0] `
  - [Zeile 41](../../../tests/test_google_connections.py#L41): ` with pytest.raises(GoogleError,match="session"): `
  - [Zeile 47](../../../tests/test_google_connections.py#L47): ` assert result["capabilities"]==["calendar_read"] `
  - [Zeile 48](../../../tests/test_google_connections.py#L48): ` assert "new-access" not in json.dumps(list(google.db.documents.values())) and "new-refresh" not in json.dumps(result) `
  - [Zeile 51](../../../tests/test_google_connections.py#L51): ` assert base64.urlsafe_b64encode(hashlib.sha256(sent["code_verifier"].encode()).digest()).decode().rstrip("=")==query["code_challenge"][0] `
- [test_native_account_cascade_resumes_failed_objects_without_foreign_loss](../../../tests/e2e/test_account_deletion_transactions.py#L60) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter Cloudadapter. **Datei**status vom 2026-10-02: passed=2.
  - [Zeile 76](../../../tests/e2e/test_account_deletion_transactions.py#L76): ` assert service.cleanup_uid(uid) == ["chats"] `
  - [Zeile 78](../../../tests/e2e/test_account_deletion_transactions.py#L78): ` assert job["status"] == "pending" and "chats" not in job["completed_areas"] `
  - [Zeile 79](../../../tests/e2e/test_account_deletion_transactions.py#L79): ` assert set(job["completed_areas"]) == AREAS - {"chats"} `
  - [Zeile 80](../../../tests/e2e/test_account_deletion_transactions.py#L80): ` with pytest.raises(persistence_guard.AccountDeletionInProgress): `
  - [Zeile 83](../../../tests/e2e/test_account_deletion_transactions.py#L83): ` assert account_deletion.FirestoreAccountDeletion(db).cleanup_uid(uid) == [] `
  - [Zeile 85](../../../tests/e2e/test_account_deletion_transactions.py#L85): ` assert final["status"] == "completed" and set(final["completed_areas"]) == AREAS `

<a id="google-02"></a>

## GOOGLE-02 · Kalender lesen und exakt bestätigen

Nur ausgewählte Kalender und begrenzte Zeiträume werden gelesen. Ein vorgeschlagener Write benötigt den angezeigten Hash, aktuelle Berechtigung und gegebenenfalls ETag. Unklarer Ausgang wird reconciled, nie blind erneut geschrieben.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Aktualisierung 02.10.2026: Assertions und ersetzte Grenzen im aktuellen Dateikatalog beschrieben.

**Testgrenze:** Native Aktionsclaims und echter Payload/Guardpfad, ausschließlich HTTPwire kontrolliert; keine echte Einladung/Zustellung.

**Befunde:** [G-043](gaps.md#g-043). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/agent_google.py](../../../app/api/routers/agent_google.py)
- [app/services/agent_actions.py](../../../app/services/agent_actions.py)
- [app/services/agent_calendar.py](../../../app/services/agent_calendar.py)
- [static/js/agent-google.js](../../../static/js/agent-google.js)

**Testdateien:**

- [tests/e2e/test_agent_google_frontend.py](../../../tests/e2e/test_agent_google_frontend.py)
- [tests/e2e/test_google_action_transactions.py](../../../tests/e2e/test_google_action_transactions.py)
- [tests/js/agent-google.test.mjs](../../../tests/js/agent-google.test.mjs)
- [tests/test_agent_calendar.py](../../../tests/test_agent_calendar.py)

</details>

**Konkrete Teilbelege:**

- [test_prepare_does_not_write_and_confirmation_is_exact_once](../../../tests/test_agent_calendar.py#L42) — Kalender-Service und HTTP-Adapter mit Fake-DB und Google-Transport. **Datei**status vom 2026-10-02: passed=9.
  - [Zeile 45](../../../tests/test_agent_calendar.py#L45): ` assert writes(google)==[] and prepared["status"]=="pending" `
  - [Zeile 46](../../../tests/test_agent_calendar.py#L46): ` assert "reviewer@example.org" in prepared["preview"]["attendees"] `
  - [Zeile 48](../../../tests/test_agent_calendar.py#L48): ` assert repeated["id"]==prepared["id"] `
  - [Zeile 49](../../../tests/test_agent_calendar.py#L49): ` with pytest.raises(GoogleError,match="changed"): `
  - [Zeile 51](../../../tests/test_agent_calendar.py#L51): ` assert writes(google)==[] `
  - [Zeile 55](../../../tests/test_agent_calendar.py#L55): ` assert any(result["status"]=="succeeded" for result in results) `
- [test_native_google_confirmation_one_attempt_and_unknown_never_retries](../../../tests/e2e/test_google_action_transactions.py#L13) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator mit echtem Aktions- und HTTP-Payloadpfad. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 45](../../../tests/e2e/test_google_action_transactions.py#L45): ` assert len(attempts) == 1 `
  - [Zeile 46](../../../tests/e2e/test_google_action_transactions.py#L46): ` assert all(result["status"] in {"executing", "unknown"} for result in results) `
  - [Zeile 47](../../../tests/e2e/test_google_action_transactions.py#L47): ` assert confirm()["status"] == "unknown" `
  - [Zeile 48](../../../tests/e2e/test_google_action_transactions.py#L48): ` assert actions.reconcile(uid, chat, proposal["id"])["status"] == "unknown" `
  - [Zeile 49](../../../tests/e2e/test_google_action_transactions.py#L49): ` assert len(attempts) == 1 `
  - [Zeile 51](../../../tests/e2e/test_google_action_transactions.py#L51): ` with pytest.raises((GoogleError, ChatNotFound)): `

<a id="google-03"></a>

## GOOGLE-03 · Gmail lesen, Entwurf und Versandfreigabe

Gezielte Suche, begrenzte Thread-/Bodyseiten und private Anhangimporte liefern untrusted Evidenz. Vorschläge binden Empfänger, Replymetadaten und Anhangversion; Versand benötigt separate Sendeberechtigung und erneute Bestätigung nach Änderung.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Aktualisierung 02.10.2026: Assertions und ersetzte Grenzen im aktuellen Dateikatalog beschrieben.

**Testgrenze:** Native Aktionsclaims und echter Payload/Guardpfad, ausschließlich HTTPwire kontrolliert; keine echte Mailzustellung.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/agent_google.py](../../../app/api/routers/agent_google.py)
- [app/services/agent_actions.py](../../../app/services/agent_actions.py)
- [app/services/agent_gmail.py](../../../app/services/agent_gmail.py)
- [static/js/agent-google.js](../../../static/js/agent-google.js)

**Testdateien:**

- [tests/e2e/test_agent_gmail_frontend.py](../../../tests/e2e/test_agent_gmail_frontend.py)
- [tests/e2e/test_google_action_transactions.py](../../../tests/e2e/test_google_action_transactions.py)
- [tests/js/agent-google.test.mjs](../../../tests/js/agent-google.test.mjs)
- [tests/test_agent_gmail.py](../../../tests/test_agent_gmail.py)

</details>

**Konkrete Teilbelege:**

- [test_separate_oauth_read_and_send_scopes_and_local_draft_before_send](../../../tests/test_agent_gmail.py#L50) — Gmail-/Aktionsdienste und echter Agentloop mit Transport-/DB-Doubles. **Datei**status vom 2026-10-02: passed=21.
  - [Zeile 54](../../../tests/test_agent_gmail.py#L54): ` assert 'calendar' not in scope and 'gmail.compose' not in scope and 'gmail.modify' not in scope `
  - [Zeile 55](../../../tests/test_agent_gmail.py#L55): ` assert ('gmail.send' in scope)==(cap=='gmail_send') `
  - [Zeile 58](../../../tests/test_agent_gmail.py#L58): ` assert saved['preview']['send_authorized'] is False and not google.wire.calls `
  - [Zeile 59](../../../tests/test_agent_gmail.py#L59): ` with pytest.raises(GoogleError): actions.confirm('owner',chat,saved['id'],saved['hash']) `
  - [Zeile 60](../../../tests/test_agent_gmail.py#L60): ` assert actions.get('owner',chat,saved['id'])['status']=='pending' `
  - [Zeile 61](../../../tests/test_agent_gmail.py#L61): ` assert all(t.name not in {'send_mail','confirm_action'} for t in tool.tools()) `
- [test_native_google_confirmation_one_attempt_and_unknown_never_retries](../../../tests/e2e/test_google_action_transactions.py#L13) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator mit echtem Aktions- und HTTP-Payloadpfad. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 45](../../../tests/e2e/test_google_action_transactions.py#L45): ` assert len(attempts) == 1 `
  - [Zeile 46](../../../tests/e2e/test_google_action_transactions.py#L46): ` assert all(result["status"] in {"executing", "unknown"} for result in results) `
  - [Zeile 47](../../../tests/e2e/test_google_action_transactions.py#L47): ` assert confirm()["status"] == "unknown" `
  - [Zeile 48](../../../tests/e2e/test_google_action_transactions.py#L48): ` assert actions.reconcile(uid, chat, proposal["id"])["status"] == "unknown" `
  - [Zeile 49](../../../tests/e2e/test_google_action_transactions.py#L49): ` assert len(attempts) == 1 `
  - [Zeile 51](../../../tests/e2e/test_google_action_transactions.py#L51): ` with pytest.raises((GoogleError, ChatNotFound)): `
- [test_gmail_draft_revision_document_download_and_restoration](../../../tests/e2e/test_agent_gmail_frontend.py#L12) — Chromium mit kontrollierten Verbindungen und Gmailaktionsantworten. **Datei**status vom 2026-10-02: passed=3.
  - [Zeile 26](../../../tests/e2e/test_agent_gmail_frontend.py#L26): ` assert route.request.headers.get('authorization','').startswith('Bearer ') `
  - [Zeile 52](../../../tests/e2e/test_agent_gmail_frontend.py#L52): ` expect(page.locator('#agentGoogleChips')).to_contain_text('Gmail · owner@example.org') `
  - [Zeile 55](../../../tests/e2e/test_agent_gmail_frontend.py#L55): ` expect(page.locator('#agentGoogleActions')).to_contain_text('Decision-v1.pdf') `
  - [Zeile 56](../../../tests/e2e/test_agent_gmail_frontend.py#L56): ` assert requests[0]['google_selection']['gmail'] is True and requests[0]['google_selection']['calendar'] is False `
  - [Zeile 57](../../../tests/e2e/test_agent_gmail_frontend.py#L57): ` expect(consent).not_to_be_checked();assert not confirmed `
  - [Zeile 57](../../../tests/e2e/test_agent_gmail_frontend.py#L57): ` expect(consent).not_to_be_checked();assert not confirmed `

<a id="cons-06"></a>

## CONS-06 · Autoritative Antwortreceipts und Abschlusszustand

Nur gespeicherte, an Owner/Run/Frage/Modell gebundene Antworten bilden Consensus. Unterbrochene Antworten gelten nicht als fertig, Tokenlimit bleibt sichtbar markiert; unvollständige Synthese wird nicht als vollständiges Ergebnis gespeichert oder gewertet.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Aktualisierung 02.10.2026: Assertions und ersetzte Grenzen im aktuellen Dateikatalog beschrieben.

**Testgrenze:** Router-/Service- und DOMgrenzen getrennt; synthetische Provider, keine durchgehende persistierte Browserreise.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/chat.py](../../../app/api/routers/chat.py)
- [app/services/answer_receipts.py](../../../app/services/answer_receipts.py)
- [app/services/llm/completion.py](../../../app/services/llm/completion.py)
- [static/js/consensus-run.js](../../../static/js/consensus-run.js)
- [static/js/query-send.js](../../../static/js/query-send.js)

**Testdateien:**

- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/js/result-integrity.test.mjs](../../../tests/js/result-integrity.test.mjs)
- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)
- [tests/test_result_integrity.py](../../../tests/test_result_integrity.py)
- [tests/test_streaming.py](../../../tests/test_streaming.py)

</details>

**Konkrete Teilbelege:**

- [test_bookmark_quota_counts_merges_and_rejects_oversize](../../../tests/test_phase5_operations.py#L160) — Gemischt: Services mit DB-/HTTP-Doubles, Thread-/Async-Tests und Deployment-Quelltextverträge. **Datei**status vom 2026-10-02: passed=34.
  - [Zeile 161](../../../tests/test_phase5_operations.py#L161): ` assert persistence_guard.MAX_BOOKMARKS_PER_USER == 250 `
  - [Zeile 176](../../../tests/test_phase5_operations.py#L176): ` assert first["query"] == "Q" `
  - [Zeile 177](../../../tests/test_phase5_operations.py#L177): ` assert isinstance(first["timestamp"], datetime) `
  - [Zeile 178](../../../tests/test_phase5_operations.py#L178): ` assert jsonable_encoder(first)["timestamp"] == first["timestamp"].isoformat() `
  - [Zeile 179](../../../tests/test_phase5_operations.py#L179): ` assert second["responses"] == {"OpenAI": "A", "Gemini": "B"} `
  - [Zeile 184](../../../tests/test_phase5_operations.py#L184): ` assert usage["bookmark_count"] == 1 `
- [test_j01_saved_consensus_reload_followup_keeps_native_identity_and_context](../../../tests/e2e/test_persisted_journeys.py#L150) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 155](../../../tests/e2e/test_persisted_journeys.py#L155): ` assert saved.ok, saved.text() `
  - [Zeile 156](../../../tests/e2e/test_persisted_journeys.py#L156): ` assert j.request('GET', '/bookmarks/' + first['bookmark'], uid='journey-'+'f'*32).status == 404 `
  - [Zeile 158](../../../tests/e2e/test_persisted_journeys.py#L158): ` j.page.wait_for_function('() => typeof window.openBookmark === "function" && window.__consensioAuthState?.known') `
  - [Zeile 160](../../../tests/e2e/test_persisted_journeys.py#L160): ` expect(j.page.locator('#consensusResponse')).to_contain_text('Mock consensus', timeout=15000) `
  - [Zeile 161](../../../tests/e2e/test_persisted_journeys.py#L161): ` expect(j.page.locator('#questionInput')).to_have_attribute('placeholder', 'Ask a follow-up question') `
  - [Zeile 163](../../../tests/e2e/test_persisted_journeys.py#L163): ` assert second['chat'] == first['chat'] and second['turn'] != first['turn'] `

<a id="quota-03"></a>

## QUOTA-03 · Gemeinsames Tokenkonto und Nachmessung

Compare, Consensus, Deep Think und Agent nutzen ein UTC-Tageskonto je Nutzer. Admission hält eine Modusschätzung, einzelne Operationen buchen einmal und geben Restholds frei; unbekannter Verbrauch bleibt als begrenzte Schätzung belastet und kann genau einmal nachgemessen werden.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Aktualisierung 02.10.2026: Assertions und ersetzte Grenzen im aktuellen Dateikatalog beschrieben.

**Testgrenze:** Synthetische Provider-Usage und tatsächliche native Buchungs-/Reservierungszustände, UTC-Bindung sowie J01/J02 vom Browser bis Ledger. Emulator-Retries sind beobachtet; reale Providerrechnungen und produktive Last sind nicht belegt.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/agent_quota.py](../../../app/services/agent_quota.py)
- [app/services/agent_usage_reconciliation.py](../../../app/services/agent_usage_reconciliation.py)
- [app/services/llm/usage_meter.py](../../../app/services/llm/usage_meter.py)
- [app/services/run_metering.py](../../../app/services/run_metering.py)
- [app/services/usage_repository.py](../../../app/services/usage_repository.py)
- [static/js/sidebar-quota.js](../../../static/js/sidebar-quota.js)
- [static/js/token-budget.js](../../../static/js/token-budget.js)

**Testdateien:**

- [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py)
- [tests/e2e/test_usage_transactions.py](../../../tests/e2e/test_usage_transactions.py)
- [tests/js/sidebar-quota.test.mjs](../../../tests/js/sidebar-quota.test.mjs)
- [tests/test_agent_root_compaction.py](../../../tests/test_agent_root_compaction.py)
- [tests/test_agent_usage_reconciliation.py](../../../tests/test_agent_usage_reconciliation.py)
- [tests/test_run_usage_endpoints.py](../../../tests/test_run_usage_endpoints.py)
- [tests/test_run_usage_repository.py](../../../tests/test_run_usage_repository.py)
- [tests/test_usage_authorization.py](../../../tests/test_usage_authorization.py)
- [tests/test_usage_meter.py](../../../tests/test_usage_meter.py)

</details>

**Konkrete Teilbelege:**

- [test_hundreds_of_sequential_steps_keep_the_root_bounded_without_losing_usage](../../../tests/test_agent_root_compaction.py#L36) — Session-/Usage-Repositories mit Fake-Transaktionen. **Datei**status vom 2026-10-02: passed=7.
  - [Zeile 43](../../../tests/test_agent_root_compaction.py#L43): ` assert store.claim(*args, loop.model, step=step, run_token=loop.run_token, `
  - [Zeile 50](../../../tests/test_agent_root_compaction.py#L50): ` assert len(root["step_states"]) == len(root["step_usage"]) == ROOT_SETTLED_STEP_WINDOW `
  - [Zeile 51](../../../tests/test_agent_root_compaction.py#L51): ` assert len(root["reservations"]) == ROOT_SETTLED_STEP_WINDOW `
  - [Zeile 52](../../../tests/test_agent_root_compaction.py#L52): ` assert root["compacted_steps"] == steps - ROOT_SETTLED_STEP_WINDOW `
  - [Zeile 53](../../../tests/test_agent_root_compaction.py#L53): ` assert max(sizes) < ROOT_MAX_BYTES and max(sizes) - min(sizes) < 1024  # flat, not growing `
  - [Zeile 54](../../../tests/test_agent_root_compaction.py#L54): ` assert root["step_states"][f"completion:{steps - 1}"] == "succeeded" `
- [test_native_identical_key_and_booking_are_exactly_once](../../../tests/e2e/test_usage_transactions.py#L26) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 32](../../../tests/e2e/test_usage_transactions.py#L32): ` assert sorted(result.idempotent for result in results) == [False, True] `
  - [Zeile 39](../../../tests/e2e/test_usage_transactions.py#L39): ` assert ledger["used"] == 25 and ledger["pipeline_estimated"] == 5 and ledger["pipeline_holds"] == {} `
  - [Zeile 40](../../../tests/e2e/test_usage_transactions.py#L40): ` assert not agent_quota.quota_ref(db, other, admission(now).period).get().exists `
- [test_j02_stop_reload_recover_preserves_partial_and_charges_only_started_step](../../../tests/e2e/test_persisted_journeys.py#L186) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. **Datei**status vom 2026-10-02: passed=6.
  - [Zeile 196](../../../tests/e2e/test_persisted_journeys.py#L196): ` expect(j.page.locator('#agentAnswerBody')).to_contain_text('Saved partial answer', timeout=30000) `
  - [Zeile 199](../../../tests/e2e/test_persisted_journeys.py#L199): ` j.page.wait_for_function('() => Date.now() - App.runRegistry.visible().startedAt > 800') `
  - [Zeile 201](../../../tests/e2e/test_persisted_journeys.py#L201): ` j.page.wait_for_function('() => App.runRegistry.visible()?.status === "canceled"') `
  - [Zeile 205](../../../tests/e2e/test_persisted_journeys.py#L205): ` assert len(state['calls']) == 8  # orchestrator + six comparison providers + partial synthesis `
  - [Zeile 208](../../../tests/e2e/test_persisted_journeys.py#L208): ` assert turn['data']['status'] == 'failed' `
  - [Zeile 209](../../../tests/e2e/test_persisted_journeys.py#L209): ` assert turn['data']['agent_failure']['code'] == 'cancelled' `

<a id="watch-07"></a>

## WATCH-07 · Dauerhafte Benachrichtigungs-Outbox

Watch-/Topicresultat und Zustellabsicht werden zusammen committed. Ein begrenzter Retry prüft vor Versand aktuellen Owner/Status/Consent, Leaseowner sperrt alte Worker; unklare externe Zustellung ist keine globale Exactly-once-Garantie.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Aktualisierung 02.10.2026: Assertions und ersetzte Grenzen im aktuellen Dateikatalog beschrieben.

**Testgrenze:** Native atomare Ergebnis-/History-/Outboxcommits, Claims und stale Acks; SMTP/Telegram ersetzt, externe Zustellung bleibt at-least-once.

**Befunde:** [G-045](gaps.md#g-045). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/mailer.py](../../../app/services/mailer.py)
- [app/services/notification_delivery.py](../../../app/services/notification_delivery.py)
- [app/services/notification_outbox.py](../../../app/services/notification_outbox.py)
- [app/services/topic_runner.py](../../../app/services/topic_runner.py)
- [app/services/watch_scheduler.py](../../../app/services/watch_scheduler.py)

**Testdateien:**

- [tests/e2e/test_account_deletion_transactions.py](../../../tests/e2e/test_account_deletion_transactions.py)
- [tests/e2e/test_watch_delivery_transactions.py](../../../tests/e2e/test_watch_delivery_transactions.py)
- [tests/test_account_deletion_retry.py](../../../tests/test_account_deletion_retry.py)
- [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)
- [tests/test_watch_review_regressions.py](../../../tests/test_watch_review_regressions.py)

</details>

**Konkrete Teilbelege:**

- [test_failed_area_remains_pending_and_only_that_area_is_retried](../../../tests/test_account_deletion_retry.py#L69) — Service mit In-Memory-Datenbank. **Datei**status vom 2026-10-02: passed=1.
  - [Zeile 163](../../../tests/test_account_deletion_retry.py#L163): ` assert first_errors == ["owned_shares"] `
  - [Zeile 164](../../../tests/test_account_deletion_retry.py#L164): ` assert second_errors == [] `
  - [Zeile 165](../../../tests/test_account_deletion_retry.py#L165): ` assert calls["shares"] == 2 `
  - [Zeile 166](../../../tests/test_account_deletion_retry.py#L166): ` assert calls["source_checks"] == 1 `
  - [Zeile 167](../../../tests/test_account_deletion_retry.py#L167): ` assert calls["api"] == 1 `
  - [Zeile 168](../../../tests/test_account_deletion_retry.py#L168): ` assert calls["subcollections"] == 1 `
- [test_native_account_cascade_resumes_failed_objects_without_foreign_loss](../../../tests/e2e/test_account_deletion_transactions.py#L60) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter Cloudadapter. **Datei**status vom 2026-10-02: passed=2.
  - [Zeile 76](../../../tests/e2e/test_account_deletion_transactions.py#L76): ` assert service.cleanup_uid(uid) == ["chats"] `
  - [Zeile 78](../../../tests/e2e/test_account_deletion_transactions.py#L78): ` assert job["status"] == "pending" and "chats" not in job["completed_areas"] `
  - [Zeile 79](../../../tests/e2e/test_account_deletion_transactions.py#L79): ` assert set(job["completed_areas"]) == AREAS - {"chats"} `
  - [Zeile 80](../../../tests/e2e/test_account_deletion_transactions.py#L80): ` with pytest.raises(persistence_guard.AccountDeletionInProgress): `
  - [Zeile 83](../../../tests/e2e/test_account_deletion_transactions.py#L83): ` assert account_deletion.FirestoreAccountDeletion(db).cleanup_uid(uid) == [] `
  - [Zeile 85](../../../tests/e2e/test_account_deletion_transactions.py#L85): ` assert final["status"] == "completed" and set(final["completed_areas"]) == AREAS `
- [test_native_outbox_claim_takeover_rejects_stale_ack_and_terminal_replay](../../../tests/e2e/test_watch_delivery_transactions.py#L8) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 15](../../../tests/e2e/test_watch_delivery_transactions.py#L15): ` assert sum(claim is not None for claim in claims) == 1 `
  - [Zeile 20](../../../tests/e2e/test_watch_delivery_transactions.py#L20): ` assert current["lease_owner"] != old["lease_owner"] `
  - [Zeile 21](../../../tests/e2e/test_watch_delivery_transactions.py#L21): ` assert not outbox.finish(ref.id, old["lease_owner"], outbox.SENT, now=later, db=db) `
  - [Zeile 22](../../../tests/e2e/test_watch_delivery_transactions.py#L22): ` assert ref.get().to_dict() == before `
  - [Zeile 23](../../../tests/e2e/test_watch_delivery_transactions.py#L23): ` assert outbox.finish(ref.id, current["lease_owner"], outbox.SENT, now=later, db=db) `
  - [Zeile 24](../../../tests/e2e/test_watch_delivery_transactions.py#L24): ` assert outbox.claim(ref.id, now=later + timedelta(days=1), db=db) is None `

<a id="watch-08"></a>

## WATCH-08 · Belegbasierte Änderung, Ziel und Probe

Neue Quellen, Wiederbewertung und Modellwechsel bleiben getrennt. Die stehende Antwort bleibt bei dünner Evidenz erhalten; Recheck bestätigt Wiederbewertung. Ein belegtes Ziel beendet den Watch, begrenzte Probes ziehen Vollprüfung nur bei neuen Belegen vor.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Aktualisierung 02.10.2026: Assertions und ersetzte Grenzen im aktuellen Dateikatalog beschrieben.

**Testgrenze:** Beleg-/Judgequalität synthetisch; Probeclaim/-budget/-konfigfences nativ geprüft. Livequalität und Tagesbudget unter produktiver Last bleiben Betriebsfragen.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/claim_ledger.py](../../../app/services/claim_ledger.py)
- [app/services/drift_signal.py](../../../app/services/drift_signal.py)
- [app/services/evidence_change.py](../../../app/services/evidence_change.py)
- [app/services/watch_probe.py](../../../app/services/watch_probe.py)
- [static/js/watch-dashboard.js](../../../static/js/watch-dashboard.js)
- [static/js/watch.js](../../../static/js/watch.js)
- [templates/topic.html](../../../templates/topic.html)

**Testdateien:**

- [tests/e2e/test_watch_delivery_transactions.py](../../../tests/e2e/test_watch_delivery_transactions.py)
- [tests/js/watch-dashboard-state.test.mjs](../../../tests/js/watch-dashboard-state.test.mjs)
- [tests/test_drift_signal.py](../../../tests/test_drift_signal.py)
- [tests/test_watch_evidence_model.py](../../../tests/test_watch_evidence_model.py)
- [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

</details>

**Konkrete Teilbelege:**

- [test_the_gpt6_record_holds_the_release_instead_of_flip_flopping](../../../tests/test_drift_signal.py#L26) — Deterministische Unit-Tests. **Datei**status vom 2026-10-02: passed=15.
  - [Zeile 39](../../../tests/test_drift_signal.py#L39): ` assert [point["signal"] for point in annotated] == ["stable", "moved", "held", "held"] `
  - [Zeile 40](../../../tests/test_drift_signal.py#L40): ` assert [point["trigger"] for point in annotated] == ["stable", "changed", "stable", "stable"] `
  - [Zeile 41](../../../tests/test_drift_signal.py#L41): ` assert drift_signal.accepted_index(annotated) == 1 `
- [test_native_outbox_claim_takeover_rejects_stale_ack_and_terminal_replay](../../../tests/e2e/test_watch_delivery_transactions.py#L8) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. **Datei**status vom 2026-10-02: passed=4.
  - [Zeile 15](../../../tests/e2e/test_watch_delivery_transactions.py#L15): ` assert sum(claim is not None for claim in claims) == 1 `
  - [Zeile 20](../../../tests/e2e/test_watch_delivery_transactions.py#L20): ` assert current["lease_owner"] != old["lease_owner"] `
  - [Zeile 21](../../../tests/e2e/test_watch_delivery_transactions.py#L21): ` assert not outbox.finish(ref.id, old["lease_owner"], outbox.SENT, now=later, db=db) `
  - [Zeile 22](../../../tests/e2e/test_watch_delivery_transactions.py#L22): ` assert ref.get().to_dict() == before `
  - [Zeile 23](../../../tests/e2e/test_watch_delivery_transactions.py#L23): ` assert outbox.finish(ref.id, current["lease_owner"], outbox.SENT, now=later, db=db) `
  - [Zeile 24](../../../tests/e2e/test_watch_delivery_transactions.py#L24): ` assert outbox.claim(ref.id, now=later + timedelta(days=1), db=db) is None `
- [test_new_evidence_must_cite_a_source_the_standing_answer_did_not_have](../../../tests/test_watch_evidence_model.py#L31) — Evidence-/Probe-/Ledgerdienste mit Fake-DB. **Datei**status vom 2026-10-02: passed=13.
  - [Zeile 36](../../../tests/test_watch_evidence_model.py#L36): ` assert verified["cause"] == "new_evidence" `
  - [Zeile 37](../../../tests/test_watch_evidence_model.py#L37): ` assert verified["evidence_sources"] == [ `
  - [Zeile 45](../../../tests/test_watch_evidence_model.py#L45): ` assert reused["cause"] == "reassessment" `
  - [Zeile 46](../../../tests/test_watch_evidence_model.py#L46): ` assert reused["evidence_sources"] == [] `

<a id="build-04"></a>

## BUILD-04 · Statische Auslieferung ohne SSE-Pufferung

Gehashtes dist ist immutable und komprimierbar, HTML komprimierbar, ungehashte Assets revalidieren. SSE und API-JSON bleiben unkomprimiert; SSE-Frames werden unmittelbar weitergegeben.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Aktualisierung 02.10.2026: Assertions und ersetzte Grenzen im aktuellen Dateikatalog beschrieben.

**Testgrenze:** ASGI-/TestClient-Nachweis ohne realen Socket/Reverseproxy/CDN.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/core/static_delivery.py](../../../app/core/static_delivery.py)
- [main.py](../../../main.py)

**Testdateien:**

- [tests/test_local_transport.py](../../../tests/test_local_transport.py)
- [tests/test_static_delivery.py](../../../tests/test_static_delivery.py)

</details>

**Konkrete Teilbelege:**

- [test_event_stream_is_never_gzip_encoded](../../../tests/test_static_delivery.py#L39) — ASGI-/TestClient-Middleware und echte lokale Assets. **Datei**status vom 2026-10-02: passed=8.
  - [Zeile 42](../../../tests/test_static_delivery.py#L42): ` assert response.status_code == 200 `
  - [Zeile 43](../../../tests/test_static_delivery.py#L43): ` assert response.headers["content-type"].startswith("text/event-stream") `
  - [Zeile 44](../../../tests/test_static_delivery.py#L44): ` assert "content-encoding" not in response.headers `
  - [Zeile 45](../../../tests/test_static_delivery.py#L45): ` assert "accept-encoding" not in response.headers.get("vary", "").lower() `
  - [Zeile 46](../../../tests/test_static_delivery.py#L46): ` assert response.text.count("event: delta") == 3 `
- [test_cancellation_closes_real_idle_provider_socket_without_retry](../../../tests/test_local_transport.py#L64) — Echte lokale TCP-/TLS-Server durch HTTP-/SDK-Adapter. **Datei**status vom 2026-10-02: passed=10.
  - [Zeile 85](../../../tests/test_local_transport.py#L85): ` assert state.seen.wait(3), 'request never reached local server' `
  - [Zeile 88](../../../tests/test_local_transport.py#L88): ` assert not thread.is_alive(), 'producer survived cancellation' `
  - [Zeile 89](../../../tests/test_local_transport.py#L89): ` assert len(errors) == 1 and isinstance(errors[0], runtime.ProviderCancelled) `
  - [Zeile 90](../../../tests/test_local_transport.py#L90): ` assert state.closed.wait(3), 'server socket stayed open' `
  - [Zeile 91](../../../tests/test_local_transport.py#L91): ` assert len(state.requests) == 1 `
