from __future__ import annotations

import argparse
import pathlib
import re
import sys


def has(text: str, pattern: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) is not None


def validate(text: str) -> list[str]:
    failures: list[str] = []

    if text.count('{') != text.count('}'):
        failures.append('unbalanced braces')
    if text.count('(') != text.count(')'):
        failures.append('unbalanced parentheses')

    generic_invariants = {
        'state setter': r'function\s+\w*set_state\s*\(',
        'phase transition function': r'function\s+\w*advance_phase\s*\(',
        'transition lock': r'\b(?:phase_)?transition_locked\b|\btransition_locked\b',
        'telegraph state': r'["\'](?:\w+_)?telegraph(?:_\w+)?["\']',
        'active state': r'["\'](?:\w+_)?active(?:_attack|_\w+)?["\']',
        'recovery state': r'["\']recovery["\']',
        'defeated state': r'["\']defeated["\']',
        'damage entry point': r'function\s+\w*apply_damage\s*\(',
        'one-shot completion guard': r'\bencounter_complete_fired\b',
        'explicit defeated transition': r'\w*set_state\s*\(\s*["\']defeated["\']\s*,\s*0\s*\)',
    }

    for name, pattern in generic_invariants.items():
        if not has(text, pattern):
            failures.append(f'missing {name}')

    if not has(text, r'function\s+\w*advance_phase\s*\([^)]*\)[\s\S]*?(?:_next(?:_phase)?\s*<=\s*phase|phase\s*>=\s*_next(?:_phase)?)'):
        failures.append('missing backwards/repeated phase guard')

    if not has(text, r'function\s+\w*(?:register_|break_|complete_|objective_)\w*\s*\('):
        failures.append('missing objective/event entry point')

    if not has(text, r'if\s*\(\s*state\s*==\s*["\']defeated["\']\s*\)'):
        failures.append('missing defeated-state guard')

    if not has(text, r'can_take_damage\s*='):
        failures.append('missing explicit damage-window control')

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description='JakeAI boss scaffold static gate')
    parser.add_argument('gml', type=pathlib.Path)
    args = parser.parse_args()
    text = args.gml.read_text(encoding='utf-8')
    failures = validate(text)
    if failures:
        print('FAIL')
        for failure in failures:
            print(f'- {failure}')
        return 1
    print('PASS: deterministic scaffold invariants satisfied')
    return 0


if __name__ == '__main__':
    sys.exit(main())
