import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core import analytics, db
from core.importer import parse_master_siswa, save_master_siswa

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


class ProfilSiswaTestCase(TempDbTestCase):
    def setUp(self):
        super().setUp()
        self.seed()
        self.jurnal = analytics.load_jurnal()
        self.siswa = analytics.load_siswa()

    def test_daftar_pilihan_gabungan_jurnal_dan_master(self):
        pilihan = analytics.daftar_pilihan_siswa(self.jurnal, self.siswa)
        self.assertEqual(sorted(pilihan['nis']), ['12403', '13069', '13500'])
        baris = pilihan[pilihan['nis'] == '12403'].iloc[0]
        self.assertEqual(baris['label'], '12403 - ALESSANDRO WILLIAM HARDIANTO (12-T1)')

    def test_profil_mengecualikan_dukungan_orang_tua_secara_baku(self):
        profil = analytics.profil_siswa(self.jurnal, '13069', siswa=self.siswa)
        self.assertEqual(profil['poin_prestasi'], 1950)
        self.assertEqual(profil['poin_pelanggaran'], 0)
        self.assertEqual(profil['netto'], 1950)
        self.assertEqual(profil['jumlah_entri'], 3)
        self.assertEqual(profil['poin_orang_tua'], 50)
        self.assertEqual(profil['jumlah_entri_orang_tua'], 1)
        self.assertEqual(profil['nama'], 'RUSSELL NICKLAUS')
        self.assertEqual(profil['kelas'], '11-T1')
        self.assertEqual(profil['sumber_identitas'], 'master_siswa')

    def test_profil_dengan_dukungan_orang_tua(self):
        profil = analytics.profil_siswa(self.jurnal, '13069', siswa=self.siswa)
        self.assertEqual(profil['netto'], 1950)
        self.assertEqual(profil['jumlah_entri'], 3)

    def test_pilihan_siswa_dengan_filter_aktif_tidak_kosong(self):
        terfilter = analytics.filter_jurnal(self.jurnal, tanggal_mulai='2026-08-01', tanggal_akhir='2026-08-31')
        self.assertFalse(terfilter.empty)
        pilihan = analytics.daftar_pilihan_siswa(terfilter, self.siswa)
        self.assertFalse(pilihan.empty)
        for _, baris in pilihan.iterrows():
            profil = analytics.profil_siswa(terfilter, baris['nis'], self.siswa)
            self.assertTrue(profil['nama'], baris['nis'])
            self.assertGreater(profil['jumlah_entri'], 0, baris['nis'])

    def test_profil_identitas_dari_jurnal_saat_master_kosong(self):
        profil = analytics.profil_siswa(self.jurnal, '12403', siswa=self.siswa.iloc[0:0])
        self.assertEqual(profil['nama'], 'ALESSANDRO WILLIAM HARDIANTO')
        self.assertEqual(profil['kelas'], '12-T1')
        self.assertEqual(profil['absen'], '01')
        self.assertEqual(profil['sumber_identitas'], 'jurnal')
        self.assertEqual(profil['netto'], -180)

    def test_riwayat_urut_turun_dan_berisi_deskripsi(self):
        riwayat = analytics.riwayat_siswa(self.jurnal, '12403')
        self.assertEqual(riwayat['id'].tolist(), [4, 3, 2, 1])
        self.assertIn('Pasal 14.', riwayat.iloc[-1]['deskripsi'])
        for kolom in ['kode_pasal', 'poin', 'judul', 'petugas', 'kelas', 'absen']:
            self.assertIn(kolom, riwayat.columns)
        self.assertEqual(set(riwayat['kelas']), {'12-T1'})
        self.assertEqual(set(riwayat['absen']), {'01'})

    def test_kumulatif_netto_dan_entri_per_subkategori(self):
        kumulatif = analytics.kumulatif_netto_siswa(self.jurnal, '12403')
        self.assertEqual(kumulatif['netto_kumulatif'].tolist(), [-50, -100, -150, -180])
        sub = analytics.entri_per_subkategori_siswa(self.jurnal, '13069').set_index('subkategori')
        self.assertEqual(sub.loc['prestasi_akademik', 'jumlah_entri'], 1)
        self.assertEqual(sub.loc['dukungan_orang_tua', 'total_poin'], 50)

    def test_profil_untuk_nis_tidak_dikenal_nol(self):
        profil = analytics.profil_siswa(self.jurnal, '00000', siswa=self.siswa)
        self.assertEqual((profil['netto'], profil['jumlah_entri']), (0, 0))
        self.assertTrue(analytics.riwayat_siswa(self.jurnal, '00000').empty)


