import base64
from datetime import date
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / 'assets'
LOGO_SEKOLAH = ASSETS / 'logo-sekolah.png'
LOGO_75 = ASSETS / 'logo-75.png'

NAMA_SEKOLAH = 'SMA Katolik Santo Paulus Jember'
EYEBROW = 'SMA KATOLIK SANTO PAULUS JEMBER'
SERIF = "Georgia, 'Times New Roman', serif"

LATAR_UTAMA = '#12100E'
LATAR_PANEL = '#1A1714'
KARTU = '#201C18'
GARIS = '#2E2823'
TEKS_UTAMA = '#F2EDE4'
TEKS_REDUP = '#A99E8D'
EMAS = '#C9A227'
EMAS_TERANG = '#E8CE7A'
PRESTASI = '#4E9E7E'
PELANGGARAN = '#C2543F'
NETRAL = '#8A7F6D'

AKSEN = {
    'emas': EMAS,
    'prestasi': PRESTASI,
    'pelanggaran': PELANGGARAN,
    'netral': NETRAL,
}

AWAL_LOGO_75 = date(2026, 8, 1)
AKHIR_LOGO_75 = date(2027, 7, 31)


def tampilkan_logo_75(tanggal=None):
    if tanggal is None:
        tanggal = date.today()
    return AWAL_LOGO_75 <= tanggal <= AKHIR_LOGO_75


def _data_uri(berkas):
    try:
        isi = Path(berkas).read_bytes()
    except OSError:
        return None
    return 'data:image/png;base64,' + base64.b64encode(isi).decode('ascii')


def _gambar_html(berkas, lebar):
    uri = _data_uri(berkas)
    if uri is None:
        return ''
    return f'<img src="{uri}" width="{int(lebar)}" alt="" style="display:block;" />'


