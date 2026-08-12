import sqlite3
import sys
import unittest
from pathlib import Path

TUTOR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TUTOR))

import router  # noqa: E402


def fresh_db():
    conn = sqlite3.connect(':memory:')
    conn.executescript((TUTOR / 'schema.sql').read_text())
    return conn


class TestSeed(unittest.TestCase):
    def test_seed_populates_registry(self):
        conn = fresh_db()
        router.seed_registry(conn)
        gaps = {r[0] for r in conn.execute("SELECT slug FROM gap_types")}
        self.assertEqual(gaps, {'model', 'reason', 'application', 'tradeoff'})
        angles = [r[0] for r in conn.execute("SELECT slug FROM angles ORDER BY ord")]
        self.assertEqual(angles, ['mechanical', 'practical', 'reasoning'])
        self.assertGreaterEqual(
            conn.execute("SELECT COUNT(*) FROM form_questions").fetchone()[0], 4)
        self.assertGreaterEqual(
            conn.execute("SELECT COUNT(*) FROM bucket_keys").fetchone()[0], 6)

    def test_seed_is_idempotent(self):
        conn = fresh_db()
        router.seed_registry(conn)
        router.seed_registry(conn)
        n = conn.execute("SELECT COUNT(*) FROM gap_types").fetchone()[0]
        self.assertEqual(n, 4)


def _registry(conn=None):
    conn = conn or fresh_db()
    router.seed_registry(conn)
    return router.load_registry(conn)


def _state(**over):
    base = {'phase': 'READ', 'slug': 'uuid', 'has_context': True,
            'open_gaps': [], 'angle_results': {}, 'current_angle': None,
            'open_misconceptions': 0}
    base.update(over)
    return base


class TestConditions(unittest.TestCase):
    def test_always(self):
        self.assertTrue(router.matches({'always': True}, _state()))

    def test_and_semantics(self):
        cond = {'has_context': True, 'open_gaps_min': 1}
        self.assertFalse(router.matches(cond, _state(open_gaps=[])))
        self.assertTrue(router.matches(cond, _state(open_gaps=['model'])))

    def test_current_angle_and_misconceptions(self):
        self.assertFalse(router.matches({'current_angle': True}, _state()))
        self.assertTrue(router.matches({'current_angle': True},
                                       _state(current_angle='mechanical')))
        self.assertTrue(router.matches({'open_misconceptions_min': 1},
                                       _state(open_misconceptions=2)))


class TestComputeSlice(unittest.TestCase):
    def setUp(self):
        self.reg = _registry()

    def test_questions_filtered_by_state(self):
        s = router.compute_slice(_state(), self.reg)
        slugs = [q['slug'] for q in s['questions']]
        self.assertIn('assess-hole', slugs)
        self.assertNotIn('assess-angle-result', slugs)   # no current angle
        self.assertNotIn('assess-misconception', slugs)  # none open
        s2 = router.compute_slice(_state(current_angle='practical',
                                         open_misconceptions=1), self.reg)
        slugs2 = [q['slug'] for q in s2['questions']]
        self.assertIn('assess-angle-result', slugs2)
        self.assertIn('assess-misconception', slugs2)

    def test_keys_filtered_by_context(self):
        names = [k['name'] for k in
                 router.compute_slice(_state(has_context=False), self.reg)['keys']]
        self.assertIn('primary_concept', names)
        self.assertNotIn('context.gaps', names)
        names2 = [k['name'] for k in router.compute_slice(_state(), self.reg)['keys']]
        self.assertIn('context.gaps', names2)

    def test_next_move_priorities(self):
        # 1. no context yet -> init + first angle
        m = router.compute_slice(_state(has_context=False), self.reg)['next_move']
        self.assertIn('mechanical', m)
        # 2. open gap outranks unexplored angles
        m = router.compute_slice(_state(open_gaps=['reason'],
                                        angle_results={'mechanical': 'pass'}),
                                 self.reg)['next_move']
        self.assertIn("gap 'reason'", m)
        # 3. no gaps -> next unexplored angle
        m = router.compute_slice(_state(angle_results={'mechanical': 'pass'}),
                                 self.reg)['next_move']
        self.assertIn("'practical'", m)
        # 4. failed angle must be re-taught before pass
        m = router.compute_slice(
            _state(angle_results={'mechanical': 'pass', 'practical': 'fail',
                                  'reasoning': 'pass'}), self.reg)['next_move']
        self.assertIn("'practical'", m)
        # 5. everything pass, nothing open -> concept-pass
        m = router.compute_slice(
            _state(angle_results={'mechanical': 'pass', 'practical': 'pass',
                                  'reasoning': 'pass'}), self.reg)['next_move']
        self.assertIn('concept-pass uuid', m)

    def test_render_is_plain_text(self):
        text = router.render_slice(router.compute_slice(_state(), self.reg))
        self.assertIn('NEXT MOVE', text)
        self.assertIn('assess-hole', text)


if __name__ == '__main__':
    unittest.main()
