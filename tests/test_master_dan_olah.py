import io
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core import analytics, db
from core.export import to_csv_bytes, to_excel_bytes
from core.importer import (MasterSiswaValidator, parse_master_csv, parse_master_siswa,
                           save_import, save_master_siswa)

PASTE_MASTER = (
    '12403\tALESSANDRO WILLIAM HARDIANTO\t12-T1\t01\n'
    '13069\tRUSSELL NICKLAUS\t11-T1\t34\n'
    '13500\tMARIA ANGELINA\t10-5\t07\n'
    '12990\tYOHANES KRISNA\t11-K3\t12\n'
)


class TempDbTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.tmp.name) / 'test.db'
        self.addCleanup(lambda: setattr(db, 'DB_PATH', self.original))
        db.init_db()
        db.load_referensi_pasal()

    def count(self, table):
        conn = db.get_conn()
        try:
            return conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        finally:
            conn.close()


class MasterParserTestCase(TempDbTestCase):
    def test_paste_parses_all_rows_with_correct_fields(self):
        records = parse_master_siswa(PASTE_MASTER)
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0], {'nis': '12403', 'nama': 'ALESSANDRO WILLIAM HARDIANTO',
                                      'kelas': '12-T1', 'absen': '01'})
        self.assertEqual(records[1]['nis'], '13069')
        self.assertEqual(records[3]['kelas'], '11-K3')

    def test_malformed_and_empty_paste_raise(self):
        with self.assertRaises(ValueError):
            parse_master_siswa(PASTE_MASTER + 'baris rusak tanpa struktur\n')
        with self.assertRaises(ValueError):
            parse_master_siswa('12403\tNAMA\t12-T1\n')
        with self.assertRaises(ValueError):
            parse_master_siswa('')
        with self.assertRaises(ValueError):
            parse_master_siswa('   \n\n')

    def test_csv_parsed_and_missing_columns_rejected(self):
        content = b'nis,nama,kelas,absen\n12403,ALESSANDRO,12-T1,01\n'
        records = parse_master_csv(content)
        self.assertEqual(records, [{'nis': '12403', 'nama': 'ALESSANDRO', 'kelas': '12-T1', 'absen': '01'}])
        with self.assertRaises(ValueError):
            parse_master_csv(b'nis,nama\n1,2\n')
        with self.assertRaises(ValueError):
            parse_master_csv(b'nis,nama,kelas,absen\n')

    def test_validation_rejects_bad_nis_kelas_absen(self):
        validator = MasterSiswaValidator()
        base = {'nis': '12403', 'nama': 'ALESSANDRO', 'kelas': '12-T1', 'absen': '01'}
        cases = {'nis': '12a', 'kelas': 'XII T1', 'absen': '1', 'nama': ''}
        for field, value in cases.items():
            with self.subTest(field=field):
                errors, _ = validator.validate_record(dict(base, **{field: value}))
                self.assertTrue(errors)
        for field, value in [('nis', '123'), ('nis', '123456'), ('kelas', '13-T1'), ('absen', '001')]:
            with self.subTest(field=field, value=value):
                errors, _ = validator.validate_record(dict(base, **{field: value}))
                self.assertTrue(errors)
        errors, warnings = validator.validate_record(base)
        self.assertEqual((errors, warnings), ([], []))
        normalized, errors, _ = validator.normalize_record(dict(base, nama='alessandro'))
        self.assertEqual((normalized['nama'], errors), ('ALESSANDRO', []))