_CSS = f"""
<style>
:root {{
  --latar-utama: {LATAR_UTAMA};
  --latar-panel: {LATAR_PANEL};
  --kartu: {KARTU};
  --garis: {GARIS};
  --teks-utama: {TEKS_UTAMA};
  --teks-redup: {TEKS_REDUP};
  --emas: {EMAS};
  --emas-terang: {EMAS_TERANG};
  --prestasi: {PRESTASI};
  --pelanggaran: {PELANGGARAN};
  --netral: {NETRAL};
}}

div[data-testid="stDecoration"],
div[data-testid="stMainMenu"],
div[data-testid="stAppDeployButton"],
div[data-testid="stStatusWidget"],
#MainMenu, footer {{
  display: none !important;
}}

header[data-testid="stHeader"] {{
  background: transparent !important;
}}
header[data-testid="stHeader"] [data-testid="stExpandSidebarButton"] {{
  display: flex !important;
  pointer-events: auto !important;
  color: var(--emas-terang) !important;
}}

.stApp {{
  background:
    radial-gradient(900px 320px at 50% -120px, rgba(201, 162, 39, 0.18), rgba(201, 162, 39, 0) 70%),
    var(--latar-utama);
}}

.block-container {{
  padding-top: 4rem !important;
  padding-bottom: 3rem !important;
  max-width: 1280px;
}}

section[data-testid="stSidebar"] {{
  background: #14110E;
  border-right: 1px solid var(--garis);
}}
section[data-testid="stSidebar"] .block-container {{
  padding-top: 1rem;
}}

h1, h2, h3, h4 {{
  color: var(--teks-utama);
  letter-spacing: -0.01em;
}}

p, label, span, li {{
  color: var(--teks-utama);
}}

hr {{
  border-color: var(--garis);
}}

.stButton > button,
.stDownloadButton > button {{
  background: transparent;
  color: var(--emas-terang);
  border: 1px solid rgba(201, 162, 39, 0.55);
  border-radius: 10px;
  padding: 0.4rem 0.95rem;
  font-weight: 500;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}}
.stButton > button:hover,
.stDownloadButton > button:hover {{
  background: rgba(201, 162, 39, 0.14);
  border-color: var(--emas);
  color: var(--emas-terang);
}}
.stButton > button:focus:not(:active),
.stDownloadButton > button:focus:not(:active) {{
  border-color: var(--emas);
  color: var(--emas-terang);
}}
.stButton > button:disabled,
.stDownloadButton > button:disabled {{
  opacity: 0.45;
}}

.stTabs [data-baseweb="tab-list"] {{
  gap: 0.35rem;
  border-bottom: 1px solid var(--garis);
}}
.stTabs [data-baseweb="tab"] {{
  background: transparent;
  color: var(--teks-redup);
  border-radius: 8px 8px 0 0;
  padding: 0.35rem 0.9rem;
}}
.stTabs [aria-selected="true"] {{
  color: var(--emas-terang) !important;
  background: rgba(201, 162, 39, 0.10);
}}
.stTabs [data-baseweb="tab-highlight"] {{
  background-color: var(--emas);
}}

div[data-testid="stExpander"] {{
  border: 1px solid var(--garis);
  border-radius: 12px;
  background: rgba(26, 23, 20, 0.65);
  overflow: hidden;
}}
div[data-testid="stExpander"] summary {{
  color: var(--teks-utama);
}}
div[data-testid="stExpander"] summary:hover {{
  color: var(--emas-terang);
}}

div[data-testid="stDataFrame"],
div[data-testid="stDataFrameResizable"] {{
  border: 1px solid var(--garis);
  border-radius: 12px;
  overflow: hidden;
  background: var(--latar-panel);
}}

div[data-testid="stMetric"] {{
  position: relative;
  background: var(--kartu);
  border: 1px solid var(--garis);
  border-radius: 14px;
  padding: 18px 18px 18px 22px;
  overflow: hidden;
}}
div[data-testid="stMetric"]::before {{
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: linear-gradient(180deg, var(--emas-terang), var(--emas));
}}
div[data-testid="stMetricLabel"] p,
div[data-testid="stMetricLabel"] {{
  text-transform: uppercase;
  letter-spacing: 0.09em;
  font-size: 0.75rem !important;
  color: var(--teks-redup) !important;
}}
div[data-testid="stMetricValue"] {{
  font-size: 1.9rem !important;
  font-weight: 600;
  color: var(--teks-utama);
}}

div[data-testid="stAlert"] {{
  border-radius: 12px;
  border: 1px solid var(--garis);
  border-left: 3px solid var(--emas);
  background: rgba(32, 28, 24, 0.9);
  color: var(--teks-utama);
}}
div[data-testid="stAlert"] p {{
  color: var(--teks-utama);
}}
div[data-testid="stAlert"][data-baseweb="notification"] {{
  border-left-width: 3px;
}}

div[data-testid="stNotification"] {{
  border-radius: 12px;
}}

* {{
  scrollbar-width: thin;
  scrollbar-color: var(--garis) transparent;
}}
::-webkit-scrollbar {{
  width: 9px;
  height: 9px;
}}
::-webkit-scrollbar-track {{
  background: transparent;
}}
::-webkit-scrollbar-thumb {{
  background: var(--garis);
  border-radius: 8px;
}}
::-webkit-scrollbar-thumb:hover {{
  background: #3B342D;
}}

.kepala-halaman {{
  margin: 0 0 1.1rem 0;
}}
.kepala-halaman .eyebrow {{
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--emas);
  margin-bottom: 0.35rem;
}}
.kepala-halaman .judul {{
  font-family: {SERIF};
  font-size: 2rem;
  line-height: 1.2;
  color: var(--teks-utama);
  margin: 0;
}}
.kepala-halaman .deskripsi {{
  color: var(--teks-redup);
  font-size: 0.92rem;
  margin-top: 0.35rem;
}}
.kepala-halaman .garis-emas {{
  height: 1px;
  margin-top: 0.9rem;
  background: linear-gradient(90deg, var(--emas), rgba(201, 162, 39, 0.05));
}}

.kartu-kpi {{
  position: relative;
  background: var(--kartu);
  border: 1px solid var(--garis);
  border-radius: 14px;
  padding: 18px 18px 18px 22px;
  overflow: hidden;
  height: 100%;
}}
.kartu-kpi::before {{
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--aksen);
}}
.kartu-kpi .label {{
  text-transform: uppercase;
  letter-spacing: 0.09em;
  font-size: 0.75rem;
  color: var(--teks-redup);
  margin-bottom: 0.35rem;
}}
.kartu-kpi .nilai {{
  font-size: 1.9rem;
  font-weight: 600;
  color: var(--teks-utama);
  line-height: 1.1;
}}
.kartu-kpi .keterangan {{
  font-size: 0.78rem;
  color: var(--teks-redup);
  margin-top: 0.35rem;
}}

.brand-sidebar {{
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 0.25rem 0 0.9rem 0;
  margin-bottom: 0.6rem;
  border-bottom: 1px solid var(--garis);
}}
.brand-sidebar .nama {{
  font-family: {SERIF};
  font-size: 0.98rem;
  color: var(--teks-utama);
  margin-top: 0.6rem;
  line-height: 1.3;
}}
.brand-sidebar .badge-75 {{
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.55rem;
  color: var(--emas-terang);
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}}

.hero-beranda {{
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 1.4rem 0 2.2rem 0;
}}
.hero-beranda .logo {{
  margin-bottom: 1.1rem;
}}
.hero-beranda .eyebrow {{
  font-size: 0.72rem;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--emas);
}}
.hero-beranda .judul {{
  font-family: {SERIF};
  font-size: 2.6rem;
  line-height: 1.15;
  color: var(--teks-utama);
  margin: 0.5rem 0 0.2rem 0;
}}
.hero-beranda .subjudul {{
  color: var(--teks-redup);
  font-size: 1rem;
  max-width: 640px;
}}
.hero-beranda .badge-75 {{
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 1.1rem;
  padding: 0.4rem 0.9rem;
  border: 1px solid rgba(201, 162, 39, 0.45);
  border-radius: 999px;
  color: var(--emas-terang);
  font-size: 0.75rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}}
.hero-beranda .garis-emas {{
  width: 160px;
  height: 1px;
  margin-top: 1.4rem;
  background: linear-gradient(90deg, rgba(201, 162, 39, 0), var(--emas), rgba(201, 162, 39, 0));
}}

[class^="st-key-kartu_"] {{
  background: var(--latar-panel);
  border: 1px solid var(--garis);
  border-radius: 14px;
  padding: 20px 20px 14px 20px;
  height: 100%;
}}

.kartu-tautan {{
  margin-bottom: 0;
}}
.kartu-tautan .ikon {{
  font-size: 1.35rem;
}}
.kartu-tautan .judul {{
  font-family: {SERIF};
  font-size: 1.15rem;
  color: var(--teks-utama);
  margin: 0.45rem 0 0.3rem 0;
}}
.kartu-tautan .isi {{
  color: var(--teks-redup);
  font-size: 0.86rem;
  line-height: 1.45;
  min-height: 3.6rem;
}}

[class^="st-key-kartu_"] [data-testid="stPageLink"] a {{
  border: 1px solid rgba(201, 162, 39, 0.55);
  border-radius: 10px;
  color: var(--emas-terang);
  text-align: center;
  margin-top: 0.5rem;
}}
[class^="st-key-kartu_"] [data-testid="stPageLink"] a:hover {{
  background: rgba(201, 162, 39, 0.14);
}}
</style>
"""


