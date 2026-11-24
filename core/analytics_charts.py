import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core import analytics, theme
from core.chart_theme import (WARNA_PELANGGARAN, WARNA_PRESTASI, teks_terang,
                              terapkan_sumbu, terapkan_tata_letak)
from core.thresholds import THRESHOLDS_SP, status_peringatan

WARNA_ABU = theme.NETRAL
WARNA_PLUS = theme.PRESTASI
WARNA_MINUS = theme.PELANGGARAN
WARNA_SISWA = theme.EMAS
WARNA_BAND = {
    'green': '#2ca02c',
    'yellow': '#f2c200',
    'orange': '#f28e2b',
    'red': '#d62728',
    'darkred': '#7f0000',
}
NAMA_RANTAI = {
    'terlambat': 'Terlambat (ME-02..ME-07)',
    'buku_prestasi_disiplin': 'Buku (ME-08..ME-10)',
}
WARNA_RANTAI = {'terlambat': WARNA_MINUS, 'buku_prestasi_disiplin': WARNA_PLUS}
TINGGI = 380

TATA_LETAK = dict(
    height=TINGGI,
    margin=dict(l=8, r=8, t=16, b=8),
    legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0, title_text=''),
    hovermode='closest',
)


def _kosong(df):
    return df is None or df.empty


def _label_pasal(data):
    hasil = data.copy()
    deskripsi = hasil['deskripsi'].fillna('').astype(str).str.strip()
    ringkas = deskripsi.str.split(r'(?<=\.)\s', n=1, regex=True).str[0].str.rstrip('.')
    ringkas = ringkas.where(ringkas.str.len() <= 34, ringkas.str.slice(0, 31) + '...')
    hasil['label'] = hasil['kode_pasal'].astype(str) + ' - ' + ringkas
    return hasil


def _label_singkat(ambang):
    return ambang['label'].split(' (')[0]


def _siapkan(fig, sumbu='x', urutan=None, sumbu_x='', sumbu_y=''):
    """Terapkan tata letak, gaya sumbu, dan paksa sumbu teks menjadi kategori."""
    terapkan_tata_letak(fig, **TATA_LETAK)
    terapkan_sumbu(fig)
    if sumbu == 'x':
        fig.update_xaxes(type='category')
        if urutan:
            fig.update_xaxes(categoryorder='array', categoryarray=urutan)
        fig.update_xaxes(title_text=sumbu_x)
    else:
        fig.update_yaxes(type='category')
        if urutan:
            fig.update_yaxes(categoryorder='array', categoryarray=urutan)
        fig.update_yaxes(title_text=sumbu_y)
    return fig


def fig_pelanggaran_berulang(df):
    """Bar horizontal 15 siswa dengan pengulangan kode pasal terbanyak."""
    if _kosong(df):
        return None
    data = analytics.pelanggaran_berulang(df)
    if data.empty:
        return None
    data = data.sort_values(['jumlah_entri', 'total_poin'], ascending=[False, True]).head(15).copy()
    data['label'] = data['nama'].astype(str) + ' - ' + data['kode_pasal'].astype(str)
    data = data.sort_values('jumlah_entri')
    fig = go.Figure(go.Bar(
        x=data['jumlah_entri'], y=data['label'], orientation='h',
        marker=dict(color=data['jumlah_entri'], colorscale=WARNA_PELANGGARAN, showscale=False),
        text=data['jumlah_entri'], textposition='outside',
        hovertemplate='%{y}<br>%{x} kali pengulangan<extra></extra>',
    ))
    return _siapkan(fig, 'y', data['label'].tolist(), 'Jumlah pengulangan', '')


def fig_eskalasi(df):
    """Bar kelompok distribusi siswa per tahap pada rantai terlambat dan buku."""
    if _kosong(df):
        return None
    data = analytics.eskalasi_tahapan(df)
    if data.empty:
        return None
    tahap_maks = int(data['tahap_maks'].max())
    label_tahap = [f'Tahap {posisi}' for posisi in range(1, tahap_maks + 1)]
    fig = go.Figure()
    for rantai, warna in WARNA_RANTAI.items():
        bagian = data[data['rantai'] == rantai]
        if bagian.empty:
            continue
        hitung = bagian['tahap'].value_counts()
        nilai = [int(hitung.get(posisi, 0)) for posisi in range(1, tahap_maks + 1)]
        fig.add_trace(go.Bar(
            x=label_tahap, y=nilai, name=NAMA_RANTAI[rantai], marker_color=warna,
            text=nilai, textposition='outside',
            hovertemplate='%{x}<br>%{y} murid<extra></extra>',
        ))
    fig.update_layout(barmode='group')
    return _siapkan(fig, 'x', label_tahap, 'Tahap', 'Jumlah murid')


