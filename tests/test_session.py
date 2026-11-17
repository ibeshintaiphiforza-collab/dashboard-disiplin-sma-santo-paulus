import sys
import unittest
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core import analytics, session


def buat_frame():
    return analytics.normalisasi_kelas(pd.DataFrame({
        'id': [1, 2, 3, 4, 5, 6],
        'tanggal_kejadian': ['2026-07-20', '2026-07-21', '2026-08-01', '2026-08-02', '2026-08-03', '2026-08-04'],
        'nis': ['12403', '12403', '13069', '13500', '13500', '12990'],
        'nama_siswa': ['ALESSANDRO', 'ALESSANDRO', 'RUSSELL', 'MARIA', 'MARIA', 'YOHANES'],
        'kelas': ['12-T1', '12-T1', '11-T1', '10-5', '10-5', '11-K3'],
        'absen': ['01', '01', '34', '07', '07', '12'],
        'kode_pasal': ['ME-02', 'ME-03', 'PA-01', 'PC-01', 'ME-09', 'PB-17'],
        'poin': [-50, -50, 1800, 50, -35, 100],
        'judul': ['terlambat i', 'terlambat ii', 'juara', 'orang tua', 'buku', 'bendera'],
        'keterangan': ['ket'] * 6,
        'petugas': ['Petugas A', 'Petugas B', 'Petugas A', 'Petugas A', 'Petugas B', 'Petugas B'],
        'sumber': ['manual'] * 6,
        'kategori': ['pelanggaran', 'pelanggaran', 'prestasi', 'prestasi', 'pelanggaran', 'prestasi'],
        'subkategori': ['pelanggaran_terhadap_kerajinan', 'pelanggaran_terhadap_kerajinan',
                        'prestasi_akademik', 'dukungan_orang_tua', 'pelanggaran_terhadap_kerajinan',
                        'prestasi_humaniora'],
        'deskripsi': ['terlambat'] * 6,
        'poin_default': [-50, -50, 1800, 50, -35, 100],
        'arah_tanda': [-1, -1, 1, 1, -1, 1],
        'mode_poin': ['fixed'] * 6,
    }))


class ApplyFiltersTestCase(unittest.TestCase):
    def setUp(self):
        self.df = buat_frame()

    def ids(self, df):
        return df['id'].tolist()

    def test_default_tanpa_filter_mengembalikan_semua_baris(self):
        hasil = session.apply_filters_to_jurnal(self.df)
        self.assertEqual(self.ids(hasil), [1, 2, 3, 4, 5, 6])

    def test_filter_rentang_tanggal(self):
        hasil = session.apply_filters_to_jurnal(self.df, '2026-07-20', '2026-07-21')
        self.assertEqual(self.ids(hasil), [1, 2])
        hasil = session.apply_filters_to_jurnal(self.df, date(2026, 8, 1), date(2026, 8, 2))
        self.assertEqual(self.ids(hasil), [3, 4])

    def test_rentang_terbalik_dinormalkan(self):
        hasil = session.apply_filters_to_jurnal(self.df, '2026-08-02', '2026-08-01')
        self.assertEqual(self.ids(hasil), [3, 4])

    def test_filter_kelas_dan_tingkat(self):
        self.assertEqual(self.ids(session.apply_filters_to_jurnal(self.df, kelas=['12-T1'])), [1, 2])
        self.assertEqual(self.ids(session.apply_filters_to_jurnal(self.df, tingkat=['10'])), [4, 5])
        self.assertEqual(self.ids(session.apply_filters_to_jurnal(self.df, tingkat=['11', '12'])), [1, 2, 3, 6])
        self.assertEqual(self.ids(session.apply_filters_to_jurnal(self.df, tingkat=['10'], kelas=['12-T1'])), [])

    def test_filter_kategori_kode_dan_petugas(self):
        self.assertEqual(self.ids(session.apply_filters_to_jurnal(self.df, kategori=['prestasi'])), [3, 4, 6])
        self.assertEqual(self.ids(session.apply_filters_to_jurnal(self.df, kode_pasal=['ME-02'])), [1])
        self.assertEqual(self.ids(session.apply_filters_to_jurnal(self.df, petugas=['Petugas B'])), [2, 5, 6])

    def test_filter_kombinasi(self):
        hasil = session.apply_filters_to_jurnal(self.df, '2026-08-01', '2026-08-04', ['10'],
                                                kelas=['10-5'], kategori=['pelanggaran'])
        self.assertEqual(self.ids(hasil), [5])

    def test_list_kosong_dianggap_tanpa_filter(self):
        hasil = session.apply_filters_to_jurnal(self.df, None, None, [], [], [], [], [])
        self.assertEqual(self.ids(hasil), [1, 2, 3, 4, 5, 6])

    def test_hasil_kosong_tetap_dataframe(self):
        hasil = session.apply_filters_to_jurnal(self.df, tanggal_mulai=datetime(2027, 1, 1))
        self.assertIsInstance(hasil, pd.DataFrame)
        self.assertTrue(hasil.empty)

    def test_none_dikembalikan_apa_adanya(self):
        self.assertIsNone(session.apply_filters_to_jurnal(None))

    def test_frame_kosong_aman(self):
        kosong = self.df.iloc[0:0]
        self.assertTrue(session.apply_filters_to_jurnal(kosong, kelas=['12-T1']).empty)
        self.assertTrue(session.apply_filters_to_jurnal(kosong, tingkat=['10']).empty)


