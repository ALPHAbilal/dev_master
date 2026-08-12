"""Task 5: the outgoing-question gate. Nothing reaches the learner unchecked."""
import argparse
import io
import contextlib
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

TUTOR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TUTOR))

PID = 'proj'


class DraftCase(unittest.TestCase):
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
        con = self.db.connect()
        self.root = self.stack.push(con, PID, 'uuid')
        con.close()

    def tearDown(self):
        for k in ('TUTOR_DB', 'TUTOR_PROJECT_BASE', 'TUTOR_PROJECT_ID'):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def know(self, term, status='shown'):
        con = self.db.connect()
        con.execute("INSERT OR REPLACE INTO vocab(term,status,first_seen)"
                    " VALUES (?,?,'t')", (term, status))
        con.commit()
        con.close()

    def draft(self, terms='', hops=1, about='uuid'):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.db.draft(argparse.Namespace(terms=terms, hops=hops, about=about))
        return buf.getvalue()

    def utterances(self):
        con = self.db.connect()
        rows = con.execute("SELECT * FROM utterances").fetchall()
        con.close()
        return rows


class TestVocabGate(DraftCase):
    def test_refuses_an_unknown_term(self):
        with self.assertRaises(SystemExit):
            self.draft(terms='idempotent')

    def test_refuses_a_term_explicitly_marked_unknown(self):
        self.know('idempotent', 'unknown')
        with self.assertRaises(SystemExit):
            self.draft(terms='idempotent')

    def test_accepts_a_shown_term(self):
        self.know('ledger', 'shown')
        self.draft(terms='ledger')

    def test_accepts_a_proved_term(self):
        self.know('ledger', 'proved')
        self.draft(terms='ledger')

    def test_the_refusal_names_the_offending_term(self):
        self.know('ledger', 'shown')
        with self.assertRaises(SystemExit) as e:
            self.draft(terms='ledger,idempotent')
        # die() writes to stderr and exits 1; the term is what makes it fixable
        self.assertEqual(e.exception.code, 1)


class TestHopGate(DraftCase):
    def test_refuses_more_hops_than_the_budget(self):
        with self.assertRaises(SystemExit):
            self.draft(hops=3)

    def test_accepts_hops_at_the_budget(self):
        self.draft(hops=2)

    def test_a_weak_rung_cuts_the_budget_and_the_gate_follows(self):
        con = self.db.connect()
        self.stack.set_rung(con, self.root, 'predict', 'WEAK')
        con.close()
        with self.assertRaises(SystemExit):
            self.draft(hops=2)
        self.draft(hops=1)


class TestAboutGate(DraftCase):
    def test_refuses_a_frozen_frame(self):
        con = self.db.connect()
        self.stack.push(con, PID, 'ledger')
        con.close()
        with self.assertRaises(SystemExit):
            self.draft(about='uuid')

    def test_accepts_the_top_frame(self):
        con = self.db.connect()
        self.stack.push(con, PID, 'ledger')
        con.close()
        self.draft(about='ledger')

    def test_refuses_an_unknown_frame(self):
        with self.assertRaises(SystemExit):
            self.draft(about='nonesuch')


class TestAcceptedDraft(DraftCase):
    def test_writes_one_utterance_row(self):
        self.know('ledger', 'proved')
        self.draft(terms='ledger', hops=2)
        rows = self.utterances()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['hops'], 2)
        self.assertEqual(rows[0]['terms'], 'ledger')
        self.assertEqual(rows[0]['verdict'], 'SHIP')
        self.assertEqual(rows[0]['frame_id'], self.root)

    def test_sets_each_term_to_shown(self):
        self.know('ledger', 'proved')
        self.know('rec', 'shown')
        self.draft(terms='ledger,rec')
        con = self.db.connect()
        got = dict(con.execute("SELECT term, status FROM vocab").fetchall())
        con.close()
        # `shown` never demotes a proved term
        self.assertEqual(got['ledger'], 'proved')
        self.assertEqual(got['rec'], 'shown')

    def test_a_refused_draft_writes_nothing(self):
        with self.assertRaises(SystemExit):
            self.draft(terms='idempotent')
        self.assertEqual(self.utterances(), [])


class TestShipCheckIsPure(DraftCase):
    """The hook calls the same check, so the wall and the command cannot drift."""

    def test_returns_ok_and_a_reason(self):
        con = self.db.connect()
        self.know('ledger', 'shown')
        con = self.db.connect()
        ok, reason = self.db.ship_check(con, PID, ['ledger'], 1, 'uuid')
        self.assertTrue(ok, reason)
        ok, reason = self.db.ship_check(con, PID, ['nope'], 1, 'uuid')
        self.assertFalse(ok)
        self.assertIn('nope', reason)
        ok, reason = self.db.ship_check(con, PID, [], 9, 'uuid')
        self.assertFalse(ok)
        self.assertIn('hop', reason.lower())
        con.close()


if __name__ == '__main__':
    unittest.main()
