import tempfile
import unittest
from pathlib import Path

from project_context import ContextError, ProjectContext
from project_context_mcp import handle


class Task:
    def __init__(self, number): self.id=f"t-{number}"; self.subject='Plan '+str(number); self.description='Acceptance '+str(number); self.status="pending"; self.owner="owner"; self.priority="medium"
class Store:
    def __init__(self, team): self.team=team
    def list_tasks(self): return [Task(number) for number in range(3)]


class ProjectContextTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); root=Path(self.temp.name); self.project=root/'project'; self.project.mkdir(); self.skills=root/'skills'; self.skills.mkdir()
        skill=self.skills/'reviewed'; skill.mkdir(); (skill/'SKILL.md').write_text('---\ndescription: Reviewed reference\n---\nhello', encoding='utf-8')
        self.context=ProjectContext(self.project, 'team', skill_roots=(self.skills,), store_factory=Store, binding_resolver=lambda team:self.project)
    def tearDown(self): self.temp.cleanup()
    def test_identity_and_board_use_one_team_store_with_paging(self):
        self.assertEqual(self.context.identity()['team'], 'team'); page=self.context.board(limit=2); self.assertEqual([row['id'] for row in page['tasks']], ['t-0','t-1']); self.assertEqual(page['tasks'][0]['description'], 'Acceptance 0'); self.assertEqual(page['nextCursor'],2)
    def test_lists_and_pages_only_registered_skill_files(self):
        self.assertEqual(self.context.skills(), [{'name':'reviewed','description':'Reviewed reference'}]); first=self.context.skill_read('reviewed', limit=5); self.assertEqual(first['text'], '---\nd'); self.assertEqual(first['nextCursor'],5)
    def test_rejects_traversal_and_symlink_references(self):
        with self.assertRaises(ContextError): self.context.skill_read('reviewed','../outside')
        target=Path(self.temp.name)/'outside'; target.write_text('no')
        (self.skills/'reviewed'/'link').symlink_to(target)
        with self.assertRaises(ContextError): self.context.skill_read('reviewed','link')
        folder=self.skills/'reviewed'/'linked'; folder.symlink_to(Path(self.temp.name))
        with self.assertRaises(ContextError): self.context.skill_read('reviewed','linked/outside')
    def test_project_and_team_binding_are_validated(self):
        with self.assertRaises(ContextError): ProjectContext(self.project,'bad team',skill_roots=(self.skills,),store_factory=Store, binding_resolver=lambda team:self.project)
        with self.assertRaises(ContextError): ProjectContext(Path(self.temp.name)/'missing','team',skill_roots=(self.skills,),store_factory=Store, binding_resolver=lambda team:self.project)
        other=Path(self.temp.name)/'other'; other.mkdir()
        with self.assertRaises(ContextError): ProjectContext(self.project,'team',skill_roots=(self.skills,),store_factory=Store, binding_resolver=lambda team:other)

    def test_mcp_rejects_invalid_requests_and_returns_tool_errors_without_mutation(self):
        with self.assertRaises(ContextError): handle(self.context, [])
        self.assertEqual(handle(self.context, {'jsonrpc':'2.0','id':1,'method':'ping'})['result'], {})
        error=handle(self.context, {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'unknown'}})
        self.assertTrue(error['result']['isError'])


if __name__ == '__main__': unittest.main()
