import hashlib
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))

from core.db import get_conn, init_db, load_referensi_pasal
from core.importer import MASTER_FIELDS, parse_master_csv, parse_master_siswa, preview_master, save_master_siswa
from core.theme import header_halaman, inject_css, kartu_kpi, sidebar_brand

st.set_page_config(page_title='Master Siswa', layout='wide')
inject_css()
sidebar_brand()
header_halaman('Master Siswa',
               'Kelola daftar induk siswa melalui paste tabel atau unggah CSV.')
init_db()
load_referensi_pasal()

conn = get_conn()
try:
    jumlah_master = conn.execute('SELECT COUNT(*) FROM siswa').fetchone()[0]
    master_df = pd.read_sql_query('SELECT nis, nama, kelas, absen FROM siswa ORDER BY kelas, absen', conn)
finally:
    conn.close()
kolom_master, _ = st.columns([1, 2])
kartu_kpi(kolom_master, 'Jumlah siswa pada master', f'{jumlah_master:,}', aksen='emas')

mode = st.radio('Sumber data', ['Paste tabel', 'Upload CSV'])
paste = st.text_area('Paste daftar siswa (NIS, NAMA, KELAS, ABSEN dipisah tab)', height=240) if mode == 'Paste tabel' else ''
upload = st.file_uploader('Upload CSV', type=['csv']) if mode == 'Upload CSV' else None
st.caption('Format paste: empat kolom dipisah tab. CSV memakai kolom nis,nama,kelas,absen. Data disimpan berdasarkan NIS; NIS yang sudah ada akan diperbarui nama, kelas, dan absennya.')
st.download_button('Template CSV', pd.DataFrame(columns=MASTER_FIELDS).to_csv(index=False), 'template_master_siswa.csv', 'text/csv')

payload = paste.encode('utf-8') if mode == 'Paste tabel' else (upload.getvalue() if upload else b'')
filename = 'paste master siswa' if mode == 'Paste tabel' else (upload.name if upload else '')
fingerprint = hashlib.sha256(mode.encode() + filename.encode() + payload).hexdigest()
if st.session_state.get('master_fingerprint') != fingerprint:
    st.session_state.pop('master_records', None)
    st.session_state['master_confirmed'] = False
    st.session_state['master_fingerprint'] = fingerprint

if st.button('Preview dan validasi', key='btn_preview_master', disabled=not payload):
    st.session_state.pop('master_records', None)
    st.session_state['master_confirmed'] = False
    try:
        records = parse_master_siswa(paste) if mode == 'Paste tabel' else parse_master_csv(payload)
        st.session_state['master_records'] = records
    except (ValueError, UnicodeError) as exc:
        st.error(str(exc))

records = st.session_state.get('master_records')
if records:
    preview = preview_master(records)
    invalid = sum(bool(row['errors']) for row in preview)
    st.write(f'{len(preview)} record; {invalid} error; {sum(bool(row["warnings"]) for row in preview)} warning')
    st.dataframe(pd.DataFrame(preview), width='stretch')
    if invalid:
        st.error('Perbaiki semua error sebelum menyimpan. Tidak ada baris yang disimpan sebagian.')
    confirmed = st.checkbox('Saya telah memeriksa preview dan menyetujui penyimpanan master siswa', key='master_confirmed', disabled=bool(invalid))
    if st.button('Simpan master siswa', key='btn_save_master', disabled=bool(invalid) or not confirmed):
        try:
            inserted, updated = save_master_siswa(records, filename, confirmed=confirmed)
            st.success(f'Baru ditambahkan {inserted}; diperbarui {updated}. Audit import tercatat.')
            st.session_state.pop('master_records', None)
        except (ValueError, sqlite3.Error) as exc:
            st.error(f'Import dibatalkan: {exc}')

st.divider()
st.subheader('Master siswa saat ini')
if master_df.empty:
    st.info('Master siswa masih kosong.')
else:
    st.dataframe(master_df, width='stretch')
