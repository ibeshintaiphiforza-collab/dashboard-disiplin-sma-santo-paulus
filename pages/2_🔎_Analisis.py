import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))

from core import analytics_charts as charts
from core.analytics import (analisis_per_pasal, analisis_per_tingkat, distribusi_hari_pelanggaran,
                            distribusi_kategori_petugas, eskalasi_tahapan, konsentrasi_pelanggaran,
                            peta_panas_pasal_kelas, peringkat_kelas,
                            pelanggaran_berulang, ringkasan_mingguan, siswa_berisiko, siswa_penyumbang,
                            statistik_petugas, top_pelanggar_per_pasal, tren_bulanan)
from core.db import load_referensi_pasal
from core.pdf import buat_pdf_kandidat_penghargaan
from core.penghargaan import daftar_kandidat
from core.export import to_csv_bytes, to_excel_bytes
from core.session import cached_jurnal, cached_siswa, ensure_init, sidebar_filters
from core.theme import header_halaman, inject_css, kartu_kpi, sidebar_brand
from core.thresholds import THRESHOLDS_SP, status_peringatan

st.set_page_config(page_title='Analisis', layout='wide', initial_sidebar_state='expanded')
inject_css()
sidebar_brand()
header_halaman('Analisis',
               'Pola pelanggaran berulang, peringatan dini, statistik per pasal, kelas, dan petugas.')
ensure_init()

jurnal_penuh = cached_jurnal()
jurnal = sidebar_filters(jurnal_penuh, load=False)
siswa = cached_siswa()

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
kelas = peringkat_kelas(jurnal, siswa)
petugas = statistik_petugas(jurnal)
distribusi_petugas = distribusi_kategori_petugas(jurnal)
bulanan = tren_bulanan(jurnal)
harian = distribusi_hari_pelanggaran(jurnal)
konsentrasi = konsentrasi_pelanggaran(jurnal)

with st.expander(f'1. Pelanggaran Berulang ({len(data_pelanggaran_berulang)})', expanded=True):
    st.caption('Murid yang mengulang kode pasal yang sama, diurutkan dari frekuensi terbanyak.')
    tabel_dengan_ekspor(data_pelanggaran_berulang, 'pelanggaran_berulang', 'Tidak ada pengulangan pasal yang sama.')
    tampilkan_gambar(charts.fig_pelanggaran_berulang(jurnal), 'Tidak ada pengulangan pasal untuk digambarkan.')
    st.subheader('Rantai Eskalasi Pasal Bertingkat')
    st.caption('Rantai terlambat ME-02 sampai ME-07 dan buku Prestasi dan Disiplin ME-08 sampai ME-10.')
    if eskalasi.empty:
        st.info('Tidak ada entri pada pasal bertingkat.')
    else:
        puncak = eskalasi[eskalasi['di_tahap_tertinggi']]
        st.write(f'{len(puncak)} murid berada pada tahap tertinggi rantai.')
        tabel_dengan_ekspor(eskalasi, 'eskalasi_tahapan', 'Tidak ada entri pada pasal bertingkat.')
    tampilkan_gambar(charts.fig_eskalasi(jurnal), 'Tidak ada entri pada pasal bertingkat untuk digambarkan.')

with st.expander('2. Early Warning (Murid Berisiko)', expanded=False):
    st.info('Ambang surat peringatan resmi sekolah: SP I (-300), SP II (-400), SP III (-500), Rapat Dewan Guru (≤ -600).')
    berisiko = siswa_berisiko(jurnal, None, siswa)
    
    if not berisiko.empty:
        berisiko['status_sp'] = berisiko['poin_minus'].apply(status_peringatan)
        berisiko['label_sp'] = berisiko['status_sp'].apply(lambda x: x['label'])
        
        kolom_berisiko, _ = st.columns([1, 2])
        kartu_kpi(kolom_berisiko, 'Total Murid Berisiko (≤ -300)',
                  f"{len(berisiko[berisiko['poin_minus'] <= -300]):,}", aksen='pelanggaran')
        for t in THRESHOLDS_SP:
            if t['threshold'] < 0:
                jumlah = len(berisiko[berisiko['poin_minus'] <= t['threshold']])
                st.write(f"**{t['label']}**: {jumlah} murid")
        
        berisiko = berisiko.drop(columns=['status_sp'], errors='ignore')
    
    st.caption('Murid diurutkan berdasarkan akumulasi poin pelanggaran.')
    tabel_dengan_ekspor(berisiko, 'murid_berisiko', 'Belum ada data poin murid.')
    tampilkan_gambar(charts.fig_early_warning(jurnal), 'Belum ada poin minus murid untuk digambarkan.')

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
    tampilkan_gambar(charts.fig_kelas(jurnal, siswa), 'Belum ada data kelas untuk digambarkan.')

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

