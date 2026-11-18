import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))

from core import dashboard
from core.session import ensure_init, sidebar_filters
from core.theme import header_halaman, inject_css, kartu_kpi, sidebar_brand

st.set_page_config(page_title='Dashboard', layout='wide')
inject_css()
sidebar_brand()
header_halaman('Dashboard Disiplin & Prestasi',
               'Ringkasan visual entri pelanggaran dan prestasi pada rentang filter yang dipilih.')
ensure_init()

jurnal = sidebar_filters()
st.caption(f'{len(jurnal)} entri jurnal sesuai filter.')

if jurnal.empty:
    st.info('Belum ada data jurnal yang sesuai filter. Ubah filter di sidebar atau import data terlebih dahulu.')
    st.stop()

pelanggaran = jurnal[jurnal['poin'] < 0]
prestasi = jurnal[jurnal['poin'] > 0]

kolom1, kolom2, kolom3, kolom4 = st.columns(4)
kolom1.metric('Entri Pelanggaran', f'{len(pelanggaran):,}')
kolom2.metric('Entri Prestasi', f'{len(prestasi):,}')
kolom3.metric('Total Poin Minus', f"{int(pelanggaran['poin'].sum()):,}")
kolom4.metric('Total Poin Plus', f"{int(prestasi['poin'].sum()):,}")

st.divider()

kolom_kiri, kolom_kanan = st.columns(2)
with kolom_kiri:
    gambar = dashboard.gambar_pie_entri(jurnal)
    if gambar is None:
        st.info('Belum ada entri untuk komposisi.')
    else:
        st.plotly_chart(gambar, width='stretch')
with kolom_kanan:
    gambar = dashboard.gambar_pie_poin(jurnal)
    if gambar is None:
        st.info('Belum ada poin untuk komposisi.')
    else:
        st.plotly_chart(gambar, width='stretch')

gambar = dashboard.gambar_tren_bulanan(jurnal)
if gambar is None:
    st.info('Belum ada tanggal kejadian yang valid untuk tren bulanan.')
else:
    st.plotly_chart(gambar, width='stretch')

kolom_kiri, kolom_kanan = st.columns(2)
with kolom_kiri:
    gambar = dashboard.gambar_top_kode(jurnal, 'pelanggaran')
    if gambar is None:
        st.info('Belum ada entri pelanggaran pada filter ini.')
    else:
        st.plotly_chart(gambar, width='stretch')
with kolom_kanan:
    gambar = dashboard.gambar_top_kode(jurnal, 'prestasi')
    if gambar is None:
        st.info('Belum ada entri prestasi pada filter ini.')
    else:
        st.plotly_chart(gambar, width='stretch')

kolom_kiri, kolom_kanan = st.columns(2)
with kolom_kiri:
    gambar = dashboard.gambar_poin_per_kelas(jurnal, 'minus')
    if gambar is None:
        st.info('Belum ada poin minus per kelas pada filter ini.')
    else:
        st.plotly_chart(gambar, width='stretch')
with kolom_kanan:
    gambar = dashboard.gambar_poin_per_kelas(jurnal, 'plus')
    if gambar is None:
        st.info('Belum ada poin plus per kelas pada filter ini.')
    else:
        st.plotly_chart(gambar, width='stretch')

gambar = dashboard.gambar_heatmap(jurnal)
if gambar is None:
    st.info('Belum ada pelanggaran dengan tanggal valid untuk heatmap hari dan jam.')
else:
    st.plotly_chart(gambar, width='stretch')

gambar = dashboard.gambar_treemap_subkategori(jurnal)
if gambar is None:
    st.info('Belum ada subkategori untuk digambarkan.')
else:
    st.plotly_chart(gambar, width='stretch')

st.divider()
st.subheader('Leaderboard')
kolom_kiri, kolom_kanan = st.columns(2)
with kolom_kiri:
    st.markdown('**Top 20 Murid Prestasi**')
    tabel = dashboard.leaderboard_prestasi(jurnal)
    if tabel.empty:
        st.info('Belum ada entri prestasi pada filter ini.')
    else:
        st.dataframe(tabel, width='stretch', hide_index=True)
with kolom_kanan:
    st.markdown('**Top 20 Murid Pelanggaran**')
    tabel = dashboard.leaderboard_pelanggaran(jurnal)
    if tabel.empty:
        st.info('Belum ada entri pelanggaran pada filter ini.')
    else:
        st.dataframe(tabel, width='stretch', hide_index=True)