def fig_early_warning(df):
    """Bar horizontal siswa menurut poin minus dengan garis ambang SP."""
    if _kosong(df):
        return None
    data = analytics.siswa_berisiko(df).copy()
    if data.empty:
        return None
    data = data[data['poin_minus'] < 0].copy()
    if data.empty:
        return None
    data['ambang'] = data['poin_minus'].map(lambda nilai: status_peringatan(int(nilai)))
    data['band'] = data['ambang'].map(lambda ambang: ambang['label'])
    data['label'] = data['nama'].astype(str) + ' - ' + data['kelas'].astype(str)
    data = data.sort_values(['poin_minus', 'label'], ascending=[False, True])
    fig = go.Figure()
    for ambang in THRESHOLDS_SP:
        bagian = data[data['band'] == ambang['label']]
        if bagian.empty:
            continue
        fig.add_trace(go.Bar(
            x=bagian['poin_minus'], y=bagian['label'], orientation='h',
            name=_label_singkat(ambang), marker_color=WARNA_BAND[ambang['color']],
            hovertemplate='%{y}<br>%{x} poin<extra></extra>',
        ))
    for ambang in THRESHOLDS_SP:
        if ambang['threshold'] >= 0:
            continue
        fig.add_vline(x=ambang['threshold'], line_dash='dash', line_color=WARNA_ABU,
                      annotation_text=f"{_label_singkat(ambang)} ({ambang['threshold']})",
                      annotation_position='top', annotation_font=teks_terang())
    fig.update_yaxes(type='category', categoryorder='array',
                     categoryarray=data['label'].tolist())
    return _siapkan(fig, 'y', data['label'].tolist(), 'Akumulasi poin minus', '')


def fig_pasal_frekuensi(df):
    """Bar horizontal 15 kode pasal terbanyak menurut jumlah entri."""
    if _kosong(df):
        return None
    data = analytics.analisis_per_pasal(df)
    if data.empty:
        return None
    data = data.sort_values(['jumlah_entri', 'kode_pasal'], ascending=[False, True]).head(15).copy()
    data = _label_pasal(data).sort_values('jumlah_entri')
    fig = go.Figure()
    for kategori, palet in [('pelanggaran', WARNA_PELANGGARAN), ('prestasi', WARNA_PRESTASI)]:
        bagian = data[data['kategori'] == kategori]
        if bagian.empty:
            continue
        fig.add_trace(go.Bar(
            x=bagian['jumlah_entri'], y=bagian['label'], orientation='h', name=kategori.capitalize(),
            marker=dict(color=bagian['jumlah_entri'], colorscale=palet, showscale=False),
            text=bagian['jumlah_entri'], textposition='outside',
            hovertemplate='%{y}<br>%{x} entri<extra></extra>',
        ))
    lainnya = data[~data['kategori'].isin(['pelanggaran', 'prestasi'])]
    if not lainnya.empty:
        fig.add_trace(go.Bar(
            x=lainnya['jumlah_entri'], y=lainnya['label'], orientation='h', name='Tanpa pasal',
            marker_color=WARNA_ABU, text=lainnya['jumlah_entri'], textposition='outside',
            hovertemplate='%{y}<br>%{x} entri<extra></extra>',
        ))
    return _siapkan(fig, 'y', data['label'].tolist(), 'Jumlah entri', '')


def fig_pasal_poin(df):
    """Bar horizontal 15 kode pasal dengan total poin terbesar."""
    if _kosong(df):
        return None
    data = analytics.analisis_per_pasal(df)
    if data.empty:
        return None
    data = data.copy()
    data['nilai'] = data['total_poin'].abs()
    data = data.sort_values(['nilai', 'kode_pasal'], ascending=[False, True]).head(15)
    data = _label_pasal(data).sort_values('nilai')
    fig = go.Figure()
    for kategori, palet in [('pelanggaran', WARNA_PELANGGARAN), ('prestasi', WARNA_PRESTASI)]:
        bagian = data[data['kategori'] == kategori]
        if bagian.empty:
            continue
        fig.add_trace(go.Bar(
            x=bagian['nilai'], y=bagian['label'], orientation='h', name=kategori.capitalize(),
            marker=dict(color=bagian['nilai'], colorscale=palet, showscale=False),
            text=bagian['nilai'], textposition='outside',
            hovertemplate='%{y}<br>%{x} poin<extra></extra>',
        ))
    lainnya = data[~data['kategori'].isin(['pelanggaran', 'prestasi'])]
    if not lainnya.empty:
        fig.add_trace(go.Bar(
            x=lainnya['nilai'], y=lainnya['label'], orientation='h', name='Tanpa pasal',
            marker_color=WARNA_ABU, text=lainnya['nilai'], textposition='outside',
            hovertemplate='%{y}<br>%{x} poin<extra></extra>',
        ))
    return _siapkan(fig, 'y', data['label'].tolist(), 'Total poin', '')


