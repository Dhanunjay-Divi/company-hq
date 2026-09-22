import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from workflow_plan import WorkflowPlans

PLAN={'goal':'Ship fixture','steps':[{'key':'design','title':'Design','description':'d','owner':'ada','dependsOn':[],'acceptance':'reviewed'},{'key':'build','title':'Build','description':'b','owner':'lin','dependsOn':['design'],'acceptance':'tested'}]}
class Store:
    def __init__(self):self.rows=[];self.fail=False
    def create(self,subject,description,**kwargs):
        if self.fail and len(self.rows)==1:raise RuntimeError('simulated crash')
        row=SimpleNamespace(id='t'+str(len(self.rows)+1),subject=subject,description=description,status='blocked' if kwargs['blocked_by'] else 'pending',**kwargs)
        self.rows.append(row);return row
    def list_tasks(self):return self.rows

class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store();self.service=WorkflowPlans(Path(self.temp.name),lambda _:self.store)
    def test_validation_dag_and_input_unchanged(self):
        original=copy.deepcopy(PLAN)
        self.assertEqual([s['key'] for s in self.service.preview('team',PLAN,['ada','lin'])['steps']],['design','build'])
        self.assertEqual(PLAN,original)
        bad=copy.deepcopy(PLAN);bad['steps'][0]['dependsOn']=['build']
        with self.assertRaises(ValueError):self.service.preview('team',bad,['ada','lin'])
        with self.assertRaises(ValueError):self.service.preview('team',PLAN,['ada'])
    def test_idempotent_apply_and_actual_progress(self):
        a=self.service.apply('team','request-123',PLAN,['ada','lin'])
        self.assertEqual(a['dependencies']['build'],['t1'])
        self.store.rows[0].status='completed'
        b=self.service.apply('team','request-123',PLAN,['ada','lin'])
        self.assertEqual(len(self.store.rows),2)
        self.assertEqual(b['statuses']['design'],'completed')
    def test_partial_import_retry_and_changed_payload_rejected(self):
        self.store.fail=True
        with self.assertRaises(RuntimeError):self.service.apply('team','request-123',PLAN,['ada','lin'])
        changed=copy.deepcopy(PLAN);changed['goal']='Different objective'
        with self.assertRaises(ValueError):self.service.apply('team','request-123',changed,['ada','lin'])
        self.store.fail=False
        value=self.service.apply('team','request-123',PLAN,['ada','lin'])
        self.assertEqual(len(self.store.rows),2)
        self.assertEqual(value['taskIDs'],{'design':'t1','build':'t2'})