with st.expander('7. Konsentrasi Pelanggaran (Pareto)', expanded=False):
    st.caption('Pelanggaran terkonsentrasi pada sebagian murid; poin dihitung nilai mutlak.')
    if len(jurnal) < 30:
        st.info('Data belum cukup untuk kesimpulan yang andal')
    if konsentrasi.empty:
        st.info('Belum ada pelanggaran untuk dihitung.')
    else:
        for ambang in (50, 80):
            ringkas = siswa_penyumbang(jurnal, ambang)
            st.write(f"**{ringkas['jumlah']} murid ({ringkas['persen_siswa']:.1f}% dari "
                     f"{ringkas['total_siswa']} murid yang pernah melanggar)** menyumbang {ambang}% total poin.")
        atas = konsentrasi.head(30).copy()
        atas['label'] = atas['nama'].astype(str)
        gambar = go.Figure()
        gambar.add_trace(go.Bar(x=atas['label'], y=atas['total_poin_mutlak'], name='Total poin',
                                marker_color=charts.WARNA_MINUS))
        gambar.add_trace(go.Scatter(x=atas['label'], y=atas['persen_kumulatif'], name='Kumulatif (%)',
                                    yaxis='y2', mode='lines+markers'))
        gambar.update_layout(yaxis2=dict(overlaying='y', side='right', range=[0, 105],
                                         title='Persen kumulatif'))
        st.plotly_chart(gambar, width='stretch')
        tabel = konsentrasi.head(15)[['nama', 'kelas', 'total_poin_mutlak', 'jumlah_entri', 'persen_kumulatif']].copy()
        tabel = tabel.rename(columns={'total_poin_mutlak': 'Total Poin (mutlak)'})
        tabel['persen_kumulatif'] = tabel['persen_kumulatif'].round(1)
        tabel_dengan_ekspor(tabel, 'konsentrasi_pelanggaran', 'Belum ada pelanggaran untuk dihitung.')

with st.expander('8. Peta Panas Pasal x Kelas', expanded=False):
    st.caption('Pasal yang sering muncul terkonsentrasi pada kelas tertentu.')
    st.caption('Menampilkan 15 pasal teratas.')
    dasar = st.radio('Hitung berdasarkan', ['jumlah_kejadian', 'total_poin'], horizontal=True,
                     key='peta_panas_dasar')
    if len(jurnal) < 30:
        st.info('Data belum cukup untuk kesimpulan yang andal')
    pivot = peta_panas_pasal_kelas(jurnal, dasar)
    if pivot.empty:
        st.info('Belum ada pelanggaran untuk dipetakan.')
    else:
        st.dataframe(pivot, width='stretch')
        angka = pivot.replace(0, None)
        gambar = go.Figure(go.Heatmap(
            z=angka.values, x=[str(kolom) for kolom in angka.columns],
            y=[str(baris) for baris in angka.index], colorscale='YlOrRd', hoverongaps=False,
            text=angka.values, texttemplate='%{text}', textfont=dict(color='#111111')))
        gambar.update_layout(xaxis_title='Kelas', yaxis_title='Kode pasal')
        st.plotly_chart(gambar, width='stretch')

