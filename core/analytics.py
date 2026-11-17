from datetime import datetime


import pandas as pd

from core.db import get_conn, pisah_kelas_absen
from core.thresholds import THRESHOLDS_SP


def _waktu_sekarang():
    return datetime.now().isoformat(timespec='seconds')

SUBKATEGORI_ORANG_TUA = 'dukungan_orang_tua'

JURNAL_COLUMNS = ['id', 'timestamp_input', 'tanggal_kejadian', 'nis', 'nama_siswa', 'kelas', 'absen',
                  'kode_pasal', 'poin', 'judul', 'keterangan', 'petugas', 'sumber']

PASAL_COLUMNS = ['kategori', 'subkategori', 'deskripsi', 'poin_default', 'arah_tanda', 'mode_poin']

TAHAPAN_PASAL = {
    'terlambat': ['ME-02', 'ME-03', 'ME-04', 'ME-05', 'ME-06', 'ME-07'],
    'buku_prestasi_disiplin': ['ME-08', 'ME-09', 'ME-10'],
}

NAMA_HARI = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
NAMA_BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']


def label_bulan(nilai):
    teks = str(nilai).strip()
    bagian = teks.split('-')
    if len(bagian) >= 2 and bagian[0].isdigit() and bagian[1].isdigit():
        bulan = int(bagian[1])
        if 1 <= bulan <= 12:
            return f'{NAMA_BULAN[bulan - 1]} {bagian[0]}'
    return teks


def load_jurnal(conn=None):
    owned = conn is None
    conn = conn or get_conn()
    try:
        df = pd.read_sql_query(
            'SELECT j.*, p.kategori, p.subkategori, p.deskripsi, p.poin_default, p.arah_tanda, p.mode_poin '
            'FROM jurnal j LEFT JOIN pasal p ON j.kode_pasal = p.kode', conn)
    finally:
        if owned:
            conn.close()
    return normalisasi_kelas(df)


def normalisasi_kelas(df):
    if df is None or 'kelas' not in df.columns:
        return df
    data = df.copy()
    if 'absen' not in data.columns:
        data['absen'] = None
    data['absen'] = data['absen'].astype(object)
    data['kelas'] = data['kelas'].astype(object)
    if not data.empty:
        pisah = data['kelas'].map(pisah_kelas_absen)
        absen_kosong = data['absen'].isna() | (data['absen'].astype(str).str.strip() == '')
        bisa_dipisah = pisah.map(lambda nilai: nilai[1] is not None) & absen_kosong
        data.loc[bisa_dipisah, 'kelas'] = pisah[bisa_dipisah].map(lambda nilai: nilai[0])
        data.loc[bisa_dipisah, 'absen'] = pisah[bisa_dipisah].map(lambda nilai: nilai[1])
    urutan = [kolom for kolom in JURNAL_COLUMNS + PASAL_COLUMNS if kolom in data.columns]
    return data[urutan + [kolom for kolom in data.columns if kolom not in urutan]]


def load_siswa(conn=None):
    owned = conn is None
    conn = conn or get_conn()
    try:
        return pd.read_sql_query('SELECT nis, nama, kelas, angkatan, absen FROM siswa', conn)
    finally:
        if owned:
            conn.close()


def filter_jurnal(df, tanggal_mulai=None, tanggal_akhir=None, kelas=None, kategori=None,
                  kode_pasal=None, petugas=None, pencarian=None):
    result = normalisasi_kelas(df)
    if result.empty:
        return result
    tanggal = pd.to_datetime(result['tanggal_kejadian'], errors='coerce')
    if tanggal_mulai is not None:
        result = result[tanggal >= pd.Timestamp(tanggal_mulai)]
        tanggal = tanggal.loc[result.index]
    if tanggal_akhir is not None:
        result = result[tanggal <= pd.Timestamp(tanggal_akhir)]
    if kelas:
        result = result[result['kelas'].isin(list(kelas))]
    if kategori:
        result = result[result['kategori'].isin(list(kategori))]
    if kode_pasal:
        result = result[result['kode_pasal'].isin(list(kode_pasal))]
    if petugas:
        result = result[result['petugas'].isin(list(petugas))]
    if pencarian:
        needle = str(pencarian).strip().lower()
        if needle:
            nama = result['nama_siswa'].fillna('').str.lower()
            judul = result['judul'].fillna('').str.lower()
            result = result[nama.str.contains(needle, regex=False) | judul.str.contains(needle, regex=False)]
    return result.reset_index(drop=True)


def anomali_poin_beda_default(df):
    if df.empty:
        return df.iloc[0:0][JURNAL_COLUMNS]
    mask = (df['mode_poin'] == 'fixed') & df['poin_default'].notna() & (df['poin'] != df['poin_default'])
    kolom = ['id', 'tanggal_kejadian', 'nis', 'nama_siswa', 'kelas', 'absen', 'kode_pasal', 'poin', 'poin_default', 'judul']
    return df.loc[mask, kolom].reset_index(drop=True)


