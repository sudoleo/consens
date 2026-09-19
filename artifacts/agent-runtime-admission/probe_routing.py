"""Opt-in: at most two routing calls per case, no account/database writes."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--case', choices=['fact', 'current', 'greeting'])
    args = parser.parse_args()
    from app.services.agent_delegation import DelegationLoop
    from app.services.agent_delegation_config import defaults
    from app.services.agent_comparison import comparison_selection
    from app.services.agent_policy import AgentPolicy
    from app.services.agent_runs import get_agent_system_prompt
    from app.services.prompt_defaults import AGENT_SYSTEM_PROMPT
    from app.services.agent_tools import search_tools
    from app.services.llm.agent_client import AgentCompletion, resolve_agent_model
    from app.services.llm.provider_runtime import AnalysisBudget, ProviderCancellation, bind_analysis_budget, bind_provider_cancellation
    key = os.environ.get('OPENROUTER_API_KEY')
    if not key:
        raise SystemExit('OPENROUTER_API_KEY is unavailable')
    model = resolve_agent_model()
    model = replace(model, request_config={**model.request_config, '_agent_bounded_search': True})
    questions = [('fact', 'Warum ist der Himmel blau?', True),
        ('current', 'wer ist aktuell der beste zwift fahrer der letzten 3 jahre?', True),
        ('greeting', 'Hallo!', False)]
    results = []
    for case, question, compare in questions:
        if args.case and args.case != case:
            continue
        cancellation = ProviderCancellation()
        loop = DelegationLoop(store=None, uid='probe', chat_id='probe', turn_id='probe', model=model,
            messages=[{'role': 'system', 'content': get_agent_system_prompt(model, config={
                'prompts': {'agent': AGENT_SYSTEM_PROMPT}, 'reference_timezone': 'Europe/Berlin'})},
                {'role': 'user', 'content': question}], api_key=key, cancellation=cancellation,
            policy=AgentPolicy.for_chat(defaults()), delegation_config=defaults(), comparison_models=comparison_selection())
        value = AgentCompletion()
        value.tool_argument_limit, value.tool_call_limit = loop.registry.argument_limit, 4
        result = {'case': case, 'passed': False}
        try:
            with bind_analysis_budget(AnalysisBudget(seconds=180, max_calls=2)), bind_provider_cancellation(cancellation):
                list(value.stream(model=model, messages=loop.messages, api_key=key,
                    tools=[*loop.registry.schemas, *search_tools(model, 1)], native_searches=1, allow_tool_calls=True))
                loop.messages.append(value.assistant_message())
                if loop._consensus_search_handoff(value):
                    result['research_usage'] = value.usage
                    result['research_source_count'] = len(value.sources)
                    value = AgentCompletion()
                    value.tool_argument_limit, value.tool_call_limit = loop.registry.argument_limit, 4
                    list(value.stream(model=model, messages=loop.messages, api_key=key,
                        tools=loop.registry.schemas, native_searches=0, allow_tool_calls=True))
            names = [call['function']['name'] for call in value.tool_calls]
            result.update(tools=names, source_count=len(value.sources), finish_reason=value.finish_reason,
                          passed=('compare_models' in names) if compare else not names and bool(value.text.strip()))
        except Exception as exc:
            result['error'] = type(exc).__name__
            import traceback
            frame = traceback.extract_tb(exc.__traceback__)[-1]
            result['error_location'] = f'{Path(frame.filename).name}:{frame.lineno}'
        result['usage'] = value.usage
        results.append(result)
        print(json.dumps(result), flush=True)
    report = {'date': datetime.now(timezone.utc).isoformat(), 'model': model.model, 'results': results}
    Path(__file__).with_name('routing-' + (args.case or 'all') + '-results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0 if all(result['passed'] for result in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
