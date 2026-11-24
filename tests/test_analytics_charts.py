import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core import analytics, analytics_charts, db, dashboard

JURNAL_ROWS = [
    (1, '2026-07-05 08:00:00', '2026-07-05', '12403', 'ALESSANDRO WILLIAM HARDIANTO', '12-T1', '01',
     'ME-02', -50, 'terlambat pertama', 'Petugas A'),
    (2, '2026-07-12 08:00:00', '2026-07-12', '12403', 'ALESSANDRO WILLIAM HARDIANTO', '12-T1', '01',
     'ME-02', -50, 'terlambat ulang', 'Petugas A'),
    (3, '2026-07-20 08:00:00', '2026-07-20', '12403', 'ALESSANDRO WILLIAM HARDIANTO', '12-T1', '01',
     'ME-03', -50, 'terlambat kedua', 'Petugas B'),
    (4, '2026-08-04 08:00:00', '2026-08-04', '12403', 'ALESSANDRO WILLIAM HARDIANTO', '12-T1', '01',
     'ME-08', -30, 'tidak bawa buku', 'Petugas B'),
    (5, '2026-08-03 09:00:00', '2026-08-03', '13069', 'RUSSELL NICKLAUS', '11-T1', '34',
     'MB-01', -300, 'perkelahian', 'Petugas A'),
    (6, '2026-08-10 08:00:00', '2026-08-10', '13069', 'RUSSELL NICKLAUS', '11-T1', '34',
     'ME-05', -50, 'terlambat keempat', 'Petugas B'),
    (7, '2026-08-11 08:00:00', '2026-08-11', '13500', 'MARIA ANGELINA', '10-5', '07',
     'MA-01', -600, 'pelanggaran sangat berat', 'Petugas A'),
    (8, '2026-08-12 08:00:00', '2026-08-12', '13500', 'MARIA ANGELINA', '10-5', '07',
     'ME-02', -50, 'terlambat', 'Petugas B'),
    (9, '2026-07-15 09:00:00', '2026-07-15', '12990', 'YOHANES KRISNA', '11-K3', '12',
     'PA-01', 1800, 'juara internasional', 'Petugas A'),
    (10, '2026-08-05 08:00:00', '2026-08-05', '12990', 'YOHANES KRISNA', '11-K3', '12',
     'ME-08', -30, 'tidak bawa buku', 'Petugas A'),
    (11, '2026-08-06 08:00:00', '2026-08-06', '12990', 'YOHANES KRISNA', '11-K3', '12',
     'ME-09', -35, 'tidak bawa buku kedua', 'Petugas B'),
    (12, '2026-08-20 09:00:00', '2026-08-20', '13500', 'MARIA ANGELINA', '10-5', '07',
     'PB-17', 100, 'pengibar bendera', 'Petugas A'),
]

