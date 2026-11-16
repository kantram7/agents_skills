"""Packaging failure cases and offline behavior of the included citation helper."""
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bundle = load('bundle', ROOT / 'scripts/validate_bundle.py')
citations = load('citations', ROOT / 'scientific-source-verification/scripts/verify_citations.py')


class Packaging(unittest.TestCase):
    def test_public_bundle(self):
        self.assertEqual([], bundle.check(ROOT))

    def modified_bundle(self):
        temp = tempfile.TemporaryDirectory(dir=os.environ.get('BUNDLE_TEST_TMPDIR'))
        self.addCleanup(temp.cleanup)
        target = Path(temp.name) / 'bundle'
        shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        return target

    def test_private_url_in_nested_reference_is_rejected(self):
        target = self.modified_bundle()
        reference = target / 'maintain-nutrition-training-diary/references/injected.md'
        reference.write_text('https://docs.google.com/spreadsheets/d/SYNTHETIC_TEST_ONLY/edit', encoding='utf-8')
        self.assertTrue(any('personal Google storage URL' in e for e in bundle.check(target)))

    def test_broken_cross_skill_link_is_rejected(self):
        target = self.modified_bundle()
        (target / 'nutrition-and-energy-balance/SKILL.md').write_text(
            (target / 'nutrition-and-energy-balance/SKILL.md').read_text(encoding='utf-8')
            + '\n[missing](../nonexistent-skill/SKILL.md)\n', encoding='utf-8')
        self.assertTrue(any('missing link target' in e for e in bundle.check(target)))

    def test_filled_profile_is_rejected(self):
        target = self.modified_bundle()
        template = target / 'maintain-nutrition-training-diary/assets/profile.example.yaml'
        template.write_text(template.read_text(encoding='utf-8').replace('owner: null', 'owner: SYNTHETIC_TEST_ONLY'), encoding='utf-8')
        self.assertTrue(any('owner must be null' in e for e in bundle.check(target)))


class CitationHelper(unittest.TestCase):
    def setUp(self):
        self.entry = {'_key': 'synthetic', 'title': 'Synthetic training study', 'author': 'Example, Alice', 'year': '2024', 'doi': '10.0000/synthetic'}
        self.record = {'DOI': '10.0000/synthetic', 'title': ['Synthetic training study'], 'author': [{'family': 'Example'}], 'issued': {'date-parts': [[2024]]}}

    def test_matching_metadata(self):
        with patch.object(citations, 'crossref_record', return_value=self.record):
            self.assertEqual('verified', citations.check_entry(self.entry)['status'])

    def test_resolving_doi_with_wrong_title_is_not_verified(self):
        self.record['title'] = ['Unrelated synthetic astronomy catalogue']
        with patch.object(citations, 'crossref_record', return_value=self.record):
            self.assertEqual('mismatch', citations.check_entry(self.entry)['status'])

    def test_unresolved_doi(self):
        with patch.object(citations, 'crossref_record', return_value=None), patch.object(citations, 'http_json', return_value=None):
            self.assertEqual('doi-not-found', citations.check_entry(self.entry)['status'])

    def test_missing_data_is_not_verified(self):
        self.assertEqual('unverifiable', citations.check_entry({'_key': 'empty'})['status'])


if __name__ == '__main__':
    unittest.main()
