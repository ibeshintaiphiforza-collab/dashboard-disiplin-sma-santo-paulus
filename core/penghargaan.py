import pandas as pd

SUBKATEGORI_ORANG_TUA = 'dukungan_orang_tua'

KELOMPOK = {
    'Akademis/Olahraga/Seni': 'prestasi_akademik',
    'Humaniora': 'prestasi_humaniora',
}

BATAS_TINGKAT = {
    'prestasi_akademik': [('I', 2501), ('II', 2001), ('III', 1501), ('IV', 1000)],
    'prestasi_humaniora': [('I', 4501), ('II', 4001), ('III', 3501), ('IV', 3000)],
}

URUTAN_TINGKAT = {'I': 0, 'II': 1, 'III': 2, 'IV': 3}

PENGHARGAAN = {
    'I': 'Sertifikat Prestasi + Medali Emas',
    'II': 'Sertifikat Prestasi + Medali Perak',
    'III': 'Sertifikat Prestasi + Medali Perunggu',
    'IV': 'Sertifikat Prestasi',
}

PIALA_TAMBAHAN = ' + Piala Prestasi dan Disiplin'

KOLOM = ['nis', 'nama', 'kelas', 'kelompok', 'total_prestasi', 'tingkat', 'penghargaan',
         'total_pelanggaran', 'memenuhi_syarat', 'piala']

DUKUNGAN_VALID = ('tidak', 'akademik', 'humaniora')


def tingkat_dari_poin(total, subkategori):
    batas = BATAS_TINGKAT.get(subkategori, [])
    for tingkat, minimum in batas:
        if total >= minimum:
            return tingkat
    return None


def _kolom_atau_kosong(data, kolom, nilai=''):
    if kolom in data.columns:
        return data[kolom]
    return pd.Series([nilai] * len(data), index=data.index, dtype=object)


def _siapkan(jurnal, pasal):
    if jurnal is None or not isinstance(jurnal, pd.DataFrame) or jurnal.empty:
        return pd.DataFrame()
    data = jurnal.copy()
    if 'kode_pasal' not in data.columns or 'poin' not in data.columns:
        return pd.DataFrame()
    if 'subkategori' not in data.columns or 'kategori' not in data.columns:
        if pasal is None or not isinstance(pasal, pd.DataFrame) or pasal.empty:
            return pd.DataFrame()
        if 'kode' not in pasal.columns or 'subkategori' not in pasal.columns:
            return pd.DataFrame()
        referensi = pasal[['kode', 'subkategori']].copy()
        if 'kategori' in pasal.columns:
            referensi['kategori'] = pasal['kategori']
        else:
            referensi['kategori'] = ''
        referensi = referensi.drop_duplicates(subset='kode')
        data = data.merge(referensi, left_on='kode_pasal', right_on='kode', how='left')
    data['subkategori'] = _kolom_atau_kosong(data, 'subkategori').fillna('').astype(str)
    data['kategori'] = _kolom_atau_kosong(data, 'kategori').fillna('').astype(str)
    data['poin'] = pd.to_numeric(data['poin'], errors='coerce').fillna(0)
    data['nis'] = _kolom_atau_kosong(data, 'nis').astype(str)
    data['nama'] = _kolom_atau_kosong(data, 'nama_siswa').astype(str)
    data['kelas'] = _kolom_atau_kosong(data, 'kelas').astype(str)
    return data


def _dalam_periode(data, periode_awal, periode_akhir):
    if periode_awal is None and periode_akhir is None:
        return data
    tanggal = pd.to_datetime(data['tanggal_kejadian'], errors='coerce') if 'tanggal_kejadian' in data.columns \
        else pd.Series(pd.NaT, index=data.index)
    mask = tanggal.notna()
    if periode_awal is not None:
        mask &= tanggal >= pd.Timestamp(periode_awal)
    if periode_akhir is not None:
        mask &= tanggal <= pd.Timestamp(periode_akhir)
    return data[mask]


def daftar_kandidat(jurnal, pasal, periode_awal=None, periode_akhir=None, batas_pelanggaran=150,
                    dukungan_ortu='humaniora'):
    if dukungan_ortu not in DUKUNGAN_VALID:
        raise ValueError(f'dukungan_ortu tidak dikenal: {dukungan_ortu}')
    data = _siapkan(jurnal, pasal)
    if data.empty:
        return pd.DataFrame(columns=KOLOM)
    data = _dalam_periode(data, periode_awal, periode_akhir)
    if data.empty:
        return pd.DataFrame(columns=KOLOM)

    pelanggaran = data[data['kategori'] == 'pelanggaran']
    total_pelanggaran = pelanggaran.groupby('nis')['poin'].apply(lambda nilai: float(nilai.abs().sum()))

    prestasi = data[data['kategori'] == 'prestasi']
    dukungan = data[data['subkategori'] == SUBKATEGORI_ORANG_TUA].groupby('nis')['poin'].sum()

    baris = []
    for kelompok, subkategori in KELOMPOK.items():
        anggota = prestasi[prestasi['subkategori'] == subkategori]
        total = anggota.groupby('nis')['poin'].sum()
        if dukungan_ortu == ('akademik' if subkategori == 'prestasi_akademik' else 'humaniora'):
            total = total.add(dukungan, fill_value=0)
        if total.empty:
            continue
        for nis, nilai in total.items():
            tingkat = tingkat_dari_poin(float(nilai), subkategori)
            if tingkat is None:
                continue
            murid = anggota[anggota['nis'] == nis]
            if murid.empty:
                murid = data[data['nis'] == nis]
            terakhir = murid.iloc[-1]
            jumlah_pelanggaran = float(total_pelanggaran.get(nis, 0))
            memenuhi = jumlah_pelanggaran <= float(batas_pelanggaran)
            piala = tingkat == 'I' and jumlah_pelanggaran == 0
            penghargaan = PENGHARGAAN[tingkat] + (PIALA_TAMBAHAN if piala else '')
            baris.append({
                'nis': nis,
                'nama': terakhir['nama'],
                'kelas': terakhir['kelas'],
                'kelompok': kelompok,
                'total_prestasi': float(nilai),
                'tingkat': tingkat,
                'penghargaan': penghargaan,
                'total_pelanggaran': jumlah_pelanggaran,
                'memenuhi_syarat': bool(memenuhi),
                'piala': bool(piala),
            })

    if not baris:
        return pd.DataFrame(columns=KOLOM)
    hasil = pd.DataFrame(baris, columns=KOLOM)
    hasil['_urutan_kelompok'] = hasil['kelompok'].map({nama: posisi for posisi, nama in enumerate(KELOMPOK)})
    hasil['_urutan_tingkat'] = hasil['tingkat'].map(URUTAN_TINGKAT)
    hasil = hasil.sort_values(['_urutan_kelompok', '_urutan_tingkat', 'total_prestasi'],
                              ascending=[True, True, False])
    return hasil.drop(columns=['_urutan_kelompok', '_urutan_tingkat']).reset_index(drop=True)
