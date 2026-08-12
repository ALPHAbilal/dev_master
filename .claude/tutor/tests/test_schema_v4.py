"""Task 1: the v4 schema. New tables, widened probes, version stamp."""
import sqlite3
import sys
import unittest
from pathlib import Path

TUTOR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TUTOR))


def fresh_db():
    con = sqlite3.connect(':memory:')
    con.executescript((TUTOR / 'schema.sql').read_text(encoding='utf-8'))
    return con


def tables(con):
    return {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def cols(con, table):
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


class TestSchemaV4(unittest.TestCase):
    def test_new_tables_exist(self):
        con = fresh_db()
        self.assertLessEqual({'stack_frames', 'vocab', 'utterances'}, tables(con))

    def test_probes_gains_five_columns(self):
        con = fresh_db()
        self.assertLessEqual({'rung', 'hole_kind', 'terms', 'question', 'answer'},
                             cols(con, 'probes'))

    def test_schema_version_is_4(self):
        con = fresh_db()
        v = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        self.assertIsNotNone(v, "schema.sql must stamp meta.schema_version")
        self.assertEqual(v[0], '4')

    def test_stack_frames_shape(self):
        con = fresh_db()
        self.assertLessEqual(
            {'id', 'project_id', 'slug', 'depth', 'parent_id', 'why', 'anchor_file',
             'anchor_lo', 'anchor_hi', 'resume_q', 'rungs', 'pending', 'state',
             'hop_budget', 'opened_at', 'closed_at'},
            cols(con, 'stack_frames'))

    def test_concepts_accepts_source_hole(self):
        con = fresh_db()
        con.execute("INSERT INTO concepts(slug,name,definition,category,depth,source)"
                    " VALUES ('x','X','x','language',1,'hole')")
        self.assertEqual(
            con.execute("SELECT source FROM concepts WHERE slug='x'").fetchone()[0],
            'hole')


class TestMigrateV4(unittest.TestCase):
    """migrate_v4 must be re-runnable against a v3 database."""

    def v3_db(self, path):
        con = sqlite3.connect(path)
        con.executescript((TUTOR / 'schema.sql').read_text(encoding='utf-8'))
        # rewind to a v3 shape: drop the v4 columns/tables schema.sql now creates
        for t in ('stack_frames', 'vocab', 'utterances'):
            con.execute(f"DROP TABLE IF EXISTS {t}")
        con.execute("DROP TABLE IF EXISTS probes")
        con.execute("""CREATE TABLE probes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL, concept_id INTEGER,
            phase TEXT NOT NULL, faculty TEXT NOT NULL DEFAULT 'write',
            depth_below INTEGER NOT NULL DEFAULT 0,
            question TEXT NOT NULL, answer TEXT, result TEXT NOT NULL,
            error_class TEXT, seconds INTEGER,
            clock TEXT NOT NULL DEFAULT 'unmeasured', asked_at TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER,
            slug TEXT NOT NULL, hole TEXT NOT NULL, gap_type TEXT,
            demonstrated INTEGER, angle TEXT, angle_result TEXT,
            evidence TEXT NOT NULL, ts TEXT NOT NULL)""")
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','2')")
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('phase','FLOOR')")
        con.execute("INSERT INTO sessions(started_at) VALUES ('t')")
        con.execute("INSERT INTO probes(session_id,phase,faculty,question,result,"
                    "asked_at) VALUES (1,'DRILL','read','q?','HIT','t')")
        con.execute("INSERT INTO assessments(session_id,slug,hole,gap_type,evidence,ts)"
                    " VALUES (1,'uuid','explicit','model','he said idk','t')")
        con.commit()
        return con

    def test_migration_is_idempotent_and_moves_assessments(self):
        import tempfile
        import migrate_v4
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'v3.db'
            self.v3_db(str(p)).close()
            migrate_v4.migrate(str(p))
            migrate_v4.migrate(str(p))          # re-run must not explode
            con = sqlite3.connect(str(p))
            self.assertLessEqual({'rung', 'hole_kind', 'terms'}, cols(con, 'probes'))
            self.assertNotIn('assessments', tables(con))
            self.assertNotIn('angles', tables(con))
            self.assertEqual(
                con.execute("SELECT value FROM meta WHERE key='schema_version'")
                   .fetchone()[0], '4')
            # the v3 probe kept its faculty, backfilled into rung
            self.assertEqual(
                con.execute("SELECT rung FROM probes WHERE question='q?'")
                   .fetchone()[0], 'read')
            # the assessment became a probe
            row = con.execute("SELECT hole_kind, answer FROM probes WHERE "
                              "hole_kind='model'").fetchone()
            self.assertEqual(row[1], 'he said idk')

    def test_phase_names_migrate(self):
        import tempfile
        import migrate_v4
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'v3.db'
            self.v3_db(str(p)).close()
            migrate_v4.migrate(str(p))
            con = sqlite3.connect(str(p))
            self.assertEqual(
                con.execute("SELECT value FROM meta WHERE key='phase'").fetchone()[0],
                'SCAN')


if __name__ == '__main__':
    unittest.main()
