from datetime import date, datetime

import pandas as pd
import streamlit as st

from core import db
from core.analytics import filter_jurnal, load_jurnal, load_siswa, tingkat_dari_kelas

FILTER_KEYS = [
    'filter_tanggal_mulai',
    'filter_tanggal_akhir',
    'filter_tingkat',
    'filter_kelas',
    'filter_kategori',
    'filter_kode_pasal',
    'filter_petugas',
]

TINGKAT_VALID = ['10', '11', '12']


def _tanggal_nilai(nilai):
    if nilai is None:
        return None
    if isinstance(nilai, datetime):
        return nilai.date()
    if isinstance(nilai, date):
        return nilai
    parsed = pd.to_datetime(nilai, errors='coerce')
    return None if pd.isna(parsed) else parsed.date()


def _daftar_hari(df):
    if df is None or df.empty or 'tanggal_kejadian' not in df.columns:
        return []
    tanggal = pd.to_datetime(df['tanggal_kejadian'], errors='coerce')
    return sorted(tanggal.dropna().dt.date.unique().tolist())


def _nilai_unik(df, kolom):
    if df is None or df.empty or kolom not in df.columns:
        return []
    nilai = df[kolom].dropna().astype(str).str.strip()
    return sorted(nilai[nilai != ''].unique().tolist())


def _rapikan(nilai, tersedia):
    return [item for item in (nilai or []) if item in tersedia]


def _mtime_db():
    try:
        return db.DB_PATH.stat().st_mtime_ns
    except OSError:
        return None


@st.cache_data(show_spinner=False)
def _jurnal_tercache(db_path, mtime):
    return load_jurnal()


@st.cache_data(show_spinner=False)
def _siswa_tercache(db_path, mtime):
    return load_siswa()


def cached_jurnal():
    return _jurnal_tercache(str(db.DB_PATH), _mtime_db())


def cached_siswa():
    return _siswa_tercache(str(db.DB_PATH), _mtime_db())


@st.cache_resource(show_spinner=False)
def _init_tercache(db_path):
    db.init_db()
    db.load_referensi_pasal()


def ensure_init():
    _init_tercache(str(db.DB_PATH))


def get_filter_defaults(df):
    hari = _daftar_hari(df)
    return {
        'filter_tanggal_mulai': hari[0] if hari else None,
        'filter_tanggal_akhir': hari[-1] if hari else None,
        'filter_tingkat': [],
        'filter_kelas': [],
        'filter_kategori': [],
        'filter_kode_pasal': [],
        'filter_petugas': [],
    }


def _sinkronkan_state(df):
    defaults = get_filter_defaults(df)
    for kunci in FILTER_KEYS:
        if kunci not in st.session_state:
            st.session_state[kunci] = defaults[kunci]
    for kunci in ['filter_tanggal_mulai', 'filter_tanggal_akhir']:
        nilai = _tanggal_nilai(st.session_state.get(kunci))
        if nilai is None:
            nilai = defaults[kunci]
        st.session_state[kunci] = nilai
    for kunci, tersedia in [
        ('filter_tingkat', TINGKAT_VALID),
        ('filter_kelas', _nilai_unik(df, 'kelas')),
        ('filter_kategori', _nilai_unik(df, 'kategori')),
        ('filter_kode_pasal', _nilai_unik(df, 'kode_pasal')),
        ('filter_petugas', _nilai_unik(df, 'petugas')),
    ]:
        st.session_state[kunci] = _rapikan(st.session_state.get(kunci), tersedia)


def sidebar_filters(df=None, load=True):
    if load:
        df = load_jurnal() if df is None else df
    empty = df is None or df.empty
    _sinkronkan_state(df)

    with st.sidebar:
        st.header('Filter Global')
        hari = _daftar_hari(df)
        if hari:
            batas_awal, batas_akhir = hari[0], hari[-1]
        else:
            batas_awal = batas_akhir = date.today()

        kolom_awal, kolom_akhir = st.columns(2)
        with kolom_awal:
            st.date_input('Tanggal mulai', min_value=batas_awal, max_value=batas_akhir,
                          key='filter_tanggal_mulai', disabled=empty)
        with kolom_akhir:
            st.date_input('Tanggal akhir', min_value=batas_awal, max_value=batas_akhir,
                          key='filter_tanggal_akhir', disabled=empty)

        st.multiselect('Tingkat', TINGKAT_VALID, key='filter_tingkat', placeholder='Semua tingkat')
        st.multiselect('Kelas', _nilai_unik(df, 'kelas'), key='filter_kelas', placeholder='Semua kelas')
        st.multiselect('Kategori', _nilai_unik(df, 'kategori'), key='filter_kategori', placeholder='Semua kategori')
        st.multiselect('Kode pasal', _nilai_unik(df, 'kode_pasal'), key='filter_kode_pasal',
                       placeholder='Semua kode pasal')
        st.multiselect('Petugas', _nilai_unik(df, 'petugas'), key='filter_petugas', placeholder='Semua petugas')

        if st.button('Reset filter', key='filter_reset'):
            for kunci in FILTER_KEYS:
                st.session_state.pop(kunci, None)
            st.rerun()

    return apply_filters_to_jurnal(
        df,
        st.session_state.get('filter_tanggal_mulai'),
        st.session_state.get('filter_tanggal_akhir'),
        st.session_state.get('filter_tingkat'),
        st.session_state.get('filter_kelas'),
        st.session_state.get('filter_kategori'),
        st.session_state.get('filter_kode_pasal'),
        st.session_state.get('filter_petugas'),
    )


def apply_filters_to_jurnal(df, tanggal_mulai=None, tanggal_akhir=None, tingkat=None, kelas=None,
                            kategori=None, kode_pasal=None, petugas=None):
    if df is None:
        return df
    mulai = _tanggal_nilai(tanggal_mulai)
    akhir = _tanggal_nilai(tanggal_akhir)
    if mulai is not None and akhir is not None and mulai > akhir:
        mulai, akhir = akhir, mulai
    hasil = filter_jurnal(df, tanggal_mulai=mulai, tanggal_akhir=akhir, kelas=kelas or None,
                          kategori=kategori or None, kode_pasal=kode_pasal or None, petugas=petugas or None)
    if tingkat and not hasil.empty and 'kelas' in hasil.columns:
        hasil = hasil[tingkat_dari_kelas(hasil['kelas']).isin(list(tingkat))].reset_index(drop=True)
    return hasil

