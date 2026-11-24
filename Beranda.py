import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).parent))

from core.session import cached_jurnal, cached_siswa, ensure_init
from core.theme import (header_halaman, hero_beranda, inject_css, kartu_kpi, kartu_tautan,
                        sidebar_brand)

st.set_page_config(
    page_title="Dashboard Disiplin & Prestasi",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

ensure_init()

inject_css()
sidebar_brand()
hero_beranda()

jurnal = cached_jurnal()
siswa = cached_siswa()

jumlah_entri = 0 if jurnal is None or jurnal.empty else int(len(jurnal))
jumlah_siswa = 0
if jurnal is not None and not jurnal.empty:
    jumlah_siswa = int(jurnal['nis'].nunique())
if siswa is not None and not siswa.empty:
    jumlah_siswa = max(jumlah_siswa, int(siswa['nis'].nunique()))
jumlah_kelas = 0
if jurnal is not None and not jurnal.empty:
    jumlah_kelas = int(jurnal['kelas'].dropna().astype(str).str.strip().replace('', None).dropna().nunique())
if siswa is not None and not siswa.empty:
    kelas_master = siswa['kelas'].dropna().astype(str).str.strip().replace('', None).dropna()
    jumlah_kelas = max(jumlah_kelas, int(kelas_master.nunique()))

kolom1, kolom2, kolom3 = st.columns(3)
kartu_kpi(kolom1, 'Entri Jurnal', f'{jumlah_entri:,}', 'Seluruh catatan disiplin dan prestasi', 'emas')
kartu_kpi(kolom2, 'Murid Terdata', f'{jumlah_siswa:,}', 'Murid pada jurnal dan master murid', 'prestasi')
kartu_kpi(kolom3, 'Kelas Terdata', f'{jumlah_kelas:,}', 'Kelas aktif pada data saat ini', 'netral')

st.write('')

kolom_dashboard, kolom_analisis, kolom_import = st.columns(3)
with kolom_dashboard:
    with st.container(key="kartu_dashboard"):
        kartu_tautan(st, 'Dashboard', 'Visualisasi ringkasan komposisi entri, tren bulanan, '
                     'poin per kelas, heatmap, dan leaderboard murid.', '📊')
        st.page_link('pages/1_📊_Dashboard.py', label='Buka Dashboard', width='stretch')

with kolom_analisis:
    with st.container(key="kartu_analisis"):
        kartu_tautan(st, 'Analisis', 'Pelanggaran Berulang, rantai eskalasi, early warning, statistik petugas, '
                     'dan tren waktu lintas kelas.', '🔎')
        st.page_link('pages/2_🔎_Analisis.py', label='Buka Analisis', width='stretch')

with kolom_import:
    with st.container(key="kartu_import"):
        kartu_tautan(st, 'Import CSV', 'Impor jalur paste e-Guru atau unggah CSV, lengkap dengan '
                     'pratinjau validasi sebelum disimpan.', '📥')
        st.page_link('pages/4_📥_Import_CSV.py', label='Buka Import CSV', width='stretch')

st.write('')

kolom_olah, kolom_master, kolom_profil = st.columns(3)
with kolom_olah:
    with st.container(key="kartu_olah"):
        kartu_tautan(st, 'Olah Data', 'Tabel interaktif, ekspor CSV/Excel, dan unduhan PDF.', '🗂️')
        st.page_link('pages/3_🗂️_Olah_Data.py', label='Buka Olah Data', width='stretch')
with kolom_master:
    with st.container(key="kartu_master"):
        kartu_tautan(st, 'Master Murid', 'Kelola data induk murid (NIS, nama, kelas).', '👥')
        st.page_link('pages/5_👥_Master_Murid.py', label='Buka Master Murid', width='stretch')
with kolom_profil:
    with st.container(key="kartu_profil"):
        kartu_tautan(st, 'Profil Murid', 'Rapor poin per murid beserta riwayat entrinya.', '👤')
        st.page_link('pages/6_👤_Profil_Murid.py', label='Buka Profil Murid', width='stretch')

st.write('')
header_halaman('Mulai dari mana?', 'Alur singkat penyiapan data sampai pembacaan laporan.')
st.markdown(
    '- **Import CSV** atau **Master Murid** untuk memasukkan data awal.\n'
    '- **Dashboard** untuk ringkasan visual, **Analisis** untuk pola dan peringatan dini.\n'
    '- **Olah Data** untuk tabel interaktif, ekspor CSV/Excel, dan unduhan PDF.\n'
    '- **Profil Murid** untuk rapor poin per murid beserta riwayat entrinya.'
)