with st.expander('9. Ringkasan Mingguan', expanded=False):
    st.caption('Perbandingan kejadian dan poin minggu ini dengan minggu sebelumnya, dihitung nilai mutlak.')
    tanggal_jurnal = pd.to_datetime(jurnal['tanggal_kejadian'], errors='coerce').dropna()
    if tanggal_jurnal.empty:
        st.info('Belum ada tanggal kejadian yang valid.')
    else:
        senin_terakhir = tanggal_jurnal.max().normalize()
        senin_terakhir = senin_terakhir - pd.Timedelta(days=senin_terakhir.day_of_week)
        awal_minggu = st.date_input('Senin awal minggu', value=senin_terakhir.date(), key='ringkasan_minggu')
        ringkasan = ringkasan_mingguan(jurnal, awal_minggu)
        ini = ringkasan['minggu_ini']
        selisih = ringkasan['selisih']
        persen = ringkasan['persen']

        def _delta(kunci):
            teks = f"{selisih[kunci]:+.0f} dari minggu lalu"
            if persen[kunci] is not None:
                teks += f" ({persen[kunci]:+.1f}%)"
            return teks

        kolom_kejadian, kolom_poin = st.columns(2)
        with kolom_kejadian:
            st.metric('Kejadian minggu ini', f"{ini['kejadian']:.0f}", _delta('kejadian'))
        with kolom_poin:
            st.metric('Total poin minggu ini', f"{ini['total_poin']:.0f}", _delta('total_poin'))

        if ini['kejadian'] < 10:
            st.info('Data minggu ini sedikit, baca dengan hati-hati')

        st.subheader('3 Pasal Teratas')
        if ringkasan['pasal_teratas']:
            st.dataframe(pd.DataFrame(ringkasan['pasal_teratas']), width='stretch', hide_index=True)
        else:
            st.caption('Tidak ada')

        st.subheader('3 Kelas Teratas')
        if ringkasan['kelas_teratas']:
            st.dataframe(pd.DataFrame(ringkasan['kelas_teratas']), width='stretch', hide_index=True)
        else:
            st.caption('Tidak ada')

        st.subheader('5 Murid dengan Kejadian Terbanyak')
        if ringkasan['murid_terbanyak']:
            st.dataframe(pd.DataFrame(ringkasan['murid_terbanyak']), width='stretch', hide_index=True)
        else:
            st.caption('Tidak ada')

        st.subheader('Murid Naik Tingkat SP')
        if ringkasan['murid_baru_melewati_ambang']:
            naik = pd.DataFrame(ringkasan['murid_baru_melewati_ambang'])
            naik['tingkat_lalu'] = naik['tingkat_lalu'].apply(
                lambda nilai: 'Belum ada' if pd.isna(nilai) else nilai)
            st.dataframe(naik[['nama', 'kelas', 'tingkat_lalu', 'tingkat_ini']], width='stretch',
                         hide_index=True)
        else:
            st.caption('Tidak ada')