class AnalisisTestCase(TempDbTestCase):
    def setUp(self):
        super().setUp()
        self.seed()
        self.jurnal = analytics.load_jurnal()
        self.siswa = analytics.load_siswa()

    def test_pelanggaran_berulang_menghitung_pengulangan_kode_sama(self):
        pelanggaran_berulang = analytics.pelanggaran_berulang(self.jurnal)
        self.assertEqual(len(pelanggaran_berulang), 1)
        baris = pelanggaran_berulang.iloc[0]
        self.assertEqual((baris['nis'], baris['kode_pasal'], baris['jumlah_entri'], baris['total_poin']),
                         ('12403', 'ME-02', 2, -100))
        self.assertTrue(analytics.pelanggaran_berulang(self.jurnal, minimal=3).empty)

    def test_eskalasi_mendeteksi_rantai_dan_tahap_tertinggi(self):
        eskalasi = analytics.eskalasi_tahapan(self.jurnal).set_index(['nis', 'rantai'])
        terlambat = eskalasi.loc[('12403', 'terlambat')]
        self.assertEqual((terlambat['kode_tertinggi'], terlambat['tahap'], terlambat['tahap_maks']),
                         ('ME-03', 2, 6))
        self.assertFalse(terlambat['di_tahap_tertinggi'])
        self.assertEqual(terlambat['jumlah_entri'], 3)
        buku = eskalasi.loc[('12403', 'buku_prestasi_disiplin')]
        self.assertEqual((buku['kode_tertinggi'], buku['tahap']), ('ME-08', 1))
        maria = eskalasi.loc[('13500', 'buku_prestasi_disiplin')]
        self.assertEqual((maria['kode_tertinggi'], maria['tahap']), ('ME-09', 2))

    def test_siswa_berisiko_ranking_dan_ambang_opsional(self):
        tanpa_ambang = analytics.siswa_berisiko(self.jurnal, None, self.siswa)
        self.assertEqual(tanpa_ambang['nis'].tolist()[0], '12403')
        self.assertFalse(tanpa_ambang['melewati_ambang'].any())
        dengan_ambang = analytics.siswa_berisiko(self.jurnal, 100, self.siswa)
        lewat = dengan_ambang[dengan_ambang['melewati_ambang']]['nis'].tolist()
        self.assertEqual(lewat, ['12403'])

    def test_analisis_per_pasal_dan_top_pelanggar(self):
        pasal = analytics.analisis_per_pasal(self.jurnal).set_index('kode_pasal')
        self.assertEqual(pasal.loc['ME-02', 'jumlah_entri'], 2)
        self.assertEqual(pasal.loc['ME-02', 'total_poin'], -100)
        self.assertEqual(pasal.loc['ME-02', 'jumlah_siswa'], 1)
        self.assertEqual(pasal.loc['PA-01', 'subkategori'], 'prestasi_akademik')
        top = analytics.top_pelanggar_per_pasal(self.jurnal)
        self.assertNotIn('PA-01', top['kode_pasal'].tolist())
        baris = top[top['kode_pasal'] == 'ME-02'].iloc[0]
        self.assertEqual((baris['nis'], baris['jumlah_entri']), ('12403', 2))

    def test_tingkat_diturunkan_dan_peringkat_kelas(self):
        self.assertEqual(analytics.tingkat_dari_kelas(['12-T1 01', '10-5 07', 'XII A', None, '12-K2', '11-T1']).tolist(),
                         ['12', '10', 'lainnya', 'lainnya', '12', '11'])
        tingkat = analytics.analisis_per_tingkat(self.jurnal).set_index('tingkat')
        self.assertEqual(tingkat.loc['12', 'netto'], -180)
        self.assertEqual(tingkat.loc['11', 'netto'], 1950)
        self.assertEqual(tingkat.loc['10', 'netto'], 115)
        self.assertEqual(tingkat.loc['12', 'jumlah_siswa'], 1)
        kelas = analytics.peringkat_kelas(self.jurnal)
        self.assertEqual(kelas['kelas'].tolist()[0], '12-T1')
        self.assertEqual(kelas.set_index('kelas').loc['11-T1', 'tingkat'], '11')
        self.assertEqual(tingkat.loc['12', 'jumlah_kelas'], 1)

    def test_statistik_petugas_dan_distribusi_kategori(self):
        petugas = analytics.statistik_petugas(self.jurnal).set_index('petugas')
        self.assertEqual(petugas.loc['Petugas A', 'jumlah_entri'], 5)
        self.assertEqual(petugas.loc['Petugas A', 'jumlah_pelanggaran'], 3)
        self.assertEqual(petugas.loc['Petugas A', 'jumlah_prestasi'], 2)
        self.assertEqual(petugas.loc['Petugas A', 'tanggal_awal'], '2026-07-20')
        self.assertEqual(petugas.loc['Petugas B', 'tanggal_akhir'], '2026-08-11')
        distribusi = analytics.distribusi_kategori_petugas(self.jurnal).set_index('petugas')
        self.assertEqual(distribusi.loc['Petugas A', 'pelanggaran'], 3)
        self.assertEqual(distribusi.loc['Petugas B', 'prestasi'], 2)

    def test_tren_bulanan_dan_distribusi_hari(self):
        bulanan = analytics.tren_bulanan(self.jurnal).set_index('bulan')
        self.assertEqual(bulanan.index.tolist(), ['2026-07', '2026-08'])
        self.assertEqual(bulanan.loc['2026-07', 'pelanggaran'], 3)
        self.assertEqual(bulanan.loc['2026-07', 'prestasi'], 1)
        self.assertEqual(bulanan.loc['2026-08', 'pelanggaran'], 2)
        self.assertEqual(bulanan.loc['2026-08', 'prestasi'], 3)
        harian = analytics.distribusi_hari_pelanggaran(self.jurnal).set_index('hari')
        self.assertEqual(harian['jumlah_entri'].sum(), 5)
        self.assertEqual(harian.loc['Senin', 'jumlah_entri'], 2)
        self.assertTrue(set(harian.index).issubset(set(analytics.NAMA_HARI)))