def anomali_nis_tidak_dikenal(df, siswa):
    kolom = ['id', 'tanggal_kejadian', 'nis', 'nama_siswa', 'kelas', 'absen', 'kode_pasal', 'poin', 'judul']
    if df.empty or siswa.empty:
        return df.iloc[0:0].reindex(columns=kolom)
    master = set(siswa['nis'].astype(str))
    mask = ~df['nis'].astype(str).isin(master)
    return df.loc[mask, kolom].reset_index(drop=True)


def anomali_duplikat(df):
    kunci = ['nis', 'tanggal_kejadian', 'kode_pasal']
    kolom = ['id', 'tanggal_kejadian', 'nis', 'nama_siswa', 'kelas', 'absen', 'kode_pasal', 'poin', 'judul']
    if df.empty:
        return df.iloc[0:0].reindex(columns=kolom)
    mask = df.duplicated(subset=kunci, keep=False)
    return df.loc[mask, kolom].sort_values(kunci).reset_index(drop=True)


# Anomali jika tanggal_kejadian (kejadian) lebih besar/setelah timestamp_input (masuk).
def anomali_tanggal_mendahului_input(df):
    kolom = ['id', 'tanggal_kejadian', 'timestamp_input', 'nis', 'nama_siswa', 'kelas', 'absen', 'kode_pasal', 'judul']
    if df.empty:
        return df.iloc[0:0].reindex(columns=kolom)
    kejadian = pd.to_datetime(df['tanggal_kejadian'], errors='coerce')
    masuk = pd.to_datetime(df['timestamp_input'], errors='coerce')
    mask = masuk.notna() & kejadian.notna() & (kejadian.dt.normalize() > masuk.dt.normalize())
    return df.loc[mask, kolom].reset_index(drop=True)


def deteksi_anomali(df, siswa=None):
    siswa = load_siswa() if siswa is None else siswa
    df = normalisasi_kelas(df)
    return {
        'poin_beda_default': anomali_poin_beda_default(df),
        'nis_tidak_dikenal': anomali_nis_tidak_dikenal(df, siswa),
        'duplikat_kandidat': anomali_duplikat(df),
        'tanggal_mendahului_input': anomali_tanggal_mendahului_input(df),
    }


def rekap_per_siswa(df, siswa=None):
    kolom = ['nis', 'nama', 'kelas', 'absen', 'poin_plus', 'poin_minus', 'netto', 'jumlah_entri']
    data = normalisasi_kelas(df)
    if data.empty:
        return pd.DataFrame(columns=kolom)
    data = data.copy()
    data['poin_plus'] = data['poin'].clip(lower=0)
    data['poin_minus'] = data['poin'].clip(upper=0)
    rekap = data.groupby('nis').agg(
        nama=('nama_siswa', 'first'),
        kelas=('kelas', 'first'),
        absen=('absen', 'first'),
        poin_plus=('poin_plus', 'sum'),
        poin_minus=('poin_minus', 'sum'),
        netto=('poin', 'sum'),
        jumlah_entri=('poin', 'size'),
    ).reset_index()
    if siswa is not None and not siswa.empty:
        master = siswa.set_index('nis')
        rekap['nama'] = rekap['nis'].map(master['nama']).fillna(rekap['nama'])
        rekap['kelas'] = rekap['nis'].map(master['kelas']).fillna(rekap['kelas'])
        if 'absen' in master.columns:
            rekap['absen'] = rekap['nis'].map(master['absen']).fillna(rekap['absen'])
    return rekap.sort_values('netto').reset_index(drop=True)[kolom]


def rekap_per_kelas(df):
    kolom = ['kelas', 'poin_plus', 'poin_minus', 'netto', 'jumlah_entri', 'jumlah_siswa']
    data = normalisasi_kelas(df)
    if data.empty:
        return pd.DataFrame(columns=kolom)
    data = data.copy()
    data['poin_plus'] = data['poin'].clip(lower=0)
    data['poin_minus'] = data['poin'].clip(upper=0)
    rekap = data.groupby('kelas').agg(
        poin_plus=('poin_plus', 'sum'),
        poin_minus=('poin_minus', 'sum'),
        netto=('poin', 'sum'),
        jumlah_entri=('poin', 'size'),
        jumlah_siswa=('nis', 'nunique'),
    ).reset_index()
    return rekap.sort_values('netto').reset_index(drop=True)[kolom]