with st.expander('10. Kandidat Penghargaan', expanded=False):
    st.caption('Dihitung dari seluruh data jurnal, tidak mengikuti filter tanggal di sidebar.')
    tanggal_penuh = pd.to_datetime(jurnal_penuh['tanggal_kejadian'], errors='coerce').dropna() \
        if 'tanggal_kejadian' in jurnal_penuh.columns else pd.Series(dtype='datetime64[ns]')

    pilihan_periode = ['Semua data']
    tahun_ajaran = []
    if not tanggal_penuh.empty:
        for tahun in range(int(tanggal_penuh.min().year), int(tanggal_penuh.max().year) + 1):
            tahun_ajaran.append(tahun)
            pilihan_periode.append(f'Tahun ajaran {tahun}/{tahun + 1}')
            pilihan_periode.append(f'Semester ganjil {tahun}/{tahun + 1} (Jul-Des)')
            pilihan_periode.append(f'Semester genap {tahun}/{tahun + 1} (Jan-Jun)')

    kolom_periode, kolom_batas = st.columns(2)
    with kolom_periode:
        periode = st.selectbox('Periode', pilihan_periode, key='penghargaan_periode')
    with kolom_batas:
        batas_pelanggaran = st.number_input('Batas pelanggaran (poin mutlak)', min_value=0, value=150,
                                            step=10, key='penghargaan_batas')
    pilihan_dukungan = ['Tidak dihitung', 'Tambah ke Akademis', 'Tambah ke Humaniora']
    dukungan = st.radio('Dukungan orang tua', pilihan_dukungan, index=2, horizontal=True,
                        key='penghargaan_dukungan')

    periode_awal = None
    periode_akhir = None
    if periode != 'Semua data':
        tahun = tahun_ajaran[pilihan_periode.index(periode) // 3]
        if periode.startswith('Tahun ajaran'):
            periode_awal = pd.Timestamp(tahun, 7, 1)
            periode_akhir = pd.Timestamp(tahun + 1, 6, 30)
        elif periode.startswith('Semester ganjil'):
            periode_awal = pd.Timestamp(tahun, 7, 1)
            periode_akhir = pd.Timestamp(tahun, 12, 31)
        else:
            periode_awal = pd.Timestamp(tahun + 1, 1, 1)
            periode_akhir = pd.Timestamp(tahun + 1, 6, 30)

    dukungan_kode = {'Tidak dihitung': 'tidak', 'Tambah ke Akademis': 'akademik',
                     'Tambah ke Humaniora': 'humaniora'}[dukungan]

    kandidat = daftar_kandidat(jurnal_penuh, load_referensi_pasal(), periode_awal, periode_akhir,
                               batas_pelanggaran=int(batas_pelanggaran), dukungan_ortu=dukungan_kode)

    if kandidat.empty:
        st.info('Belum ada murid yang mencapai tingkat IV pada periode ini.')
    else:
        tampil = kandidat.copy()
        tampil['memenuhi_syarat'] = tampil['memenuhi_syarat'].map({True: 'Ya', False: 'Tidak'})
        tampil['piala'] = tampil['piala'].map({True: 'Ya', False: 'Tidak'})

        def _rapikan_nama(nilai):
            if not isinstance(nilai, str) or not nilai.strip():
                return nilai
            if nilai == nilai.lower() or nilai == nilai.upper():
                return ' '.join(kata.capitalize() for kata in nilai.split(' '))
            return nilai

        tampil['nama'] = tampil['nama'].apply(_rapikan_nama)
        for kunci in ('total_prestasi', 'total_pelanggaran'):
            if kunci in tampil.columns:
                tampil[kunci] = pd.to_numeric(tampil[kunci], errors='coerce').round(0).astype('Int64')
        tampil = tampil.rename(columns={
            'nis': 'NIS', 'nama': 'Nama', 'kelas': 'Kelas', 'kelompok': 'Kelompok',
            'total_prestasi': 'Total Prestasi', 'tingkat': 'Tingkat', 'penghargaan': 'Penghargaan',
            'total_pelanggaran': 'Total Pelanggaran', 'memenuhi_syarat': 'Memenuhi Syarat',
            'piala': 'Piala',
        })

        def _tandai(baris):
            if baris['Memenuhi Syarat'] == 'Tidak':
                return ['background-color: #fde2e1'] * len(baris)
            return [''] * len(baris)

        st.dataframe(tampil.style.apply(_tandai, axis=1), width='stretch', hide_index=True)

        tanggal_cetak = pd.Timestamp.now().strftime('%d-%m-%Y')
        parameter_pdf = {
            'periode': periode,
            'batas_pelanggaran': int(batas_pelanggaran),
            'dukungan_orang_tua': dukungan,
            'jumlah_kandidat': len(tampil),
            'tanggal_cetak': tanggal_cetak,
        }
        kolom_csv, kolom_pdf = st.columns(2)
        with kolom_csv:
            st.download_button('CSV kandidat_penghargaan', to_csv_bytes(tampil),
                               'kandidat_penghargaan.csv', 'text/csv',
                               key='csv_kandidat_penghargaan')
        with kolom_pdf:
            st.download_button('PDF kandidat_penghargaan',
                               buat_pdf_kandidat_penghargaan(tampil, parameter_pdf),
                               f'kandidat_penghargaan_{tanggal_cetak}.pdf',
                               'application/pdf', key='pdf_kandidat_penghargaan')

    st.caption('Daftar kandidat, bukan keputusan. Tafsir syarat pelanggaran dan periode perlu '
               'dikonfirmasi dari Buku Prestasi dan Disiplin.')
