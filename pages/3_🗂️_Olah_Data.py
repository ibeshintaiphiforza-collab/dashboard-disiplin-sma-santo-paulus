import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))

from core.analytics import (deteksi_anomali, filter_jurnal, hapus_jurnal, import_terakhir,
                            rekap_per_kelas, rekap_per_siswa, rekap_per_subkategori,
                            rollback_import_terakhir)
from core.export import to_csv_bytes, to_excel_bytes
from core.pdf import periode_label, rekap_kelas_pdf, rekap_sekolah_pdf
from core.session import cached_jurnal, cached_siswa, ensure_init, sidebar_filters
from core.theme import header_halaman, inject_css, sidebar_brand

st.set_page_config(page_title='Olah Data', layout='wide')
inject_css()
sidebar_brand()
header_halaman('Olah Data',
               'Tabel jurnal interaktif, deteksi anomali, rekap, ekspor, dan unduhan PDF.')
ensure_init()

jurnal = cached_jurnal()
siswa = cached_siswa()

if jurnal.empty:
    st.warning('Belum ada data jurnal. Silakan import data terlebih dahulu di halaman Import CSV.')
    st.stop()

terfilter = sidebar_filters(jurnal, load=False)

st.subheader('Filter dan Tabel Jurnal')
pencarian = st.text_input('Cari nama murid atau judul', key='filter_cari')
terfilter = filter_jurnal(terfilter, pencarian=pencarian)
tabel = terfilter.sort_values('tanggal_kejadian', ascending=False).head(200)
st.write(f'{len(terfilter)} dari {len(jurnal)} entri jurnal; menampilkan {len(tabel)} terbaru')
st.dataframe(tabel, width='stretch')

st.divider()
st.subheader('Deteksi Anomali')
anomali = deteksi_anomali(terfilter, siswa)
label_anomali = {
    'poin_beda_default': 'Poin berbeda dari poin baku pasal (mode fixed)',
    'nis_tidak_dikenal': 'NIS tidak ada pada master murid',
    'duplikat_kandidat': 'Kandidat duplikat: NIS + tanggal + kode pasal sama',
    'tanggal_mendahului_input': 'Tanggal kejadian melampaui tanggal input',
}
if siswa.empty:
    st.info('Master murid kosong; pemeriksaan NIS tidak dikenal dilewati.')
for kunci, judul in label_anomali.items():
    data = anomali[kunci]
    with st.expander(f'{judul} ({len(data)})'):
        if data.empty:
            st.success('Tidak ada anomali pada kategori ini.')
        else:
            if kunci == 'duplikat_kandidat':
                st.warning('Peringatan saja: duplikat sah mungkin terjadi, misalnya pelanggaran berulang pada hari yang sama.')
            st.dataframe(data, width='stretch')

st.divider()
st.subheader('Rekap')
rekap_siswa = rekap_per_siswa(terfilter, siswa)
rekap_kelas = rekap_per_kelas(terfilter)
rekap_sub = rekap_per_subkategori(terfilter)
tab_siswa, tab_kelas, tab_sub = st.tabs(['Per Murid', 'Per Kelas', 'Per Subkategori'])
with tab_siswa:
    st.dataframe(rekap_siswa, width='stretch')
with tab_kelas:
    st.dataframe(rekap_kelas, width='stretch')
with tab_sub:
    st.dataframe(rekap_sub, width='stretch')

st.subheader('Unduh Rekap PDF')
ringkasan = {
    'total_entri': len(terfilter),
    'jumlah_siswa': int(terfilter['nis'].nunique()) if not terfilter.empty else 0,
    'jumlah_kelas': int(terfilter['kelas'].nunique()) if not terfilter.empty else 0,
    'poin_prestasi': int(terfilter['poin'].clip(lower=0).sum()) if not terfilter.empty else 0,
    'poin_pelanggaran': int(terfilter['poin'].clip(upper=0).sum()) if not terfilter.empty else 0,
}
periode = periode_label(terfilter)
daftar_kelas = []
if not terfilter.empty and 'kelas' in terfilter.columns:
    nilai_kelas = terfilter['kelas'].dropna().astype(str).str.strip()
    daftar_kelas = sorted(nilai for nilai in nilai_kelas.unique() if nilai)
if daftar_kelas:
    kelas_pdf = st.selectbox('Kelas untuk rekap PDF', daftar_kelas, key='pdf_kelas')
    st.download_button(f'PDF Rekap Kelas {kelas_pdf}',
                       rekap_kelas_pdf(rekap_kelas, rekap_siswa, kelas_pdf, periode),
                       f'rekap_kelas_{kelas_pdf}.pdf', 'application/pdf', key='pdf_rekap_kelas')
else:
    st.info('Tidak ada kelas pada data terfilter; rekap PDF kelas tidak tersedia.')
st.download_button('PDF Rekap Sekolah', rekap_sekolah_pdf(rekap_kelas, periode, ringkasan),
                   'rekap_sekolah.pdf', 'application/pdf', key='pdf_rekap_sekolah')