def rekap_per_subkategori(df):
    kolom = ['subkategori', 'kategori', 'poin_plus', 'poin_minus', 'netto', 'jumlah_entri', 'jumlah_siswa']
    if df.empty or 'subkategori' not in df.columns:
        return pd.DataFrame(columns=kolom)
    data = df.copy()
    data['subkategori'] = data['subkategori'].fillna('tanpa_pasal')
    data['kategori'] = data['kategori'].fillna('tanpa_pasal')
    data['poin_plus'] = data['poin'].clip(lower=0)
    data['poin_minus'] = data['poin'].clip(upper=0)
    rekap = data.groupby('subkategori').agg(
        kategori=('kategori', 'first'),
        poin_plus=('poin_plus', 'sum'),
        poin_minus=('poin_minus', 'sum'),
        netto=('poin', 'sum'),
        jumlah_entri=('poin', 'size'),
        jumlah_siswa=('nis', 'nunique'),
    ).reset_index()
    return rekap.sort_values('jumlah_entri', ascending=False).reset_index(drop=True)[kolom]


def _entri_siswa(df, nis):
    if df is None or df.empty or 'nis' not in df.columns:
        return df.iloc[0:0] if df is not None else pd.DataFrame()
    return df[df['nis'].astype(str) == str(nis)]


def _hanya_orang_tua(df):
    if df.empty or 'subkategori' not in df.columns:
        return df.iloc[0:0]
    return df[df['subkategori'] == SUBKATEGORI_ORANG_TUA]


def daftar_pilihan_siswa(df, siswa=None):
    kolom = ['nis', 'nama', 'kelas', 'label']
    bagian = []
    if df is not None and not df.empty and 'nis' in df.columns:
        urut = normalisasi_kelas(df).sort_values('tanggal_kejadian')
        jurnal = urut.groupby(urut['nis'].astype(str)).agg(
            nama=('nama_siswa', 'last'), kelas=('kelas', 'last')).reset_index()
        jurnal = jurnal.rename(columns={'nis': 'nis'})
        bagian.append(jurnal)
    if siswa is not None and not siswa.empty:
        master = siswa.copy()
        master['nis'] = master['nis'].astype(str)
        bagian.append(master[['nis', 'nama', 'kelas']])
    if not bagian:
        return pd.DataFrame(columns=kolom)
    gabung = pd.concat(bagian, ignore_index=True)
    gabung = gabung.drop_duplicates(subset='nis', keep='last').reset_index(drop=True)
    gabung['nama'] = gabung['nama'].fillna('')
    gabung['kelas'] = gabung['kelas'].fillna('')
    gabung['label'] = gabung['nis'] + ' - ' + gabung['nama'].astype(str) + ' (' + gabung['kelas'].astype(str) + ')'
    return gabung.sort_values(['kelas', 'nama']).reset_index(drop=True)[kolom]


def _teks(nilai):
    return '' if nilai is None or pd.isna(nilai) else str(nilai).strip()


def profil_siswa(df, nis, siswa=None):
    entri = normalisasi_kelas(_entri_siswa(df, nis))
    nama = kelas = absen = ''
    if siswa is not None and not siswa.empty:
        master = siswa[siswa['nis'].astype(str) == str(nis)]
        if not master.empty:
            nama = _teks(master.iloc[0]['nama'])
            kelas = _teks(master.iloc[0]['kelas'])
            absen = _teks(master.iloc[0]['absen']) if 'absen' in master.columns else ''
    sumber_identitas = 'master_siswa' if nama else 'jurnal'
    if not entri.empty:
        terakhir = entri.sort_values('tanggal_kejadian').iloc[-1]
        nama = nama or _teks(terakhir['nama_siswa'])
        kelas = kelas or _teks(terakhir['kelas'])
        absen = absen or _teks(terakhir['absen'])
    inti = entri
    orang_tua = _hanya_orang_tua(entri)
    return {
        'nis': str(nis),
        'nama': nama,
        'kelas': kelas,
        'absen': absen,
        'sumber_identitas': sumber_identitas if not entri.empty or nama else 'tidak_ditemukan',
        'poin_prestasi': int(inti['poin'].clip(lower=0).sum()) if not inti.empty else 0,
        'poin_pelanggaran': int(inti['poin'].clip(upper=0).sum()) if not inti.empty else 0,
        'netto': int(inti['poin'].sum()) if not inti.empty else 0,
        'jumlah_entri': int(len(inti)),
        'poin_orang_tua': int(orang_tua['poin'].sum()) if not orang_tua.empty else 0,
        'jumlah_entri_orang_tua': int(len(orang_tua)),
    }


def riwayat_siswa(df, nis):
    kolom = ['id', 'tanggal_kejadian', 'kelas', 'absen', 'kode_pasal', 'deskripsi', 'kategori', 'subkategori',
             'poin', 'judul', 'keterangan', 'petugas']
    entri = normalisasi_kelas(_entri_siswa(df, nis))
    if entri.empty:
        return pd.DataFrame(columns=kolom)
    hasil = entri.reindex(columns=kolom)
    return hasil.sort_values('tanggal_kejadian', ascending=False).reset_index(drop=True)


