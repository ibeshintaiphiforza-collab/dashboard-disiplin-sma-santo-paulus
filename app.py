import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).parent))

from core.analytics import load_jurnal, load_siswa
from core.db import init_db, load_referensi_pasal
from core.theme import (header_halaman, hero_beranda, inject_css, kartu_kpi, kartu_tautan,
                        sidebar_brand)

st.set_page_config(
    page_title="Dashboard Disiplin & Prestasi",
    page_icon="📊",
    layout="wide"
)

init_db()
load_referensi_pasal()

inject_css()
sidebar_brand()
hero_beranda()

jurnal = load_jurnal()
siswa = load_siswa()

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
kartu_kpi(kolom2, 'Siswa Terdata', f'{jumlah_siswa:,}', 'Siswa pada jurnal dan master siswa', 'prestasi')
kartu_kpi(kolom3, 'Kelas Terdata', f'{jumlah_kelas:,}', 'Kelas aktif pada data saat ini', 'netral')

st.write('')

kolom_dashboard, kolom_analisis, kolom_import = st.columns(3)
kartu_tautan(kolom_dashboard, 'Dashboard', 'Visualisasi ringkasan komposisi entri, tren bulanan, '
             'poin per kelas, heatmap, dan leaderboard siswa.', '📊')
with kolom_dashboard:
    st.page_link('pages/1_📊_Dashboard.py', label='Buka Dashboard', width='stretch')

kartu_tautan(kolom_analisis, 'Analisis', 'Pelanggaran Berulang, rantai eskalasi, early warning, statistik petugas, '
             'dan tren waktu lintas kelas.', '🔎')
with kolom_analisis:
    st.page_link('pages/2_Analisis.py', label='Buka Analisis', width='stretch')

kartu_tautan(kolom_import, 'Import CSV', 'Impor jalur paste e-Guru atau unggah CSV, lengkap dengan '
             'pratinjau validasi sebelum disimpan.', '📥')
with kolom_import:
    st.page_link('pages/4_Import_CSV.py', label='Buka Import CSV', width='stretch')

st.write('')
header_halaman('Mulai dari mana?', 'Alur singkat penyiapan data sampai pembacaan laporan.')
st.markdown(
    '- **Import CSV** atau **Master Siswa** untuk memasukkan data awal.\n'
    '- **Dashboard** untuk ringkasan visual, **Analisis** untuk pola dan peringatan dini.\n'
    '- **Olah Data** untuk tabel interaktif, ekspor CSV/Excel, dan unduhan PDF.\n'
    '- **Profil Siswa** untuk rapor poin per siswa beserta riwayat entrinya.'
)
