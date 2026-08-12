"""Task 4: `classify` — the one verdict command. Four values, one probes row."""
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


class ClassifyCase(unittest.TestCase):
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
        self.anchor = d / 'run_prompts.py'
        self.anchor.write_text(
            "\n" * 10 + "ledger = {}\nfor rec in records:\n    ledger[rec['id']] = 1\n")
        self.con = tutor_db.connect()
        self.root = stack.push(self.con, PID, 'uuid', why='the anchor',
                               anchor=(str(self.anchor), 11, 13))

    def tearDown(self):
        for k in ('TUTOR_DB', 'TUTOR_PROJECT_BASE', 'TUTOR_PROJECT_ID'):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def run_classify(self, slug='uuid', result='HIT', rung='predict',
                     answer='he said the thing', terms=None):
        self.db.classify(argparse.Namespace(
            slug=slug, result=result, rung=rung, answer=answer, terms=terms))

    def probes(self):
        return self.db.connect().execute("SELECT * FROM probes").fetchall()


class TestBlocked(ClassifyCase):
    def test_two_terms_push_exactly_one_frame_and_queue_the_other(self):
        self.run_classify(result='BLOCKED', terms='pathlib,ledger')
        con = self.db.connect()
        frames = con.execute(
            "SELECT slug FROM stack_frames ORDER BY id").fetchall()
        self.assertEqual([r[0] for r in frames], ['uuid', 'ledger'],
                         "exactly one push; `ledger` wins the anchor tie-break")
        self.assertEqual(self.stack.pending(con, self.root), ['pathlib'])

    def test_pushed_frame_records_the_interrupted_question(self):
        self.run_classify(result='BLOCKED', terms='ledger',
                          answer='what is a ledger?')
        con = self.db.connect()
        top = self.stack.top(con, PID)
        self.assertEqual(top['slug'], 'ledger')
        self.assertEqual(top['parent_id'], self.root)

    def test_unknown_terms_are_inserted_as_hole_sourced_concepts(self):
        self.run_classify(result='BLOCKED', terms='pathlib,ledger')
        con = self.db.connect()
        rows = con.execute(
            "SELECT slug, source, depth, state FROM concepts ORDER BY slug"
        ).fetchall()
        got = {r['slug']: (r['source'], r['depth'], r['state']) for r in rows}
        self.assertEqual(got['pathlib'], ('hole', 0, 'CANT'))
        self.assertEqual(got['ledger'], ('hole', 0, 'CANT'))

    def test_blocked_without_terms_is_refused(self):
        with self.assertRaises(SystemExit):
            self.run_classify(result='BLOCKED', terms=None)

    def test_lowest_existing_depth_wins_over_the_anchor_tiebreak(self):
        con = self.db.connect()
        con.execute("INSERT INTO concepts(slug,name,definition,category,depth)"
                    " VALUES ('pathlib','pathlib','p','stdlib',1)")
        con.execute("INSERT INTO concepts(slug,name,definition,category,depth)"
                    " VALUES ('ledger','ledger','l','pattern',4)")
        con.commit()
        self.run_classify(result='BLOCKED', terms='ledger,pathlib')
        self.assertEqual(self.stack.top(self.db.connect(), PID)['slug'], 'pathlib')


class TestOneRowPerJudgment(ClassifyCase):
    def _reset_rungs(self):
        con = self.db.connect()
        con.execute("UPDATE stack_frames SET rungs='{}' WHERE id=?", (self.root,))
        con.commit()
        con.close()

    def test_every_result_writes_exactly_one_probe(self):
        """Whichever of the four it is, it is one row. Not zero, not two."""
        for res in ('HIT', 'WEAK', 'MISS'):
            self._reset_rungs()
            before = len(self.probes())
            self.run_classify(result=res, rung='predict')
            self.assertEqual(len(self.probes()) - before, 1,
                             f"{res} must write exactly one probes row")
        self._reset_rungs()
        before = len(self.probes())
        self.run_classify(result='BLOCKED', rung='predict', terms='thing')
        self.assertEqual(len(self.probes()) - before, 1,
                         "BLOCKED must write exactly one probes row too")

    def test_the_probe_carries_the_rung_and_the_answer(self):
        self.run_classify(result='HIT', rung='perturb', answer='he traced it')
        p = self.probes()[-1]
        self.assertEqual(p['rung'], 'perturb')
        self.assertEqual(p['result'], 'HIT')
        self.assertEqual(p['answer'], 'he traced it')


class TestVocab(ClassifyCase):
    def test_hit_on_a_term_proves_it(self):
        self.run_classify(result='HIT', terms='ledger')
        row = self.db.connect().execute(
            "SELECT status FROM vocab WHERE term='ledger'").fetchone()
        self.assertEqual(row[0], 'proved')

    def test_blocked_on_a_term_leaves_it_unknown(self):
        self.run_classify(result='BLOCKED', terms='ledger')
        row = self.db.connect().execute(
            "SELECT status FROM vocab WHERE term='ledger'").fetchone()
        self.assertEqual(row[0], 'unknown')


class TestWeakLocksTheRung(ClassifyCase):
    def test_weak_refuses_a_move_to_the_next_rung(self):
        self.run_classify(result='WEAK', rung='predict')
        with self.assertRaises(SystemExit):
            self.run_classify(result='HIT', rung='perturb')

    def test_weak_allows_a_retry_on_the_same_rung(self):
        self.run_classify(result='WEAK', rung='predict')
        self.run_classify(result='HIT', rung='predict')
        self.assertEqual(
            self.stack.rungs(self.db.connect(), self.root)['predict'], 'HIT')


class TestRefusals(ClassifyCase):
    def test_unknown_rung(self):
        with self.assertRaises(SystemExit):
            self.run_classify(rung='vibes')

    def test_unknown_result(self):
        with self.assertRaises(SystemExit):
            self.run_classify(result='GREAT')

    def test_slug_that_is_not_the_top_frame(self):
        self.stack.push(self.db.connect(), PID, 'ledger')
        with self.assertRaises(SystemExit):
            self.run_classify(slug='uuid')

    def test_empty_stack(self):
        con = self.db.connect()
        con.execute("DELETE FROM stack_frames")
        con.commit()
        con.close()
        with self.assertRaises(SystemExit):
            self.run_classify()


class TestRemovedCommands(unittest.TestCase):
    def test_v3_verdict_commands_are_gone(self):
        import tutor_db
        for gone in ('assess', 'turn_brief', 'concept_pass', 'teach_open',
                     'teach_close'):
            self.assertFalse(hasattr(tutor_db, gone),
                             f"{gone} must be removed — classify replaces it")
        for gone in ('assess', 'turn-brief', 'concept-pass', 'teach-open',
                     'teach-close'):
            self.assertNotIn(gone, tutor_db.DISPATCH)


if __name__ == '__main__':
    unittest.main()
