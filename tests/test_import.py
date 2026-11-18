import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core import analytics, db
from core.importer import FIELDS, ImportValidator, PasteEguruParser, preview_records, save_import

FIXTURE = ROOT / 'data' / 'contoh_paste_eguru.txt'
CSV_HEADER = 'id,timestamp_input,tanggal_kejadian,nis,nama_siswa,kelas,kode_pasal,poin,judul,keterangan,petugas\n'
CSV_ROW = '90001,,2026-07-20,12613,violita cahyadi,12-A2 32,ME-02,-50,terlambat i,uraian,40Eli48\n'
CSV_HEADER_ABSEN = 'id,timestamp_input,tanggal_kejadian,nis,nama_siswa,kelas,absen,kode_pasal,poin,judul,keterangan,petugas\n'
LEGACY_JURNAL = """
CREATE TABLE jurnal (
    id INTEGER PRIMARY KEY,
    timestamp_input TEXT,
    tanggal_kejadian TEXT NOT NULL,
    nis TEXT NOT NULL,
    nama_siswa TEXT NOT NULL,
    kelas TEXT NOT NULL,
    kode_pasal TEXT NOT NULL,
    poin INTEGER NOT NULL,
    judul TEXT NOT NULL,
    keterangan TEXT,
    petugas TEXT,
    sumber TEXT NOT NULL DEFAULT 'manual',
    FOREIGN KEY (kode_pasal) REFERENCES pasal(kode)
)
"""
LEGACY_ROWS = [
    (40839, '2026-07-20', '12613', 'A', '12-A2 32', 'ME-02', -50, 'j'),
    (40840, '2026-07-20', '12419', 'B', '12-K2 05', 'MD-10', -10, 'j'),
    (40841, '2026-07-21', '12420', 'C', '12-K2 21', 'MD-10', -10, 'j'),
    (40842, '2026-07-21', '12500', 'D', 'XII A', 'MD-10', -10, 'j'),
    (40843, '2026-07-21', '12501', 'E', '12-K2', 'MD-10', -10, 'j'),
    (40844, '2026-07-21', '12502', 'F', '12-K2 1', 'MD-10', -10, 'j'),
    (40845, '2026-07-21', '12503', 'G', '13-K2 05', 'MD-10', -10, 'j'),
    (40846, '2026-07-21', '12504', 'H', '12-k2 05', 'MD-10', -10, 'j'),
]


class ImportTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.tmp.name) / 'test.db'
        self.addCleanup(lambda: setattr(db, 'DB_PATH', self.original))
        db.init_db()
        db.load_referensi_pasal()
        self.paste = FIXTURE.read_text(encoding='utf-8')

    def reference(self):
        conn = db.get_conn()
        try:
            import pandas as pd
            return pd.read_sql_query('SELECT * FROM pasal', conn).set_index('kode')
        finally:
            conn.close()

    def test_reference_schema_preserved(self):
        conn = db.get_conn()
        try:
            columns = [row[1] for row in conn.execute('PRAGMA table_info(pasal)')]
            count = conn.execute('SELECT COUNT(*) FROM pasal').fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(columns, ['kode', 'kategori', 'subkategori', 'deskripsi',
                                   'poin_default', 'arah_tanda', 'mode_poin'])
        self.assertEqual(count, 178)

    def test_broken_english_schema_is_renamed_without_data_loss(self):
        conn = db.get_conn()
        try:
            conn.execute('DROP TABLE pasal')
            conn.execute('CREATE TABLE pasal (code TEXT PRIMARY KEY, kind TEXT, subcategory TEXT, '
                         'label TEXT, default_points INTEGER, expected_sign INTEGER, points_mode TEXT)')
            conn.execute("INSERT INTO pasal VALUES ('ME-02','pelanggaran','x','y',-50,-1,'fixed')")
            conn.commit()
        finally:
            conn.close()
        db.load_referensi_pasal()
        conn = db.get_conn()
        try:
            columns = [row[1] for row in conn.execute('PRAGMA table_info(pasal)')]
            rows = conn.execute('SELECT kode, poin_default FROM pasal').fetchall()
        finally:
            conn.close()
        self.assertIn('kode', columns)
        self.assertNotIn('code', columns)
        self.assertEqual(rows, [('ME-02', -50)])

    def buat_jurnal_lama(self):
        conn = db.get_conn()
        try:
            conn.execute('DROP TABLE jurnal')
            conn.execute(LEGACY_JURNAL)
            conn.executemany(
                'INSERT INTO jurnal (id,tanggal_kejadian,nis,nama_siswa,kelas,kode_pasal,poin,judul) '
                'VALUES (?,?,?,?,?,?,?,?)', LEGACY_ROWS)
            conn.commit()
        finally:
            conn.close()

    def isi_jurnal(self):
        conn = db.get_conn()
        try:
            return conn.execute('SELECT * FROM jurnal ORDER BY id').fetchall()
        finally:
            conn.close()

    def test_jurnal_schema_has_absen_column(self):
        conn = db.get_conn()
        try:
            columns = [row[1] for row in conn.execute('PRAGMA table_info(jurnal)')]
        finally:
            conn.close()
        self.assertIn('absen', columns)
        self.assertEqual(columns.index('absen'), columns.index('kelas') + 1)

    def test_migration_splits_combined_kelas_and_keeps_others(self):
        self.buat_jurnal_lama()
        db.init_db()
        conn = db.get_conn()
        try:
            columns = [row[1] for row in conn.execute('PRAGMA table_info(jurnal)')]
            rows = dict((row[0], row[1:]) for row in conn.execute('SELECT id, kelas, absen FROM jurnal'))
            sisa = conn.execute('SELECT id, nis, poin, kode_pasal FROM jurnal ORDER BY id').fetchall()
        finally:
            conn.close()
        self.assertIn('absen', columns)
        self.assertEqual(len(rows), len(LEGACY_ROWS))
        self.assertEqual(sorted(rows), [row[0] for row in LEGACY_ROWS])
        self.assertEqual(rows[40839], ('12-A2', '32'))
        self.assertEqual(rows[40840], ('12-K2', '05'))
        self.assertEqual(rows[40841], ('12-K2', '21'))
        self.assertEqual(rows[40842], ('XII A', None))
        self.assertEqual(rows[40843], ('12-K2', None))
        self.assertEqual(rows[40844], ('12-K2 1', None))
        self.assertEqual(rows[40845], ('13-K2 05', None))
        self.assertEqual(rows[40846], ('12-k2 05', None))
        self.assertEqual(sisa, [(row[0], row[2], row[6], row[5]) for row in LEGACY_ROWS])

    def test_migration_is_idempotent(self):
        self.buat_jurnal_lama()
        db.init_db()
        pertama = self.isi_jurnal()
        conn = db.get_conn()
        try:
            self.assertEqual(db.migrasi_absen_jurnal(conn), 0)
        finally:
            conn.close()
        db.init_db()
        self.assertEqual(self.isi_jurnal(), pertama)
        self.assertEqual(len(pertama), len(LEGACY_ROWS))

    def test_migration_does_not_overwrite_conflicting_absen(self):
        self.buat_jurnal_lama()
        conn = db.get_conn()
        try:
            conn.execute('ALTER TABLE jurnal ADD COLUMN absen TEXT')
            conn.execute("UPDATE jurnal SET absen = '99' WHERE id = 40840")
            conn.commit()
            self.assertEqual(db.migrasi_absen_jurnal(conn), 2)
            row = conn.execute('SELECT kelas, absen FROM jurnal WHERE id = 40840').fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ('12-K2 05', '99'))

    def test_pisah_kelas_absen(self):
        self.assertEqual(db.pisah_kelas_absen('12-K2 21'), ('12-K2', '21'))
        self.assertEqual(db.pisah_kelas_absen(' 10-5 07 '), ('10-5', '07'))
        self.assertEqual(db.pisah_kelas_absen('12-K2'), ('12-K2', None))
        self.assertEqual(db.pisah_kelas_absen('XII A'), ('XII A', None))
        self.assertEqual(db.pisah_kelas_absen(None), ('', None))

    def test_fixture_parses_exactly_100_unique_ids(self):
        records = PasteEguruParser.parse_paste(self.paste)
        self.assertEqual(len(records), 100)
        self.assertEqual(len({r['id_eguru'] for r in records}), 100)
        self.assertEqual(records[0]['nis'], '12613')
        self.assertEqual(records[0]['tanggal_kejadian'], '20-07-2026')
        self.assertIsNone(records[0]['timestamp_input'])
        self.assertEqual(records[0]['petugas'], '40Eli48')
        self.assertEqual((records[0]['kelas'], records[0]['absen']), ('12-A2', '32'))
        self.assertEqual((records[1]['kelas'], records[1]['absen']), ('12-K2', '05'))
        for record in records:
            self.assertRegex(record['kelas'], r'^(10|11|12)-[A-Z0-9]+$')
            self.assertRegex(record['absen'], r'^\d{2}$')

    def test_fixture_saved_with_separate_kelas_and_absen(self):
        records = PasteEguruParser.parse_paste(self.paste)
        save_import(records, 'paste', confirmed=True)
        conn = db.get_conn()
        try:
            row = conn.execute('SELECT kelas, absen FROM jurnal WHERE id = 40839').fetchone()
            spasi = conn.execute("SELECT COUNT(*) FROM jurnal WHERE kelas LIKE '% %'").fetchone()[0]
            tanpa_absen = conn.execute('SELECT COUNT(*) FROM jurnal WHERE absen IS NULL').fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(row, ('12-A2', '32'))
        self.assertEqual((spasi, tanpa_absen), (0, 0))

    def test_unparsed_paste_rows_raise_instead_of_silent_loss(self):
        with self.assertRaises(ValueError):
            PasteEguruParser.parse_paste(self.paste + '\nbaris rusak tanpa struktur\n')
        with self.assertRaises(ValueError):
            PasteEguruParser.parse_paste('')

    def test_save_requires_confirmation_and_is_transactional(self):
        records = PasteEguruParser.parse_paste(self.paste)
        with self.assertRaises(ValueError):
            save_import(records, 'paste', confirmed=False)
        self.assertEqual(self.count('jurnal'), 0)
        broken = records[:2] + [dict(records[2], nis='abc')]
        with self.assertRaises(ValueError):
            save_import(broken, 'paste', confirmed=True)
        self.assertEqual(self.count('jurnal'), 0)
        self.assertEqual(self.count('import_log'), 0)

    def test_fixture_import_then_reimport_adds_zero(self):
        records = PasteEguruParser.parse_paste(self.paste)
        saved, duplicates = save_import(records, 'paste', confirmed=True)
        self.assertEqual((saved, duplicates), (100, 0))
        saved, duplicates = save_import(records, 'paste', confirmed=True)
        self.assertEqual((saved, duplicates), (0, 100))
        self.assertEqual(self.count('jurnal'), 100)
        self.assertEqual(self.count('import_log'), 2)

    def test_nis_leading_zero_preserved_and_dates_normalized(self):
        conn = db.get_conn()
        try:
            save_import([{
                'id': '91001', 'timestamp_input': '', 'tanggal_kejadian': '20-07-2026',
                'nis': '01234', 'nama_siswa': 'tes', 'kelas': '10-1 01', 'kode_pasal': 'ME-02',
                'poin': '', 'judul': 'terlambat', 'keterangan': '', 'petugas': ''
            }], 'csv', confirmed=True)
            row = conn.execute('SELECT nis, tanggal_kejadian, poin, timestamp_input FROM jurnal').fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ('01234', '2026-07-20', -50, None))

    def test_kode_pasal_dinormalisasi_case_dan_spasi(self):
        conn = db.get_conn()
        try:
            save_import([{
                'id': '91002', 'timestamp_input': '', 'tanggal_kejadian': '2026-07-20',
                'nis': '12613', 'nama_siswa': 'tes', 'kelas': '10-1 01', 'kode_pasal': 'pb-54 ',
                'poin': '', 'judul': 'j', 'keterangan': '', 'petugas': ''
            }], 'csv', confirmed=True)
            row = conn.execute(
                "SELECT j.kode_pasal, p.kode FROM jurnal j "
                "LEFT JOIN pasal p ON j.kode_pasal = p.kode WHERE j.id = 91002"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ('PB-54', 'PB-54'))

    def test_invalid_inputs_produce_errors_not_crashes(self):
        validator = ImportValidator(self.reference())
        base = {'id': '1', 'tanggal_kejadian': '2026-07-20', 'nis': '12613', 'nama_siswa': 'a',
                'kelas': '10-1 01', 'kode_pasal': 'ME-02', 'poin': '-50', 'judul': 'j',
                'keterangan': '', 'petugas': '', 'timestamp_input': ''}
        cases = {
            'tanggal_kejadian': '31-02-2026', 'nis': '12a', 'kelas': 'XII A',
            'poin': 'abc', 'id': 'x', 'nama_siswa': '',
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                errors, _ = validator.validate_record(dict(base, **{field: value}))
                self.assertTrue(errors)
        errors, warnings = validator.validate_record(dict(base, kode_pasal='ZZ-9', poin='10'))
        self.assertEqual(errors, [])
        self.assertTrue(warnings)
        errors, warnings = validator.validate_record(dict(base, kode_pasal='PB-16', poin='120'))
        self.assertEqual((errors, warnings), ([], []))
        errors, warnings = validator.validate_record(dict(base, kode_pasal='PB-16', poin='0'))
        self.assertEqual((errors, warnings), ([], []))
        errors, _ = validator.validate_record(dict(base, kode_pasal='PB-16', poin='-5'))
        self.assertTrue(errors)
        errors, warnings = validator.validate_record(dict(base, poin='-40'))
        self.assertEqual(errors, [])
        self.assertTrue(warnings)

    def test_tanggal_tidak_wajar_ditolak(self):
        validator = ImportValidator(self.reference())
        base = {'id': '1', 'tanggal_kejadian': '2026-08-04', 'nis': '12613', 'nama_siswa': 'a',
                'kelas': '10-1 01', 'kode_pasal': 'ME-02', 'poin': '-50', 'judul': 'j',
                'keterangan': '', 'petugas': '', 'timestamp_input': ''}
        for tanggal in ('1970-01-01', '01-01-1970', '1999-12-31'):
            with self.subTest(tanggal=tanggal):
                errors, _ = validator.validate_record(dict(base, tanggal_kejadian=tanggal))
                self.assertTrue(any('tidak wajar' in pesan for pesan in errors))
        for tanggal in ('2026-08-04', '04-08-2026', '2000-01-01'):
            with self.subTest(tanggal=tanggal):
                errors, _ = validator.validate_record(dict(base, tanggal_kejadian=tanggal))
                self.assertEqual(errors, [])
        for kosong in ('', '-', '0000-00-00', '(not set)'):
            with self.subTest(kosong=kosong):
                errors, _ = validator.validate_record(dict(base, tanggal_kejadian=kosong))
                self.assertTrue(any('wajib diisi' in pesan for pesan in errors))

    def test_csv_bytes_parsed_and_malformed_csv_rejected(self):
        records = PasteEguruParser.parse_csv((CSV_HEADER + CSV_ROW).encode('utf-8'))
        self.assertEqual(records[0]['id_eguru'], '90001')
        saved, _ = save_import(records, 'x.csv', confirmed=True)
        self.assertEqual(saved, 1)
        with self.assertRaises(ValueError):
            PasteEguruParser.parse_csv(b'kolom_a,kolom_b\n1,2\n')
        with self.assertRaises(ValueError):
            PasteEguruParser.parse_csv(CSV_HEADER.encode('utf-8'))
        with self.assertRaises(ValueError):
            PasteEguruParser.parse_csv((CSV_HEADER + CSV_ROW.replace('90001', '90002') + '1,2,3\n').encode('utf-8'))

    def test_csv_tanpa_kolom_absen_tidak_error(self):
        header = 'id,timestamp_input,tanggal_kejadian,nis,nama_siswa,kelas,kode_pasal,poin,judul,keterangan,petugas\n'
        rows = ('90011,,2026-07-20,12621,dodi,12-A2,ME-02,-50,terlambat i,,\n'
                '90012,,2026-07-20,12622,eka,12-A2 05,ME-02,-50,terlambat i,,\n')
        records = PasteEguruParser.parse_csv((header + rows).encode('utf-8'))
        conn = db.get_conn()
        try:
            preview = preview_records(records, conn)
        finally:
            conn.close()
        self.assertEqual([row['errors'] for row in preview], [[], []])
        self.assertEqual([(row['kelas'], row['absen']) for row in preview],
                         [('12-A2', None), ('12-A2', '05')])

    def test_csv_legacy_combined_kelas_is_split(self):
        records = PasteEguruParser.parse_csv((CSV_HEADER + CSV_ROW).encode('utf-8'))
        self.assertEqual((records[0]['kelas'], records[0]['absen']), ('12-A2', '32'))
        save_import(records, 'x.csv', confirmed=True)
        self.assertEqual(self.kelas_absen(90001), ('12-A2', '32'))

    def test_csv_separate_kelas_and_absen_columns(self):
        rows = ('90001,,2026-07-20,12613,violita,12-A2,32,ME-02,-50,terlambat i,,\n'
                '90002,,2026-07-20,12614,budi,12-A2,7,ME-02,-50,terlambat i,,\n'
                '90003,,2026-07-20,12615,citra,10-5,,ME-02,-50,terlambat i,,\n')
        records = PasteEguruParser.parse_csv((CSV_HEADER_ABSEN + rows).encode('utf-8'))
        conn = db.get_conn()
        try:
            preview = preview_records(records, conn)
        finally:
            conn.close()
        self.assertEqual([row['errors'] for row in preview], [[], [], []])
        self.assertEqual([(row['kelas'], row['absen']) for row in preview],
                         [('12-A2', '32'), ('12-A2', '07'), ('10-5', None)])
        saved, _ = save_import(records, 'x.csv', confirmed=True)
        self.assertEqual(saved, 3)
        self.assertEqual(self.kelas_absen(90002), ('12-A2', '07'))
        self.assertEqual(self.kelas_absen(90003), ('10-5', None))

    def test_csv_absen_and_kelas_validation(self):
        validator = ImportValidator(self.reference())
        base = {'id': '1', 'tanggal_kejadian': '2026-07-20', 'nis': '12613', 'nama_siswa': 'a',
                'kelas': '12-A2', 'absen': '32', 'kode_pasal': 'ME-02', 'poin': '-50', 'judul': 'j',
                'keterangan': '', 'petugas': '', 'timestamp_input': ''}
        self.assertEqual(validator.validate_record(base), ([], []))
        for field, value in [('absen', '123'), ('absen', 'ab'), ('kelas', '12-A2 3'),
                             ('kelas', '13-A2'), ('kelas', '12-a2')]:
            with self.subTest(field=field, value=value):
                errors, _ = validator.validate_record(dict(base, **{field: value}))
                self.assertTrue(errors)
        normalized, errors, _ = validator.normalize_record(dict(base, kelas='12-A2 32', absen=''))
        self.assertEqual((normalized['kelas'], normalized['absen'], errors), ('12-A2', '32', []))
        normalized, errors, _ = validator.normalize_record(dict(base, kelas='12-A2 32', absen='32'))
        self.assertEqual((normalized['kelas'], normalized['absen'], errors), ('12-A2', '32', []))
        _, errors, _ = validator.normalize_record(dict(base, kelas='12-A2 32', absen='05'))
        self.assertTrue(errors)

    def test_template_fields_include_absen(self):
        self.assertIn('absen', FIELDS)
        self.assertEqual(FIELDS.index('absen'), FIELDS.index('kelas') + 1)

    def test_rekap_per_kelas_groups_different_absen(self):
        save_import([
            {'id': '91001', 'tanggal_kejadian': '2026-07-20', 'nis': '12419', 'nama_siswa': 'a',
             'kelas': '12-K2', 'absen': '01', 'kode_pasal': 'ME-02', 'poin': '', 'judul': 'j'},
            {'id': '91002', 'tanggal_kejadian': '2026-07-20', 'nis': '12420', 'nama_siswa': 'b',
             'kelas': '12-K2', 'absen': '02', 'kode_pasal': 'ME-02', 'poin': '', 'judul': 'j'},
            {'id': '91003', 'tanggal_kejadian': '2026-07-20', 'nis': '12421', 'nama_siswa': 'c',
             'kelas': '12-K2 21', 'kode_pasal': 'ME-02', 'poin': '', 'judul': 'j'},
        ], 'x.csv', confirmed=True)
        rekap = analytics.rekap_per_kelas(analytics.load_jurnal())
        self.assertEqual(rekap['kelas'].tolist(), ['12-K2'])
        self.assertEqual((rekap.iloc[0]['jumlah_siswa'], rekap.iloc[0]['jumlah_entri'], rekap.iloc[0]['netto']),
                         (3, 3, -150))
        peringkat = analytics.peringkat_kelas(analytics.load_jurnal())
        self.assertEqual((peringkat.iloc[0]['kelas'], peringkat.iloc[0]['tingkat']), ('12-K2', '12'))

    def test_analytics_normalizes_unmigrated_frames(self):
        import pandas as pd
        lama = pd.DataFrame({'nis': ['1', '2'], 'nama_siswa': ['a', 'b'], 'kelas': ['12-K2 01', '12-K2 02'],
                             'poin': [-10, -20], 'tanggal_kejadian': ['2026-07-20', '2026-07-21']})
        rekap = analytics.rekap_per_kelas(lama)
        self.assertEqual(rekap['kelas'].tolist(), ['12-K2'])
        self.assertEqual(rekap.iloc[0]['jumlah_siswa'], 2)
        siswa = analytics.rekap_per_siswa(lama).set_index('nis')
        self.assertEqual((siswa.loc['2', 'kelas'], siswa.loc['2', 'absen']), ('12-K2', '02'))

    def kelas_absen(self, ident):
        conn = db.get_conn()
        try:
            return conn.execute('SELECT kelas, absen FROM jurnal WHERE id = ?', (ident,)).fetchone()
        finally:
            conn.close()

    def test_csv_without_id_duplicate_warning_absent_and_rows_added(self):
        header = CSV_HEADER.replace('id,', '')
        row = CSV_ROW.replace('90001,', '')
        records = PasteEguruParser.parse_csv((header + row).encode('utf-8'))
        save_import(records, 'x.csv', confirmed=True)
        save_import(records, 'x.csv', confirmed=True)
        self.assertEqual(self.count('jurnal'), 2)

    def count(self, table):
        conn = db.get_conn()
        try:
            return conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        finally:
            conn.close()


class StreamlitSmokeTestCase(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest
        self.AppTest = AppTest
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.tmp.name) / 'smoke.db'
        self.addCleanup(lambda: setattr(db, 'DB_PATH', self.original))
        db.init_db()
        db.load_referensi_pasal()

    def test_import_page_preview_and_save_smoke(self):
        app = self.AppTest.from_file(str(ROOT / 'pages' / '4_📥_Import_CSV.py'), default_timeout=60).run()
        self.assertFalse(app.exception)
        app.text_area[0].set_value(FIXTURE.read_text(encoding='utf-8')).run()
        app.button(key='btn_preview').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('100 record; 0 error' in str(m.value) for m in app.markdown))
        app.checkbox[0].check().run()
        app.button(key='btn_save').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.success)
        conn = db.get_conn()
        try:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM jurnal').fetchone()[0], 100)
        finally:
            conn.close()

    def test_dashboard_smoke_with_imported_fixture(self):
        records = PasteEguruParser.parse_paste(FIXTURE.read_text(encoding='utf-8'))
        save_import(records, 'paste', confirmed=True)
        app = self.AppTest.from_file(str(ROOT / 'pages' / '1_📊_Dashboard.py'), default_timeout=60).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '88')
        self.assertEqual(app.metric[1].value, '12')
        self.assertEqual(len(app.get('plotly_chart')), 9)
        self.assertTrue(app.dataframe)
        self.assertEqual(app.multiselect(key='filter_kelas').options, sorted({r['kelas'] for r in records}))

    def test_dashboard_smoke_empty_database(self):
        app = self.AppTest.from_file(str(ROOT / 'pages' / '1_📊_Dashboard.py'), default_timeout=60).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.metric)
        self.assertFalse(app.dataframe)
        self.assertEqual(len(app.get('plotly_chart')), 0)
        self.assertTrue(app.info)


if __name__ == '__main__':
    unittest.main()
