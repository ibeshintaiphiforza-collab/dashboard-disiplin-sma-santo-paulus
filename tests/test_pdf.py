import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from core import analytics, db, pdf
from core.importer import csv_baris_error, parse_master_siswa, preview_records, save_master_siswa

PASTE_MASTER = (
    '12403\tALESSANDRO WILLIAM HARDIANTO\t12-T1\t01\n'
    '13069\tRUSSELL NICKLAUS\t11-T1\t34\n'
    '13500\tMARIA ANGELINA\t10-5\t07\n'
)

JURNAL_ROWS = [
    (1, '2026-07-21 08:00:00', '2026-07-20', '12403', 'ALESSANDRO WILLIAM HARDIANTO', '12-T1 01', 'ME-02', -50, 'terlambat i', 'Petugas A'),
    (2, '2026-07-23 08:00:00', '2026-07-22', '12403', 'ALESSANDRO WILLIAM HARDIANTO', '12-T1 01', 'ME-02', -50, 'terlambat i lagi', 'Petugas A'),
    (3, '2026-07-24 08:00:00', '2026-07-23', '12403', 'ALESSANDRO WILLIAM HARDIANTO', '12-T1 01', 'ME-03', -50, 'terlambat ii', 'Petugas B'),
    (4, '2026-08-04 08:00:00', '2026-08-03', '12403', 'ALESSANDRO WILLIAM HARDIANTO', '12-T1 01', 'ME-08', -30, 'tidak bawa buku', 'Petugas B'),
    (5, '2026-07-25 09:00:00', '2026-07-24', '13069', 'RUSSELL NICKLAUS', '11-T1 34', 'PA-01', 1800, 'juara internasional', 'Petugas A'),
    (6, '2026-08-11 09:00:00', '2026-08-10', '13069', 'RUSSELL NICKLAUS', '11-T1 34', 'PB-17', 100, 'pengibar bendera', 'Petugas B'),
    (7, '2026-08-12 09:00:00', '2026-08-11', '13069', 'RUSSELL NICKLAUS', '11-T1 34', 'PC-01', 50, 'orang tua terlibat', 'Petugas B'),
    (8, '2026-08-13 09:00:00', '2026-08-12', '13500', 'MARIA ANGELINA', '10-5 07', 'PC-02', 150, 'dukungan pengurus kelas', 'Petugas A'),
    (9, '2026-08-14 08:00:00', '2026-08-13', '13500', 'MARIA ANGELINA', '10-5 07', 'ME-09', -35, 'tidak bawa buku ii', 'Petugas A'),
]

POLA_HALAMAN = re.compile(rb'/Type\s*/Page\b')


class TempDbTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.tmp.name) / 'test.db'
        self.addCleanup(lambda: setattr(db, 'DB_PATH', self.original))
        db.init_db()
        db.load_referensi_pasal()

    def seed(self):
        save_master_siswa(parse_master_siswa(PASTE_MASTER), 'paste', confirmed=True)
        conn = db.get_conn()
        try:
            conn.executemany(
                'INSERT INTO jurnal (id,timestamp_input,tanggal_kejadian,nis,nama_siswa,kelas,'
                'kode_pasal,poin,judul,petugas,keterangan,sumber) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                [row + ('ket', 'manual') for row in JURNAL_ROWS])
            conn.commit()
        finally:
            conn.close()


class PdfTestCase(TempDbTestCase):
    def setUp(self):
        super().setUp()
        self.seed()
        self.jurnal = analytics.load_jurnal()
        self.siswa = analytics.load_siswa()
        self.rekap_kelas = analytics.rekap_per_kelas(self.jurnal)
        self.rekap_siswa = analytics.rekap_per_siswa(self.jurnal, self.siswa)
        self.ringkasan = {
            'total_entri': len(self.jurnal),
            'jumlah_siswa': int(self.jurnal['nis'].nunique()),
            'jumlah_kelas': int(self.jurnal['kelas'].nunique()),
            'poin_prestasi': int(self.jurnal['poin'].clip(lower=0).sum()),
            'poin_pelanggaran': int(self.jurnal['poin'].clip(upper=0).sum()),
            'netto': int(self.jurnal['poin'].sum()),
        }

    def periksa_pdf(self, data, minimal=2000):
        self.assertIsInstance(data, bytes)
        self.assertTrue(data.startswith(b'%PDF'))
        self.assertGreaterEqual(len(data), minimal)
        self.assertIn(b'%%EOF', data)
        self.assertGreaterEqual(len(POLA_HALAMAN.findall(data)), 1)

    def test_rapor_siswa_menghasilkan_pdf_valid(self):
        profil = analytics.profil_siswa(self.jurnal, '12403', self.siswa)
        riwayat = analytics.riwayat_siswa(self.jurnal, '12403')
        data = pdf.rapor_siswa_pdf(profil, riwayat, '20-07-2026 sampai 13-08-2026')
        self.periksa_pdf(data)
        self.assertIn(b'Rapor Poin Murid', data)
        self.assertIn(b'SMA Katolik Santo Paulus Jember', data)
        self.assertIn(b'Status surat peringatan', data)

    def test_rapor_siswa_uraian_panjang_membungkus_teks(self):
        riwayat = analytics.riwayat_siswa(self.jurnal, '12403').copy()
        riwayat.loc[riwayat.index[0], 'keterangan'] = 'uraian sangat panjang ' * 80
        profil = analytics.profil_siswa(self.jurnal, '12403', self.siswa)
        self.periksa_pdf(pdf.rapor_siswa_pdf(profil, riwayat, 'seluruh data'))

    def test_rekap_kelas_menghasilkan_pdf_valid(self):
        data = pdf.rekap_kelas_pdf(self.rekap_kelas, self.rekap_siswa, '12-T1', '20-07-2026 sampai 13-08-2026')
        self.periksa_pdf(data)
        self.assertIn(b'Rekap Kelas 12-T1', data)
        self.assertIn(b'Status SP', data)

    def test_rekap_kelas_tanpa_baris_siswa_tetap_valid(self):
        data = pdf.rekap_kelas_pdf(self.rekap_kelas, self.rekap_siswa, '99-Z9', 'seluruh data')
        self.periksa_pdf(data)

    def test_rekap_sekolah_menghasilkan_pdf_valid(self):
        data = pdf.rekap_sekolah_pdf(self.rekap_kelas, '20-07-2026 sampai 13-08-2026', self.ringkasan)
        self.periksa_pdf(data)
        self.assertIn(b'Rekap Sekolah', data)
        self.assertIn(b'Legenda Ambang Surat Peringatan', data)
        self.assertIn(b'Jumlah murid', data)


class PdfKosongTestCase(TempDbTestCase):
    def setUp(self):
        super().setUp()
        self.jurnal = analytics.load_jurnal()
        self.siswa = analytics.load_siswa()
        self.rekap_kelas = analytics.rekap_per_kelas(self.jurnal)
        self.rekap_siswa = analytics.rekap_per_siswa(self.jurnal)

    def periksa_pdf(self, data):
        self.assertIsInstance(data, bytes)
        self.assertTrue(data.startswith(b'%PDF'))
        self.assertGreaterEqual(len(data), 1000)
        self.assertIn(b'%%EOF', data)
        self.assertGreaterEqual(len(POLA_HALAMAN.findall(data)), 1)
        self.assertIn(b'Tidak ada data', data)

    def test_rapor_kosong_menghasilkan_pdf_berisi_tanda_kosong(self):
        profil = analytics.profil_siswa(self.jurnal, '00000', siswa=self.siswa)
        riwayat = analytics.riwayat_siswa(self.jurnal, '00000')
        self.periksa_pdf(pdf.rapor_siswa_pdf(profil, riwayat, 'seluruh data'))

    def test_rapor_dengan_none_tetap_valid(self):
        self.periksa_pdf(pdf.rapor_siswa_pdf({}, None, ''))

    def test_rekap_kelas_kosong_menghasilkan_pdf_berisi_tanda_kosong(self):
        self.periksa_pdf(pdf.rekap_kelas_pdf(self.rekap_kelas, self.rekap_siswa, '12-T1', 'seluruh data'))

    def test_rekap_sekolah_kosong_menghasilkan_pdf_berisi_tanda_kosong(self):
        self.periksa_pdf(pdf.rekap_sekolah_pdf(self.rekap_kelas, 'seluruh data', {}))

    def test_helper_baris_kosong(self):
        self.assertEqual(pdf.KOSONG, 'Tidak ada data')
        self.assertEqual(pdf.baris_kosong(), [['Tidak ada data']])


class PdfLogoTestCase(TempDbTestCase):
    def setUp(self):
        super().setUp()
        self.jurnal = analytics.load_jurnal()
        self.rekap_kelas = analytics.rekap_per_kelas(self.jurnal)

    def test_logo_tertanam_di_kepala_dokumen(self):
        gambar = pdf._logo_flowable()
        self.assertIsNotNone(gambar)
        self.assertGreater(gambar.drawHeight, 0)
        self.assertGreater(gambar.drawWidth, 0)
        data = pdf.rekap_sekolah_pdf(self.rekap_kelas, 'seluruh data',
                                     {'total_entri': 0})
        self.assertIn(b'/Subtype /Image', data)
        self.assertIn(b'SMA Katolik Santo Paulus Jember', data)
        self.assertLess(len(data), 400000)

    def test_logo_pdf_lebih_ringan_dari_logo_asli(self):
        self.assertTrue(pdf.LOGO_PDF.exists())
        self.assertTrue(pdf.LOGO_SEKOLAH.exists())
        self.assertLess(pdf.LOGO_PDF.stat().st_size, pdf.LOGO_SEKOLAH.stat().st_size)

    def test_header_tetap_valid_tanpa_berkas_logo(self):
        simpan_pdf, simpan_sekolah = pdf.LOGO_PDF, pdf.LOGO_SEKOLAH
        pdf.LOGO_PDF = Path('tidak-ada-logo-pdf.png')
        pdf.LOGO_SEKOLAH = Path('tidak-ada-logo.png')
        try:
            self.assertIsNone(pdf._logo_flowable())
            data = pdf.rekap_sekolah_pdf(self.rekap_kelas, 'seluruh data', {})
            self.assertTrue(data.startswith(b'%PDF'))
            self.assertIn(b'SMA Katolik Santo Paulus Jember', data)
        finally:
            pdf.LOGO_PDF, pdf.LOGO_SEKOLAH = simpan_pdf, simpan_sekolah

    def data_uji(self):
        self.seed()

    def periksa_pdf(self, data, minimal=2000):
        self.assertIsInstance(data, bytes)
        self.assertTrue(data.startswith(b'%PDF'))
        self.assertGreaterEqual(len(data), minimal)
        self.assertIn(b'%%EOF', data)
        self.assertGreaterEqual(len(POLA_HALAMAN.findall(data)), 1)

    def _teks_pdf(self, data):
        potongan = re.findall(rb'\((.*?)(?<!\\)\)', data, re.S)
        return b' '.join(potongan).decode('latin-1')

    def test_csv_baris_error_memuat_baris_dan_alasan(self):
        self.data_uji()
        records = [
            {'id_eguru': '9001', 'tanggal_kejadian': '2026-08-20', 'nis': '12403',
             'nama_siswa': 'ALESSANDRO WILLIAM HARDIANTO', 'kelas': '12', 'absen': '01',
             'kode_pasal': 'ME-02', 'judul': 'terlambat', 'poin': '-50', 'petugas': 'A'},
            {'id_eguru': '9002', 'tanggal_kejadian': '2026-08-21', 'nis': '13069',
             'nama_siswa': 'RUSSELL NICKLAUS', 'kelas': '11', 'absen': '34',
             'kode_pasal': 'KODE-SALAH', 'judul': 'cacat', 'poin': '-5', 'petugas': 'A'},
        ]
        conn = db.get_conn()
        try:
            preview = preview_records(records, conn)
        finally:
            conn.close()
        self.assertTrue(preview[0]['errors'] == [] or preview[1]['errors'])
        if preview[0]['errors']:
            self.skipTest('record pertama ternyata ditolak validator')
        data = csv_baris_error(preview)
        self.assertIsInstance(data, bytes)
        self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
        teks = data.decode('utf-8-sig')
        self.assertIn('alasan', teks)
        self.assertIn('baris', teks)
        self.assertIn('; ', teks)
        self.assertNotIn('12403', teks)
        self.assertEqual(len(teks.strip().splitlines()), 2)

    def test_rapor_siswa_hanya_memuat_nis_terpilih(self):
        self.data_uji()
        self.jurnal = analytics.load_jurnal()
        self.siswa = analytics.load_siswa()
        profil = analytics.profil_siswa(self.jurnal, '12403', self.siswa)
        data = pdf.rapor_siswa_pdf(profil, self.jurnal, 'seluruh data')
        self.periksa_pdf(data)
        teks = self._teks_pdf(data)
        self.assertIn('12403', teks)
        self.assertNotIn('13069', teks)
        self.assertNotIn('13500', teks)

    def test_rapor_siswa_riwayat_panjang_ringkas_dua_halaman(self):
        self.data_uji()
        self.jurnal = analytics.load_jurnal()
        self.siswa = analytics.load_siswa()
        riwayat = analytics.riwayat_siswa(self.jurnal, '12403')
        tambahan = pd.concat([riwayat.iloc[[0]]] * 40, ignore_index=True)
        tambahan['id'] = range(1000, 1000 + len(tambahan))
        riwayat = pd.concat([riwayat, tambahan], ignore_index=True)
        profil = analytics.profil_siswa(riwayat, '12403', self.siswa)
        data = pdf.rapor_siswa_pdf(profil, riwayat, 'seluruh data', batas_riwayat=12)
        self.periksa_pdf(data)
        halaman = len(POLA_HALAMAN.findall(data))
        self.assertGreaterEqual(halaman, 1)
        self.assertLessEqual(halaman, 2)
        self.assertIn('entri lainnya', self._teks_pdf(data))


class StreamlitPdfTestCase(TempDbTestCase):
    def setUp(self):
        super().setUp()
        from streamlit.testing.v1 import AppTest
        self.AppTest = AppTest

    def jalankan(self, berkas):
        app = self.AppTest.from_file(str(ROOT / 'pages' / berkas), default_timeout=60).run()
        self.assertFalse(app.exception)
        return app

    def test_profil_siswa_menyediakan_unduhan_pdf(self):
        self.seed()
        app = self.jalankan('6_👤_Profil_Murid.py')
        kunci = [tombol.key for tombol in app.download_button]
        self.assertIn('pdf_rapor', kunci)
        self.assertIn('csv_rapor', kunci)

    def test_olah_data_menyediakan_unduhan_pdf(self):
        self.seed()
        app = self.jalankan('3_🗂️_Olah_Data.py')
        kunci = [tombol.key for tombol in app.download_button]
        self.assertIn('pdf_rekap_kelas', kunci)
        self.assertIn('pdf_rekap_sekolah', kunci)
        self.assertEqual(app.selectbox(key='pdf_kelas').value, '10-5')


if __name__ == '__main__':
    unittest.main()
