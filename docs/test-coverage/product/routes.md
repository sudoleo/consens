# Runtime-Routeninventar

[Einstieg](README.md) · [Rohdaten](routes.json)

Aus `main.app.routes` im Unit-Test-Modus erfasst: **158 App-Routeneinträge und 4 Frameworkrouten**. Methoden werden pro registriertem Eintrag gebündelt; GET/HEAD ist deshalb ein Eintrag. Die neun dynamischen `/ask_*`-Routen wurden zur Laufzeit aufgelöst. Das `/static`-Mount ist keine App-Endpointdefinition und wird über Assets/Build im Dateiinventar behandelt. Vertragszuordnungen beschreiben Handlerzuständigkeit, nicht einen bestandenen HTTP-Test. Pfadtext in einem Browsertest kann eine Route ersetzen statt sie auszuführen.

| ID | Methoden | Pfad | Handler | Vertrag |
|---|---|---|---|---|
| R-001 | GET, HEAD | ` /openapi.json ` | Framework | — |
| R-002 | GET, HEAD | ` /docs ` | Framework | — |
| R-003 | GET, HEAD | ` /docs/oauth2-redirect ` | Framework | — |
| R-004 | GET, HEAD | ` /redoc ` | Framework | — |
| R-005 | GET | ` /health/maintenance ` | [maintenance_health](../../../main.py#L196) | [OPS-01](matrix.md#ops-01) |
| R-006 | GET | ` /health/metrics ` | [operational_metrics](../../../main.py#L208) | [OPS-03](matrix.md#ops-03) |
| R-007 | GET | ` /agent/models ` | [available_agent_models](../../../app/api/routers/agent.py#L120) | [AGENT-02](matrix.md#agent-02) |
| R-008 | GET | ` /agent/budget ` | [available_agent_budget](../../../app/api/routers/agent.py#L131) | [AGENT-01](matrix.md#agent-01) |
| R-009 | POST | ` /agent ` | [run_agent](../../../app/api/routers/agent.py#L140) | [AGENT-01](matrix.md#agent-01), [AGENT-02](matrix.md#agent-02), [AGENT-04](matrix.md#agent-04) |
| R-010 | GET | ` /agent/chats/{chat_id}/turns/{turn_id}/agents ` | [list_agents](../../../app/api/routers/agent.py#L342) | [AGENT-03](matrix.md#agent-03), [AGENT-04](matrix.md#agent-04) |
| R-011 | GET | ` /agent/chats/{chat_id}/turns/{turn_id}/agents/{agent_id} ` | [agent_details](../../../app/api/routers/agent.py#L348) | [AGENT-03](matrix.md#agent-03), [AGENT-04](matrix.md#agent-04) |
| R-012 | POST | ` /agent/chats/{chat_id}/turns/{turn_id}/stop ` | [stop_agent_run](../../../app/api/routers/agent.py#L368) | [AGENT-04](matrix.md#agent-04) |
| R-013 | POST | ` /register ` | [register_user](../../../app/api/routers/auth.py#L76) | [AUTH-01](matrix.md#auth-01) |
| R-014 | POST | ` /confirm-registration ` | [confirm_registration](../../../app/api/routers/auth.py#L111) | [AUTH-01](matrix.md#auth-01) |
| R-015 | DELETE | ` /auth/session ` | [clear_session](../../../app/api/routers/auth.py#L161) | [AUTH-02](matrix.md#auth-02) |
| R-016 | GET | ` /user_status ` | [get_user_status](../../../app/api/routers/users.py#L52) | [QUOTA-02](matrix.md#quota-02), [AUTH-02](matrix.md#auth-02) |
| R-017 | POST | ` /usage ` | [get_usage_post](../../../app/api/routers/users.py#L102) | [QUOTA-01](matrix.md#quota-01) |
| R-018 | POST | ` /usage/run/release ` | [release_usage_run](../../../app/api/routers/users.py#L147) | [QUOTA-01](matrix.md#quota-01) |
| R-019 | GET | ` /api/my/memory ` | [get_user_memory](../../../app/api/routers/users.py#L250) | [MEM-01](matrix.md#mem-01) |
| R-020 | PUT | ` /api/my/memory ` | [put_user_memory](../../../app/api/routers/users.py#L268) | [MEM-01](matrix.md#mem-01) |
| R-021 | POST | ` /api/my/memory/edit ` | [edit_user_memory](../../../app/api/routers/users.py#L313) | [MEM-02](matrix.md#mem-02) |
| R-022 | POST | ` /api/my/memory/undo ` | [undo_user_memory](../../../app/api/routers/users.py#L338) | [MEM-02](matrix.md#mem-02) |
| R-023 | POST | ` /delete_account ` | [delete_account](../../../app/api/routers/users.py#L355) | [AUTH-03](matrix.md#auth-03) |
| R-024 | POST | ` /track-interest ` | [track_interest](../../../app/api/routers/users.py#L418) | [OPS-03](matrix.md#ops-03) |
| R-025 | GET | ` /bookmarks ` | [load_bookmarks](../../../app/api/routers/bookmarks.py#L395) | [CHAT-04](matrix.md#chat-04) |
| R-026 | GET | ` /bookmarks/{bookmark_id} ` | [load_bookmark_detail](../../../app/api/routers/bookmarks.py#L430) | [CHAT-04](matrix.md#chat-04) |
| R-027 | GET | ` /bookmarks/{bookmark_id}/conversation ` | [load_bookmark_conversation](../../../app/api/routers/bookmarks.py#L453) | [CHAT-04](matrix.md#chat-04) |
| R-028 | POST | ` /bookmark ` | [save_bookmark](../../../app/api/routers/bookmarks.py#L544) | [CHAT-04](matrix.md#chat-04) |
| R-029 | POST | ` /bookmark/consensus ` | [save_bookmark_consensus](../../../app/api/routers/bookmarks.py#L751) | [CHAT-04](matrix.md#chat-04) |
| R-030 | POST | ` /bookmark/consensus/share-result ` | [prepare_bookmark_share_result](../../../app/api/routers/bookmarks.py#L778) | [SHARE-01](matrix.md#share-01) |
| R-031 | DELETE | ` /bookmark ` | [delete_bookmark](../../../app/api/routers/bookmarks.py#L884) | [CHAT-04](matrix.md#chat-04) |
| R-032 | POST | ` /ask_openai ` | [ask_openai_post](../../../app/api/routers/chat.py#L1068) | [LLM-01](matrix.md#llm-01), [LLM-02](matrix.md#llm-02), [CHAT-03](matrix.md#chat-03) |
| R-033 | POST | ` /ask_mistral ` | [ask_mistral_post](../../../app/api/routers/chat.py#L1068) | [LLM-01](matrix.md#llm-01), [LLM-02](matrix.md#llm-02), [CHAT-03](matrix.md#chat-03) |
| R-034 | POST | ` /ask_claude ` | [ask_claude_post](../../../app/api/routers/chat.py#L1068) | [LLM-01](matrix.md#llm-01), [LLM-02](matrix.md#llm-02), [CHAT-03](matrix.md#chat-03) |
| R-035 | POST | ` /ask_gemini ` | [ask_gemini_post](../../../app/api/routers/chat.py#L1068) | [LLM-01](matrix.md#llm-01), [LLM-02](matrix.md#llm-02), [CHAT-03](matrix.md#chat-03) |
| R-036 | POST | ` /ask_deepseek ` | [ask_deepseek_post](../../../app/api/routers/chat.py#L1068) | [LLM-01](matrix.md#llm-01), [LLM-02](matrix.md#llm-02), [CHAT-03](matrix.md#chat-03) |
| R-037 | POST | ` /ask_grok ` | [ask_grok_post](../../../app/api/routers/chat.py#L1068) | [LLM-01](matrix.md#llm-01), [LLM-02](matrix.md#llm-02), [CHAT-03](matrix.md#chat-03) |
| R-038 | POST | ` /ask_kimi ` | [ask_kimi_post](../../../app/api/routers/chat.py#L1068) | [LLM-01](matrix.md#llm-01), [LLM-02](matrix.md#llm-02), [CHAT-03](matrix.md#chat-03) |
| R-039 | POST | ` /ask_glm ` | [ask_glm_post](../../../app/api/routers/chat.py#L1068) | [LLM-01](matrix.md#llm-01), [LLM-02](matrix.md#llm-02), [CHAT-03](matrix.md#chat-03) |
| R-040 | POST | ` /ask_muse ` | [ask_muse_post](../../../app/api/routers/chat.py#L1068) | [LLM-01](matrix.md#llm-01), [LLM-02](matrix.md#llm-02), [CHAT-03](matrix.md#chat-03) |
| R-041 | POST | ` /prepare ` | [prepare](../../../app/api/routers/chat.py#L1089) | [QUOTA-01](matrix.md#quota-01), [CHAT-03](matrix.md#chat-03) |
| R-042 | POST | ` /consensus ` | [consensus](../../../app/api/routers/chat.py#L1160) | [CONS-01](matrix.md#cons-01), [CONS-02](matrix.md#cons-02), [CONS-05](matrix.md#cons-05) |
| R-043 | POST | ` /resolve ` | [resolve](../../../app/api/routers/chat.py#L1996) | [CONS-04](matrix.md#cons-04) |
| R-044 | POST | ` /chats ` | [create_chat](../../../app/api/routers/chat_history.py#L286) | [CHAT-01](matrix.md#chat-01) |
| R-045 | GET | ` /chats ` | [list_chats](../../../app/api/routers/chat_history.py#L304) | [CHAT-01](matrix.md#chat-01) |
| R-046 | GET | ` /chats/{chat_id} ` | [get_chat](../../../app/api/routers/chat_history.py#L319) | [CHAT-01](matrix.md#chat-01) |
| R-047 | DELETE | ` /chats/{chat_id} ` | [delete_chat](../../../app/api/routers/chat_history.py#L329) | [CHAT-01](matrix.md#chat-01), [CHAT-02](matrix.md#chat-02) |
| R-048 | POST | ` /chats/{chat_id}/turns ` | [create_turn](../../../app/api/routers/chat_history.py#L347) | [CHAT-01](matrix.md#chat-01), [CHAT-02](matrix.md#chat-02) |
| R-049 | GET | ` /chats/{chat_id}/turns/{turn_id} ` | [get_turn](../../../app/api/routers/chat_history.py#L371) | [CHAT-01](matrix.md#chat-01) |
| R-050 | POST | ` /chats/{chat_id}/turns/{turn_id}/context ` | [build_turn_context](../../../app/api/routers/chat_history.py#L384) | [CHAT-03](matrix.md#chat-03) |
| R-051 | GET | ` /chats/{chat_id}/turns ` | [list_turns](../../../app/api/routers/chat_history.py#L448) | [CHAT-01](matrix.md#chat-01) |
| R-052 | POST | ` /api/client-errors ` | [report_client_error](../../../app/api/routers/client_errors.py#L111) | [OPS-03](matrix.md#ops-03) |
| R-053 | GET | ` /robots.txt ` | [robots_txt](../../../app/api/routers/pages.py#L93) | [SEO-05](matrix.md#seo-05) |
| R-054 | GET | ` /sitemap.xml ` | [sitemap_xml](../../../app/api/routers/pages.py#L103) | [SEO-05](matrix.md#seo-05) |
| R-055 | GET | ` /sitemap-pages.xml ` | [sitemap_pages_xml](../../../app/api/routers/pages.py#L121) | [SEO-05](matrix.md#seo-05) |
| R-056 | GET | ` / ` | [landing](../../../app/api/routers/pages.py#L142) | [SEO-05](matrix.md#seo-05) |
| R-057 | GET | ` /privacy ` | [privacy](../../../app/api/routers/pages.py#L146) | [SEO-05](matrix.md#seo-05) |
| R-058 | GET | ` /imprint ` | [imprint](../../../app/api/routers/pages.py#L152) | [SEO-05](matrix.md#seo-05) |
| R-059 | GET | ` /terms ` | [terms](../../../app/api/routers/pages.py#L158) | [SEO-05](matrix.md#seo-05) |
| R-060 | GET | ` /about ` | [about](../../../app/api/routers/pages.py#L164) | [SEO-05](matrix.md#seo-05) |
| R-061 | GET | ` /ai-model-comparison ` | [ai_model_comparison](../../../app/api/routers/pages.py#L168) | [SEO-05](matrix.md#seo-05) |
| R-062 | GET | ` /consensus-engine ` | [consensus_engine_page](../../../app/api/routers/pages.py#L172) | [SEO-05](matrix.md#seo-05) |
| R-063 | GET | ` /benchmark ` | [benchmark](../../../app/api/routers/pages.py#L176) | [SEO-05](matrix.md#seo-05) |
| R-064 | GET | ` /model-pulse ` | [model_pulse](../../../app/api/routers/pages.py#L181) | [SEO-05](matrix.md#seo-05) |
| R-065 | GET | ` /api/model-leaderboard ` | [public_model_leaderboard](../../../app/api/routers/pages.py#L393) | [SEO-05](matrix.md#seo-05) |
| R-066 | GET | ` /app/watches ` | [read_root](../../../app/api/routers/pages.py#L423) | [UI-07](matrix.md#ui-07) |
| R-067 | GET | ` /app ` | [read_root](../../../app/api/routers/pages.py#L423) | [UI-07](matrix.md#ui-07) |
| R-068 | GET | ` /admin ` | [admin_page](../../../app/api/routers/pages.py#L488) | [ADMIN-02](matrix.md#admin-02) |
| R-069 | GET | ` /admin/benchmark ` | [admin_benchmark_page](../../../app/api/routers/pages.py#L502) | [BENCH-03](matrix.md#bench-03) |
| R-070 | GET | ` /admin/topics ` | [admin_topics_page](../../../app/api/routers/pages.py#L517) | [TOPIC-01](matrix.md#topic-01) |
| R-071 | POST | ` /feedback ` | [submit_feedback](../../../app/api/routers/pages.py#L521) | [DATA-01](matrix.md#data-01) |
| R-072 | POST | ` /vote ` | [record_vote](../../../app/api/routers/pages.py#L561) | [DATA-01](matrix.md#data-01) |
| R-073 | POST | ` /check_keys ` | [check_keys](../../../app/api/routers/pages.py#L607) | [LLM-01](matrix.md#llm-01) |
| R-074 | GET | ` /api/admin/agent-budget ` | [admin_get_agent_budget](../../../app/api/routers/admin.py#L185) | [ADMIN-01](matrix.md#admin-01) |
| R-075 | PUT | ` /api/admin/agent-budget ` | [admin_save_agent_budget](../../../app/api/routers/admin.py#L206) | [ADMIN-01](matrix.md#admin-01) |
| R-076 | POST | ` /api/admin/agent-budget/reset ` | [admin_reset_agent_budgets](../../../app/api/routers/admin.py#L213) | [ADMIN-01](matrix.md#admin-01) |
| R-077 | GET | ` /api/admin/prompt-config ` | [admin_get_prompt_config](../../../app/api/routers/admin.py#L220) | [ADMIN-01](matrix.md#admin-01) |
| R-078 | PUT | ` /api/admin/prompt-config ` | [admin_save_prompt_config](../../../app/api/routers/admin.py#L230) | [ADMIN-01](matrix.md#admin-01) |
| R-079 | GET | ` /api/admin/seo ` | [admin_get_seo_overview](../../../app/api/routers/admin.py#L246) | [SEO-01](matrix.md#seo-01), [SEO-02](matrix.md#seo-02) |
| R-080 | POST | ` /api/admin/seo/check ` | [admin_check_seo_connection](../../../app/api/routers/admin.py#L261) | [SEO-01](matrix.md#seo-01), [SEO-02](matrix.md#seo-02) |
| R-081 | POST | ` /api/admin/seo/collect ` | [admin_collect_seo_data](../../../app/api/routers/admin.py#L274) | [SEO-01](matrix.md#seo-01), [SEO-02](matrix.md#seo-02) |
| R-082 | GET | ` /api/admin/seo/review ` | [admin_get_seo_weekly_review](../../../app/api/routers/admin.py#L316) | [SEO-03](matrix.md#seo-03), [SEO-04](matrix.md#seo-04) |
| R-083 | GET | ` /api/admin/seo/reviews ` | [admin_list_seo_weekly_reviews](../../../app/api/routers/admin.py#L328) | [SEO-03](matrix.md#seo-03), [SEO-04](matrix.md#seo-04) |
| R-084 | PUT | ` /api/admin/seo/review/config ` | [admin_save_seo_weekly_review_config](../../../app/api/routers/admin.py#L340) | [SEO-03](matrix.md#seo-03), [SEO-04](matrix.md#seo-04) |
| R-085 | POST | ` /api/admin/seo/review/run ` | [admin_run_seo_weekly_review](../../../app/api/routers/admin.py#L363) | [SEO-03](matrix.md#seo-03), [SEO-04](matrix.md#seo-04) |
| R-086 | POST | ` /api/admin/seo/reviews/{run_id}/preview ` | [admin_preview_seo_review_actions](../../../app/api/routers/admin.py#L378) | [SEO-03](matrix.md#seo-03), [SEO-04](matrix.md#seo-04) |
| R-087 | POST | ` /api/admin/seo/reviews/{run_id}/apply ` | [admin_apply_seo_review_actions](../../../app/api/routers/admin.py#L395) | [SEO-03](matrix.md#seo-03), [SEO-04](matrix.md#seo-04) |
| R-088 | POST | ` /api/admin/seo/reviews/{run_id}/topic-brief/accept ` | [admin_accept_seo_review_topic_brief](../../../app/api/routers/admin.py#L415) | [SEO-03](matrix.md#seo-03), [SEO-04](matrix.md#seo-04) |
| R-089 | POST | ` /api/admin/seo/reviews/{run_id}/topic-brief/reject ` | [admin_reject_seo_review_topic_brief](../../../app/api/routers/admin.py#L428) | [SEO-03](matrix.md#seo-03), [SEO-04](matrix.md#seo-04) |
| R-090 | POST | ` /api/admin/seo/reviews/{run_id}/editorial-decision ` | [admin_record_seo_editorial_decision](../../../app/api/routers/admin.py#L441) | [SEO-03](matrix.md#seo-03), [SEO-04](matrix.md#seo-04) |
| R-091 | POST | ` /api/admin/seo/pages/{page_id}/recommendation ` | [admin_generate_seo_recommendation](../../../app/api/routers/admin.py#L459) | [SEO-03](matrix.md#seo-03) |
| R-092 | POST | ` /api/admin/seo/pages/{page_id}/content-judge ` | [admin_ask_seo_content_judge](../../../app/api/routers/admin.py#L476) | [SEO-02](matrix.md#seo-02) |
| R-093 | POST | ` /api/admin/api-keys ` | [admin_issue_api_key](../../../app/api/routers/admin.py#L496) | [API-01](matrix.md#api-01) |
| R-094 | GET | ` /api/admin/api-keys ` | [admin_list_api_keys](../../../app/api/routers/admin.py#L533) | [API-01](matrix.md#api-01) |
| R-095 | DELETE | ` /api/admin/api-keys/{key_id} ` | [admin_revoke_api_key](../../../app/api/routers/admin.py#L544) | [API-01](matrix.md#api-01) |
| R-096 | GET | ` /api/admin/account-tier ` | [admin_get_account_tier](../../../app/api/routers/admin.py#L574) | [QUOTA-02](matrix.md#quota-02), [ADMIN-02](matrix.md#admin-02) |
| R-097 | PUT | ` /api/admin/account-tier ` | [admin_set_account_tier](../../../app/api/routers/admin.py#L588) | [QUOTA-02](matrix.md#quota-02), [ADMIN-02](matrix.md#admin-02) |
| R-098 | GET | ` /api/admin/account-tiers ` | [admin_list_account_tiers](../../../app/api/routers/admin.py#L613) | [QUOTA-02](matrix.md#quota-02), [ADMIN-02](matrix.md#admin-02) |
| R-099 | GET | ` /api/admin/publisher-config ` | [admin_get_publisher_config](../../../app/api/routers/admin.py#L628) | [API-04](matrix.md#api-04), [ADMIN-01](matrix.md#admin-01) |
| R-100 | PUT | ` /api/admin/publisher-config ` | [admin_update_publisher_config](../../../app/api/routers/admin.py#L641) | [API-04](matrix.md#api-04), [ADMIN-01](matrix.md#admin-01) |
| R-101 | GET | ` /api/admin/watches ` | [admin_list_watches](../../../app/api/routers/admin.py#L660) | [WATCH-02](matrix.md#watch-02), [WATCH-04](matrix.md#watch-04) |
| R-102 | POST | ` /api/admin/watches/{watch_id}/run ` | [admin_run_watch](../../../app/api/routers/admin.py#L683) | [WATCH-02](matrix.md#watch-02), [WATCH-04](matrix.md#watch-04) |
| R-103 | POST | ` /api/admin/watches/test-email ` | [admin_send_watch_test_email](../../../app/api/routers/admin.py#L698) | [WATCH-02](matrix.md#watch-02), [WATCH-04](matrix.md#watch-04) |
| R-104 | GET | ` /api/admin/shares ` | [admin_list_shares](../../../app/api/routers/admin.py#L721) | [SHARE-03](matrix.md#share-03) |
| R-105 | POST | ` /api/admin/shares/{share_id}/moderate ` | [admin_moderate_share](../../../app/api/routers/admin.py#L739) | [SHARE-03](matrix.md#share-03) |
| R-106 | DELETE | ` /api/admin/shares/{share_id} ` | [admin_delete_share](../../../app/api/routers/admin.py#L772) | [SHARE-03](matrix.md#share-03) |
| R-107 | GET | ` /api/admin/benchmark/runs ` | [admin_list_benchmark_runs](../../../app/api/routers/admin.py#L786) | [BENCH-03](matrix.md#bench-03) |
| R-108 | GET | ` /api/admin/benchmark/runs/{run_id} ` | [admin_get_benchmark_run](../../../app/api/routers/admin.py#L800) | [BENCH-03](matrix.md#bench-03) |
| R-109 | GET | ` /api/admin/models ` | [get_models](../../../app/api/routers/admin.py#L1488) | [ADMIN-01](matrix.md#admin-01) |
| R-110 | POST | ` /api/admin/models ` | [update_models](../../../app/api/routers/admin.py#L1541) | [ADMIN-01](matrix.md#admin-01) |
| R-111 | POST | ` /api/share ` | [create_share](../../../app/api/routers/share.py#L300) | [SHARE-01](matrix.md#share-01) |
| R-112 | DELETE | ` /api/share/{share_id} ` | [delete_share](../../../app/api/routers/share.py#L326) | [SHARE-03](matrix.md#share-03) |
| R-113 | GET | ` /api/my/shares ` | [my_shares](../../../app/api/routers/share.py#L340) | [SHARE-01](matrix.md#share-01) |
| R-114 | POST | ` /api/share/{share_id}/indexing-request ` | [request_indexing](../../../app/api/routers/share.py#L352) | [SHARE-03](matrix.md#share-03) |
| R-115 | POST | ` /api/share/{share_id}/report ` | [report_share](../../../app/api/routers/share.py#L374) | [SHARE-03](matrix.md#share-03) |
| R-116 | GET | ` /sitemap-shares.xml ` | [sitemap_shares](../../../app/api/routers/share.py#L401) | [SHARE-02](matrix.md#share-02) |
| R-117 | GET | ` /questions ` | [questions_hub](../../../app/api/routers/share.py#L433) | [SHARE-02](matrix.md#share-02) |
| R-118 | GET | ` /s/{slug_id}/og.png ` | [share_og_card](../../../app/api/routers/share.py#L486) | [SHARE-04](matrix.md#share-04) |
| R-119 | GET | ` /s/{slug_id} ` | [share_page](../../../app/api/routers/share.py#L555) | [SHARE-02](matrix.md#share-02) |
| R-120 | GET | ` /api/source-checks/{job_id} ` | [get_source_check](../../../app/api/routers/source_checks.py#L61) | [SRC-04](matrix.md#src-04) |
| R-121 | POST | ` /api/source-checks/{job_id}/resume ` | [resume_source_check](../../../app/api/routers/source_checks.py#L74) | [SRC-04](matrix.md#src-04) |
| R-122 | GET | ` /api/share/{share_id}/source-check ` | [get_shared_source_check](../../../app/api/routers/source_checks.py#L93) | [SRC-04](matrix.md#src-04) |
| R-123 | GET | ` /api/topics/{slug}/source-check ` | [get_topic_source_check](../../../app/api/routers/source_checks.py#L124) | [SRC-04](matrix.md#src-04) |
| R-124 | POST | ` /api/watch ` | [create_watch](../../../app/api/routers/watch.py#L41) | [WATCH-01](matrix.md#watch-01) |
| R-125 | GET | ` /api/my/watches ` | [my_watches](../../../app/api/routers/watch.py#L74) | [WATCH-01](matrix.md#watch-01) |
| R-126 | PATCH | ` /api/watch/{watch_id} ` | [patch_watch](../../../app/api/routers/watch.py#L103) | [WATCH-01](matrix.md#watch-01) |
| R-127 | GET | ` /api/my/telegram ` | [my_telegram](../../../app/api/routers/watch.py#L120) | [WATCH-04](matrix.md#watch-04) |
| R-128 | POST | ` /api/my/telegram/link ` | [create_telegram_link](../../../app/api/routers/watch.py#L131) | [WATCH-04](matrix.md#watch-04) |
| R-129 | POST | ` /api/my/telegram/test ` | [test_telegram](../../../app/api/routers/watch.py#L147) | [WATCH-04](matrix.md#watch-04) |
| R-130 | DELETE | ` /api/my/telegram ` | [disconnect_telegram](../../../app/api/routers/watch.py#L161) | [WATCH-04](matrix.md#watch-04) |
| R-131 | POST | ` /api/telegram/webhook ` | [telegram_webhook](../../../app/api/routers/watch.py#L175) | [WATCH-04](matrix.md#watch-04) |
| R-132 | DELETE | ` /api/watch/{watch_id} ` | [remove_watch](../../../app/api/routers/watch.py#L192) | [WATCH-01](matrix.md#watch-01) |
| R-133 | GET | ` /api/my/watch-brief ` | [my_watch_brief](../../../app/api/routers/watch.py#L215) | [WATCH-05](matrix.md#watch-05) |
| R-134 | PATCH | ` /api/my/watch-brief ` | [patch_watch_brief](../../../app/api/routers/watch.py#L230) | [WATCH-05](matrix.md#watch-05) |
| R-135 | POST | ` /api/share/{share_id}/follow ` | [follow_share](../../../app/api/routers/watch.py#L259) | [WATCH-03](matrix.md#watch-03) |
| R-136 | GET | ` /watch/follow/confirm ` | [follow_confirm](../../../app/api/routers/watch.py#L291) | [WATCH-03](matrix.md#watch-03) |
| R-137 | GET | ` /watch/follow/unsubscribe ` | [follow_unsubscribe](../../../app/api/routers/watch.py#L306) | [WATCH-03](matrix.md#watch-03) |
| R-138 | GET | ` /watch/unsubscribe ` | [unsubscribe](../../../app/api/routers/watch.py#L318) | [WATCH-01](matrix.md#watch-01) |
| R-139 | GET | ` /watch/brief/unsubscribe ` | [unsubscribe_brief](../../../app/api/routers/watch.py#L329) | [WATCH-05](matrix.md#watch-05) |
| R-140 | GET | ` /topics ` | [topics_hub](../../../app/api/routers/topics.py#L246) | [TOPIC-04](matrix.md#topic-04) |
| R-141 | GET | ` /sitemap-topics.xml ` | [sitemap_topics](../../../app/api/routers/topics.py#L284) | [TOPIC-04](matrix.md#topic-04) |
| R-142 | GET | ` /topics/{slug} ` | [topic_page](../../../app/api/routers/topics.py#L313) | [TOPIC-04](matrix.md#topic-04) |
| R-143 | GET | ` /api/topics/favicon ` | [topic_favicon](../../../app/api/routers/topics.py#L476) | [TOPIC-04](matrix.md#topic-04) |
| R-144 | POST | ` /api/topics/{slug}/follow ` | [follow_topic](../../../app/api/routers/topics.py#L524) | [TOPIC-04](matrix.md#topic-04) |
| R-145 | GET | ` /topic-follow/confirm ` | [topic_follow_confirm](../../../app/api/routers/topics.py#L561) | [TOPIC-04](matrix.md#topic-04) |
| R-146 | GET | ` /topic-follow/unsubscribe ` | [topic_follow_unsubscribe](../../../app/api/routers/topics.py#L578) | [TOPIC-04](matrix.md#topic-04) |
| R-147 | GET | ` /api/admin/topics ` | [admin_list_topics](../../../app/api/routers/topics.py#L603) | [TOPIC-01](matrix.md#topic-01) |
| R-148 | POST | ` /api/admin/topics ` | [admin_create_topic](../../../app/api/routers/topics.py#L615) | [TOPIC-01](matrix.md#topic-01) |
| R-149 | GET | ` /api/admin/topics/{topic_id} ` | [admin_get_topic](../../../app/api/routers/topics.py#L632) | [TOPIC-01](matrix.md#topic-01) |
| R-150 | PUT | ` /api/admin/topics/{topic_id} ` | [admin_update_topic](../../../app/api/routers/topics.py#L648) | [TOPIC-01](matrix.md#topic-01) |
| R-151 | POST | ` /api/admin/topics/{topic_id}/runs ` | [admin_create_topic_run](../../../app/api/routers/topics.py#L667) | [TOPIC-01](matrix.md#topic-01) |
| R-152 | GET | ` /api/v1/publisher/config ` | [get_api_publisher_config](../../../app/api/routers/api_v1.py#L188) | [API-04](matrix.md#api-04) |
| R-153 | POST | ` /api/v1/consensus/runs ` | [create_consensus_run](../../../app/api/routers/api_v1.py#L213) | [API-02](matrix.md#api-02) |
| R-154 | GET | ` /api/v1/consensus/runs/{run_id}/source-check ` | [get_run_source_check](../../../app/api/routers/api_v1.py#L370) | [API-03](matrix.md#api-03) |
| R-155 | GET | ` /api/v1/consensus/runs/{run_id} ` | [get_consensus_run](../../../app/api/routers/api_v1.py#L395) | [API-02](matrix.md#api-02) |
| R-156 | DELETE | ` /api/v1/consensus/runs/{run_id} ` | [delete_consensus_run](../../../app/api/routers/api_v1.py#L418) | [API-02](matrix.md#api-02) |
| R-157 | POST | ` /api/v1/consensus/runs/{run_id}/share ` | [publish_consensus_run](../../../app/api/routers/api_v1.py#L448) | [API-04](matrix.md#api-04) |
| R-158 | GET | ` /api/v1/shares ` | [list_api_shares](../../../app/api/routers/api_v1.py#L492) | [API-04](matrix.md#api-04) |
| R-159 | GET | ` /api/v1/shares/{share_id} ` | [get_api_share](../../../app/api/routers/api_v1.py#L512) | [API-04](matrix.md#api-04) |
| R-160 | POST | ` /api/v1/shares/{share_id}/watch ` | [create_api_publisher_watch](../../../app/api/routers/api_v1.py#L534) | [API-04](matrix.md#api-04) |
| R-161 | PUT | ` /api/v1/shares/{share_id}/indexing ` | [set_api_share_indexing](../../../app/api/routers/api_v1.py#L609) | [API-04](matrix.md#api-04) |
| R-162 | DELETE | ` /api/v1/shares/{share_id} ` | [delete_api_share](../../../app/api/routers/api_v1.py#L650) | [API-04](matrix.md#api-04) |
