import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))

from core.analytics import (daftar_pilihan_siswa, entri_per_subkategori_siswa, kumulatif_netto_siswa,
                            load_jurnal, load_siswa, profil_siswa, riwayat_siswa)
from core.db import init_db, load_referensi_pasal
from core.export import to_csv_bytes, to_excel_bytes
from core.pdf import periode_label, rapor_siswa_pdf
from core.session import sidebar_filters
from core.theme import header_halaman, inject_css, kartu_kpi, sidebar_brand

st.set_page_config(page_title='Profil Siswa', layout='wide')
inject_css()
sidebar_brand()
header_halaman('Profil Siswa',
               'Rapor poin per siswa: prestasi, pelanggaran, netto, dan riwayat entri.')
init_db()
load_referensi_pasal()

jurnal = load_jurnal()
siswa = load_siswa()
jurnal_filter = sidebar_filters(jurnal, load=False)
abaikan_filter = st.toggle('abaikan filter (tampilkan seluruh riwayat)', key='profil_abaikan_filter')
jurnal_aktif = jurnal if abaikan_filter else jurnal_filter
pilihan = daftar_pilihan_siswa(jurnal_aktif if not jurnal_aktif.empty else jurnal, siswa)

if pilihan.empty:
    st.warning('Belum ada data siswa maupun jurnal. Silakan import data terlebih dahulu.')
    st.stop()

label_ke_nis = dict(zip(pilihan['label'], pilihan['nis']))
label_terpilih = st.selectbox('Cari siswa berdasarkan NIS atau nama', pilihan['label'].tolist(), key='profil_siswa')
nis = label_ke_nis[label_terpilih]

profil = profil_siswa(jurnal_aktif, nis, siswa)
st.subheader(f"{profil['nama']} ({profil['kelas']})")
st.write(f"NIS {profil['nis']} | Absen {profil['absen'] or '-'} | sumber identitas: {profil['sumber_identitas']}")

kolom1, kolom2, kolom3, kolom4 = st.columns(4)
kolom1.metric('Total poin prestasi', f"{profil['poin_prestasi']:,}")
kolom2.metric('Total poin pelanggaran', f"{profil['poin_pelanggaran']:,}")
kolom3.metric('Netto', f"{profil['netto']:,}")
kolom4.metric('Jumlah entri', f"{profil['jumlah_entri']:,}")

st.divider()
st.subheader('Grafik')
kumulatif = kumulatif_netto_siswa(jurnal_aktif, nis)
per_subkategori = entri_per_subkategori_siswa(jurnal_aktif, nis)
tab_kumulatif, tab_subkategori = st.tabs(['Netto Kumulatif', 'Entri per Subkategori'])
with tab_kumulatif:
    if kumulatif.empty:
        st.info('Belum ada entri untuk digambarkan.')
    else:
        st.line_chart(kumulatif.set_index('tanggal_kejadian')['netto_kumulatif'])
with tab_subkategori:
    if per_subkategori.empty:
        st.info('Belum ada entri untuk digambarkan.')
    else:
        st.bar_chart(per_subkategori.set_index('subkategori')['jumlah_entri'])

st.divider()
st.subheader('Riwayat Entri')
riwayat = riwayat_siswa(jurnal_aktif, nis)
if riwayat.empty:
    st.info('Siswa ini belum memiliki entri jurnal.')
else:
    st.dataframe(riwayat, width='stretch')

st.divider()
st.subheader('Ekspor Rapor Poin')
nama_berkas = f"rapor_poin_{profil['nis']}"
kolom_csv, kolom_xlsx = st.columns(2)
with kolom_csv:
    st.download_button('CSV Rapor Poin', to_csv_bytes(riwayat), f'{nama_berkas}.csv', 'text/csv',
                       key='csv_rapor')
with kolom_xlsx:
    st.download_button('Excel Rapor Poin', to_excel_bytes(riwayat, 'rapor_poin'), f'{nama_berkas}.xlsx',
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', key='xlsx_rapor')

st.divider()
st.subheader('Unduh Rapor PDF')
st.caption('Rapor memuat identitas, ringkasan poin, rincian subkategori, status SP, dan riwayat entri kronologis.')
if abaikan_filter:
    st.info('Rapor PDF memuat seluruh riwayat entri karena opsi abaikan filter aktif.')
else:
    st.info('Rapor PDF hanya memuat entri yang lolos filter global di sidebar.')
st.download_button('PDF Rapor Poin', rapor_siswa_pdf(profil, riwayat, periode_label(jurnal_aktif)),
                   f'{nama_berkas}.pdf', 'application/pdf', key='pdf_rapor')
