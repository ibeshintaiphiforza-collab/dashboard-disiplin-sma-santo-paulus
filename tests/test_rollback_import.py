import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core import analytics, db
from core.importer import parse_master_siswa, save_import, save_master_siswa


def _record(nis, id_eguru, tanggal='2024-01-01', kode='ME-01', poin='-5', judul='X', nama='SISWA', kelas='10-A'):
    return {
        'id_eguru': id_eguru, 'timestamp_input': '2024-01-02 08:00:00', 'tanggal_kejadian': tanggal,
        'nis': nis, 'nama_siswa': nama, 'kelas': kelas, 'absen': '01', 'kode_pasal': kode,
        'poin': poin, 'judul': judul, 'keterangan': '', 'petugas': 'OP',
    }


class RollbackImportTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.tmp.name) / 'test.db'
        self.addCleanup(lambda: setattr(db, 'DB_PATH', self.original))
        db.init_db()
        db.load_referensi_pasal()

    def count(self, table, where=None):
        conn = db.get_conn()
        try:
            if where:
                return conn.execute(f'SELECT COUNT(*) FROM {table} WHERE {where}').fetchone()[0]
            return conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        finally:
            conn.close()

    def test_rollback_removes_exactly_last_import_rows(self):
        save_import([_record('12403', 1), _record('13069', 2)], 'a.csv', confirmed=True)
        save_import([_record('13500', 3), _record('12990', 4), _record('12403', 5)], 'b.csv', confirmed=True)
        self.assertEqual(self.count('jurnal'), 5)
        terhapus = analytics.rollback_import_terakhir()
        self.assertEqual(terhapus, 3)
        self.assertEqual(self.count('jurnal'), 2)
        ids = {r[0] for r in db.get_conn().execute('SELECT id FROM jurnal')}
        self.assertEqual(ids, {1, 2})
        self.assertEqual(self.count('import_log', "di_rollback = 1"), 1)

    def test_rollback_does_not_touch_other_imports_or_audit(self):
        save_import([_record('12403', 1)], 'a.csv', confirmed=True)
        save_import([_record('13069', 2)], 'b.csv', confirmed=True)
        analytics.hapus_jurnal([1], confirmed=True)
        self.assertEqual(self.count('jurnal'), 1)
        self.assertEqual(self.count('import_log'), 3)
        analytics.rollback_import_terakhir()
        self.assertEqual(self.count('jurnal'), 0)
        self.assertEqual(self.count('import_log'), 3)
        self.assertEqual(self.count('import_log', "di_rollback = 1"), 1)
        self.assertEqual(self.count('import_log', "nama_file LIKE 'hapus_jurnal:%'"), 1)


if __name__ == '__main__':
    unittest.main()
