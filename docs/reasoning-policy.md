# Reasoning budget in Admin

`app_config/models.reasoning_policy` stores `{profile: "existing" | "economy",
models: {<internal model ID>: "existing" | "economy"}}`. An absent policy
preserves the previous behavior. An absent model override follows the profile.
The existing Models Save/Reload flow persists, activates and rolls back it with
the rest of the configuration. Old clients that omit this field preserve the
active policy. No provider calls are needed for the preview.

Savings uses a small, explicit compatibility list, never prefix matching or a
guess for newly added models:

| Models | Savings request | Reason |
|---|---|---|
| GPT-5.5 | `effort: low` | Reduce the documented medium default |
| Mistral Small / Medium 3.5 | `effort: none` | Supported none/high control; none means minimal thinking |
| Grok 4.3 reasoning variant | `effort: low` | Reduce the existing high policy |
| GLM 5.3 Flash / 5.3, Muse Glimmer / Spark | Existing low | Already reduced; Muse cannot disable reasoning |
| Kimi K2.6 / K3 | Existing disabled / enabled | Preserve the verified search and Moonshot routing contracts |
| All other models | Existing behavior | No verified savings rule; provider default is not synonymous with off |

The cap preserves explicit disabled/none/minimal/low settings. It applies to
standard answers, Deep Think answers and synchronous/streamed engine calls
(synthesis, judges, resolve, chat memory), including consumers such as API,
Watches and Topics. It does not change routing, output caps or fixed task
settings for Memory Edit, SEO review and Publisher screening. The selected
model's exception restores its original **flow-specific** behavior, not one
invented global effort. Smaller models and cheaper token prices remain a
separate model-selection decision; the cap is not a token or currency limit.
Actual quality and savings require a workload comparison.

The main Admin table previews the selected request type using backend-generated
values for each profile. Editable models are shown first; protected models can
be revealed. Technical details describe the saved snapshot. Previewing a
request type does not dirty the configuration. Changes apply after Save, and
Reload discards them. Deep Think preview shows only each family's Pro model,
matching the actual answer-model selection.

Verified sources (2026-09-05):

- [Mistral reasoning: none/high](https://docs.mistral.ai/studio/conversations/reasoning)
- [GPT-5.5 model guidance: medium default](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.5)
- [OpenRouter reasoning effort support](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
- [Grok 4.3 supported efforts](https://docs.x.ai/developers/models/grok-4.3)

GLM, Muse and Kimi preserve the repository's existing verified model policies.
Recheck compatibility before adding models to `reasoning_savings_models()`.