st.divider()
st.subheader('Ekspor')
unduhan = {
    'jurnal_terfilter': terfilter,
    'rekap_siswa': rekap_siswa,
    'rekap_kelas': rekap_kelas,
    'rekap_subkategori': rekap_sub,
}
for indeks, (nama, data) in enumerate(unduhan.items()):
    kolom_csv, kolom_xlsx = st.columns(2)
    with kolom_csv:
        st.download_button(f'CSV {nama}', to_csv_bytes(data), f'{nama}.csv', 'text/csv', key=f'csv_{indeks}')
    with kolom_xlsx:
        st.download_button(f'Excel {nama}', to_excel_bytes(data, nama),
                           f'{nama}.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                           key=f'xlsx_{indeks}')

st.divider()
st.subheader('Hapus Entri Jurnal')
st.error('Tindakan ini menghapus baris jurnal secara permanen dan tidak dapat dibatalkan.')
pilihan_id = st.multiselect('ID jurnal yang akan dihapus', terfilter['id'].tolist(), key='hapus_ids')
if pilihan_id:
    st.dataframe(terfilter[terfilter['id'].isin(pilihan_id)], width='stretch')
hapus_dikonfirmasi = st.checkbox('Saya memahami penghapusan ini permanen dan menyetujuinya', key='hapus_confirmed', disabled=not pilihan_id)
if st.button('Hapus entri terpilih', key='btn_hapus', disabled=not pilihan_id or not hapus_dikonfirmasi):
    try:
        terhapus = hapus_jurnal(pilihan_id, confirmed=hapus_dikonfirmasi)
        st.success(f'{terhapus} entri jurnal dihapus.')
        st.rerun()
    except (ValueError, sqlite3.Error) as exc:
        st.error(f'Penghapusan dibatalkan: {exc}')

st.divider()
st.subheader('Rollback Import Terakhir')
from core import backup as backup_mod
info_rollback = import_terakhir()
if info_rollback:
    import_id, nama_file, jumlah = info_rollback
    st.write(f'Import terakhir: `{nama_file}` ({jumlah} baris jurnal).')
    konfirmasi_rollback = st.checkbox('Saya memahami rollback menghapus baris jurnal dari import terakhir', key='rollback_conf')
    if st.button('Rollback import terakhir', key='btn_rollback', disabled=not konfirmasi_rollback):
        try:
            backup_mod.backup_db()
            terhapus = rollback_import_terakhir()
            st.success(f'{terhapus} baris jurnal di-rollback.')
            st.rerun()
        except (ValueError, sqlite3.Error) as exc:
            st.error(f'Rollback dibatalkan: {exc}')
else:
    st.info('Tidak ada import yang dapat di-rollback.')

st.divider()
st.subheader('Cadangan Basis Data')
col_b1, col_b2 = st.columns([1, 2])
with col_b1:
    if st.button('Backup Sekarang', key='btn_backup'):
        try:
            berkas, dihapus, pesan_eksternal = backup_mod.backup_db()
            st.success(f'Cadangan dibuat: {berkas.name}')
            if dihapus:
                st.caption(f'Rotasi: {len(dihapus)} cadangan lama dihapus.')
            if pesan_eksternal:
                if 'tidak tersedia' in pesan_eksternal or 'gagal' in pesan_eksternal:
                    st.warning(pesan_eksternal)
                else:
                    st.info(pesan_eksternal)
            st.rerun()
        except Exception as exc:
            st.error(f'Backup gagal: {exc}')
with col_b2:
    st.caption('Cadangan disimpan di folder backups/ dengan stempel waktu (sqlite3 backup API). Rotasi menyimpan 14 cadangan terbaru.')

folder_eksternal = st.text_input('Salinan cadangan ke folder eksternal (mis. E:\\backup-disiplin, kosongkan untuk menonaktifkan)', value=backup_mod.baca_folder_eksternal(), key='input_eksternal')
col_e1, col_e2 = st.columns([1, 2])
with col_e1:
    if st.button('Simpan', key='btn_simpan_eksternal'):
        backup_mod.tulis_folder_eksternal(folder_eksternal)
        st.success('Pengaturan folder eksternal disimpan.')
with col_e2:
    if st.button('Tes folder', key='btn_tes_eksternal'):
        folder_uji = Path(folder_eksternal.strip()) if folder_eksternal.strip() else None
        if folder_uji is None or not folder_uji.is_dir():
            st.warning(backup_mod.PESAN_EKSTERNAL_TIDAK_ADA)
        else:
            uji = folder_uji / '.tes-tulis.tmp'
            try:
                uji.write_text('tes', encoding='utf-8')
                uji.unlink()
                st.success('Folder eksternal dapat ditulis.')
            except OSError as exc:
                st.warning(f'Folder eksternal tidak dapat ditulis: {exc}')
daftar = backup_mod.daftar_backup()
if daftar:
    st.write('Daftar cadangan:')
    baris = []
    for b in daftar:
        baris.append({
            'file': b.name,
            'waktu': datetime.fromtimestamp(b.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'ukuran': backup_mod.format_ukuran(backup_mod.ukuran_berkas(b)),
        })
    st.dataframe(baris, width='stretch', hide_index=True)
    pilihan = st.selectbox('Pilih cadangan untuk dikembalikan', [b.name for b in daftar], key='restore_pilih')
    konfirm = st.checkbox('Saya memahami restore akan menimpa data jurnal saat ini dan tidak dapat dibatalkan', key='restore_conf')
    if st.button('Restore cadangan terpilih', key='btn_restore', disabled=not konfirm):
        try:
            pre, ok = backup_mod.restore_db(backup_mod.DEFAULT_BACKUP_DIR / pilihan, confirmed=True)
            st.success(f'Restore berhasil: {pilihan}')
            if pre:
                st.caption(f'Cadangan pra-restore: {pre.name}')
            st.rerun()
        except Exception as exc:
            st.error(f'Restore dibatalkan: {exc}')
else:
    st.info('Belum ada cadangan basis data.')