class DataKosongTestCase(TempDbTestCase):
    def setUp(self):
        super().setUp()
        self.jurnal = analytics.load_jurnal()
        self.siswa = analytics.load_siswa()

    def test_semua_fungsi_mengembalikan_dataframe_kosong(self):
        fungsi = [
            (analytics.daftar_pilihan_siswa, (self.jurnal, self.siswa)),
            (analytics.riwayat_siswa, (self.jurnal, '12403')),
            (analytics.kumulatif_netto_siswa, (self.jurnal, '12403')),
            (analytics.entri_per_subkategori_siswa, (self.jurnal, '12403')),
            (analytics.pelanggaran_berulang, (self.jurnal,)),
            (analytics.eskalasi_tahapan, (self.jurnal,)),
            (analytics.siswa_berisiko, (self.jurnal,)),
            (analytics.analisis_per_pasal, (self.jurnal,)),
            (analytics.top_pelanggar_per_pasal, (self.jurnal,)),
            (analytics.analisis_per_tingkat, (self.jurnal,)),
            (analytics.peringkat_kelas, (self.jurnal,)),
            (analytics.statistik_petugas, (self.jurnal,)),
            (analytics.distribusi_kategori_petugas, (self.jurnal,)),
            (analytics.tren_bulanan, (self.jurnal,)),
            (analytics.distribusi_hari_pelanggaran, (self.jurnal,)),
        ]
        for fn, args in fungsi:
            with self.subTest(fungsi=fn.__name__):
                hasil = fn(*args)
                self.assertTrue(hasil.empty)

    def test_profil_pada_basis_data_kosong(self):
        profil = analytics.profil_siswa(self.jurnal, '12403', siswa=self.siswa)
        self.assertEqual(profil['netto'], 0)
        self.assertEqual(profil['jumlah_entri'], 0)
        self.assertEqual(profil['poin_orang_tua'], 0)
        self.assertEqual(profil['sumber_identitas'], 'tidak_ditemukan')


class StreamlitSmokeTestCase(TempDbTestCase):
    def setUp(self):
        super().setUp()
        from streamlit.testing.v1 import AppTest
        self.AppTest = AppTest

    def jalankan(self, berkas):
        app = self.AppTest.from_file(str(ROOT / 'pages' / berkas), default_timeout=60).run()
        self.assertFalse(app.exception)
        return app

    def test_profil_siswa_page_smoke_dengan_data(self):
        self.seed()
        app = self.jalankan('6_Profil_Siswa.py')
        self.assertTrue(app.selectbox)
        self.assertTrue(app.metric)
        self.assertTrue(app.dataframe)

    def test_profil_siswa_page_smoke_basis_data_kosong(self):
        app = self.jalankan('6_Profil_Siswa.py')
        self.assertTrue(app.warning)

    def test_analisis_page_smoke_dengan_data(self):
        self.seed()
        app = self.jalankan('2_Analisis.py')
        self.assertTrue(app.dataframe)
        self.assertTrue(app.info)
        self.assertGreaterEqual(len(app.get('plotly_chart')), 1)

    def test_analisis_page_smoke_basis_data_kosong(self):
        app = self.jalankan('2_Analisis.py')
        self.assertFalse(app.exception)
        self.assertFalse(app.dataframe)


if __name__ == '__main__':
    unittest.main()