def fig_tingkat(df):
    """Bar kelompok poin plus dan minus per tingkat dengan garis jumlah siswa."""
    if _kosong(df):
        return None
    data = analytics.analisis_per_tingkat(df)
    if data.empty:
        return None
    data = data[data['tingkat'].isin(['10', '11', '12'])].sort_values('tingkat')
    if data.empty:
        return None
    fig = make_subplots(specs=[[{'secondary_y': True}]])
    fig.add_trace(go.Bar(
        x=data['tingkat'], y=data['poin_plus'], name='Poin plus', marker_color=WARNA_PLUS,
        text=data['poin_plus'], textposition='outside',
        hovertemplate='Tingkat %{x}<br>%{y} poin plus<extra></extra>',
    ), secondary_y=False)
    fig.add_trace(go.Bar(
        x=data['tingkat'], y=data['poin_minus'].abs(), name='Poin minus', marker_color=WARNA_MINUS,
        text=data['poin_minus'].abs(), textposition='outside',
        hovertemplate='Tingkat %{x}<br>%{y} poin minus<extra></extra>',
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=data['tingkat'], y=data['jumlah_siswa'], name='Jumlah murid', mode='lines+markers',
        line=dict(color=WARNA_SISWA), marker=dict(size=9),
        hovertemplate='Tingkat %{x}<br>%{y} murid<extra></extra>',
    ), secondary_y=True)
    fig.update_layout(**TATA_LETAK, barmode='group')
    _siapkan(fig, 'x', data['tingkat'].tolist(), 'Tingkat', '')
    fig.update_yaxes(title_text='Poin', secondary_y=False)
    fig.update_yaxes(title_text='Jumlah murid', secondary_y=True, rangemode='tozero')
    return fig


def fig_kelas(df, siswa=None):
    """Bar bertumpuk horizontal poin plus dan minus per kelas."""
    if _kosong(df):
        return None
    data = analytics.peringkat_kelas(df, siswa)
    if data.empty:
        return None
    data = data.copy()
    data['poin_minus'] = data['poin_minus'].abs()
    data = data.sort_values(['poin_plus', 'poin_minus', 'kelas'])
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=data['poin_plus'], y=data['kelas'], orientation='h', name='Poin plus',
        marker_color=WARNA_PLUS, hovertemplate='%{y}<br>%{x} poin plus<extra></extra>',
    ))
    fig.add_trace(go.Bar(
        x=data['poin_minus'], y=data['kelas'], orientation='h', name='Poin minus',
        marker_color=WARNA_MINUS, hovertemplate='%{y}<br>%{x} poin minus<extra></extra>',
    ))
    fig.update_layout(barmode='stack')
    fig.update_yaxes(type='category', categoryorder='array',
                     categoryarray=data['kelas'].tolist())
    return _siapkan(fig, 'y', data['kelas'].tolist(), 'Total poin', '')


def fig_petugas(df):
    """Dua subplot: jumlah entri per petugas dan komposisi kategori."""
    if _kosong(df):
        return None
    stat = analytics.statistik_petugas(df)
    distribusi = analytics.distribusi_kategori_petugas(df)
    if stat.empty and distribusi.empty:
        return None
    urutan = stat['petugas'].tolist() if not stat.empty else distribusi['petugas'].tolist()
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.12,
                        subplot_titles=['Entri per petugas', 'Komposisi kategori per petugas'])
    if not stat.empty:
        data = stat.set_index('petugas').reindex(urutan).reset_index()
        fig.add_trace(go.Bar(
            x=data['petugas'], y=data['jumlah_entri'], name='Jumlah entri',
            marker_color=WARNA_SISWA, text=data['jumlah_entri'], textposition='outside',
            hovertemplate='%{x}<br>%{y} entri<extra></extra>',
        ), row=1, col=1)
    if not distribusi.empty:
        data = distribusi.set_index('petugas').reindex(urutan).fillna(0).reset_index()
        kategori = [kolom for kolom in data.columns if kolom != 'petugas']
        warna = {'pelanggaran': WARNA_MINUS, 'prestasi': WARNA_PLUS}
        for kolom in kategori:
            fig.add_trace(go.Bar(
                x=data['petugas'], y=data[kolom], name=kolom.replace('_', ' ').capitalize(),
                marker_color=warna.get(kolom, WARNA_ABU), showlegend=True,
                hovertemplate='%{x}<br>%{y} entri<extra></extra>',
            ), row=1, col=2)
    fig.update_layout(**TATA_LETAK, barmode='stack')
    _siapkan(fig, 'x', urutan)
    fig.update_yaxes(title_text='Jumlah entri', row=1, col=1)
    fig.update_yaxes(title_text='Jumlah entri', row=1, col=2)
    return fig