class MasterSaveTestCase(TempDbTestCase):
    def test_save_requires_confirmation_and_is_transactional(self):
        records = parse_master_siswa(PASTE_MASTER)
        with self.assertRaises(ValueError):
            save_master_siswa(records, 'paste', confirmed=False)
        self.assertEqual(self.count('siswa'), 0)
        broken = records[:2] + [dict(records[2], nis='abc')]
        with self.assertRaises(ValueError):
            save_master_siswa(broken, 'paste', confirmed=True)
        self.assertEqual(self.count('siswa'), 0)
        self.assertEqual(self.count('import_log'), 0)

    def test_resave_with_changed_kelas_updates_without_duplicates(self):
        records = parse_master_siswa(PASTE_MASTER)
        inserted, updated = save_master_siswa(records, 'paste', confirmed=True)
        self.assertEqual((inserted, updated), (4, 0))
        self.assertEqual(self.count('siswa'), 4)
        naik = [dict(row, kelas=row['kelas'].replace('11-', '12-'), absen='05') for row in records]
        inserted, updated = save_master_siswa(naik, 'paste', confirmed=True)
        self.assertEqual((inserted, updated), (0, 4))
        self.assertEqual(self.count('siswa'), 4)
        conn = db.get_conn()
        try:
            row = conn.execute('SELECT kelas, absen, angkatan FROM siswa WHERE nis = ?', ('13069',)).fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ('12-T1', '05', None))
        self.assertEqual(self.count('import_log'), 2)

    def test_absen_column_migration_preserves_existing_rows(self):
        conn = db.get_conn()
        try:
            conn.execute('DROP TABLE siswa')
            conn.execute('CREATE TABLE siswa (nis TEXT PRIMARY KEY, nama TEXT NOT NULL, '
                         'kelas TEXT NOT NULL, angkatan TEXT)')
            conn.execute("INSERT INTO siswa VALUES ('12403','LAMA','12-T1','2023')")
            conn.commit()
        finally:
            conn.close()
        db.init_db()
        conn = db.get_conn()
        try:
            columns = [row[1] for row in conn.execute('PRAGMA table_info(siswa)')]
            rows = conn.execute('SELECT nis, nama, angkatan, absen FROM siswa').fetchall()
        finally:
            conn.close()
        self.assertIn('absen', columns)
        self.assertEqual(rows, [('12403', 'LAMA', '2023', None)])


