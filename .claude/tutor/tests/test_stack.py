"""Task 3: the stack. Holes nest, so FOCUS is a stack and only the top teaches."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

TUTOR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TUTOR))

import stack  # noqa: E402

PID = 'proj'


def fresh():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript((TUTOR / 'schema.sql').read_text(encoding='utf-8'))
    return con


def all_hit(con, fid):
    for r in stack.RUNGS:
        stack.set_rung(con, fid, r, 'HIT')


class TestPush(unittest.TestCase):
    def test_push_twice_deeper_frame_is_top_and_parent_freezes(self):
        con = fresh()
        a = stack.push(con, PID, 'uuid', why='the anchor',
                       anchor=('run_prompts.py', 469, 486))
        b = stack.push(con, PID, 'ledger', why='blocked on uuid',
                       resume_q='what does uuid4 give you?')
        top = stack.top(con, PID)
        self.assertEqual(top['id'], b)
        self.assertEqual(top['slug'], 'ledger')
        self.assertEqual(top['depth'], 1)
        self.assertEqual(top['parent_id'], a)
        parent = stack.frame(con, a)
        self.assertEqual(parent['state'], 'FROZEN')

    def test_child_inherits_the_parent_anchor_file_and_lines(self):
        """A hole found in those lines is taught FROM those lines. Inheriting
        the file without the range printed `file:None-None` and no code."""
        con = fresh()
        stack.push(con, PID, 'uuid', anchor=('run_prompts.py', 469, 486))
        b = stack.frame(con, stack.push(con, PID, 'ledger'))
        self.assertEqual(b['anchor_file'], 'run_prompts.py')
        self.assertEqual((b['anchor_lo'], b['anchor_hi']), (469, 486))

    def test_an_explicit_child_anchor_wins_over_inheritance(self):
        con = fresh()
        stack.push(con, PID, 'uuid', anchor=('run_prompts.py', 469, 486))
        b = stack.frame(con, stack.push(con, PID, 'ledger',
                                        anchor=('other.py', 1, 5)))
        self.assertEqual((b['anchor_file'], b['anchor_lo'], b['anchor_hi']),
                         ('other.py', 1, 5))

    def test_push_stores_the_interrupted_question_as_resume_q(self):
        con = fresh()
        stack.push(con, PID, 'uuid')
        b = stack.push(con, PID, 'ledger', resume_q='what does uuid4 give you?')
        self.assertEqual(stack.frame(con, b)['resume_q'],
                         'what does uuid4 give you?')

    def test_path_is_root_to_top(self):
        con = fresh()
        stack.push(con, PID, 'uuid')
        stack.push(con, PID, 'ledger')
        stack.push(con, PID, 'pathlib')
        self.assertEqual(stack.path(con, PID), ['uuid', 'ledger', 'pathlib'])


class TestPop(unittest.TestCase):
    def test_pop_refuses_while_a_rung_is_not_hit(self):
        con = fresh()
        f = stack.push(con, PID, 'uuid')
        stack.set_rung(con, f, 'predict', 'HIT')
        with self.assertRaises(stack.StackRefusal) as e:
            stack.pop(con, f)
        msg = str(e.exception)
        self.assertIn('perturb', msg)
        self.assertIn('produce', msg)
        self.assertIn('transfer', msg)
        self.assertNotIn('predict', msg)

    def test_clean_pop_thaws_the_parent_and_returns_resume_q(self):
        con = fresh()
        with tempfile.TemporaryDirectory() as d:
            a = stack.push(con, PID, 'uuid')
            b = stack.push(con, PID, 'ledger', resume_q='what does uuid4 give you?')
            all_hit(con, b)
            q = stack.pop(con, b, base=d)
            self.assertEqual(q, 'what does uuid4 give you?')
            self.assertEqual(stack.frame(con, b)['state'], 'PASSED')
            self.assertEqual(stack.frame(con, a)['state'], 'ACTIVE')
            self.assertEqual(stack.top(con, PID)['id'], a)

    def test_clean_pop_writes_the_frame_to_passed_context(self):
        con = fresh()
        with tempfile.TemporaryDirectory() as d:
            f = stack.push(con, PID, 'uuid', why='the anchor')
            all_hit(con, f)
            stack.pop(con, f, base=d)
            files = list((Path(d) / 'passed_context').glob('uuid_*.json'))
            self.assertEqual(len(files), 1)
            blob = json.loads(files[0].read_text())
            self.assertEqual(blob['slug'], 'uuid')
            self.assertEqual(blob['rungs']['predict'], 'HIT')

    def test_pop_refuses_while_pending_is_non_empty(self):
        con = fresh()
        f = stack.push(con, PID, 'uuid')
        all_hit(con, f)
        stack.queue_pending(con, f, ['ledger', 'pathlib'])
        with self.assertRaises(stack.StackRefusal) as e:
            stack.pop(con, f)
        self.assertIn('ledger', str(e.exception))
        self.assertIn('pathlib', str(e.exception))

    def test_popping_a_frozen_frame_is_refused(self):
        con = fresh()
        a = stack.push(con, PID, 'uuid')
        stack.push(con, PID, 'ledger')
        all_hit(con, a)
        with self.assertRaises(stack.StackRefusal):
            stack.pop(con, a)


class TestPending(unittest.TestCase):
    def test_queue_pending_dedupes(self):
        con = fresh()
        f = stack.push(con, PID, 'uuid')
        stack.queue_pending(con, f, ['ledger', 'pathlib'])
        stack.queue_pending(con, f, ['ledger', 'json'])
        self.assertEqual(stack.pending(con, f), ['ledger', 'pathlib', 'json'])

    def test_take_pending_removes_it(self):
        con = fresh()
        f = stack.push(con, PID, 'uuid')
        stack.queue_pending(con, f, ['ledger'])
        stack.take_pending(con, f, 'ledger')
        self.assertEqual(stack.pending(con, f), [])


class TestRungs(unittest.TestCase):
    def test_two_weak_on_one_rung_becomes_miss(self):
        con = fresh()
        f = stack.push(con, PID, 'uuid')
        stack.set_rung(con, f, 'predict', 'WEAK')
        self.assertEqual(stack.rungs(con, f)['predict'], 'WEAK')
        stack.set_rung(con, f, 'predict', 'WEAK')
        self.assertEqual(stack.rungs(con, f)['predict'], 'MISS')

    def test_weak_cuts_the_hop_budget_to_one(self):
        con = fresh()
        f = stack.push(con, PID, 'uuid')
        self.assertEqual(stack.frame(con, f)['hop_budget'], 2)
        stack.set_rung(con, f, 'predict', 'WEAK')
        self.assertEqual(stack.frame(con, f)['hop_budget'], 1)

    def test_unknown_rung_is_refused(self):
        con = fresh()
        f = stack.push(con, PID, 'uuid')
        with self.assertRaises(stack.StackRefusal):
            stack.set_rung(con, f, 'vibes', 'HIT')

    def test_unknown_result_is_refused(self):
        con = fresh()
        f = stack.push(con, PID, 'uuid')
        with self.assertRaises(stack.StackRefusal):
            stack.set_rung(con, f, 'predict', 'GREAT')


if __name__ == '__main__':
    unittest.main()
