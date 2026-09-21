from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from bakeoff_evidence import assess, changes, compression_gate, coverage, exit_code, selection_status, snapshot, text


class EvidenceTests(unittest.TestCase):
    def test_timeout_bytes_are_decoded(self):
        self.assertEqual(text(b'partial\xff'), 'partial\ufffd')
        self.assertEqual(text(None), '')

    def test_error_output_cannot_score(self):
        self.assertFalse(coverage('authorize_session', ['authorize_session'], ok=False)['coverage_complete'])
        self.assertIsNone(coverage('error', ['error'], ok=False)['stdout_bytes'])

    def test_partial_identifier_not_a_match(self):
        self.assertFalse(coverage('not_authorize_session_old', ['authorize_session'], ok=True)['coverage_complete'])

    def test_exact_identifier_and_path_required(self):
        self.assertTrue(coverage('authorize_session() auth/session.py:16', ['authorize_session', 'auth/session.py'], ok=True)['coverage_complete'])
        self.assertFalse(coverage('authorize_session', ['authorize_session', 'auth/session.py'], ok=True)['coverage_complete'])

    def test_empty_expected_is_not_success(self):
        self.assertFalse(coverage('', [], ok=True)['coverage_complete'])

    def test_all_failed_cannot_pass(self):
        self.assertEqual(exit_code({'a': {'status': 'build_failed'}}), 1)

    def test_skipped_candidate_blocks_complete_suite(self):
        self.assertEqual(selection_status({'a': {'status': 'smoke_passed'}, 'b': {'status': 'not_run'}}), 'incomplete')

    def test_clean_smoke_is_not_universal_winner(self):
        self.assertEqual(selection_status({'a': {'status': 'smoke_passed'}}), 'smoke_candidates_only')

    def test_mutation_blocks_selection(self):
        self.assertNotEqual(exit_code({'a': {'status': 'smoke_passed'}, 'b': {'status': 'source_changed'}}), 0)

    def test_nested_generated_state_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'auth').mkdir()
            (root / 'auth/a.py').write_text('x=1')
            before = snapshot(root)
            (root / 'auth/cache.db').write_text('generated')
            delta = changes(before, snapshot(root))
            self.assertTrue(delta['source_unchanged'])
            self.assertFalse(delta['project_clean'])
            self.assertEqual(delta['generated_paths'], ['auth/cache.db'])

    def test_original_deletion_detected(self):
        self.assertFalse(changes({'a.py': 'hash'}, {})['source_unchanged'])

    def test_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'repo'; root.mkdir()
            secret = Path(td) / 'outside'; secret.write_text('do not read')
            try:
                (root / 'link').symlink_to(secret)
            except OSError:
                self.skipTest('symlinks unavailable')
            self.assertEqual(snapshot(root)['link'], 'link:' + str(secret))

    def test_query_failure_beats_coverage(self):
        self.assertEqual(assess({'ok': True}, [{'ok': False, 'coverage_complete': True}], {'source_unchanged': True}), 'query_failed')

    def test_failed_build_cannot_hide_source_mutation(self):
        self.assertEqual(assess({'ok': False}, [], {'source_unchanged': False}), 'source_changed')

    def test_project_cache_needs_adapter(self):
        self.assertEqual(assess({'ok': True}, [{'ok': True, 'coverage_complete': True}], {'source_unchanged': True, 'project_clean': False}), 'needs_external_state_adapter')

    def test_short_error_is_not_compression(self):
        result = compression_gate({'text': 'x'*80 + 'FAIL', 'returncode': 1}, {'text': 'command missing', 'returncode': 127}, ['FAIL'], 1)
        self.assertFalse(result['passed']); self.assertIsNone(result['byte_reduction'])

    def test_lost_failure_is_not_saving(self):
        result = compression_gate({'text': 'x'*80 + 'FAIL', 'returncode': 1}, {'text': 'all passed', 'returncode': 0}, ['FAIL'], 1)
        self.assertFalse(result['passed'])

    def test_lost_identifier_is_not_saving(self):
        result = compression_gate({'text': 'x'*80 + 'FAIL invoice-173', 'returncode': 1}, {'text': 'FAIL', 'returncode': 1}, ['FAIL', 'invoice-173'], 1)
        self.assertFalse(result['passed']); self.assertEqual(result['missing_evidence'], ['invoice-173'])

    def test_lossless_fixture_reduction_is_bytes_only(self):
        result = compression_gate({'text': 'x'*80 + 'FAIL', 'returncode': 1}, {'text': 'FAIL', 'returncode': 1}, ['FAIL'], 1)
        self.assertTrue(result['passed']); self.assertIsNone(result['actual_model_tokens']); self.assertIsNone(result['billed_savings'])

if __name__ == '__main__':
    unittest.main()
