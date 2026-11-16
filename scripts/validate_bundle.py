#!/usr/bin/env python3
"""Check the distributed skill bundle without network access or private data.

Uses only the Python standard library. This validates packaging invariants,
not clinical correctness or the behavioral reliability of an AI model.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

SKILLS = (
    'maintain-nutrition-training-diary',
    'nutrition-and-energy-balance',
    'training-plan-and-progress',
    'scientific-source-verification',
    'freediving-training-profile',
    'objective-partner',
)
PRIVATE_URL = re.compile(r'https?://(?:drive\.google\.com|docs\.google\.com)/\S+', re.I)
LOCAL_PATH = re.compile(r'(?:[A-Z]:[\\/](?:Users|Documents)[\\/]|/mnt/data/|/workspace/scratch/|sandbox:)', re.I)
SECRET = re.compile(r'(?:-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}|\bAKIA[0-9A-Z]{16}\b)')
LINK = re.compile(r'\[[^\]\n]*\]\((<[^>\n]+>|[^)\n]+)\)')


def markdown_targets(body: str):
    # Fenced samples contain command syntax, not rendered local file links.
    body = re.sub(r'^```.*?^```\s*$', '', body, flags=re.M | re.S)
    for match in LINK.finditer(body):
        raw = match.group(1)
        yield raw[1:-1] if raw.startswith('<') else raw.split(' ', 1)[0]


def check(root: Path) -> list[str]:
    root = root.resolve()
    errors = []
    for name in SKILLS:
        folder = root / name
        for required in ('SKILL.md', 'README.md', 'agents/openai.yaml'):
            if not (folder / required).is_file():
                errors.append(f'{name}: missing {required}')
        skill_file = folder / 'SKILL.md'
        if not skill_file.is_file():
            continue
        body = skill_file.read_text(encoding='utf-8')
        front = re.match(r'^---\n(.*?)\n---\n', body, flags=re.S)
        if not front:
            errors.append(f'{name}: missing frontmatter')
        else:
            if not re.search(r'^name: ' + re.escape(name) + r'\s*$', front[1], re.M):
                errors.append(f'{name}: frontmatter name differs from folder')
            if not re.search(r'^description:\s*\S', front[1], re.M):
                errors.append(f'{name}: missing description')

    # Only distributed content is inspected, never .git or local private folders.
    paths = [root / 'README.md', root / 'THIRD_PARTY_NOTICES.md']
    for name in SKILLS:
        paths.extend(p for p in (root / name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for file in paths:
        if not file.is_file():
            errors.append(f'missing {file.relative_to(root)}')
            continue
        body = file.read_text(encoding='utf-8')
        label = file.relative_to(root).as_posix()
        for rule, message in ((PRIVATE_URL, 'personal Google storage URL'), (LOCAL_PATH, 'machine-specific/private path'), (SECRET, 'credential pattern')):
            if rule.search(body):
                errors.append(f'{label}: {message}')
        if file.suffix != '.md':
            continue
        for target in markdown_targets(body):
            split = urlsplit(target)
            if split.scheme or target.startswith(('#', '//')):
                continue
            resolved = (file.parent / unquote(split.path)).resolve()
            if not resolved.is_relative_to(root):
                errors.append(f'{label}: link escapes bundle: {target}')
            elif not resolved.exists():
                errors.append(f'{label}: missing link target: {target}')

    template = root / 'maintain-nutrition-training-diary/assets/profile.example.yaml'
    if not template.is_file():
        errors.append('missing empty profile template')
    else:
        body = template.read_text(encoding='utf-8')
        # Public templates must contain no owner, source locator or body metrics.
        for key in ('owner', 'locator', 'personalization_source', 'context_source', 'language', 'timezone', 'write_enabled'):
            if not re.search(r'^\s*' + key + r': null\s*$', body, re.M):
                errors.append(f'profile template: {key} must be null')
        if not re.search(r'^activity_types: \[\]\s*$', body, re.M):
            errors.append('profile template: activity_types must be empty')
        if re.search(r'^\s*(?:weight_kg|height_cm|age|birth_date|bmr|calorie_goal|protein_goal):', body, re.M):
            errors.append('profile template: personal body/goal fields must not be prefilled')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = check(args.root)
    for error in errors:
        print('ERROR:', error)
    print(f'{len(SKILLS)} skills checked; {len(errors)} packaging errors')
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())
