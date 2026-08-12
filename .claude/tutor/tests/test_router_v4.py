"""Task 5: `brief` is a delta, and it re-reads the anchor off disk every time."""
import argparse
import io
import os
import contextlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

TUTOR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TUTOR))

PID = 'proj'


class BriefCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        os.environ['TUTOR_DB'] = str(d / 'tutor.db')
        os.environ['TUTOR_PROJECT_BASE'] = str(d / 'base')
        os.environ['TUTOR_PROJECT_ID'] = PID
        import tutor_db
        import stack
        import router
        self.db, self.stack, self.router = tutor_db, stack, router
        con = sqlite3.connect(str(d / 'tutor.db'))
        con.executescript((TUTOR / 'schema.sql').read_text(encoding='utf-8'))
        con.execute("INSERT INTO sessions(started_at) VALUES ('t')")
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('phase','DRILL')")
        con.commit()
        con.close()
        self.anchor = d / 'run_prompts.py'
        self.anchor.write_text("\n" * 10 + "ledger = {}\nfor rec in records:\n"
                                           "    ledger[rec['id']] = 1\n")
        con = self.db.connect()
        self.root = self.stack.push(con, PID, 'uuid', why='the anchor',
                                    anchor=(str(self.anchor), 11, 13))
        con.close()

    def tearDown(self):
        for k in ('TUTOR_DB', 'TUTOR_PROJECT_BASE', 'TUTOR_PROJECT_ID'):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def brief(self, full=False):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.db.brief(argparse.Namespace(full=full))
        return buf.getvalue()


class TestBriefContent(BriefCase):
    def test_prints_stack_path_rungs_pending_and_mode(self):
        con = self.db.connect()
        child = self.stack.push(con, PID, 'ledger', resume_q='what does uuid4 give?')
        self.stack.set_rung(con, child, 'predict', 'HIT')
        self.stack.queue_pending(con, child, ['pathlib'])
        con.close()
        out = self.brief(full=True)
        self.assertIn('uuid > ledger', out)
        self.assertIn('predict=HIT', out)
        self.assertIn('perturb=', out)
        self.assertIn('pathlib', out)
        self.assertIn('ADVERSARY', out)
        self.assertIn('what does uuid4 give?', out)

    def test_reads_the_anchor_lines_off_disk(self):
        out = self.brief(full=True)
        self.assertIn("ledger = {}", out)
        self.assertIn("for rec in records:", out)

    def test_anchor_is_re_read_not_remembered(self):
        self.brief(full=True)
        self.anchor.write_text("\n" * 10 + "CHANGED = 1\nx\ny\n")
        out = self.brief(full=True)
        self.assertIn('CHANGED = 1', out)
        self.assertNotIn('ledger = {}', out)

    def test_a_relative_anchor_resolves_against_the_project_root(self):
        """Hooks and commands run from different cwds. A path that only works
        from one of them silently prints no code from the other."""
        rel = Path('.claude/tutor/relanchor.py')
        real = TUTOR.parent.parent / rel
        real.write_text("alpha = 1\nbeta = 2\n")
        try:
            con = self.db.connect()
            con.execute("UPDATE stack_frames SET anchor_file=?, anchor_lo=1,"
                        " anchor_hi=2 WHERE id=?", (str(rel), self.root))
            con.commit()
            con.close()
            out = self.brief(full=True)
            self.assertIn('alpha = 1', out)
        finally:
            real.unlink()

    def test_build_phase_prints_the_ally_doctrine(self):
        con = self.db.connect()
        con.execute("UPDATE meta SET value='BUILD' WHERE key='phase'")
        con.commit()
        con.close()
        self.assertIn('ALLY', self.brief(full=True))


class TestBriefDelta(BriefCase):
    def test_second_brief_with_no_change_is_delta_none(self):
        self.brief()
        out = self.brief()
        self.assertIn('Δ none', out)
        self.assertNotIn('ANCHOR', out)

    def test_a_state_change_reprints(self):
        self.brief()
        con = self.db.connect()
        self.stack.set_rung(con, self.root, 'predict', 'HIT')
        con.close()
        out = self.brief()
        self.assertNotIn('Δ none', out)
        self.assertIn('predict=HIT', out)

    def test_full_always_reprints(self):
        self.brief()
        self.assertNotIn('Δ none', self.brief(full=True))


class TestRouterIsNoLongerARegistry(unittest.TestCase):
    def test_seed_constants_are_gone(self):
        import router
        for gone in ('GAP_TYPES', 'ANGLES', 'FORM_QUESTIONS', 'BUCKET_KEYS',
                     'seed_registry', 'compute_slice', 'render_slice'):
            self.assertFalse(hasattr(router, gone),
                             f"router.{gone} must be gone — the DB is the source")

    def test_render_returns_the_delta_brief(self):
        import router
        state = {'phase': 'DRILL', 'mode': 'ADVERSARY', 'path': ['uuid'],
                 'slug': 'uuid', 'depth': 0, 'anchor_file': 'f.py',
                 'anchor_lo': 1, 'anchor_hi': 1, 'anchor_text': 'x = 1',
                 'rungs': {}, 'pending': [], 'hop_budget': 2, 'resume_q': None}
        first = router.render(dict(state, last_sig=None))
        self.assertIn('uuid', first)
        same = router.render(dict(state, last_sig=router.signature(state)))
        self.assertEqual(same.strip(), 'Δ none')


if __name__ == '__main__':
    unittest.main()
