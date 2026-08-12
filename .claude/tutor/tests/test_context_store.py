import sys
import tempfile
import unittest
from pathlib import Path

TUTOR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TUTOR))

import context_store as cs  # noqa: E402


class TestContextStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_and_has_context(self):
        self.assertFalse(cs.has_context(self.base, 'uuid'))
        cs.init_context(self.base, 'uuid')
        self.assertTrue(cs.has_context(self.base, 'uuid'))
        ctx = cs.read_context(self.base, 'uuid')
        self.assertEqual(ctx, {'gaps': [], 'angles': [], 'log': []})

    def test_gap_open_dedup_and_close(self):
        cs.init_context(self.base, 'uuid')
        cs.open_gap(self.base, 'uuid', 'model', "said uuid4 makes 12 chars")
        cs.open_gap(self.base, 'uuid', 'model', "did not know .hex output")
        ctx = cs.read_context(self.base, 'uuid')
        self.assertEqual(len(ctx['gaps']), 1)          # deduped, evidence merged
        self.assertIn('.hex', ctx['gaps'][0]['evidence'])
        self.assertEqual(cs.open_gaps(ctx), ['model'])
        self.assertTrue(cs.close_gap(self.base, 'uuid', 'model', "predicted hex output correctly"))
        ctx = cs.read_context(self.base, 'uuid')
        self.assertEqual(cs.open_gaps(ctx), [])
        self.assertFalse(cs.close_gap(self.base, 'uuid', 'model', "again"))

    def test_angle_results_latest_wins(self):
        cs.init_context(self.base, 'uuid')
        cs.log_angle(self.base, 'uuid', 'mechanical', 'fail')
        cs.log_angle(self.base, 'uuid', 'mechanical', 'pass')
        ctx = cs.read_context(self.base, 'uuid')
        self.assertEqual(cs.angle_results(ctx), {'mechanical': 'pass'})

    def test_pass_refuses_open_gaps_then_relocates(self):
        cs.init_context(self.base, 'uuid')
        cs.open_gap(self.base, 'uuid', 'reason', "no idea why 8 chars")
        with self.assertRaises(RuntimeError):
            cs.pass_concept(self.base, 'uuid')
        cs.close_gap(self.base, 'uuid', 'reason', "explained readability tradeoff unprompted")
        dest = cs.pass_concept(self.base, 'uuid')
        self.assertFalse(cs.has_context(self.base, 'uuid'))
        self.assertTrue(dest.exists())
        self.assertTrue(str(dest).startswith(str(self.base / 'passed_context')))


if __name__ == '__main__':
    unittest.main()
