"""v4.1 — two exit prices (TARGET/TRANSIT), the --done finish line, the vocab door.

Fixes A, D, E from TUTOR_AUDIT.md. The descent is never capped; only the price of
climbing back and the requirement of a finish line change.
"""
import argparse
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

TUTOR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TUTOR))

PID = 'proj'


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        os.environ['TUTOR_DB'] = str(d / 'tutor.db')
        os.environ['TUTOR_PROJECT_BASE'] = str(d / 'base')
        os.environ['TUTOR_PROJECT_ID'] = PID
        import tutor_db
        import stack
        self.db, self.stack = tutor_db, stack
        con = sqlite3.connect(str(d / 'tutor.db'))
        con.executescript((TUTOR / 'schema.sql').read_text(encoding='utf-8'))
        con.execute("INSERT INTO sessions(started_at) VALUES ('t')")
        con.commit()
        con.close()
        self.con = tutor_db.connect()
        self.root = stack.push(self.con, PID, 'uuid', why='anchor')

    def tearDown(self):
        for k in ('TUTOR_DB', 'TUTOR_PROJECT_BASE', 'TUTOR_PROJECT_ID'):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def classify(self, **kw):
        base = dict(slug='uuid', result='HIT', rung='predict',
                    answer='x', terms=None, kind=None, done=None)
        base.update(kw)
        self.db.classify(argparse.Namespace(**base))


class TestExitPrice(unittest.TestCase):
    def con(self):
        c = sqlite3.connect(':memory:')
        c.row_factory = sqlite3.Row
        c.executescript((TUTOR / 'schema.sql').read_text(encoding='utf-8'))
        return c

    def test_transit_pops_on_predict_and_perturb_only(self):
        import stack
        con = self.con()
        f = stack.push(con, PID, 'object', kind='TRANSIT', done_def='say why 3 is obj')
        stack.set_rung(con, f, 'predict', 'HIT')
        stack.set_rung(con, f, 'perturb', 'HIT')
        with tempfile.TemporaryDirectory() as d:
            stack.pop(con, f, base=d)      # must NOT raise
        self.assertEqual(stack.frame(con, f)['state'], 'PASSED')

    def test_target_still_needs_all_four(self):
        import stack
        con = self.con()
        f = stack.push(con, PID, 'uuid', kind='TARGET')
        stack.set_rung(con, f, 'predict', 'HIT')
        stack.set_rung(con, f, 'perturb', 'HIT')
        with self.assertRaises(stack.StackRefusal) as e:
            stack.pop(con, f)
        self.assertIn('produce', str(e.exception))

    def test_unknown_kind_is_refused(self):
        import stack
        con = self.con()
        with self.assertRaises(stack.StackRefusal):
            stack.push(con, PID, 'x', kind='WHATEVER')


class TestDescentContract(Case):
    def test_blocked_defaults_to_transit(self):
        self.classify(result='BLOCKED', terms='object', done='say why 3 is obj')
        con = self.db.connect()
        child = con.execute(
            "SELECT kind FROM stack_frames WHERE slug='object'").fetchone()
        self.assertEqual(child['kind'], 'TRANSIT')

    def test_blocked_requires_a_finish_line(self):
        with self.assertRaises(SystemExit):
            self.classify(result='BLOCKED', terms='object', done=None)

    def test_kind_can_be_overridden_to_target(self):
        self.classify(result='BLOCKED', terms='object', done='master objects',
                      kind='target')
        con = self.db.connect()
        child = con.execute(
            "SELECT kind FROM stack_frames WHERE slug='object'").fetchone()
        self.assertEqual(child['kind'], 'TARGET')


class TestVocabDoor(Case):
    def test_show_marks_a_term_shown_so_ship_check_passes(self):
        # unshown term is rejected
        ok, _ = self.db.ship_check(self.db.connect(), PID, ['Path'], 1, 'uuid')
        self.assertFalse(ok)
        # teach it, then it passes
        self.db.show_term(argparse.Namespace(terms=['Path']))
        ok, _ = self.db.ship_check(self.db.connect(), PID, ['Path'], 1, 'uuid')
        self.assertTrue(ok)


if __name__ == '__main__':
    unittest.main()
