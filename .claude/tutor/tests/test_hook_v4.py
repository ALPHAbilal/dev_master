"""Task 6: the hooks. The pointer is short, the wall is real, the map is a file."""
import argparse
import contextlib
import io
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

TUTOR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TUTOR))

PID = 'proj'


class HookCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        os.environ['TUTOR_DB'] = str(d / 'tutor.db')
        os.environ['TUTOR_PROJECT_BASE'] = str(d / 'base')
        os.environ['TUTOR_PROJECT_ID'] = PID
        os.environ['TUTOR_PROGRESS'] = str(d / 'PROGRESS.md')
        os.environ['TUTOR_PHASE_STATE'] = str(d / '.phase_gate.json')
        import tutor_db
        import tutor_hook
        import stack
        self.db, self.hook, self.stack = tutor_db, tutor_hook, stack
        con = sqlite3.connect(str(d / 'tutor.db'))
        con.executescript((TUTOR / 'schema.sql').read_text(encoding='utf-8'))
        con.execute("INSERT INTO sessions(started_at) VALUES ('t')")
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('phase','DRILL')")
        con.execute("INSERT INTO targets(learner,name,created_at)"
                    " VALUES ('bilal','t','t')")
        con.commit()
        con.close()
        self.anchor = d / 'run_prompts.py'
        self.anchor.write_text("\n" * 10 + "ledger = {}\nx\ny\n")
        con = self.db.connect()
        self.root = stack.push(con, PID, 'uuid',
                               anchor=(str(self.anchor), 11, 13))
        con.close()
        self.progress = d / 'PROGRESS.md'

    def tearDown(self):
        for k in ('TUTOR_DB', 'TUTOR_PROJECT_BASE', 'TUTOR_PROJECT_ID',
                  'TUTOR_PROGRESS', 'TUTOR_PHASE_STATE'):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def run_hook(self, fn, data):
        buf = io.StringIO()
        err = io.StringIO()
        code = 0
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                fn(data)
        except SystemExit as e:
            code = e.code
        return code, buf.getvalue(), err.getvalue()


class TestPhaseGuard(HookCase):
    def test_prints_file_doctrine_and_stack_in_ten_lines(self):
        _, out, _ = self.run_hook(self.hook.cmd_phase_guard,
                                  {'session_id': 's1'})
        self.assertIn('03-drill.md', out)
        self.assertIn('ADVERSARY', out)
        self.assertIn('uuid', out)
        lines = [l for l in out.splitlines() if l.strip()]
        self.assertLessEqual(len(lines), 10,
                             f"the pointer must stay readable:\n{out}")

    def test_shows_the_whole_stack_path(self):
        con = self.db.connect()
        self.stack.push(con, PID, 'ledger')
        con.close()
        _, out, _ = self.run_hook(self.hook.cmd_phase_guard, {'session_id': 's1'})
        self.assertIn('uuid > ledger', out)

    def test_build_phase_switches_the_doctrine_to_ally(self):
        con = self.db.connect()
        con.execute("UPDATE meta SET value='BUILD' WHERE key='phase'")
        con.commit()
        con.close()
        _, out, _ = self.run_hook(self.hook.cmd_phase_guard, {'session_id': 's1'})
        self.assertIn('ALLY', out)
        self.assertIn('05-build.md', out)

    def test_the_bucket_message_is_gone(self):
        _, out, _ = self.run_hook(self.hook.cmd_phase_guard, {'session_id': 's1'})
        self.assertNotIn('BUCKET', out)
        self.assertNotIn('turn-brief', out)


class TestShipCheckHook(HookCase):
    def bash(self, cmd):
        return self.run_hook(self.hook.cmd_ship_check,
                             {'session_id': 's1', 'tool_input': {'command': cmd}})

    def test_blocks_a_draft_using_an_unknown_term(self):
        code, _, err = self.bash(
            "python3 tutor_db.py draft --terms idempotent --hops 1 --about uuid")
        self.assertEqual(code, 2)
        self.assertIn('idempotent', err)

    def test_blocks_a_draft_over_the_hop_budget(self):
        code, _, err = self.bash(
            "python3 tutor_db.py draft --hops 5 --about uuid")
        self.assertEqual(code, 2)
        self.assertIn('hop', err.lower())

    def test_allows_a_clean_draft(self):
        con = self.db.connect()
        con.execute("INSERT INTO vocab(term,status,first_seen)"
                    " VALUES ('ledger','shown','t')")
        con.commit()
        con.close()
        code, _, _ = self.bash(
            "python3 tutor_db.py draft --terms ledger --hops 1 --about uuid")
        self.assertEqual(code, 0)

    def test_ignores_commands_that_are_not_a_draft(self):
        code, _, _ = self.bash("ls -la")
        self.assertEqual(code, 0)
        code, _, _ = self.bash("python3 tutor_db.py brief")
        self.assertEqual(code, 0)


