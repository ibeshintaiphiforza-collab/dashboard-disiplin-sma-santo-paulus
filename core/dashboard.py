import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from core import theme
from core.analytics import NAMA_HARI, label_bulan, tingkat_dari_kelas
from core.chart_theme import (WARNA_HEATMAP, WARNA_KATEGORI, WARNA_PELANGGARAN, WARNA_PRESTASI,
                              terapkan_sumbu, terapkan_tata_letak)
from core.thresholds import status_peringatan

TANPA_JAM = 'tanpa jam'
TANPA_PASAL = 'tanpa_pasal'
KOLOM_LEADERBOARD = ['NIS', 'Nama', 'Kelas', 'Total Poin', 'Jumlah Entri', 'Status']


def _kosong(df):
    return df is None or df.empty


def _rapikan_kategori(df):
    data = df.copy()
    if 'kategori' not in data.columns:
        data['kategori'] = TANPA_PASAL
    data['kategori'] = data['kategori'].fillna(TANPA_PASAL).astype(str)
    return data


def _label_kode(df):
    data = df.copy()
    if 'deskripsi' not in data.columns:
        data['deskripsi'] = ''
    deskripsi = data['deskripsi'].fillna('').astype(str).str.strip()
    ringkas = deskripsi.str.split(r'(?<=\.)\s', n=1, regex=True).str[0].str.rstrip('.')
    ringkas = ringkas.where(ringkas.str.len() <= 40, ringkas.str.slice(0, 37) + '...')
    data['label'] = data['kode_pasal'].astype(str) + ' - ' + ringkas
    return data


def komposisi_entri(df):
    kolom = ['kategori', 'jumlah_entri']
    if _kosong(df):
        return pd.DataFrame(columns=kolom)
    data = _rapikan_kategori(df)
    hasil = data.groupby('kategori').size().reset_index(name='jumlah_entri')
    urutan = ['pelanggaran', 'prestasi']
    urutan += [kategori for kategori in hasil['kategori'] if kategori not in urutan]
    hasil['_urutan'] = hasil['kategori'].map({kategori: posisi for posisi, kategori in enumerate(urutan)})
    return hasil.sort_values('_urutan').reset_index(drop=True)[kolom]


def komposisi_poin(df):
    kolom = ['kategori', 'total_poin']
    if _kosong(df):
        return pd.DataFrame(columns=kolom)
    data = _rapikan_kategori(df)
    data['total_poin'] = data['poin'].clip(lower=0)
    data.loc[data['kategori'] == 'pelanggaran', 'total_poin'] = data['poin'].abs()
    hasil = data.groupby('kategori').agg(total_poin=('total_poin', 'sum')).reset_index()
    urutan = ['pelanggaran', 'prestasi']
    urutan += [kategori for kategori in hasil['kategori'] if kategori not in urutan]
    hasil['_urutan'] = hasil['kategori'].map({kategori: posisi for posisi, kategori in enumerate(urutan)})
    return hasil.sort_values('_urutan').reset_index(drop=True)[kolom]


def top_kode(df, kategori, batas=10):
    kolom = ['kode_pasal', 'label', 'jumlah_entri', 'total_poin']
    if _kosong(df) or 'kode_pasal' not in df.columns:
        return pd.DataFrame(columns=kolom)
    data = _rapikan_kategori(_label_kode(df))
    data = data[data['kategori'] == kategori]
    if data.empty:
        return pd.DataFrame(columns=kolom)
    hasil = data.groupby(['kode_pasal', 'label']).agg(
        jumlah_entri=('poin', 'size'), total_poin=('poin', 'sum')).reset_index()
    hasil = hasil.sort_values(['jumlah_entri', 'kode_pasal'], ascending=[False, True]).head(int(batas))
    return hasil.reset_index(drop=True)[kolom]


def poin_per_kelas(df):
    kolom = ['kelas', 'tingkat', 'poin_minus', 'poin_plus', 'jumlah_entri']
    if _kosong(df) or 'kelas' not in df.columns:
        return pd.DataFrame(columns=kolom)
    data = df.copy()
    data['poin_minus'] = data['poin'].clip(upper=0).abs()
    data['poin_plus'] = data['poin'].clip(lower=0)
    hasil = data.groupby('kelas').agg(
        poin_minus=('poin_minus', 'sum'),
        poin_plus=('poin_plus', 'sum'),
        jumlah_entri=('poin', 'size'),
    ).reset_index()
    hasil['tingkat'] = tingkat_dari_kelas(hasil['kelas']).values
    return hasil.reset_index(drop=True)[kolom]


