"""Inspect or repair one explicitly selected production account's Agent holds.

Uses the application's idempotent recovery path. Never resets measured usage,
changes the configured limit, or starts a provider generation.
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True)
    parser.add_argument('--project-id', required=True)
    parser.add_argument('--apply', action='store_true', help='Apply the reviewed repair; otherwise inspect only.')
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    if any(os.environ.get(key) for key in ('FIRESTORE_EMULATOR_HOST', 'FIREBASE_AUTH_EMULATOR_HOST')) or os.environ.get('UNIT_TEST_MODE') == '1':
        parser.error('Production repair cannot run with test/emulator configuration.')
    os.chdir(ROOT)
    import firebase_admin
    from firebase_admin import auth
    from app.core.security import db_firestore
    from app.services import agent_budget_config, agent_quota
    if firebase_admin.get_app().project_id != args.project_id:
        parser.error('Configured Firebase project does not match --project-id.')
    user = auth.get_user_by_email(args.email)
    config = agent_budget_config.get_config(db_firestore)
    day = agent_quota.period_key(config)
    ref = agent_quota.quota_ref(db_firestore, user.uid, day)
    before = ref.get().to_dict() or {}
    result = {'uid': user.uid, 'period': day, 'before': before, 'applied': args.apply}
    if args.apply:
        result['budget'] = agent_quota.snapshot(db_firestore, user.uid)
        result['after'] = ref.get().to_dict() or {}
    print(json.dumps(result, default=str))
    db_firestore.close()


if __name__ == '__main__':
    main()
