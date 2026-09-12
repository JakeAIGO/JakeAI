from __future__ import annotations

import argparse
import pathlib
import sys

REQUIRED_SNIPPETS = {
    'state setter': 'function set_state',
    'phase transition function': 'function advance_phase',
    'transition lock': 'phase_transition_locked',
    'telegraph state': '_telegraph',
    'active state': '_active',
    'recovery state': '"recovery"',
    'defeated state': '"defeated"',
    'damage entry point': 'function boss_apply_damage',
    'objective entry point': 'function register_product_return',
    'one-shot completion guard': 'encounter_complete_fired',
}


def validate(text: str) -> list[str]:
    failures: list[str] = []
    if text.count('{') != text.count('}'):
        failures.append('unbalanced braces')
    if text.count('(') != text.count(')'):
        failures.append('unbalanced parentheses')
    for name, snippet in REQUIRED_SNIPPETS.items():
        if snippet not in text:
            failures.append(f'missing {name}')
    if '_next_phase <= phase' not in text:
        failures.append('missing backwards/repeated phase guard')
    if 'phase == 3' not in text or 'return false' not in text:
        failures.append('missing final-phase HP damage rejection')
    if 'products_returned >= required_returns' not in text:
        failures.append('missing reachable objective completion condition')
    if 'set_state("defeated", 0)' not in text:
        failures.append('missing explicit defeated transition')
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