class TestGatedCommands(HookCase):
    def test_classify_and_draft_are_gated(self):
        self.assertIn('classify', self.hook.GATED_CMDS)
        self.assertIn('draft', self.hook.GATED_CMDS)

    def test_phase_gate_blocks_classify_before_the_file_is_read(self):
        self.run_hook(self.hook.cmd_phase_guard, {'session_id': 's1'})
        code, _, err = self.run_hook(
            self.hook.cmd_phase_gate,
            {'session_id': 's1',
             'tool_input': {'command': 'python3 tutor_db.py classify uuid '
                                       '--result HIT --rung predict --answer x'}})
        self.assertEqual(code, 2)
        self.assertIn('03-drill.md', err)


class TestProgressMap(HookCase):
    def test_progress_has_a_stack_section(self):
        con = self.db.connect()
        self.stack.push(con, PID, 'ledger')
        con.close()
        self.db.tree(argparse.Namespace(quiet=True))
        body = self.progress.read_text(encoding='utf-8')
        self.assertIn('STACK', body)
        self.assertIn('uuid > ledger', body)

    def test_hole_sourced_concepts_are_marked(self):
        con = self.db.connect()
        con.execute("INSERT INTO concepts(slug,name,definition,category,depth,source)"
                    " VALUES ('ledger','ledger','l','pattern',1,'hole')")
        con.execute("INSERT INTO concepts(slug,name,definition,category,depth,source)"
                    " VALUES ('uuid','uuid','u','stdlib',1,'code')")
        con.commit()
        con.close()
        self.db.tree(argparse.Namespace(quiet=True))
        body = self.progress.read_text(encoding='utf-8')
        ledger = [l for l in body.splitlines() if 'ledger' in l][0]
        uuid = [l for l in body.splitlines() if l.strip().startswith(('[', ' '))
                and 'uuid' in l and 'ledger' not in l]
        self.assertIn('[h]', ledger)
        self.assertTrue(uuid and '[h]' not in uuid[0])


class TestNoDuplication(unittest.TestCase):
    def test_hook_imports_from_tutor_db_instead_of_copying(self):
        src = (TUTOR / 'tutor_hook.py').read_text(encoding='utf-8')
        self.assertNotIn('def get_bucket', src)
        self.assertNotIn('def bucket_status_message', src)
        self.assertNotIn('def detect_project_id', src)
        self.assertNotIn('ready_archive', src)

    def test_tree_runs_only_on_the_commands_that_move_the_map(self):
        import tutor_db
        self.assertEqual(set(tutor_db.TREE_ON),
                         {'classify', 'pass', 'phase', 'session'})


class TestPhaseFiles(unittest.TestCase):
    def test_all_six_exist(self):
        import tutor_hook
        skill = TUTOR.parent / 'skills' / 'tutor_v3'
        for phase, rel in tutor_hook.PHASE_FILE.items():
            self.assertTrue((skill / rel).exists(), f"missing {rel} for {phase}")

    def test_adversary_files_carry_law_zero_and_build_carries_ally(self):
        import tutor_hook
        skill = TUTOR.parent / 'skills' / 'tutor_v3'
        for phase, rel in tutor_hook.PHASE_FILE.items():
            body = (skill / rel).read_text(encoding='utf-8')
            if tutor_hook.MODE[phase] == 'ADVERSARY':
                self.assertIn('LAW 0', body, f"{rel} must carry LAW 0")
            else:
                self.assertIn('ALLY', body, f"{rel} must carry the ALLY doctrine")

    def test_each_file_states_its_rungs(self):
        import tutor_hook
        import stack
        skill = TUTOR.parent / 'skills' / 'tutor_v3'
        for rel in tutor_hook.PHASE_FILE.values():
            body = (skill / rel).read_text(encoding='utf-8')
            self.assertTrue(any(r in body for r in stack.RUNGS),
                            f"{rel} must say which rungs it uses")


if __name__ == '__main__':
    unittest.main()