def kumulatif_netto_siswa(df, nis):
    kolom = ['tanggal_kejadian', 'poin', 'netto_kumulatif']
    entri = _entri_siswa(df, nis)
    if entri.empty:
        return pd.DataFrame(columns=kolom)
    data = entri.copy()
    data['tanggal_kejadian'] = pd.to_datetime(data['tanggal_kejadian'], errors='coerce')
    harian = data.groupby('tanggal_kejadian', as_index=False)['poin'].sum().sort_values('tanggal_kejadian')
    harian['netto_kumulatif'] = harian['poin'].cumsum()
    return harian.reset_index(drop=True)[kolom]


def entri_per_subkategori_siswa(df, nis):
    kolom = ['subkategori', 'jumlah_entri', 'total_poin']
    entri = _entri_siswa(df, nis)
    if entri.empty or 'subkategori' not in entri.columns:
        return pd.DataFrame(columns=kolom)
    data = entri.copy()
    data['subkategori'] = data['subkategori'].fillna('tanpa_pasal')
    hasil = data.groupby('subkategori').agg(
        jumlah_entri=('poin', 'size'), total_poin=('poin', 'sum')).reset_index()
    return hasil.sort_values('jumlah_entri', ascending=False).reset_index(drop=True)[kolom]


def pelanggaran_berulang(df, minimal=2):
    kolom = ['nis', 'nama', 'kelas', 'absen', 'kode_pasal', 'deskripsi', 'jumlah_entri', 'total_poin']
    if df is None or df.empty or 'kode_pasal' not in df.columns:
        return pd.DataFrame(columns=kolom)
    data = normalisasi_kelas(df)
    data = data[data['poin'] < 0].copy()
    if data.empty:
        return pd.DataFrame(columns=kolom)
    data['nis'] = data['nis'].astype(str)
    hasil = data.groupby(['nis', 'kode_pasal']).agg(
        nama=('nama_siswa', 'last'),
        kelas=('kelas', 'last'),
        absen=('absen', 'last'),
        deskripsi=('deskripsi', 'first') if 'deskripsi' in data.columns else ('judul', 'first'),
        jumlah_entri=('poin', 'size'),
        total_poin=('poin', 'sum'),
    ).reset_index()
    hasil = hasil[hasil['jumlah_entri'] >= int(minimal)]
    if hasil.empty:
        return pd.DataFrame(columns=kolom)
    return hasil.sort_values(['jumlah_entri', 'total_poin'], ascending=[False, True]).reset_index(drop=True)[kolom]


def eskalasi_tahapan(df, tahapan=None):
    kolom = ['nis', 'nama', 'kelas', 'absen', 'rantai', 'kode_tertinggi', 'tahap', 'tahap_maks',
             'di_tahap_tertinggi', 'jumlah_entri', 'total_poin']
    tahapan = TAHAPAN_PASAL if tahapan is None else tahapan
    if df is None or df.empty or 'kode_pasal' not in df.columns:
        return pd.DataFrame(columns=kolom)
    df = normalisasi_kelas(df)
    baris = []
    for rantai, kode_urut in tahapan.items():
        urutan = {kode: posisi + 1 for posisi, kode in enumerate(kode_urut)}
        data = df[df['kode_pasal'].isin(kode_urut)].copy()
        if data.empty:
            continue
        data['nis'] = data['nis'].astype(str)
        data['tahap'] = data['kode_pasal'].map(urutan)
        for nis, kelompok in data.groupby('nis'):
            puncak = kelompok.loc[kelompok['tahap'].idxmax()]
            terakhir = kelompok.sort_values('tanggal_kejadian').iloc[-1]
            baris.append({
                'nis': nis,
                'nama': terakhir['nama_siswa'],
                'kelas': terakhir['kelas'],
                'absen': terakhir['absen'],
                'rantai': rantai,
                'kode_tertinggi': puncak['kode_pasal'],
                'tahap': int(puncak['tahap']),
                'tahap_maks': len(kode_urut),
                'di_tahap_tertinggi': bool(int(puncak['tahap']) == len(kode_urut)),
                'jumlah_entri': int(len(kelompok)),
                'total_poin': int(kelompok['poin'].sum()),
            })
    if not baris:
        return pd.DataFrame(columns=kolom)
    hasil = pd.DataFrame(baris)
    return hasil.sort_values(['tahap', 'jumlah_entri'], ascending=[False, False]).reset_index(drop=True)[kolom]


