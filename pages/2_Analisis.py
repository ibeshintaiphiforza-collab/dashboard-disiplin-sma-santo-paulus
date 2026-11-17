import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))

from core import analytics_charts as charts
from core.analytics import (analisis_per_pasal, analisis_per_tingkat, distribusi_hari_pelanggaran,
                            distribusi_kategori_petugas, eskalasi_tahapan, load_siswa,
                            peringkat_kelas, pelanggaran_berulang, siswa_berisiko, statistik_petugas,
                            top_pelanggar_per_pasal, tren_bulanan)
from core.db import init_db, load_referensi_pasal
from core.export import to_csv_bytes, to_excel_bytes
from core.session import sidebar_filters
from core.theme import header_halaman, inject_css, kartu_kpi, sidebar_brand
from core.thresholds import THRESHOLDS_SP, status_peringatan

st.set_page_config(page_title='Analisis', layout='wide')
inject_css()
sidebar_brand()
header_halaman('Analisis',
               'Pola pelanggaran berulang, peringatan dini, statistik per pasal, kelas, dan petugas.')
init_db()
load_referensi_pasal()

jurnal = sidebar_filters()
siswa = load_siswa()

if jurnal.empty:
    st.info('Belum ada data jurnal yang sesuai filter. Ubah filter di sidebar atau import data terlebih dahulu.')
    st.stop()