def inject_css():
    st.markdown(_CSS, unsafe_allow_html=True)


def header_halaman(judul, deskripsi=''):
    deskripsi_html = f'<div class="deskripsi">{deskripsi}</div>' if deskripsi else ''
    st.markdown(
        f'<div class="kepala-halaman">'
        f'<div class="eyebrow">{EYEBROW}</div>'
        f'<h1 class="judul">{judul}</h1>'
        f'{deskripsi_html}'
        f'<div class="garis-emas"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def sidebar_brand():
    logo = _gambar_html(LOGO_SEKOLAH, 120)
    badge = ''
    if tampilkan_logo_75():
        gambar_75 = _gambar_html(LOGO_75, 64)
        if gambar_75:
            badge = f'<div class="badge-75">{gambar_75}<span>75 Tahun</span></div>'
    with st.sidebar:
        st.markdown(
            f'<div class="brand-sidebar">{logo}<div class="nama">{NAMA_SEKOLAH}</div>{badge}</div>',
            unsafe_allow_html=True,
        )


def kartu_kpi(kolom, label, nilai, keterangan=None, aksen='emas'):
    warna = AKSEN.get(aksen, EMAS)
    keterangan_html = f'<div class="keterangan">{keterangan}</div>' if keterangan else ''
    with kolom:
        st.markdown(
            f'<div class="kartu-kpi" style="--aksen: {warna};">'
            f'<div class="label">{label}</div>'
            f'<div class="nilai">{nilai}</div>'
            f'{keterangan_html}'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="height:0;overflow:hidden;">'
            f'<span data-testid="stMetricLabel">{label}</span>'
            f'<span data-testid="stMetricValue">{nilai}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


def hero_beranda():
    logo = _gambar_html(LOGO_SEKOLAH, 150)
    badge = ''
    if tampilkan_logo_75():
        gambar_75 = _gambar_html(LOGO_75, 44)
        if gambar_75:
            badge = f'<div class="badge-75">{gambar_75}<span>75 Tahun Santo Paulus</span></div>'
    st.markdown(
        f'<div class="hero-beranda">'
        f'<div class="logo">{logo}</div>'
        f'<div class="eyebrow">{EYEBROW}</div>'
        f'<div class="judul">Dashboard Disiplin &amp; Prestasi</div>'
        f'<div class="subjudul">Pemantauan kedisiplinan dan capaian murid dalam satu tampilan yang tenang, '
        f'rapi, dan siap dipakai tim disiplin sekolah.</div>'
        f'{badge}'
        f'<div class="garis-emas"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def kartu_tautan(kolom, judul, isi, ikon=''):
    kolom.markdown(
        f'<div class="kartu-tautan">'
        f'<div class="ikon">{ikon}</div>'
        f'<div class="judul">{judul}</div>'
        f'<div class="isi">{isi}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
