"""Shared argument boundaries for supported auxiliary benchmark launchers."""
import math
import re


def add_execution_arguments(parser):
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='Payloads and cost projection; no provider calls')
    mode.add_argument('--live', action='store_true', help='Run with explicit credentials and budget')
    parser.add_argument('--budget', type=float, default=None, help='Positive finite budget in USD; required for --live')
    parser.add_argument('--resume', action='store_true', help='Resume and retry failed cells')


def validate_execution_arguments(parser, args):
    if args.live and args.budget is None:
        parser.error('--live requires an explicit --budget')
    if args.budget is not None and (not math.isfinite(args.budget) or args.budget <= 0):
        parser.error('--budget must be finite and greater than zero')
    if hasattr(args, 'run_id') and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', args.run_id):
        parser.error('--run-id must be one directory name (letters, digits, underscore, hyphen or dot)')
    return args