def tabel_dengan_ekspor(data, nama, pesan_kosong):
    if data.empty:
        st.info(pesan_kosong)
        return
    st.dataframe(data, width='stretch')
    kolom_csv, kolom_xlsx = st.columns(2)
    with kolom_csv:
        st.download_button(f'CSV {nama}', to_csv_bytes(data), f'{nama}.csv', 'text/csv', key=f'csv_{nama}')
    with kolom_xlsx:
        st.download_button(f'Excel {nama}', to_excel_bytes(data, nama), f'{nama}.xlsx',
                           'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                           key=f'xlsx_{nama}')


def tampilkan_gambar(gambar, pesan_kosong):
    if gambar is None:
        st.info(pesan_kosong)
    else:
        st.plotly_chart(gambar, width='stretch')


data_pelanggaran_berulang = pelanggaran_berulang(jurnal)
eskalasi = eskalasi_tahapan(jurnal)
pasal = analisis_per_pasal(jurnal)
top_pasal = top_pelanggar_per_pasal(jurnal)
tingkat = analisis_per_tingkat(jurnal)
kelas = peringkat_kelas(jurnal)
petugas = statistik_petugas(jurnal)
distribusi_petugas = distribusi_kategori_petugas(jurnal)
bulanan = tren_bulanan(jurnal)
harian = distribusi_hari_pelanggaran(jurnal)

with st.expander(f'1. Pelanggaran Berulang ({len(data_pelanggaran_berulang)})', expanded=True):
    st.caption('Siswa yang mengulang kode pasal yang sama, diurutkan dari frekuensi terbanyak.')
    tabel_dengan_ekspor(data_pelanggaran_berulang, 'pelanggaran_berulang', 'Tidak ada pengulangan pasal yang sama.')
    tampilkan_gambar(charts.fig_pelanggaran_berulang(jurnal), 'Tidak ada pengulangan pasal untuk digambarkan.')
    st.subheader('Rantai Eskalasi Pasal Bertingkat')
    st.caption('Rantai terlambat ME-02 sampai ME-07 dan buku Prestasi dan Disiplin ME-08 sampai ME-10.')
    if eskalasi.empty:
        st.info('Tidak ada entri pada pasal bertingkat.')
    else:
        puncak = eskalasi[eskalasi['di_tahap_tertinggi']]
        st.write(f'{len(puncak)} siswa berada pada tahap tertinggi rantai.')
        tabel_dengan_ekspor(eskalasi, 'eskalasi_tahapan', 'Tidak ada entri pada pasal bertingkat.')
    tampilkan_gambar(charts.fig_eskalasi(jurnal), 'Tidak ada entri pada pasal bertingkat untuk digambarkan.')

with st.expander('2. Early Warning (Siswa Berisiko)', expanded=False):
    st.info('Ambang surat peringatan resmi sekolah: SP I (-300), SP II (-400), SP III (-500), Rapat Dewan Guru (≤ -600).')
    berisiko = siswa_berisiko(jurnal, None, siswa)
    
    if not berisiko.empty:
        berisiko['status_sp'] = berisiko['poin_minus'].apply(status_peringatan)
        berisiko['label_sp'] = berisiko['status_sp'].apply(lambda x: x['label'])
        
        kolom_berisiko, _ = st.columns([1, 2])
        kartu_kpi(kolom_berisiko, 'Total Siswa Berisiko (≤ -300)',
                  f"{len(berisiko[berisiko['poin_minus'] <= -300]):,}", aksen='pelanggaran')
        for t in THRESHOLDS_SP:
            if t['threshold'] < 0:
                jumlah = len(berisiko[berisiko['poin_minus'] <= t['threshold']])
                st.write(f"**{t['label']}**: {jumlah} siswa")
        
        berisiko = berisiko.drop(columns=['status_sp'], errors='ignore')
    
    st.caption('Siswa diurutkan berdasarkan akumulasi poin pelanggaran.')
    tabel_dengan_ekspor(berisiko, 'siswa_berisiko', 'Belum ada data poin siswa.')
    tampilkan_gambar(charts.fig_early_warning(jurnal), 'Belum ada poin minus siswa untuk digambarkan.')

with st.expander('3. Analisis per Pasal', expanded=False):
    tabel_dengan_ekspor(pasal, 'analisis_per_pasal', 'Belum ada entri pasal.')
    tampilkan_gambar(charts.fig_pasal_frekuensi(jurnal), 'Belum ada entri pasal untuk digambarkan.')
    tampilkan_gambar(charts.fig_pasal_poin(jurnal), 'Belum ada poin pasal untuk digambarkan.')
    st.subheader('Pelanggar Terbanyak per Pasal')
    tabel_dengan_ekspor(top_pasal, 'top_pelanggar_per_pasal', 'Belum ada entri pelanggaran.')

with st.expander('4. Analisis per Kelas dan Tingkat', expanded=False):
    st.caption('Tingkat diturunkan dari awalan 10-, 11-, atau 12- pada kelas jurnal.')
    tabel_dengan_ekspor(tingkat, 'analisis_per_tingkat', 'Belum ada data kelas.')
    tampilkan_gambar(charts.fig_tingkat(jurnal), 'Belum ada data tingkat untuk digambarkan.')
    st.subheader('Peringkat per Kelas')
    tabel_dengan_ekspor(kelas, 'peringkat_kelas', 'Belum ada data kelas.')
    tampilkan_gambar(charts.fig_kelas(jurnal), 'Belum ada data kelas untuk digambarkan.')

with st.expander('5. Statistik Petugas', expanded=False):
    tabel_dengan_ekspor(petugas, 'statistik_petugas', 'Belum ada data petugas.')
    tampilkan_gambar(charts.fig_petugas(jurnal), 'Belum ada data petugas untuk digambarkan.')
    st.subheader('Distribusi Kategori per Petugas')
    tabel_dengan_ekspor(distribusi_petugas, 'distribusi_kategori_petugas', 'Belum ada data petugas.')

with st.expander('6. Tren Waktu', expanded=False):
    if bulanan.empty:
        st.info('Belum ada tanggal kejadian yang valid.')
    else:
        tampilkan_gambar(charts.fig_tren(jurnal), 'Belum ada tanggal kejadian yang valid.')
    tabel_dengan_ekspor(bulanan, 'tren_bulanan', 'Belum ada tanggal kejadian yang valid.')
    st.subheader('Distribusi Hari Pelanggaran')
    if harian.empty:
        st.info('Belum ada pelanggaran dengan tanggal valid.')
    else:
        tampilkan_gambar(charts.fig_hari(jurnal), 'Belum ada tanggal kejadian yang valid.')
    tabel_dengan_ekspor(harian, 'distribusi_hari_pelanggaran', 'Belum ada pelanggaran dengan tanggal valid.')