BANDS = {
    'green': '#2ca02c',
    'yellow': '#f2c200',
    'darkred': '#7f0000',
}


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
        conn = db.get_conn()
        try:
            conn.executemany(
                'INSERT INTO jurnal (id,timestamp_input,tanggal_kejadian,nis,nama_siswa,kelas,absen,'
                'kode_pasal,poin,judul,petugas,keterangan,sumber) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                [row + ('ket', 'manual') for row in JURNAL_ROWS])
            conn.commit()
        finally:
            conn.close()


class FigureTestCase(TempDbTestCase):
    def setUp(self):
        super().setUp()
        self.seed()
        self.jurnal = analytics.load_jurnal()
        self.semua = [
            (analytics_charts.fig_pelanggaran_berulang, self.jurnal),
            (analytics_charts.fig_eskalasi, self.jurnal),
            (analytics_charts.fig_early_warning, self.jurnal),
            (analytics_charts.fig_pasal_frekuensi, self.jurnal),
            (analytics_charts.fig_pasal_poin, self.jurnal),
            (analytics_charts.fig_tingkat, self.jurnal),
            (analytics_charts.fig_kelas, self.jurnal),
            (analytics_charts.fig_petugas, self.jurnal),
            (analytics_charts.fig_tren, self.jurnal),
            (analytics_charts.fig_hari, self.jurnal),
        ]

    @staticmethod
    def trace(fig, nama):
        for item in fig.data:
            if item.name == nama:
                return item
        raise AssertionError(f'trace {nama} tidak ditemukan')

    def test_semua_pembangun_mengembalikan_figure_berisi_trace(self):
        for fn, data in self.semua:
            with self.subTest(fungsi=fn.__name__):
                fig = fn(data)
                self.assertIsInstance(fig, go.Figure)
                self.assertGreaterEqual(len(fig.data), 1)
                self.assertEqual(fig.layout.height, analytics_charts.TINGGI)

    def test_pelanggaran_berulang_memakai_label_nama_dan_kode(self):
        fig = analytics_charts.fig_pelanggaran_berulang(self.jurnal)
        label = list(fig.data[0].y)
        nilai = list(fig.data[0].x)
        self.assertIn('ALESSANDRO WILLIAM HARDIANTO - ME-02', label)
        self.assertEqual(nilai[label.index('ALESSANDRO WILLIAM HARDIANTO - ME-02')], 2)
        self.assertLessEqual(len(label), 15)

    def test_eskalasi_mengelompokkan_dua_rantai(self):
        fig = analytics_charts.fig_eskalasi(self.jurnal)
        self.assertEqual([item.name for item in fig.data],
                         ['Terlambat (ME-02..ME-07)', 'Buku (ME-08..ME-10)'])
        terlambat = self.trace(fig, 'Terlambat (ME-02..ME-07)')
        buku = self.trace(fig, 'Buku (ME-08..ME-10)')
        self.assertEqual(list(terlambat.x), [f'Tahap {posisi}' for posisi in range(1, 7)])
        self.assertEqual(list(terlambat.y)[1], 1)
        self.assertEqual(list(terlambat.y)[3], 1)
        self.assertEqual(list(buku.y)[0], 1)
        self.assertEqual(list(buku.y)[1], 1)

    def test_early_warning_warna_sesuai_ambang_dan_garis_threshold(self):
        fig = analytics_charts.fig_early_warning(self.jurnal)
        merah_gelap = [item for item in fig.data if item.marker.color == BANDS['darkred']]
        kuning = [item for item in fig.data if item.marker.color == BANDS['yellow']]
        hijau = [item for item in fig.data if item.marker.color == BANDS['green']]
        self.assertEqual(len(merah_gelap), 1)
        self.assertEqual(len(kuning), 1)
        self.assertEqual(len(hijau), 1)
        self.assertEqual(len(list(hijau[0].y)), 2)
        self.assertEqual(list(merah_gelap[0].x), [-650])
        self.assertEqual(list(merah_gelap[0].y), ['MARIA ANGELINA - 10-5'])
        self.assertEqual(list(kuning[0].x), [-350])
        self.assertEqual(len(fig.layout.shapes), 4)
        self.assertEqual(len(fig.layout.annotations), 4)

    def test_pasal_frekuensi_dan_poin(self):
        frekuensi = analytics_charts.fig_pasal_frekuensi(self.jurnal)
        pelanggaran = self.trace(frekuensi, 'Pelanggaran')
        prestasi = self.trace(frekuensi, 'Prestasi')
        label = list(pelanggaran.y)
        label_me02 = next(teks for teks in label if teks.startswith('ME-02 - '))
        self.assertEqual(list(pelanggaran.x)[label.index(label_me02)], 3)
        self.assertTrue(any(teks.startswith('PA-01 - ') for teks in list(prestasi.y)))

        poin = analytics_charts.fig_pasal_poin(self.jurnal)
        nilai_pelanggaran = list(self.trace(poin, 'Pelanggaran').x)
        nilai_prestasi = list(self.trace(poin, 'Prestasi').x)
        self.assertIn(600, nilai_pelanggaran)
        self.assertIn(1800, nilai_prestasi)

    def test_tingkat_plus_minus_dan_jumlah_siswa(self):
        fig = analytics_charts.fig_tingkat(self.jurnal)
        plus = self.trace(fig, 'Poin plus')
        minus = self.trace(fig, 'Poin minus')
        siswa = self.trace(fig, 'Jumlah murid')
        self.assertEqual(list(plus.x), ['10', '11', '12'])
        self.assertEqual(list(plus.y), [100, 1800, 0])
        self.assertEqual(list(minus.y), [650, 415, 180])
        self.assertEqual(list(siswa.y), [1, 2, 1])

    def test_kelas_poin_plus_dan_minus(self):
        fig = analytics_charts.fig_kelas(self.jurnal, analytics.load_siswa())
        plus = self.trace(fig, 'Poin plus')
        minus = self.trace(fig, 'Poin minus')
        self.assertEqual(set(plus.y), {'10-5', '11-K3', '11-T1', '12-T1'})
        self.assertEqual(list(plus.x)[list(plus.y).index('11-K3')], 1800)
        self.assertEqual(list(minus.x)[list(minus.y).index('10-5')], 650)

    def test_petugas_memakai_dua_subplot(self):
        fig = analytics_charts.fig_petugas(self.jurnal)
        entri = self.trace(fig, 'Jumlah entri')
        self.assertEqual(list(entri.x), ['Petugas A', 'Petugas B'])
        self.assertEqual(list(entri.y), [7, 5])
        self.assertIn('xaxis2', fig.layout)
        self.assertGreaterEqual(len(fig.data), 3)

    def test_tren_bulanan_dan_kumulatif_poin(self):
        fig = analytics_charts.fig_tren(self.jurnal)
        pelanggaran = self.trace(fig, 'Pelanggaran')
        prestasi = self.trace(fig, 'Prestasi')
        kum_pelanggaran = self.trace(fig, 'Kumulatif pelanggaran')
        kum_prestasi = self.trace(fig, 'Kumulatif prestasi')
        self.assertEqual(list(pelanggaran.x), ['Jul 2026', 'Agu 2026'])
        self.assertEqual(fig.layout.xaxis.type, 'category')
        self.assertEqual(list(pelanggaran.y), [3, 7])
        self.assertEqual(list(prestasi.y), [1, 1])
        self.assertEqual(list(kum_pelanggaran.y), [-150, -1245])
        self.assertEqual(list(kum_prestasi.y), [1800, 1900])

    def test_hari_pelanggaran_dan_prestasi(self):
        fig = analytics_charts.fig_hari(self.jurnal)
        pelanggaran = self.trace(fig, 'Pelanggaran')
        prestasi = self.trace(fig, 'Prestasi')
        self.assertEqual(list(pelanggaran.x), analytics.NAMA_HARI)
        self.assertEqual(sum(pelanggaran.y), 10)
        self.assertEqual(sum(prestasi.y), 2)

    def test_label_bulan_berubah_format_angka(self):
        self.assertEqual(analytics.label_bulan('2026-07'), 'Jul 2026')
        self.assertEqual(analytics.label_bulan('2026-08'), 'Agu 2026')
        self.assertEqual(analytics.label_bulan('2026-01'), 'Jan 2026')
        self.assertEqual(analytics.label_bulan('tidak-ada-bulan'), 'tidak-ada-bulan')

    def test_tren_bulanan_dashboard_berkategori(self):
        fig = dashboard.gambar_tren_bulanan(self.jurnal)
        pelanggaran = self.trace(fig, 'Pelanggaran')
        self.assertEqual(list(pelanggaran.x), ['Jul 2026', 'Agu 2026'])
        self.assertEqual(fig.layout.xaxis.type, 'category')


class EmptyInputTestCase(TempDbTestCase):
    def setUp(self):
        super().setUp()
        self.kosong = analytics.load_jurnal()

    def test_input_kosong_mengembalikan_none(self):
        for nama in ['fig_pelanggaran_berulang', 'fig_eskalasi', 'fig_early_warning', 'fig_pasal_frekuensi',
                     'fig_pasal_poin', 'fig_tingkat', 'fig_kelas', 'fig_petugas', 'fig_tren', 'fig_hari']:
            with self.subTest(fungsi=nama):
                self.assertIsNone(getattr(analytics_charts, nama)(self.kosong))
                self.assertIsNone(getattr(analytics_charts, nama)(pd.DataFrame()))
                self.assertIsNone(getattr(analytics_charts, nama)(None))


class StreamlitSmokeTestCase(TempDbTestCase):
    def setUp(self):
        super().setUp()
        from streamlit.testing.v1 import AppTest
        self.AppTest = AppTest

    def jalankan(self):
        app = self.AppTest.from_file(str(ROOT / 'pages' / '2_🔎_Analisis.py'), default_timeout=60).run()
        self.assertFalse(app.exception)
        return app

    def test_halaman_analisis_merender_plotly_dan_tabel(self):
        self.seed()
        app = self.jalankan()
        self.assertTrue(app.dataframe)
        self.assertGreaterEqual(len(app.get('plotly_chart')), 1)

    def test_halaman_analisis_tanpa_data(self):
        app = self.jalankan()
        self.assertFalse(app.dataframe)
        self.assertEqual(len(app.get('plotly_chart')), 0)
        self.assertTrue(app.info)


if __name__ == '__main__':
    unittest.main()
