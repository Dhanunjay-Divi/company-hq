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

    def test_codex_app_path_fallback_is_used_when_path_lookup_is_empty(self):
        with tempfile.TemporaryDirectory() as temporary:
            app_codex = Path(temporary) / 'codex'
            app_codex.write_text('fixture')
            app_codex.chmod(0o700)
            with mock.patch.object(d.shutil, 'which', return_value=None), mock.patch.object(d, 'codex_executable', return_value=app_codex):
                self.assertEqual(d._client_paths()['codex'], str(app_codex))

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
            with mock.patch.object(d.shutil,'which',side_effect=lambda n:'/native/codex' if n=='codex' else None), mock.patch.object(d,'codex_models',return_value=[*self.rows,alternate]) as catalog:
                d.discover(base=base)
                policy['preferred_supervisors'][0]['model']='other'
                (base/'routing.json').write_text(json.dumps(policy))
                value=d.discover(base=base)
                self.assertTrue(value['cached'])
                self.assertEqual(value['selection']['model'],'other')
                self.assertEqual(json.loads((base/'capabilities.json').read_text())['selection']['model'],'other')
                catalog.assert_called_once()


if __name__=='__main__':unittest.main()