def siswa_berisiko(df, ambang=None, siswa=None):
    kolom = ['nis', 'nama', 'kelas', 'absen', 'poin_plus', 'poin_minus', 'netto', 'jumlah_entri', 'melewati_ambang']
    rekap = rekap_per_siswa(df, siswa)
    if rekap.empty:
        return pd.DataFrame(columns=kolom)
    hasil = rekap.copy()
    if ambang is None:
        hasil['melewati_ambang'] = False
    else:
        hasil['melewati_ambang'] = hasil['poin_minus'] <= -abs(int(ambang))
    return hasil.sort_values(['poin_minus', 'netto']).reset_index(drop=True)[kolom]


def analisis_per_pasal(df):
    kolom = ['kode_pasal', 'deskripsi', 'kategori', 'subkategori', 'jumlah_entri', 'total_poin', 'jumlah_siswa']
    if df is None or df.empty or 'kode_pasal' not in df.columns:
        return pd.DataFrame(columns=kolom)
    data = df.copy()
    for field in ['deskripsi', 'kategori', 'subkategori']:
        if field not in data.columns:
            data[field] = 'tanpa_pasal'
        data[field] = data[field].fillna('tanpa_pasal')
    hasil = data.groupby('kode_pasal').agg(
        deskripsi=('deskripsi', 'first'),
        kategori=('kategori', 'first'),
        subkategori=('subkategori', 'first'),
        jumlah_entri=('poin', 'size'),
        total_poin=('poin', 'sum'),
        jumlah_siswa=('nis', 'nunique'),
    ).reset_index()
    return hasil.sort_values('jumlah_entri', ascending=False).reset_index(drop=True)[kolom]


def top_pelanggar_per_pasal(df, jumlah_teratas=3):
    kolom = ['kode_pasal', 'nis', 'nama', 'kelas', 'absen', 'jumlah_entri', 'total_poin']
    if df is None or df.empty or 'kode_pasal' not in df.columns:
        return pd.DataFrame(columns=kolom)
    data = normalisasi_kelas(df)
    data = data[data['poin'] < 0].copy()
    if data.empty:
        return pd.DataFrame(columns=kolom)
    data['nis'] = data['nis'].astype(str)
    hasil = data.groupby(['kode_pasal', 'nis']).agg(
        nama=('nama_siswa', 'last'),
        kelas=('kelas', 'last'),
        absen=('absen', 'last'),
        jumlah_entri=('poin', 'size'),
        total_poin=('poin', 'sum'),
    ).reset_index()
    hasil = hasil.sort_values(['kode_pasal', 'jumlah_entri', 'total_poin'], ascending=[True, False, True])
    hasil = hasil.groupby('kode_pasal').head(int(jumlah_teratas))
    return hasil.reset_index(drop=True)[kolom]


def tingkat_dari_kelas(kelas):
    nilai = pd.Series(kelas, dtype='object').fillna('').astype(str).str.strip()
    tingkat = nilai.str.extract(r'^(10|11|12)-', expand=False)
    return tingkat.fillna('lainnya')


def analisis_per_tingkat(df):
    kolom = ['tingkat', 'poin_plus', 'poin_minus', 'netto', 'jumlah_entri', 'jumlah_siswa', 'jumlah_kelas']
    data = normalisasi_kelas(df) if df is not None else None
    if data is None or data.empty or 'kelas' not in data.columns:
        return pd.DataFrame(columns=kolom)
    data = data.copy()
    data['tingkat'] = tingkat_dari_kelas(data['kelas']).values
    data['poin_plus'] = data['poin'].clip(lower=0)
    data['poin_minus'] = data['poin'].clip(upper=0)
    hasil = data.groupby('tingkat').agg(
        poin_plus=('poin_plus', 'sum'),
        poin_minus=('poin_minus', 'sum'),
        netto=('poin', 'sum'),
        jumlah_entri=('poin', 'size'),
        jumlah_siswa=('nis', 'nunique'),
        jumlah_kelas=('kelas', 'nunique'),
    ).reset_index()
    return hasil.sort_values('tingkat').reset_index(drop=True)[kolom]


def peringkat_kelas(df):
    kolom = ['kelas', 'tingkat', 'poin_plus', 'poin_minus', 'netto', 'jumlah_entri',
             'jumlah_siswa', 'rata_rata_netto']
    rekap = rekap_per_kelas(df)
    if rekap.empty:
        return pd.DataFrame(columns=kolom)
    hasil = rekap.copy()
    hasil['tingkat'] = tingkat_dari_kelas(hasil['kelas']).values
    hasil['rata_rata_netto'] = (hasil['netto'] / hasil['jumlah_siswa']).round(2)
    return hasil.sort_values('netto').reset_index(drop=True)[kolom]


