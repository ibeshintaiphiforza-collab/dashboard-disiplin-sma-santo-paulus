import plotly.graph_objects as go
import plotly.io as pio

from core import theme

NAMA_TEMPLATE = 'disiplin_gelap'

TATA_LETAK_GELAP = dict(
    template=NAMA_TEMPLATE,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color=theme.TEKS_REDUP, size=12),
    title=dict(font=dict(color=theme.TEKS_UTAMA, size=14), x=0, xanchor='left'),
    legend=dict(font=dict(color=theme.TEKS_UTAMA)),
    hoverlabel=dict(bgcolor=theme.KARTU, bordercolor=theme.GARIS,
                    font=dict(color=theme.TEKS_UTAMA)),
    xaxis=dict(gridcolor=theme.GARIS, zerolinecolor=theme.GARIS, linecolor=theme.GARIS,
               tickfont=dict(color=theme.TEKS_REDUP), title=dict(font=dict(color=theme.TEKS_REDUP))),
    yaxis=dict(gridcolor=theme.GARIS, zerolinecolor=theme.GARIS, linecolor=theme.GARIS,
               tickfont=dict(color=theme.TEKS_REDUP), title=dict(font=dict(color=theme.TEKS_REDUP))),
)

WARNA_PELANGGARAN = ['#2A1712', '#5C2A20', '#8F3D2D', theme.PELANGGARAN, '#E2836B']
WARNA_PRESTASI = ['#12241D', '#1F4A3A', '#327A5E', theme.PRESTASI, '#8FD1B4']
WARNA_NETRAL = ['#1F1B17', '#3B342D', '#5D5347', theme.NETRAL, '#C3B7A3']
WARNA_KATEGORI = {'pelanggaran': theme.PELANGGARAN, 'prestasi': theme.PRESTASI,
                  'tanpa_pasal': theme.NETRAL}
WARNA_HEATMAP = [[0, theme.KARTU], [0.35, '#5C2A20'], [0.7, theme.PELANGGARAN], [1, '#E8CE7A']]


def _template():
    return go.layout.Template(
        layout=dict(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            colorway=[theme.EMAS, theme.PRESTASI, theme.PELANGGARAN, theme.EMAS_TERANG,
                      theme.NETRAL],
            font=dict(color=theme.TEKS_REDUP, size=12),
            title=dict(font=dict(color=theme.TEKS_UTAMA, size=14)),
            legend=dict(font=dict(color=theme.TEKS_UTAMA), bgcolor='rgba(0,0,0,0)'),
            xaxis=dict(gridcolor=theme.GARIS, zerolinecolor=theme.GARIS, linecolor=theme.GARIS,
                       tickfont=dict(color=theme.TEKS_REDUP), automargin=True),
            yaxis=dict(gridcolor=theme.GARIS, zerolinecolor=theme.GARIS, linecolor=theme.GARIS,
                       tickfont=dict(color=theme.TEKS_REDUP), automargin=True),
            coloraxis=dict(colorbar=dict(tickfont=dict(color=theme.TEKS_REDUP),
                                         title=dict(font=dict(color=theme.TEKS_REDUP)))),
        )
    )


def daftarkan_template():
    if NAMA_TEMPLATE not in pio.templates:
        pio.templates[NAMA_TEMPLATE] = _template()
    return NAMA_TEMPLATE


def terapkan_tata_letak(fig, **tambahan):
    daftarkan_template()
    fig.update_layout(**TATA_LETAK_GELAP)
    if tambahan:
        fig.update_layout(**tambahan)
    return fig


def terapkan_sumbu(fig):
    daftarkan_template()
    fig.update_layout(template=NAMA_TEMPLATE)
    fig.update_xaxes(gridcolor=theme.GARIS, zerolinecolor=theme.GARIS, linecolor=theme.GARIS,
                     tickfont=dict(color=theme.TEKS_REDUP),
                     title=dict(font=dict(color=theme.TEKS_REDUP)))
    fig.update_yaxes(gridcolor=theme.GARIS, zerolinecolor=theme.GARIS, linecolor=theme.GARIS,
                     tickfont=dict(color=theme.TEKS_REDUP),
                     title=dict(font=dict(color=theme.TEKS_REDUP)))
    return fig


def teks_terang():
    return dict(color=theme.TEKS_UTAMA)
