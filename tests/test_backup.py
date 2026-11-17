import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import sys
from pathlib import Path as _P
ROOT = _P(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import backup as backup_mod


class BackupTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.src_db = self.tmp_path / 'sumber.db'
        self._buat_db_sumber(self.src_db)
        self.backup_dir = self.tmp_path / 'backups'
        self.restore_dir = self.tmp_path / 'restore'

    def tearDown(self):
        self.tmp.cleanup()

    def _buat_db_sumber(self, path):
        con = sqlite3.connect(str(path))
        try:
            con.execute('CREATE TABLE jurnal (id INTEGER PRIMARY KEY, tanggal TEXT, nis TEXT, poin INTEGER)')
            con.execute("INSERT INTO jurnal (tanggal, nis, poin) VALUES ('2026-07-20','12403',-50)")
            con.execute("INSERT INTO jurnal (tanggal, nis, poin) VALUES ('2026-08-13','13069',100)")
            con.commit()
        finally:
            con.close()

    def test_backup_membuat_berkas_dan_integritas_ok(self):
        berkas, dihapus = backup_mod.backup_db(db_path=self.src_db, backup_dir=self.backup_dir, keep=14)
        self.assertTrue(berkas.exists())
        self.assertTrue(backup_mod.integritas_db(berkas))
        self.assertEqual(dihapus, [])

    def test_backup_nama_berstempel_waktu(self):
        berkas, _ = backup_mod.backup_db(db_path=self.src_db, backup_dir=self.backup_dir, keep=14)
        self.assertTrue(berkas.name.startswith('disiplin-'))
        self.assertTrue(berkas.name.endswith('.db'))

    def test_rotasi_menghapus_cadangan_lama(self):
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        berkas_buatan = []
        for i in range(5):
            b = self.backup_dir / f'disiplin-2026010{i}-000000.db'
            b.write_bytes(b'')
            berkas_buatan.append(b)
        for idx, b in enumerate(berkas_buatan):
            # atur mtime semakin tua seiring indeks
            epoch = 1_700_000_000 + idx * 100
            os.utime(b, (epoch, epoch))
        dihapus = backup_mod.rotasi_backup(backup_dir=self.backup_dir, keep=2)
        sisa = sorted(p.name for p in self.backup_dir.glob('disiplin-*.db'))
        self.assertEqual(len(sisa), 2)
        self.assertEqual(len(dihapus), 3)

    def test_restore_ke_db_baru(self):
        berkas, _ = backup_mod.backup_db(db_path=self.src_db, backup_dir=self.backup_dir, keep=14)
        db_tujuan = self.restore_dir / 'tujuan.db'
        self.restore_dir.mkdir(parents=True, exist_ok=True)
        pre, ok = backup_mod.restore_db(berkas, db_path=db_tujuan, confirmed=True)
        self.assertTrue(ok)
        self.assertTrue(db_tujuan.exists())
        self.assertTrue(backup_mod.integritas_db(db_tujuan))
        # data utuh
        con = sqlite3.connect(str(db_tujuan))
        try:
            n = con.execute('SELECT COUNT(*) FROM jurnal').fetchone()[0]
        finally:
            con.close()
        self.assertEqual(n, 2)

    def test_restore_membuat_cadangan_pra_restore(self):
        berkas, _ = backup_mod.backup_db(db_path=self.src_db, backup_dir=self.backup_dir, keep=14)
        db_tujuan = self.restore_dir / 'tujuan.db'
        self.restore_dir.mkdir(parents=True, exist_ok=True)
        # salin sumber sebagai db saat ini
        shutil.copy2(self.src_db, db_tujuan)
        pre, ok = backup_mod.restore_db(berkas, db_path=db_tujuan, confirmed=True)
        self.assertTrue(ok)
        self.assertIsNotNone(pre)
        self.assertTrue(pre.exists())
        self.assertTrue(pre.name.startswith('disiplin-prerestore-'))

    def test_restore_tanpa_konfirmasi_ditolak(self):
        berkas, _ = backup_mod.backup_db(db_path=self.src_db, backup_dir=self.backup_dir, keep=14)
        with self.assertRaises(ValueError):
            backup_mod.restore_db(berkas, confirmed=False)

    def test_integritas_db_tidak_ada_file(self):
        self.assertFalse(backup_mod.integritas_db(self.tmp_path / 'tidakada.db'))

    def test_restore_backup_korup_db_asli_tetap_utuh(self):
        db_tujuan = self.restore_dir / 'tujuan.db'
        self.restore_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.src_db, db_tujuan)
        korup = self.tmp_path / 'korup.db'
        korup.write_bytes(b'bukan database sqlite')
        with self.assertRaises(RuntimeError):
            backup_mod.restore_db(korup, db_path=db_tujuan, confirmed=True)
        con = sqlite3.connect(str(db_tujuan))
        try:
            n = con.execute('SELECT COUNT(*) FROM jurnal').fetchone()[0]
        finally:
            con.close()
        self.assertEqual(n, 2)
        self.assertFalse((db_tujuan.parent / 'tujuan.db.restore-tmp').exists())

    def test_restore_gagal_saat_db_terkunci(self):
        from unittest import mock
        berkas, _ = backup_mod.backup_db(db_path=self.src_db, backup_dir=self.backup_dir, keep=14)
        db_tujuan = self.restore_dir / 'tujuan.db'
        self.restore_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.src_db, db_tujuan)
        with mock.patch('core.backup.os.replace', side_effect=PermissionError('terkunci')):
            with self.assertRaises(RuntimeError) as ctx:
                backup_mod.restore_db(berkas, db_path=db_tujuan, confirmed=True)
        self.assertIn('Database sedang dipakai', str(ctx.exception))
        self.assertFalse((db_tujuan.parent / 'tujuan.db.restore-tmp').exists())
        self.assertTrue(backup_mod.integritas_db(db_tujuan))

    def test_restore_dari_folder_lain_dan_db_path_lain(self):
        sumber_lain = self.tmp_path / 'lain' / 'sumber.db'
        sumber_lain.parent.mkdir(parents=True, exist_ok=True)
        self._buat_db_sumber(sumber_lain)
        berkas, _ = backup_mod.backup_db(db_path=sumber_lain, backup_dir=self.backup_dir, keep=14)
        db_tujuan = self.tmp_path / 'hasil' / 'target.db'
        db_tujuan.parent.mkdir(parents=True, exist_ok=True)
        pre, ok = backup_mod.restore_db(berkas, db_path=db_tujuan, confirmed=True)
        self.assertTrue(ok)
        self.assertTrue(backup_mod.integritas_db(db_tujuan))
        con = sqlite3.connect(str(db_tujuan))
        try:
            n = con.execute('SELECT COUNT(*) FROM jurnal').fetchone()[0]
        finally:
            con.close()
        self.assertEqual(n, 2)


if __name__ == '__main__':
    unittest.main()