def statistik_petugas(df):
    kolom = ['petugas', 'jumlah_entri', 'jumlah_pelanggaran', 'jumlah_prestasi', 'jumlah_siswa',
             'total_poin', 'tanggal_awal', 'tanggal_akhir']
    if df is None or df.empty or 'petugas' not in df.columns:
        return pd.DataFrame(columns=kolom)
    data = df.copy()
    data['petugas'] = data['petugas'].fillna('').replace('', 'tanpa_petugas')
    data['tanggal'] = pd.to_datetime(data['tanggal_kejadian'], errors='coerce')
    data['jumlah_pelanggaran'] = (data['poin'] < 0).astype(int)
    data['jumlah_prestasi'] = (data['poin'] > 0).astype(int)
    hasil = data.groupby('petugas').agg(
        jumlah_entri=('poin', 'size'),
        jumlah_pelanggaran=('jumlah_pelanggaran', 'sum'),
        jumlah_prestasi=('jumlah_prestasi', 'sum'),
        jumlah_siswa=('nis', 'nunique'),
        total_poin=('poin', 'sum'),
        tanggal_awal=('tanggal', 'min'),
        tanggal_akhir=('tanggal', 'max'),
    ).reset_index()
    for field in ['tanggal_awal', 'tanggal_akhir']:
        hasil[field] = hasil[field].dt.strftime('%Y-%m-%d')
    return hasil.sort_values('jumlah_entri', ascending=False).reset_index(drop=True)[kolom]


def distribusi_kategori_petugas(df):
    if df is None or df.empty or 'petugas' not in df.columns or 'kategori' not in df.columns:
        return pd.DataFrame(columns=['petugas'])
    data = df.copy()
    data['petugas'] = data['petugas'].fillna('').replace('', 'tanpa_petugas')
    data['kategori'] = data['kategori'].fillna('tanpa_pasal')
    tabel = pd.crosstab(data['petugas'], data['kategori'])
    tabel.columns.name = None
    return tabel.reset_index()


def tren_bulanan(df):
    kolom = ['bulan', 'pelanggaran', 'prestasi', 'netto']
    if df is None or df.empty or 'tanggal_kejadian' not in df.columns:
        return pd.DataFrame(columns=kolom)
    data = df.copy()
    data['tanggal'] = pd.to_datetime(data['tanggal_kejadian'], errors='coerce')
    data = data[data['tanggal'].notna()]
    if data.empty:
        return pd.DataFrame(columns=kolom)
    data['bulan'] = data['tanggal'].dt.strftime('%Y-%m')
    data['pelanggaran'] = (data['poin'] < 0).astype(int)
    data['prestasi'] = (data['poin'] > 0).astype(int)
    hasil = data.groupby('bulan').agg(
        pelanggaran=('pelanggaran', 'sum'),
        prestasi=('prestasi', 'sum'),
        netto=('poin', 'sum'),
    ).reset_index()
    return hasil.sort_values('bulan').reset_index(drop=True)[kolom]


def distribusi_hari_pelanggaran(df):
    kolom = ['hari', 'jumlah_entri', 'total_poin']
    if df is None or df.empty or 'tanggal_kejadian' not in df.columns:
        return pd.DataFrame(columns=kolom)
    data = df[df['poin'] < 0].copy()
    data['tanggal'] = pd.to_datetime(data['tanggal_kejadian'], errors='coerce')
    data = data[data['tanggal'].notna()]
    if data.empty:
        return pd.DataFrame(columns=kolom)
    data['indeks_hari'] = data['tanggal'].dt.day_of_week
    hasil = data.groupby('indeks_hari').agg(
        jumlah_entri=('poin', 'size'), total_poin=('poin', 'sum')).reset_index()
    hasil['hari'] = hasil['indeks_hari'].map(lambda posisi: NAMA_HARI[posisi])
    return hasil.sort_values('indeks_hari').reset_index(drop=True)[kolom]


def konsentrasi_pelanggaran(df):
    kolom = ['nis', 'nama', 'kelas', 'total_poin', 'jumlah_entri', 'persen', 'persen_kumulatif']
    if df is None or df.empty or 'poin' not in df.columns:
        return pd.DataFrame(columns=kolom)
    data = normalisasi_kelas(df)
    data = data[data['poin'] < 0].copy()
    if data.empty:
        return pd.DataFrame(columns=kolom)
    data['nis'] = data['nis'].astype(str)
    data['poin_mutlak'] = data['poin'].abs()
    hasil = data.groupby('nis').agg(
        nama=('nama_siswa', 'last'),
        kelas=('kelas', 'last'),
        total_poin=('poin_mutlak', 'sum'),
        jumlah_entri=('poin', 'size'),
    ).reset_index()
    hasil = hasil.sort_values(['total_poin', 'jumlah_entri'], ascending=[False, False]).reset_index(drop=True)
    total = hasil['total_poin'].sum()
    hasil['persen'] = hasil['total_poin'] / total * 100 if total else 0.0
    hasil['persen_kumulatif'] = hasil['persen'].cumsum()
    return hasil[kolom]


