"""Граничные проверки требований формы публикации; без сети и новых зависимостей."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('distribution', ROOT / 'checks' / 'validate_distribution.py')
distribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distribution)


class ListingMetadataTests(unittest.TestCase):
    def setUp(self):
        manifest = json.loads((ROOT / 'packaging' / 'plugin.json').read_text(encoding='utf-8'))
        self.metadata = copy.deepcopy(manifest['extensions']['com.openai']['interface'])

    def test_subtitle_limit_counts_spaces(self):
        self.metadata['shortDescription'] = 'А' * 29 + ' '
        self.assertFalse(distribution.listing_errors(self.metadata))
        self.metadata['shortDescription'] += 'А'
        self.assertTrue(any('shortDescription' in p for p in distribution.listing_errors(self.metadata)))

    def test_local_package_and_submission_have_different_url_requirements(self):
        for field in distribution.LISTING_URLS:
            self.metadata.pop(field, None)
        self.assertFalse(distribution.listing_errors(self.metadata))
        errors = distribution.listing_errors(self.metadata, require_urls=True)
        self.assertEqual(len(errors), 4)
        self.assertTrue(all(any(field in error for error in errors) for field in distribution.LISTING_URLS))

    def test_present_url_must_use_https_without_credentials(self):
        for invalid in ('http://example.com/privacy', 'https://user:secret@example.com/privacy'):
            self.metadata['privacyPolicyURL'] = invalid
            self.assertTrue(distribution.listing_errors(self.metadata))
        self.metadata['privacyPolicyURL'] = 'https://example.com/privacy'
        # Это лишь синтаксическая проверка; существование страницы не утверждается.
        self.assertFalse(distribution.listing_errors(self.metadata))


if __name__ == '__main__':
    unittest.main()