class AnalyticsTestCase(TempDbTestCase):
    def setUp(self):
        super().setUp()
        save_master_siswa(parse_master_siswa(PASTE_MASTER), 'paste', confirmed=True)
        rows = [
            (1, '2026-07-21 08:00:00', '2026-07-20', '12403', 'ALESSANDRO WILLIAM HARDIANTO', '12-T1 01', 'ME-02', -50, 'terlambat'),
            (2, '2026-07-21 08:00:00', '2026-07-20', '12403', 'ALESSANDRO WILLIAM HARDIANTO', '12-T1 01', 'ME-02', -50, 'terlambat lagi'),
            (3, '2026-07-21 08:00:00', '2026-07-22', '13069', 'RUSSELL NICKLAUS', '11-T1 34', 'ME-02', -40, 'terlambat'),
            (4, None, '2026-07-23', '99999', 'SISWA LUAR MASTER', '10-5 07', 'PA-01', 1800, 'juara'),
            (5, '2026-07-24 09:00:00', '2026-07-24', '13500', 'MARIA ANGELINA', '10-5 07', 'PC-01', 50, 'orang tua terlibat'),
        ]
        conn = db.get_conn()
        try:
            conn.executemany(
                'INSERT INTO jurnal (id,timestamp_input,tanggal_kejadian,nis,nama_siswa,kelas,'
                'kode_pasal,poin,judul,keterangan,petugas,sumber) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                [row + ('ket', 'Petugas A', 'manual') for row in rows])
            conn.commit()
        finally:
            conn.close()
        db.init_db()
        self.jurnal = analytics.load_jurnal()
        self.siswa = analytics.load_siswa()

    def test_filter_by_date_kelas_and_search(self):
        hasil = analytics.filter_jurnal(self.jurnal, '2026-07-20', '2026-07-20')
        self.assertEqual(sorted(hasil['id']), [1, 2])
        hasil = analytics.filter_jurnal(self.jurnal, kelas=['11-T1'])
        self.assertEqual(hasil['id'].tolist(), [3])
        self.assertEqual(hasil['absen'].tolist(), ['34'])
        hasil = analytics.filter_jurnal(self.jurnal, kelas=['10-5'])
        self.assertEqual(sorted(hasil['id']), [4, 5])
        self.assertTrue(analytics.filter_jurnal(self.jurnal, kelas=['11-T1 34']).empty)
        hasil = analytics.filter_jurnal(self.jurnal, pencarian='maria')
        self.assertEqual(hasil['id'].tolist(), [5])
        hasil = analytics.filter_jurnal(self.jurnal, kategori=['prestasi'])
        self.assertEqual(sorted(hasil['id']), [4, 5])
        hasil = analytics.filter_jurnal(self.jurnal, petugas=['Tidak Ada'])
        self.assertTrue(hasil.empty)

    def test_anomaly_detection_returns_expected_rows(self):
        anomali = analytics.deteksi_anomali(self.jurnal, self.siswa)
        self.assertEqual(anomali['poin_beda_default']['id'].tolist(), [3])
        self.assertEqual(anomali['nis_tidak_dikenal']['id'].tolist(), [4])
        self.assertEqual(sorted(anomali['duplikat_kandidat']['id']), [1, 2])
        self.assertEqual(anomali['tanggal_mendahului_input']['id'].tolist(), [1, 2])

    def test_nis_check_skipped_when_master_empty(self):
        kosong = self.siswa.iloc[0:0]
        anomali = analytics.deteksi_anomali(self.jurnal, kosong)
        self.assertTrue(anomali['nis_tidak_dikenal'].empty)

    def test_rekap_totals_and_dukungan_orang_tua_toggle(self):
        rekap = analytics.rekap_per_siswa(self.jurnal, siswa=self.siswa)
        self.assertIn('13500', rekap['nis'].tolist())
        baris = rekap[rekap['nis'] == '12403'].iloc[0]
        self.assertEqual((baris['poin_plus'], baris['poin_minus'], baris['netto'], baris['jumlah_entri']),
                         (0, -100, -100, 2))
        self.assertEqual(baris['nama'], 'ALESSANDRO WILLIAM HARDIANTO')
        self.assertEqual(rekap[rekap['nis'] == '13500'].iloc[0]['netto'], 50)
        kelas = analytics.rekap_per_kelas(self.jurnal)
        self.assertEqual(kelas[kelas['kelas'] == '12-T1'].iloc[0]['netto'], -100)
        self.assertEqual(kelas[kelas['kelas'] == '10-5'].iloc[0]['jumlah_entri'], 2)
        self.assertEqual(sorted(kelas['kelas']), ['10-5', '11-T1', '12-T1'])
        self.assertEqual(baris['kelas'], '12-T1')
        self.assertEqual(baris['absen'], '01')
        sub = analytics.rekap_per_subkategori(self.jurnal).set_index('subkategori')
        self.assertEqual(sub.loc['dukungan_orang_tua', 'jumlah_entri'], 1)
        self.assertEqual(sub.loc['dukungan_orang_tua', 'netto'], 50)
        self.assertEqual(sub.loc['prestasi_akademik', 'netto'], 1800)

    def test_rekap_on_empty_frame_returns_empty_columns(self):
        kosong = self.jurnal.iloc[0:0]
        self.assertTrue(analytics.rekap_per_siswa(kosong).empty)
        self.assertTrue(analytics.rekap_per_kelas(kosong).empty)
        self.assertTrue(analytics.rekap_per_subkategori(kosong).empty)
        self.assertIn('netto', analytics.rekap_per_siswa(kosong).columns)

    def test_delete_requires_confirmation_and_counts(self):
        with self.assertRaises(ValueError):
            analytics.hapus_jurnal([1, 2], confirmed=False)
        self.assertEqual(self.count('jurnal'), 5)
        with self.assertRaises(ValueError):
            analytics.hapus_jurnal([], confirmed=True)
        terhapus = analytics.hapus_jurnal([1, 2], confirmed=True)
        self.assertEqual(terhapus, 2)
        self.assertEqual(self.count('jurnal'), 3)

    def test_hapus_jurnal_tepat_dan_menulis_audit(self):
        terhapus = analytics.hapus_jurnal([3], confirmed=True, user='tester')
        self.assertEqual(terhapus, 1)
        self.assertEqual(self.count('jurnal'), 4)
        conn = db.get_conn()
        try:
            sisa = [r[0] for r in conn.execute('SELECT id FROM jurnal ORDER BY id')]
            audit = conn.execute(
                'SELECT nama_file, jumlah_baris, gagal, user FROM import_log '
                "WHERE nama_file = 'hapus_jurnal:3' ORDER BY waktu DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(sisa, [1, 2, 4, 5])
        self.assertEqual(audit, ('hapus_jurnal:3', 1, 1, 'tester'))


class ExportTestCase(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({'nis': ['12403', '13069'], 'netto': [-100, 50]})

    def test_csv_bytes_non_empty_and_readable(self):
        data = to_csv_bytes(self.df)
        self.assertTrue(data)
        kembali = pd.read_csv(io.BytesIO(data), dtype={'nis': str})
        self.assertEqual(kembali['netto'].tolist(), [-100, 50])

    def test_excel_bytes_non_empty_and_readable(self):
        data = to_excel_bytes(self.df, 'rekap_siswa')
        self.assertTrue(data)
        kembali = pd.read_excel(io.BytesIO(data), dtype={'nis': str})
        self.assertEqual(kembali['nis'].tolist(), ['12403', '13069'])
        self.assertEqual(kembali['netto'].tolist(), [-100, 50])

    def test_excel_handles_empty_frame_and_long_sheet_name(self):
        data = to_excel_bytes(pd.DataFrame(columns=['a']), 'nama_sheet_yang_sangat_panjang_sekali_melebihi_batas')
        self.assertTrue(data)


class StreamlitSmokeTestCase(TempDbTestCase):
    def setUp(self):
        super().setUp()
        from streamlit.testing.v1 import AppTest
        self.AppTest = AppTest

    def test_master_page_paste_preview_and_save_smoke(self):
        app = self.AppTest.from_file(str(ROOT / 'pages' / '5_Master_Siswa.py'), default_timeout=60).run()
        self.assertFalse(app.exception)
        app.text_area[0].set_value(PASTE_MASTER).run()
        app.button(key='btn_preview_master').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('4 record; 0 error' in str(m.value) for m in app.markdown))
        app.checkbox(key='master_confirmed').check().run()
        app.button(key='btn_save_master').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.success)
        self.assertEqual(self.count('siswa'), 4)

    def test_olah_data_page_smoke_without_data(self):
        app = self.AppTest.from_file(str(ROOT / 'pages' / '3_Olah_Data.py'), default_timeout=60).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.warning)

    def test_olah_data_page_smoke_with_data(self):
        save_master_siswa(parse_master_siswa(PASTE_MASTER), 'paste', confirmed=True)
        save_import([{
            'id': '90001', 'timestamp_input': '', 'tanggal_kejadian': '2026-07-20',
            'nis': '12403', 'nama_siswa': 'ALESSANDRO', 'kelas': '12-T1 01', 'kode_pasal': 'ME-02',
            'poin': '', 'judul': 'terlambat', 'keterangan': '', 'petugas': 'Petugas A'
        }], 'csv', confirmed=True)
        app = self.AppTest.from_file(str(ROOT / 'pages' / '3_Olah_Data.py'), default_timeout=60).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.dataframe)
        self.assertTrue(any('1 dari 1 entri jurnal' in str(m.value) for m in app.markdown))
        self.assertEqual(app.multiselect(key='filter_kelas').options, ['12-T1'])
        tabel = app.dataframe[0].value
        self.assertEqual((tabel.iloc[0]['kelas'], tabel.iloc[0]['absen']), ('12-T1', '01'))

    def test_olah_data_page_pencarian_lokal_dan_reset_filter(self):
        save_import([{
            'id': '90001', 'timestamp_input': '', 'tanggal_kejadian': '2026-07-20',
            'nis': '12403', 'nama_siswa': 'ALESSANDRO', 'kelas': '12-T1 01', 'kode_pasal': 'ME-02',
            'poin': '', 'judul': 'terlambat', 'keterangan': '', 'petugas': 'Petugas A'
        }, {
            'id': '90002', 'timestamp_input': '', 'tanggal_kejadian': '2026-07-21',
            'nis': '13069', 'nama_siswa': 'RUSSELL', 'kelas': '11-T1 34', 'kode_pasal': 'PA-01',
            'poin': '1800', 'judul': 'juara', 'keterangan': '', 'petugas': 'Petugas B'
        }], 'csv', confirmed=True)
        app = self.AppTest.from_file(str(ROOT / 'pages' / '3_Olah_Data.py'), default_timeout=60).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.multiselect(key='filter_tingkat').options, ['10', '11', '12'])
        self.assertEqual(app.multiselect(key='filter_kategori').options, ['pelanggaran', 'prestasi'])
        self.assertEqual(app.multiselect(key='filter_petugas').options, ['Petugas A', 'Petugas B'])
        app.text_input(key='filter_cari').set_value('russell').run()
        self.assertFalse(app.exception)
        self.assertTrue(any('1 dari 2 entri jurnal' in str(m.value) for m in app.markdown))
        app.multiselect(key='filter_kategori').set_value(['pelanggaran']).run()
        app.multiselect(key='filter_petugas').set_value(['Petugas A']).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('0 dari 2 entri jurnal' in str(m.value) for m in app.markdown))
        app.button(key='filter_reset').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.multiselect(key='filter_kategori').value, [])
        self.assertEqual(app.multiselect(key='filter_petugas').value, [])
        self.assertTrue(any('1 dari 2 entri jurnal' in str(m.value) for m in app.markdown))
        app.text_input(key='filter_cari').set_value('').run()
        self.assertTrue(any('2 dari 2 entri jurnal' in str(m.value) for m in app.markdown))


if __name__ == '__main__':
    unittest.main()