def siswa_penyumbang(df, ambang=50):
    data = konsentrasi_pelanggaran(df)
    if data.empty:
        return {'jumlah': 0, 'persen_siswa': 0.0, 'total_siswa': 0}
    kena = data[data['persen_kumulatif'] >= ambang]
    jumlah = int(kena.index[0]) + 1 if not kena.empty else int(len(data))
    return {'jumlah': jumlah, 'persen_siswa': jumlah / len(data) * 100, 'total_siswa': int(len(data))}


def peta_panas_pasal_kelas(df, dasar='jumlah_kejadian', batas_pasal=15):
    if df is None or df.empty or 'kode_pasal' not in df.columns or 'poin' not in df.columns:
        return pd.DataFrame()
    data = normalisasi_kelas(df)
    data = data[data['poin'] < 0].copy()
    if data.empty:
        return pd.DataFrame()
    data['nilai'] = 1 if dasar == 'jumlah_kejadian' else data['poin'].abs()
    urutan_pasal = (data.groupby('kode_pasal')['nilai'].sum()
                    .sort_values(ascending=False).head(int(batas_pasal)).index.tolist())
    data = data[data['kode_pasal'].isin(urutan_pasal)]
    pivot = data.pivot_table(index='kode_pasal', columns='kelas', values='nilai',
                             aggfunc='sum', fill_value=0)
    pivot = pivot.reindex(urutan_pasal)
    return pivot.loc[:, sorted(pivot.columns, key=lambda nilai: str(nilai))]


def hapus_jurnal(ids, confirmed=False, user='operator'):
    if not confirmed:
        raise ValueError('Konfirmasi eksplisit diperlukan')
    ids = [int(value) for value in ids]
    if not ids:
        raise ValueError('Tidak ada baris yang dipilih')
    conn = get_conn()
    conn.isolation_level = None
    try:
        conn.execute('BEGIN IMMEDIATE')
        try:
            cursor = conn.execute(
                f"DELETE FROM jurnal WHERE id IN ({','.join(['?'] * len(ids))})", ids)
            terhapus = cursor.rowcount
            conn.execute(
                'INSERT INTO import_log (waktu,nama_file,jumlah_baris,berhasil,gagal,duplikat,user) '
                "VALUES (?,?,?,?,?,?,?)",
                (_waktu_sekarang(), f'hapus_jurnal:{",".join(str(i) for i in ids)}', len(ids), 0, terhapus, 0, user)
            )
            conn.execute('COMMIT')
            return terhapus
        except Exception:
            conn.execute('ROLLBACK')
            raise
    finally:
        conn.close()


