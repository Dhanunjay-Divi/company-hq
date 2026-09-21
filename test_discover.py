import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import discover as d


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.policy = {'preferred_supervisors': [{'provider':'codex','model':'reviewed','effort':'high'}],
                       'follow_official_upgrade_hint':True, 'reviewed_on':'2026-09-13'}
        self.rows = [{'id':'reviewed','model':'reviewed','upgrade':None,'defaultReasoningEffort':'medium',
                      'supportedReasoningEfforts':[{'reasoningEffort':'medium'},{'reasoningEffort':'high'}]}]
        self.caps = {'providers':{'codex':{'status':'catalog_verified','models':self.rows}}}

    def test_uses_reviewed_available_supervisor(self):
        self.assertEqual(d.select_supervisor(self.policy,self.caps)['model'],'reviewed')

    def test_follows_available_official_upgrade(self):
        self.rows[0]['upgrade']='successor'
        successor=copy.deepcopy(self.rows[0]);successor.update(id='successor',model='successor',upgrade=None)
        self.rows.append(successor)
        value=d.select_supervisor(self.policy,self.caps)
        self.assertEqual(value['model'],'successor');self.assertEqual(value['upgraded_from'],['reviewed'])

    def test_unknown_names_do_not_establish_quality_ranking(self):
        self.rows.append({'id':'gpt-999-unreviewed','model':'gpt-999-unreviewed','isDefault':True})
        self.assertEqual(d.select_supervisor(self.policy,self.caps)['model'],'reviewed')

    def test_unavailable_client_cannot_be_selected(self):
        self.caps['providers']['codex']['status']='client_detected'
        self.assertIsNone(d.select_supervisor(self.policy,self.caps)['model'])

    def test_missing_upgrade_does_not_invent_availability(self):
        self.rows[0]['upgrade']='unavailable-model'
        self.assertEqual(d.select_supervisor(self.policy,self.caps)['model'],'reviewed')

    def test_effort_matches_runtime_and_cycles_terminate(self):
        self.rows[0]['supportedReasoningEfforts']=[{'reasoningEffort':'medium'}]
        self.rows[0]['upgrade']='reviewed'
        self.assertEqual(d.select_supervisor(self.policy,self.caps)['effort'],'medium')

    def test_schema_two_selects_explicit_supervisor_tier_and_only_explicit_reviewed_fallback(self):
        policy = {
            'supervisor_tier': 'flagship',
            'escalation': {'start_tier': 'standard'},
            'tiers': {
                'flagship': {'codex_model': 'astra', 'default_effort': 'high'},
                'standard': {'codex_model': 'terra', 'default_effort': 'medium'},
            },
            'reviewed_codex_models': ['astra', 'terra'],
        }
        self.rows[:] = [
            {'id': 'astra', 'model': 'astra', 'defaultReasoningEffort': 'high', 'supportedReasoningEfforts': [{'reasoningEffort': 'high'}]},
            {'id': 'terra', 'model': 'terra', 'defaultReasoningEffort': 'medium', 'supportedReasoningEfforts': [{'reasoningEffort': 'medium'}]},
            {'id': 'unreviewed', 'model': 'unreviewed', 'defaultReasoningEffort': 'high', 'supportedReasoningEfforts': [{'reasoningEffort': 'high'}]},
        ]
        self.assertEqual(d.select_supervisor(policy, self.caps)['model'], 'astra')
        self.rows.pop(0)
        self.assertEqual(d.select_supervisor(policy, self.caps)['model'], 'terra')
        self.rows.pop(0)
        self.assertIsNone(d.select_supervisor(policy, self.caps)['model'])

    def test_desktop_presence_does_not_become_a_codex_cli_path(self):
        with mock.patch.object(d.shutil, 'which', return_value=None):
            self.assertIsNone(d._client_paths()['codex'])

    def test_checked_in_schema_two_routing_selects_its_configured_tier_model(self):
        policy = json.loads((d.BASE / 'routing.json').read_text())
        tier_name = policy.get('supervisor_tier') or policy['escalation']['start_tier']
        model = policy['tiers'][tier_name]['codex_model']
        capabilities = {
            'providers': {'codex': {'status': 'catalog_verified', 'models': [{
                'id': model, 'model': model,
                'defaultReasoningEffort': 'high',
                'supportedReasoningEfforts': [{'reasoningEffort': 'high'}],
            }]}},
        }
        self.assertEqual(d.select_supervisor(policy, capabilities)['model'], model)

    def test_policy_change_updates_cached_selection_used_by_installer(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)
            policy=copy.deepcopy(self.policy)
            (base/'routing.json').write_text(json.dumps(policy))
            alternate=copy.deepcopy(self.rows[0]);alternate.update(id='other',model='other')
            fixture_inventory = {'checkedAt': '2026-01-01T00:00:00+00:00', 'providers': [
                {'id': provider, 'cliPath': '/native/codex' if provider == 'codex' else None,
                 'desktopPath': None, 'installed': provider == 'codex', 'authentication': 'not_checked',
                 'runtimeReady': provider == 'codex', 'reason': 'fixture'}
                for provider in ('codex', 'claude', 'kimi', 'zai', 'cursor', 'grok', 'ollama')
            ]}
            with mock.patch.object(d.shutil,'which',side_effect=lambda n:'/native/codex' if n=='codex' else None), mock.patch.object(d,'provider_inventory',return_value=fixture_inventory), mock.patch.object(d,'codex_models',return_value=[*self.rows,alternate]) as catalog:
                d.discover(base=base)
                policy['preferred_supervisors'][0]['model']='other'
                (base/'routing.json').write_text(json.dumps(policy))
                value=d.discover(base=base)
                self.assertTrue(value['cached'])
                self.assertEqual(value['selection']['model'],'other')
                self.assertEqual(json.loads((base/'capabilities.json').read_text())['selection']['model'],'other')
                catalog.assert_called_once()

    def test_desktop_inventory_change_invalidates_cached_discovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base / 'routing.json').write_text(json.dumps(self.policy))
            def inventory(desktop):
                return {'checkedAt': '2026-01-01T00:00:00+00:00', 'providers': [
                    {'id': provider, 'cliPath': '/native/codex' if provider == 'codex' else None,
                     'desktopPath': desktop if provider == 'claude' else None,
                     'installed': provider in {'codex', 'claude'} if desktop else provider == 'codex',
                     'authentication': 'not_checked', 'runtimeReady': provider == 'codex', 'reason': 'fixture'}
                    for provider in ('codex', 'claude', 'kimi', 'zai', 'cursor', 'grok', 'ollama')
                ]}
            with mock.patch.object(d.shutil, 'which', side_effect=lambda n: '/native/codex' if n == 'codex' else None), mock.patch.object(d, 'provider_inventory', side_effect=[inventory(None), inventory('/Applications/Claude.app')]), mock.patch.object(d, 'codex_models', return_value=self.rows) as catalog:
                self.assertFalse(d.discover(base=base)['cached'])
                self.assertFalse(d.discover(base=base)['cached'])
                self.assertEqual(catalog.call_count, 2)


if __name__=='__main__':unittest.main()