def fig_tren(df):
    """Garis bulanan pelanggaran dan prestasi plus kumulatif terpisah."""
    if _kosong(df):
        return None
    data = analytics.tren_bulanan(df)
    if data.empty:
        return None
    data = data.copy()
    data['label'] = data['bulan'].map(analytics.label_bulan)
    fig = make_subplots(specs=[[{'secondary_y': True}]])
    fig.add_trace(go.Scatter(
        x=data['label'], y=data['pelanggaran'], name='Pelanggaran', mode='lines+markers',
        line=dict(color=WARNA_MINUS), hovertemplate='%{x}<br>%{y} pelanggaran<extra></extra>',
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=data['label'], y=data['prestasi'], name='Prestasi', mode='lines+markers',
        line=dict(color=WARNA_PLUS), hovertemplate='%{x}<br>%{y} prestasi<extra></extra>',
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=data['label'], y=data['kumulatif_pelanggaran'], name='Kumulatif pelanggaran', mode='lines+markers',
        line=dict(color=WARNA_MINUS, dash='dot'),
        hovertemplate='%{x}<br>%{y} poin<extra></extra>',
    ), secondary_y=True)
    fig.add_trace(go.Scatter(
        x=data['label'], y=data['kumulatif_prestasi'], name='Kumulatif prestasi', mode='lines+markers',
        line=dict(color=WARNA_PLUS, dash='dot'),
        hovertemplate='%{x}<br>%{y} poin<extra></extra>',
    ), secondary_y=True)
    fig.update_layout(**TATA_LETAK)
    _siapkan(fig, 'x', data['label'].tolist(), 'Bulan', '')
    fig.update_yaxes(title_text='Jumlah entri', secondary_y=False)
    fig.update_yaxes(title_text='Kumulatif poin', secondary_y=True)
    return fig


def fig_kumulatif_siswa(data):
    """Garis kumulatif pelanggaran dan prestasi siswa pada sumbu terpisah."""
    kolom = {'tanggal_kejadian', 'kumulatif_pelanggaran', 'kumulatif_prestasi'}
    if _kosong(data) or not kolom.issubset(data.columns):
        return None
    fig = make_subplots(specs=[[{'secondary_y': True}]])
    fig.add_trace(go.Scatter(
        x=data['tanggal_kejadian'], y=data['kumulatif_pelanggaran'],
        name='Kumulatif pelanggaran', mode='lines+markers',
        line=dict(color=WARNA_MINUS),
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=data['tanggal_kejadian'], y=data['kumulatif_prestasi'],
        name='Kumulatif prestasi', mode='lines+markers',
        line=dict(color=WARNA_PLUS),
    ), secondary_y=True)
    fig.update_layout(**TATA_LETAK)
    _siapkan(fig, 'x', data['tanggal_kejadian'].tolist(), 'Tanggal', '')
    fig.update_yaxes(title_text='Poin pelanggaran', secondary_y=False)
    fig.update_yaxes(title_text='Poin prestasi', secondary_y=True)
    return fig


def fig_hari(df):
    """Bar kelompok pelanggaran dan prestasi per hari."""
    if _kosong(df) or 'tanggal_kejadian' not in df.columns:
        return None
    data = df.copy()
    tanggal = pd.to_datetime(data['tanggal_kejadian'], errors='coerce')
    data = data[tanggal.notna()].copy()
    if data.empty:
        return None
    data['hari'] = tanggal[tanggal.notna()].dt.day_of_week.map(
        lambda posisi: analytics.NAMA_HARI[posisi]).values
    data['pelanggaran'] = (data['poin'] < 0).astype(int)
    data['prestasi'] = (data['poin'] > 0).astype(int)
    hitung = data.groupby('hari')[['pelanggaran', 'prestasi']].sum().reindex(
        analytics.NAMA_HARI, fill_value=0)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=hitung.index.tolist(), y=hitung['pelanggaran'].tolist(), name='Pelanggaran',
        marker_color=WARNA_MINUS, hovertemplate='%{x}<br>%{y} pelanggaran<extra></extra>',
    ))
    fig.add_trace(go.Bar(
        x=hitung.index.tolist(), y=hitung['prestasi'].tolist(), name='Prestasi',
        marker_color=WARNA_PLUS, hovertemplate='%{x}<br>%{y} prestasi<extra></extra>',
    ))
    fig.update_layout(barmode='group')
    _siapkan(fig, 'x', analytics.NAMA_HARI)
    return _terapkan(fig, 'Hari', 'Jumlah entri')


def _terapkan(fig, sumbu_x='', sumbu_y=''):
    """Fallback kompatibilitas: terapkan tata standar tanpa mengubah kategori."""
    terapkan_tata_letak(fig, **TATA_LETAK)
    terapkan_sumbu(fig)
    fig.update_xaxes(title_text=sumbu_x)
    fig.update_yaxes(title_text=sumbu_y)
    return fig
