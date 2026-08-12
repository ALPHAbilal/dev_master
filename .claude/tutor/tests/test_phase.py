"""Task 2: one phase variable. meta.phase, and nothing else, decides the file."""
import sqlite3
import sys
import unittest
from pathlib import Path

TUTOR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TUTOR))

import tutor_hook  # noqa: E402


def db_with_phase(value):
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript((TUTOR / 'schema.sql').read_text(encoding='utf-8'))
    if value is not None:
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('phase',?)",
                    (value,))
    else:
        con.execute("DELETE FROM meta WHERE key='phase'")
    return con


class TestCurrentPhase(unittest.TestCase):
    def test_reads_meta_phase(self):
        self.assertEqual(tutor_hook.current_phase(db_with_phase('DRILL')), 'DRILL')

    def test_drill_points_at_its_file(self):
        con = db_with_phase('DRILL')
        self.assertEqual(tutor_hook.PHASE_FILE[tutor_hook.current_phase(con)],
                         'phases/03-drill.md')

    def test_unknown_phase_falls_back_to_scan_without_raising(self):
        self.assertEqual(tutor_hook.current_phase(db_with_phase('BUILD_V1')), 'SCAN')
        self.assertEqual(tutor_hook.current_phase(db_with_phase('')), 'SCAN')

    def test_missing_phase_row_falls_back_to_scan(self):
        self.assertEqual(tutor_hook.current_phase(db_with_phase(None)), 'SCAN')

    def test_every_phase_has_a_file_and_a_mode(self):
        self.assertEqual(set(tutor_hook.PHASE_FILE), set(tutor_hook.MODE))
        self.assertEqual(set(tutor_hook.PHASE_FILE),
                         {'SCAN', 'READ', 'DRILL', 'ASSEMBLE', 'BUILD', 'SOLO'})
        self.assertEqual(tutor_hook.MODE['BUILD'], 'ALLY')
        self.assertTrue(all(m == 'ADVERSARY' for p, m in tutor_hook.MODE.items()
                            if p != 'BUILD'))

    def test_phase_no_longer_comes_from_targets(self):
        """targets.phase and targets.unlock_gate must not decide routing."""
        src = (TUTOR / 'tutor_hook.py').read_text(encoding='utf-8')
        self.assertNotIn('PHASE_SEQUENCE', src)
        self.assertNotIn('next_phase', src)
        self.assertNotIn("t['unlock_gate']", src)


class TestPhaseGateState(unittest.TestCase):
    def test_state_file_carries_no_phase_copy(self):
        """.phase_gate.json is {session_id, expected, read} only — a second copy
        of the phase is a second thing that can be wrong."""
        import inspect
        src = inspect.getsource(tutor_hook.cmd_phase_guard)
        self.assertNotIn("'phase': phase", src)


if __name__ == '__main__':
    unittest.main()
