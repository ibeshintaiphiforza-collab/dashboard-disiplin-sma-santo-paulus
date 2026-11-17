import hashlib
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))

from core.db import get_conn, init_db, load_referensi_pasal
from core.importer import FIELDS, PasteEguruParser, csv_baris_error, preview_records, save_import
from core.theme import header_halaman, inject_css, sidebar_brand

st.set_page_config(page_title='Import CSV', layout='wide')
inject_css()
sidebar_brand()
header_halaman('Import CSV',
               'Impor jalur paste e-Guru atau unggah CSV dengan pratinjau validasi sebelum disimpan.')
init_db()
load_referensi_pasal()
mode = st.radio('Sumber data', ['Paste eGuru', 'Upload CSV'])
paste = st.text_area('Paste tabel eGuru', height=240) if mode == 'Paste eGuru' else ''
upload = st.file_uploader('Upload CSV', type=['csv']) if mode == 'Upload CSV' else None
st.caption('CSV memakai kolom kelas dan absen terpisah; kelas gabungan lama dipisah otomatis. Absen opsional, 1-2 digit akan dilengkapi menjadi 2 digit. id atau id_eguru opsional. ID yang sudah ada dilewati. Tanpa ID, import ulang membuat entri baru.')
st.download_button('Template CSV', pd.DataFrame(columns=['id'] + FIELDS).to_csv(index=False), 'template_import.csv', 'text/csv')
payload = paste.encode('utf-8') if mode == 'Paste eGuru' else (upload.getvalue() if upload else b'')
filename = 'paste eGuru' if mode == 'Paste eGuru' else (upload.name if upload else '')
fingerprint = hashlib.sha256(mode.encode() + filename.encode() + payload).hexdigest()
if st.session_state.get('import_fingerprint') != fingerprint:
    st.session_state.pop('import_records', None)
    st.session_state['import_confirmed'] = False
    st.session_state['import_fingerprint'] = fingerprint
if st.button('Preview dan validasi', key='btn_preview', disabled=not payload):
    st.session_state.pop('import_records', None)
    st.session_state['import_confirmed'] = False
    try:
        records = PasteEguruParser.parse_paste(paste) if mode == 'Paste eGuru' else PasteEguruParser.parse_csv(payload)
        st.session_state['import_records'] = records
    except (ValueError, UnicodeError) as exc:
        st.error(str(exc))
records = st.session_state.get('import_records')
if records:
    conn = get_conn()
    try:
        preview = preview_records(records, conn)
    finally:
        conn.close()
    invalid = sum(bool(row['errors']) for row in preview)
    st.write(f'{len(preview)} record; {invalid} error; {sum(bool(row["warnings"]) for row in preview)} warning')
    st.dataframe(pd.DataFrame(preview), width='stretch')
    if invalid:
        st.error('Perbaiki semua error sebelum menyimpan. Tidak ada baris yang disimpan sebagian.')
        st.download_button('Unduh baris error (CSV)', csv_baris_error(preview),
                           'baris_error_import.csv', 'text/csv', key='csv_error')
    confirmed = st.checkbox('Saya telah memeriksa preview dan menyetujui penyimpanan', key='import_confirmed', disabled=bool(invalid))
    if st.button('Simpan import', key='btn_save', disabled=bool(invalid) or not confirmed):
        try:
            saved, duplicates = save_import(records, filename, confirmed=confirmed,
                                             source='import_paste' if mode == 'Paste eGuru' else 'import_csv')
            st.success(f'Tersimpan {saved}; duplikat dilewati {duplicates}. Audit import tercatat.')
            st.session_state.pop('import_records', None)
        except (ValueError, sqlite3.Error) as exc:
            st.error(f'Import dibatalkan: {exc}')