def import_terakhir():
    conn = get_conn()
    try:
        baris = conn.execute(
            "SELECT id, nama_file, berhasil FROM import_log "
            "WHERE nama_file NOT LIKE 'hapus_jurnal:%' AND di_rollback = 0 "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not baris:
            return None
        import_id, nama_file, berhasil = baris
        jumlah = conn.execute(
            'SELECT COUNT(*) FROM jurnal WHERE import_id = ?', (import_id,)
        ).fetchone()[0]
        return import_id, nama_file, jumlah
    finally:
        conn.close()


def ringkasan_mingguan(jurnal, tanggal_awal_minggu):
    awal = pd.Timestamp(tanggal_awal_minggu).normalize()
    awal = awal - pd.Timedelta(days=awal.dayofweek)
    akhir = awal + pd.Timedelta(days=6)
    awal_lalu = awal - pd.Timedelta(days=7)
    akhir_lalu = awal - pd.Timedelta(days=1)

    hasil = {
        'minggu_ini': {'kejadian': 0, 'total_poin': 0},
        'minggu_lalu': {'kejadian': 0, 'total_poin': 0},
        'selisih': {'kejadian': 0, 'total_poin': 0},
        'persen': {'kejadian': None, 'total_poin': None},
        'pasal_teratas': [],
        'kelas_teratas': [],
        'murid_terbanyak': [],
        'murid_baru_melewati_ambang': [],
    }
    if jurnal is None or getattr(jurnal, 'empty', True):
        return hasil
    data = normalisasi_kelas(jurnal)
    if 'poin' not in data.columns or 'tanggal_kejadian' not in data.columns:
        return hasil
    data = data[data['poin'] < 0].copy()
    if data.empty:
        return hasil
    data['tanggal'] = pd.to_datetime(data['tanggal_kejadian'], errors='coerce')
    data = data[data['tanggal'].notna()]
    if data.empty:
        return hasil
    data['tanggal'] = data['tanggal'].dt.normalize()
    data['nis'] = data['nis'].astype(str)
    data['poin_mutlak'] = data['poin'].abs()

    ini = data[(data['tanggal'] >= awal) & (data['tanggal'] <= akhir)]
    lalu = data[(data['tanggal'] >= awal_lalu) & (data['tanggal'] <= akhir_lalu)]

    hasil['minggu_ini'] = {'kejadian': int(len(ini)), 'total_poin': float(ini['poin_mutlak'].sum())}
    hasil['minggu_lalu'] = {'kejadian': int(len(lalu)), 'total_poin': float(lalu['poin_mutlak'].sum())}
    for kunci in ('kejadian', 'total_poin'):
        beda = hasil['minggu_ini'][kunci] - hasil['minggu_lalu'][kunci]
        hasil['selisih'][kunci] = beda
        dasar = hasil['minggu_lalu'][kunci]
        hasil['persen'][kunci] = None if not dasar else beda / dasar * 100

    if not ini.empty:
        pasal = ini.groupby('kode_pasal').agg(
            jumlah_kejadian=('poin', 'size'), total_poin=('poin_mutlak', 'sum')).reset_index()
        pasal = pasal.sort_values(['jumlah_kejadian', 'total_poin'], ascending=[False, False])
        hasil['pasal_teratas'] = pasal.head(3).to_dict('records')

        kelas = ini.groupby('kelas').agg(
            jumlah_kejadian=('poin', 'size'), total_poin=('poin_mutlak', 'sum')).reset_index()
        kelas = kelas.sort_values(['jumlah_kejadian', 'total_poin'], ascending=[False, False])
        hasil['kelas_teratas'] = kelas.head(3).to_dict('records')

        murid = ini.groupby('nis').agg(
            nama=('nama_siswa', 'last'),
            kelas=('kelas', 'last'),
            jumlah_kejadian=('poin', 'size'),
            total_poin=('poin_mutlak', 'sum'),
        ).reset_index()
        murid = murid.sort_values(['jumlah_kejadian', 'total_poin'], ascending=[False, False])
        hasil['murid_terbanyak'] = murid.head(5).to_dict('records')

    def _item(item):
        if isinstance(item, dict):
            return item.get('threshold', 0), item.get('label')
        return getattr(item, 'threshold', 0), getattr(item, 'label', None)

    ambang_min = min(_item(item)[0] for item in THRESHOLDS_SP)

    def _tingkat(total):
        level = None
        for item in THRESHOLDS_SP:
            ambang, label = _item(item)
            if ambang < 0 and total >= abs(ambang):
                level = label
        return level

    def _peringkat(label):
        for i, item in enumerate(THRESHOLDS_SP):
            if _item(item)[1] == label:
                return i
        return -1

    if ambang_min < 0:
        kumulatif = data[data['tanggal'] <= akhir].groupby('nis').agg(
            nama=('nama_siswa', 'last'),
            kelas=('kelas', 'last'),
            sampai_ini=('poin_mutlak', 'sum'),
        ).reset_index()
        sampai_lalu = data[data['tanggal'] <= akhir_lalu].groupby('nis')['poin_mutlak'].sum()
        kumulatif['sampai_lalu'] = kumulatif['nis'].map(sampai_lalu).fillna(0.0).astype(float)
        kumulatif['sampai_ini'] = kumulatif['sampai_ini'].astype(float)
        kumulatif['tingkat_lalu'] = kumulatif['sampai_lalu'].map(_tingkat)
        kumulatif['tingkat_ini'] = kumulatif['sampai_ini'].map(_tingkat)
        kumulatif['_peringkat_ini'] = kumulatif['tingkat_ini'].map(_peringkat)
        kumulatif['_peringkat_lalu'] = kumulatif['tingkat_lalu'].map(_peringkat)
        baru = kumulatif[(kumulatif['tingkat_ini'].notna()) & (kumulatif['_peringkat_ini'] > kumulatif['_peringkat_lalu'])]
        baru = baru.sort_values(['_peringkat_ini', 'sampai_ini'], ascending=[False, False])
        hasil['murid_baru_melewati_ambang'] = baru[
            ['nis', 'nama', 'kelas', 'sampai_lalu', 'sampai_ini', 'tingkat_lalu', 'tingkat_ini']
        ].to_dict('records')
    return hasil


def rollback_import_terakhir():
    conn = get_conn()
    conn.isolation_level = None
    try:
        conn.execute('BEGIN IMMEDIATE')
        try:
            baris = conn.execute(
                "SELECT id FROM import_log "
                "WHERE nama_file NOT LIKE 'hapus_jurnal:%' AND di_rollback = 0 "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not baris:
                conn.execute('ROLLBACK')
                raise ValueError('Tidak ada import yang dapat di-rollback')
            import_id = baris[0]
            cursor = conn.execute('DELETE FROM jurnal WHERE import_id = ?', (import_id,))
            terhapus = cursor.rowcount
            conn.execute('UPDATE import_log SET di_rollback = 1 WHERE id = ?', (import_id,))
            conn.execute('COMMIT')
            return terhapus
        except Exception:
            conn.execute('ROLLBACK')
            raise
    finally:
        conn.close()