def heatmap_hari_jam(df):
    kolom = ['hari', 'jam', 'jumlah_entri']
    if _kosong(df) or 'tanggal_kejadian' not in df.columns:
        return pd.DataFrame(columns=kolom)
    data = df[df['poin'] < 0].copy()
    if data.empty:
        return pd.DataFrame(columns=kolom)
    data = data[pd.to_datetime(data['tanggal_kejadian'], errors='coerce').notna()].copy()
    if data.empty:
        return pd.DataFrame(columns=kolom)
    data['hari'] = pd.to_datetime(data['tanggal_kejadian'], errors='coerce').dt.day_of_week.map(
        lambda posisi: NAMA_HARI[posisi])
    jam = pd.Series(TANPA_JAM, index=data.index, dtype='object')
    if 'timestamp_input' in data.columns:
        masuk = pd.to_datetime(data['timestamp_input'], errors='coerce')
        ada_jam = masuk.notna()
        if ada_jam.any():
            jam = jam.where(~ada_jam, masuk.dt.strftime('%H:00'))
    data['jam'] = jam.values
    hasil = data.groupby(['hari', 'jam']).size().reset_index(name='jumlah_entri')
    urutan_hari = {nama: posisi for posisi, nama in enumerate(NAMA_HARI)}
    urutan_jam = sorted([j for j in hasil['jam'].unique() if j != TANPA_JAM]) + [TANPA_JAM]
    hasil['_hari'] = hasil['hari'].map(urutan_hari)
    hasil['_jam'] = hasil['jam'].map({jam_: posisi for posisi, jam_ in enumerate(urutan_jam)})
    hasil = hasil.sort_values(['_hari', '_jam'])
    return hasil.reset_index(drop=True)[kolom]


def distribusi_subkategori(df):
    kolom = ['subkategori', 'kategori', 'jumlah_entri']
    if _kosong(df):
        return pd.DataFrame(columns=kolom)
    data = _rapikan_kategori(df)
    if 'subkategori' not in data.columns:
        data['subkategori'] = TANPA_PASAL
    data['subkategori'] = data['subkategori'].fillna(TANPA_PASAL).astype(str)
    hasil = data.groupby(['subkategori', 'kategori']).size().reset_index(name='jumlah_entri')
    return hasil.sort_values('jumlah_entri', ascending=False).reset_index(drop=True)[kolom]


def leaderboard_prestasi(df, batas=20):
    kolom = KOLOM_LEADERBOARD[:5]
    if _kosong(df) or 'poin' not in df.columns:
        return pd.DataFrame(columns=kolom)
    data = df[df['poin'] > 0].copy()
    if data.empty:
        return pd.DataFrame(columns=kolom)
    data['nis'] = data['nis'].astype(str)
    hasil = data.groupby('nis').agg(
        Nama=('nama_siswa', 'last'),
        Kelas=('kelas', 'last'),
        **{'Total Poin': ('poin', 'sum'), 'Jumlah Entri': ('poin', 'size')},
    ).reset_index().rename(columns={'nis': 'NIS'})
    hasil = hasil.sort_values(['Total Poin', 'Jumlah Entri', 'NIS'], ascending=[False, False, True])
    return hasil.head(int(batas)).reset_index(drop=True)[kolom]


def leaderboard_pelanggaran(df, batas=20):
    if _kosong(df) or 'poin' not in df.columns:
        return pd.DataFrame(columns=KOLOM_LEADERBOARD)
    data = df[df['poin'] < 0].copy()
    if data.empty:
        return pd.DataFrame(columns=KOLOM_LEADERBOARD)
    data['nis'] = data['nis'].astype(str)
    hasil = data.groupby('nis').agg(
        Nama=('nama_siswa', 'last'),
        Kelas=('kelas', 'last'),
        **{'Total Poin': ('poin', 'sum'), 'Jumlah Entri': ('poin', 'size')},
    ).reset_index().rename(columns={'nis': 'NIS'})
    hasil = hasil.sort_values(['Total Poin', 'Jumlah Entri', 'NIS'], ascending=[True, False, True])
    hasil = hasil.head(int(batas)).reset_index(drop=True)
    hasil['Status'] = hasil['Total Poin'].map(lambda nilai: status_peringatan(int(nilai))['label'])
    return hasil[KOLOM_LEADERBOARD]


def _gambar_pie(data, nama_kolom, judul, warna):
    if _kosong(data):
        return None
    fig = px.pie(data, names='kategori', values=nama_kolom, hole=0.35,
                 color='kategori', color_discrete_map=warna)
    fig.update_traces(textinfo='label+percent+value', textfont=dict(color=theme.TEKS_UTAMA))
    terapkan_tata_letak(fig, title=judul, margin=dict(t=48, b=8, l=8, r=8), showlegend=False)
    return terapkan_sumbu(fig)


def gambar_pie_entri(df):
    return _gambar_pie(komposisi_entri(df), 'jumlah_entri', 'Komposisi Entri', WARNA_KATEGORI)


def gambar_pie_poin(df):
    return _gambar_pie(komposisi_poin(df), 'total_poin', 'Komposisi Total Poin', WARNA_KATEGORI)


