import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core.penghargaan import daftar_kandidat

KOLOM_JURNAL = ['tanggal_kejadian', 'nis', 'nama_siswa', 'kelas', 'kode_pasal', 'poin',
                'kategori', 'subkategori']


def jurnal(baris):
    return pd.DataFrame(baris, columns=KOLOM_JURNAL)


def prestasi(nis, poin, subkategori='prestasi_akademik', tanggal='2026-08-01'):
    return (tanggal, nis, f'MURID {nis}', '10-1', 'PA-01', poin, 'prestasi', subkategori)


def pelanggaran(nis, poin, tanggal='2026-08-01'):
    return (tanggal, nis, f'MURID {nis}', '10-1', 'ME-01', -poin, 'pelanggaran', 'pelanggaran_umum')


class BatasTingkatTest(unittest.TestCase):
    def test_batas_akademik_dan_humaniora(self):
        data = jurnal([
            prestasi('A1', 2500), prestasi('A2', 2501),
            prestasi('A3', 1500), prestasi('A4', 1501),
            prestasi('H1', 4500, 'prestasi_humaniora'), prestasi('H2', 4501, 'prestasi_humaniora'),
        ])
        hasil = daftar_kandidat(data, None)
        tingkat = {(baris.nis, baris.kelompok): baris.tingkat for baris in hasil.itertuples()}
        self.assertEqual(tingkat[('A1', 'Akademis/Olahraga/Seni')], 'II')
        self.assertEqual(tingkat[('A3', 'Akademis/Olahraga/Seni')], 'IV')
        self.assertEqual(tingkat[('H1', 'Humaniora')], 'II')
        self.assertEqual(tingkat[('A2', 'Akademis/Olahraga/Seni')], 'I')
        self.assertEqual(tingkat[('A4', 'Akademis/Olahraga/Seni')], 'III')
        self.assertEqual(tingkat[('H2', 'Humaniora')], 'I')


class BatasPelanggaranTest(unittest.TestCase):
    def test_150_memenuhi_151_tidak(self):
        data = jurnal([
            prestasi('B1', 2001), pelanggaran('B1', 150),
            prestasi('B2', 2001), pelanggaran('B2', 151),
        ])
        hasil = daftar_kandidat(data, None)
        syarat = {baris.nis: baris.memenuhi_syarat for baris in hasil.itertuples()}
        self.assertTrue(syarat['B1'])
        self.assertFalse(syarat['B2'])


class PialaTest(unittest.TestCase):
    def test_piala_hanya_tingkat_satu_tanpa_pelanggaran(self):
        data = jurnal([
            prestasi('C1', 2501),
            prestasi('C2', 2501), pelanggaran('C2', 100),
            prestasi('C3', 2001),
        ])
        hasil = daftar_kandidat(data, None)
        piala = {baris.nis: baris.piala for baris in hasil.itertuples()}
        self.assertTrue(piala['C1'])
        self.assertFalse(piala['C2'])
        self.assertFalse(piala['C3'])


class DukunganOrangTuaTest(unittest.TestCase):
    def test_default_diabaikan_dan_opsi_akademik_dihitung(self):
        data = jurnal([
            prestasi('D1', 2400),
            prestasi('D1', 200, 'dukungan_orang_tua'),
        ])
        tanpa = daftar_kandidat(data, None, dukungan_ortu='tidak')
        self.assertEqual(tanpa.loc[tanpa['nis'] == 'D1', 'tingkat'].iloc[0], 'II')
        self.assertEqual(tanpa.loc[tanpa['nis'] == 'D1', 'total_prestasi'].iloc[0], 2400)
        dengan = daftar_kandidat(data, None, dukungan_ortu='akademik')
        self.assertEqual(dengan.loc[dengan['nis'] == 'D1', 'tingkat'].iloc[0], 'I')
        self.assertEqual(dengan.loc[dengan['nis'] == 'D1', 'total_prestasi'].iloc[0], 2600)

    def test_default_masuk_humaniora(self):
        data = jurnal([
            prestasi('E1', 2400, 'prestasi_humaniora'),
            prestasi('E1', 200, 'dukungan_orang_tua'),
        ])
        hasil = daftar_kandidat(data, None)
        self.assertEqual(len(hasil), 1)
        self.assertEqual(hasil['kelompok'].iloc[0], 'Humaniora')
        self.assertEqual(hasil['total_prestasi'].iloc[0], 2600)


if __name__ == '__main__':
    unittest.main()