class FilterDefaultTestCase(unittest.TestCase):
    def setUp(self):
        self.df = buat_frame()

    def test_default_semua_terpilih_dan_tanpa_batasan_tambahan(self):
        defaults = session.get_filter_defaults(self.df)
        self.assertEqual(defaults['filter_tingkat'], [])
        self.assertEqual(defaults['filter_kelas'], [])
        self.assertEqual(defaults['filter_kategori'], [])
        self.assertEqual(defaults['filter_kode_pasal'], [])
        self.assertEqual(defaults['filter_petugas'], [])
        self.assertEqual(defaults['filter_tanggal_mulai'], date(2026, 7, 20))
        self.assertEqual(defaults['filter_tanggal_akhir'], date(2026, 8, 4))

    def test_default_frame_kosong_tanpa_tanggal(self):
        defaults = session.get_filter_defaults(self.df.iloc[0:0])
        self.assertIsNone(defaults['filter_tanggal_mulai'])
        self.assertIsNone(defaults['filter_tanggal_akhir'])
        self.assertEqual(defaults['filter_kelas'], [])

    def test_kunci_state_berprefiks_filter(self):
        for kunci in session.FILTER_KEYS:
            self.assertTrue(kunci.startswith('filter_'))


class StaleValueTestCase(unittest.TestCase):
    def setUp(self):
        self.df = buat_frame().iloc[0:3]
        self.df = self.df[self.df['kelas'] != '11-T1'].reset_index(drop=True)

    def test_kelas_hilang_dari_data_tidak_merusak_multiselect(self):
        self.assertEqual(session._nilai_unik(self.df, 'kelas'), ['12-T1'])
        self.assertEqual(session._rapikan(['12-T1', '11-T1'], session._nilai_unik(self.df, 'kelas')), ['12-T1'])

    def test_tingkat_tidak_valid_dibuang(self):
        self.assertEqual(session._rapikan(['10', '13', 'lainnya', '12'], session.TINGKAT_VALID), ['10', '12'])

    def test_rapikan_menangani_none(self):
        self.assertEqual(session._rapikan(None, ['a']), [])
        self.assertEqual(session._rapikan([], ['a']), [])

    def test_tanggal_teks_dinormalkan(self):
        self.assertEqual(session._tanggal_nilai('2026-07-20'), date(2026, 7, 20))
        self.assertIsNone(session._tanggal_nilai(None))
        self.assertIsNone(session._tanggal_nilai('bukan tanggal'))
        self.assertEqual(session._tanggal_nilai(datetime(2026, 7, 20, 8, 0)), date(2026, 7, 20))


if __name__ == '__main__':
    unittest.main()