def gambar_tren_bulanan(df):
    if _kosong(df):
        return None
    data = df.copy()
    tanggal = pd.to_datetime(data['tanggal_kejadian'], errors='coerce')
    data = data[tanggal.notna()]
    if data.empty:
        return None
    data['bulan'] = tanggal[tanggal.notna()].dt.strftime('%Y-%m').values
    data['pelanggaran'] = (data['poin'] < 0).astype(int)
    data['prestasi'] = (data['poin'] > 0).astype(int)
    bulanan = data.groupby('bulan').agg(pelanggaran=('pelanggaran', 'sum'),
                                        prestasi=('prestasi', 'sum')).reset_index()
    bulanan = bulanan.sort_values('bulan')
    bulanan['label'] = bulanan['bulan'].map(label_bulan)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bulanan['label'], y=bulanan['pelanggaran'], mode='lines+markers',
                             name='Pelanggaran', line=dict(color=WARNA_PELANGGARAN[-1])))
    fig.add_trace(go.Scatter(x=bulanan['label'], y=bulanan['prestasi'], mode='lines+markers',
                             name='Prestasi', line=dict(color=WARNA_PRESTASI[-1])))
    terapkan_tata_letak(fig, title='Tren Bulanan Jumlah Entri', xaxis_title='Bulan',
                        yaxis_title='Jumlah entri', legend=dict(orientation='h', y=1.12, x=0),
                        margin=dict(t=64, b=8, l=8, r=8))
    terapkan_sumbu(fig)
    fig.update_xaxes(type='category', categoryorder='array',
                     categoryarray=bulanan['label'].tolist())
    return fig


def gambar_top_kode(df, kategori):
    data = top_kode(df, kategori)
    if _kosong(data):
        return None
    data = data.sort_values('jumlah_entri', ascending=False)
    palet = WARNA_PELANGGARAN if kategori == 'pelanggaran' else WARNA_PRESTASI
    fig = px.bar(data, x='label', y='jumlah_entri', text='jumlah_entri',
                 color='jumlah_entri', color_continuous_scale=palet)
    terapkan_tata_letak(fig, title=f'Top 10 Kode {kategori.capitalize()} berdasarkan Frekuensi',
                        xaxis_title='', yaxis_title='Jumlah entri', coloraxis_showscale=False,
                        height=460, margin=dict(t=48, b=8, l=8, r=8))
    terapkan_sumbu(fig)
    fig.update_xaxes(tickangle=-35)
    fig.update_traces(textposition='outside', textfont=dict(color=theme.TEKS_UTAMA))
    return fig


def gambar_poin_per_kelas(df, arah):
    data = poin_per_kelas(df)
    kolom = 'poin_minus' if arah == 'minus' else 'poin_plus'
    data = data[data[kolom] > 0]
    if _kosong(data):
        return None
    data = data.sort_values(kolom, ascending=True)
    palet = WARNA_PELANGGARAN if arah == 'minus' else WARNA_PRESTASI
    judul = 'Total Poin Minus per Kelas' if arah == 'minus' else 'Total Poin Plus per Kelas'
    fig = px.bar(data, x=kolom, y='kelas', orientation='h', text=kolom,
                 color=kolom, color_continuous_scale=palet)
    terapkan_tata_letak(fig, title=judul, xaxis_title='Total poin', yaxis_title='',
                        coloraxis_showscale=False, margin=dict(t=48, b=8, l=8, r=8))
    terapkan_sumbu(fig)
    fig.update_yaxes(type='category', categoryorder='array',
                     categoryarray=data['kelas'].tolist())
    fig.update_traces(textposition='outside', textfont=dict(color=theme.TEKS_UTAMA))
    return fig


def gambar_heatmap(df):
    data = heatmap_hari_jam(df)
    if _kosong(data):
        return None
    urutan_hari = [hari for hari in NAMA_HARI if hari in set(data['hari'])]
    urutan_jam = sorted([jam for jam in data['jam'].unique() if jam != TANPA_JAM]) + [TANPA_JAM]
    urutan_jam = [jam for jam in urutan_jam if jam in set(data['jam'])]
    pivot = data.pivot_table(index='hari', columns='jam', values='jumlah_entri',
                             aggfunc='sum', fill_value=0).reindex(index=urutan_hari, columns=urutan_jam)
    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
        colorscale=WARNA_HEATMAP,
        text=pivot.values, texttemplate='%{text}', textfont=dict(color=theme.TEKS_UTAMA),
        hovertemplate='Hari %{y}<br>Jam %{x}<br>%{z} entri<extra></extra>',
        colorbar=dict(title=dict(text='Entri', font=dict(color=theme.TEKS_REDUP)),
                      tickfont=dict(color=theme.TEKS_REDUP)),
    ))
    terapkan_tata_letak(fig, title='Heatmap Pelanggaran per Hari dan Jam Input',
                        xaxis_title='Jam input', yaxis_title='', margin=dict(t=48, b=8, l=8, r=8))
    return terapkan_sumbu(fig)


def gambar_treemap_subkategori(df):
    data = distribusi_subkategori(df)
    if _kosong(data):
        return None
    fig = px.treemap(data, path=['kategori', 'subkategori'], values='jumlah_entri',
                     color='kategori', color_discrete_map=WARNA_KATEGORI)
    fig.update_traces(textinfo='label+value+percent parent', textfont=dict(color=theme.TEKS_UTAMA))
    terapkan_tata_letak(fig, title='Distribusi Subkategori', margin=dict(t=48, b=8, l=8, r=8))
    return terapkan_sumbu(fig)
