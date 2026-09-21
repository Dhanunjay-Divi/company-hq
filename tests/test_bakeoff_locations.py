from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from bakeoff_locations import location_pattern

class LocationTests(unittest.TestCase):
    def test_locations_are_derived_from_observed_trace_not_reference_answers(self):
        result = location_pattern('authorize_session', 'fixture.auth:\n  validate_token 1\n  Session 2\nfixture.api:\n  get_report 1\n')
        self.assertIn('validate_token', result)
        self.assertIn('authorize_session', result)
        self.assertNotIn('check_permission', result)

    def test_location_seed_is_escaped_and_preserved_on_empty_trace(self):
        self.assertEqual(location_pattern('module.fn', ''), r'module\.fn')
