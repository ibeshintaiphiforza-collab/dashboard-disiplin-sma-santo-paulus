import io
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from core.thresholds import THRESHOLDS_SP, status_peringatan

NAMA_SEKOLAH = 'SMA Katolik Santo Paulus Jember'
KOSONG = 'Tidak ada data'
WARNA_KEPALA = colors.HexColor('#1F3864')
WARNA_GARIS = colors.HexColor('#B7B7B7')
WARNA_LAJUR = colors.HexColor('#F2F2F2')
WARNA_META = colors.HexColor('#444444')

AKAR_PROYEK = Path(__file__).resolve().parent.parent
LOGO_PDF = AKAR_PROYEK / 'assets' / 'logo-pdf.png'
LOGO_SEKOLAH = AKAR_PROYEK / 'assets' / 'logo-sekolah.png'
TINGGI_LOGO = 46

LABEL_RINGKASAN = {
    'total_entri': 'Jumlah entri',
    'jumlah_entri': 'Jumlah entri',
    'jumlah_siswa': 'Jumlah murid',
    'jumlah_kelas': 'Jumlah kelas',
    'poin_prestasi': 'Total poin prestasi',
    'poin_pelanggaran': 'Total poin pelanggaran',
    'poin_plus': 'Total poin plus',
    'poin_minus': 'Total poin minus',
    'netto': 'Netto',
    'siswa_berisiko': 'Jumlah murid berisiko',
    'jumlah_siswa_berisiko': 'Jumlah murid berisiko',
}


def _teks_opsional(nilai):
    if nilai is None:
        return ''
    try:
        if pd.isna(nilai):
            return ''
    except (TypeError, ValueError):
        pass
    teks = str(nilai).strip()
    return teks


def _teks(nilai):
    return _teks_opsional(nilai) or '-'


def _angka(nilai):
    if nilai is None:
        return '-'
    try:
        if pd.isna(nilai):
            return '-'
    except (TypeError, ValueError):
        pass
    try:
        return f'{int(round(float(nilai)))}'
    except (TypeError, ValueError):
        return _teks(nilai)


def _tanggal(nilai):
    parsed = pd.to_datetime(nilai, errors='coerce')
    if parsed is None or pd.isna(parsed):
        return _teks(nilai)
    return parsed.strftime('%d-%m-%Y')


def _label(nilai):
    teks = _teks(nilai)
    return teks.replace('_', ' ')


def _frame_aman(data):
    return data if isinstance(data, pd.DataFrame) else pd.DataFrame()


def _uraian(baris):
    for kolom in ['keterangan', 'judul', 'deskripsi']:
        teks = _teks_opsional(baris.get(kolom))
        if teks:
            return teks
    return '-'


def _gaya():
    dasar = getSampleStyleSheet()
    return {
        'sekolah': ParagraphStyle('sekolah', parent=dasar['Title'], fontName='Helvetica-Bold',
                                  fontSize=15, leading=18, alignment=TA_CENTER, spaceAfter=1),
        'judul': ParagraphStyle('judul', parent=dasar['Heading2'], fontName='Helvetica-Bold',
                                fontSize=11.5, leading=14, alignment=TA_CENTER, spaceAfter=2),
        'meta': ParagraphStyle('meta', parent=dasar['Normal'], fontName='Helvetica', fontSize=8.5,
                               leading=11, alignment=TA_CENTER, textColor=WARNA_META),
        'seksi': ParagraphStyle('seksi', parent=dasar['Heading3'], fontName='Helvetica-Bold',
                                fontSize=10, leading=13, spaceBefore=10, spaceAfter=4,
                                textColor=WARNA_KEPALA),
        'sel': ParagraphStyle('sel', parent=dasar['Normal'], fontName='Helvetica', fontSize=8.5,
                              leading=10.5),
        'kepala': ParagraphStyle('kepala', parent=dasar['Normal'], fontName='Helvetica-Bold',
                                 fontSize=8.5, leading=10.5, textColor=colors.white),
        'catatan': ParagraphStyle('catatan', parent=dasar['Normal'], fontName='Helvetica', fontSize=8.5,
                                  leading=11, textColor=WARNA_META),
    }


def _sel(teks, gaya):
    return Paragraph(escape(_teks(teks)), gaya['sel'])


def _tabel(kepala, baris, lebar, gaya, sejajar=None):
    if not baris:
        return Paragraph(escape(f'{baris_kosong()[0][0]}.'), gaya['catatan'])
    data = [[Paragraph(escape(str(kolom)), gaya['kepala']) for kolom in kepala]]
    for isi in baris:
        data.append([_sel(nilai, gaya) for nilai in isi])
    tabel = Table(data, colWidths=lebar, repeatRows=1)
    perintah = [
        ('BACKGROUND', (0, 0), (-1, 0), WARNA_KEPALA),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.4, WARNA_GARIS),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, WARNA_LAJUR]),
    ]
    for posisi, rata in (sejajar or {}).items():
        perintah.append(('ALIGN', (posisi, 1), (posisi, -1), rata))
    tabel.setStyle(TableStyle(perintah))
    return tabel


def _logo_flowable(tinggi=TINGGI_LOGO):
    try:
        berkas = LOGO_PDF if LOGO_PDF.exists() else LOGO_SEKOLAH
        if not berkas.exists():
            return None
        from reportlab.lib.utils import ImageReader
        pembaca = ImageReader(str(berkas))
        lebar_px, tinggi_px = pembaca.getSize()
        if not lebar_px or not tinggi_px:
            return None
        lebar = tinggi * (lebar_px / tinggi_px)
        gambar = Image(str(berkas), width=lebar, height=tinggi)
        gambar.hAlign = 'LEFT'
        return gambar
    except Exception:
        return None


def _kepala_dokumen(judul, periode_label, gaya):
    periode = _teks_opsional(periode_label) or 'seluruh data'
    dibuat = datetime.now().strftime('%d-%m-%Y %H:%M')
    teks = [
        Paragraph(escape(NAMA_SEKOLAH), gaya['sekolah']),
        Paragraph(escape(judul), gaya['judul']),
        Paragraph(escape(f'Periode: {periode}'), gaya['meta']),
        Paragraph(escape(f'Dibuat: {dibuat}'), gaya['meta']),
    ]
    logo = _logo_flowable()
    if logo is None:
        alur = list(teks)
    else:
        tabel = Table([[logo, teks]], colWidths=[logo.drawWidth + 10, None])
        tabel.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        alur = [tabel]
    alur.append(Spacer(1, 6))
    return alur


def _footer(canvas, doc):
    canvas.saveState()
    lebar = doc.pagesize[0]
    canvas.setStrokeColor(WARNA_GARIS)
    canvas.setLineWidth(0.4)
    canvas.line(15 * mm, 14 * mm, lebar - 15 * mm, 14 * mm)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(WARNA_META)
    canvas.drawString(15 * mm, 9 * mm, NAMA_SEKOLAH)
    canvas.drawRightString(lebar - 15 * mm, 9 * mm, f'Halaman {doc.page}')
    canvas.restoreState()


def _bangun(alur, pagesize, judul):
    buffer = io.BytesIO()
    dokumen = SimpleDocTemplate(
        buffer, pagesize=pagesize, pageCompression=0,
        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=18 * mm,
        title=judul, author=NAMA_SEKOLAH, subject='Laporan Disiplin dan Prestasi')
    dokumen.build(alur, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def periode_label(df, baku='seluruh data'):
    data = _frame_aman(df)
    if data.empty or 'tanggal_kejadian' not in data.columns:
        return baku
    tanggal = pd.to_datetime(data['tanggal_kejadian'], errors='coerce').dropna()
    if tanggal.empty:
        return baku
    awal = tanggal.min().strftime('%d-%m-%Y')
    akhir = tanggal.max().strftime('%d-%m-%Y')
    return awal if awal == akhir else f'{awal} sampai {akhir}'


def baris_kosong():
    return [[KOSONG]]


def _baris_kelas(rekap):
    baris = []
    for _, data in rekap.iterrows():
        baris.append([
            _teks(data.get('kelas')),
            _angka(data.get('poin_plus')),
            _angka(data.get('poin_minus')),
            _angka(data.get('netto')),
            _angka(data.get('jumlah_entri')),
            _angka(data.get('jumlah_siswa')),
        ])
    return baris


def _tabel_kelas(rekap, gaya):
    return _tabel(['Kelas', 'Poin plus', 'Poin minus', 'Netto', 'Jumlah entri', 'Jumlah murid'],
                  _baris_kelas(rekap), [50 * mm, 45 * mm, 45 * mm, 42 * mm, 40 * mm, 45 * mm],
                  gaya, {1: 'RIGHT', 2: 'RIGHT', 3: 'RIGHT', 4: 'RIGHT', 5: 'RIGHT'})


def _ringkasan_subkategori(data):
    kolom = ['subkategori', 'kategori', 'poin_plus', 'poin_minus', 'netto', 'jumlah_entri']
    if data.empty or 'subkategori' not in data.columns or 'poin' not in data.columns:
        return pd.DataFrame(columns=kolom)
    salinan = data.copy()
    salinan['subkategori'] = salinan['subkategori'].fillna('tanpa_pasal')
    if 'kategori' not in salinan.columns:
        salinan['kategori'] = 'tanpa_pasal'
    salinan['kategori'] = salinan['kategori'].fillna('tanpa_pasal')
    salinan['poin_plus'] = salinan['poin'].clip(lower=0)
    salinan['poin_minus'] = salinan['poin'].clip(upper=0)
    hasil = salinan.groupby(['subkategori', 'kategori']).agg(
        poin_plus=('poin_plus', 'sum'),
        poin_minus=('poin_minus', 'sum'),
        netto=('poin', 'sum'),
        jumlah_entri=('poin', 'size'),
    ).reset_index()
    return hasil.sort_values('jumlah_entri', ascending=False).reset_index(drop=True)[kolom]


def rapor_siswa_pdf(profil, riwayat, periode_label, batas_riwayat=None):
    gaya = _gaya()
    data = _frame_aman(riwayat)
    profil = dict(profil or {})
    nama = _teks(profil.get('nama'))
    nis = _teks(profil.get('nis'))
    if not data.empty and 'nis' in data.columns:
        data = data[data['nis'].astype(str) == str(profil.get('nis'))]

    judul = f'Rapor Poin Murid - {nama if nama != "-" else nis}'
    alur = _kepala_dokumen(judul, periode_label, gaya)

    alur.append(Paragraph('Identitas Murid', gaya['seksi']))
    identitas = [
        ['NIS', nis],
        ['Nama', nama],
        ['Kelas', _teks(profil.get('kelas'))],
        ['Absen', _teks(profil.get('absen'))],
        ['Sumber identitas', _label(profil.get('sumber_identitas'))],
    ]
    alur.append(_tabel(['Keterangan', 'Nilai'], identitas, [40 * mm, 140 * mm], gaya))

    alur.append(Paragraph('Ringkasan Poin', gaya['seksi']))
    ringkasan = [
        ['Poin prestasi', _angka(profil.get('poin_prestasi'))],
        ['Poin pelanggaran', _angka(profil.get('poin_pelanggaran'))],
        ['Netto', _angka(profil.get('netto'))],
        ['Jumlah entri', _angka(profil.get('jumlah_entri'))],
    ]
    alur.append(_tabel(['Keterangan', 'Nilai'], ringkasan, [40 * mm, 140 * mm], gaya,
                       {1: 'RIGHT'}))

    try:
        poin_minus = int(profil.get('poin_pelanggaran') or 0)
    except (TypeError, ValueError):
        poin_minus = 0
    status = status_peringatan(poin_minus)
    alur.append(Spacer(1, 6))
    alur.append(Paragraph(
        escape(f'Status surat peringatan: {status["label"]}.'), gaya['catatan']))
    alur.append(Paragraph(
        'Status dihitung dari akumulasi poin pelanggaran pada periode ini.', gaya['catatan']))

    alur.append(Paragraph('Rincian Prestasi dan Pelanggaran per Subkategori', gaya['seksi']))
    rekap_sub = _ringkasan_subkategori(data)
    baris_sub = []
    for _, baris in rekap_sub.iterrows():
        baris_sub.append([
            _label(baris.get('subkategori')),
            _label(baris.get('kategori')),
            _angka(baris.get('poin_plus')),
            _angka(baris.get('poin_minus')),
            _angka(baris.get('netto')),
            _angka(baris.get('jumlah_entri')),
        ])
    alur.append(_tabel(['Subkategori', 'Kategori', 'Poin plus', 'Poin minus', 'Netto', 'Entri'],
                       baris_sub, [55 * mm, 35 * mm, 22 * mm, 22 * mm, 20 * mm, 26 * mm],
                       gaya, {2: 'RIGHT', 3: 'RIGHT', 4: 'RIGHT', 5: 'RIGHT'}))

    alur.append(Paragraph('Riwayat Entri Kronologis', gaya['seksi']))
    urut = data
    if not data.empty and 'tanggal_kejadian' in data.columns:
        urut = (data.assign(_tanggal_urut=pd.to_datetime(data['tanggal_kejadian'], errors='coerce'))
                .sort_values('_tanggal_urut', kind='stable').drop(columns='_tanggal_urut'))
    sisa = 0
    if batas_riwayat is not None and len(urut) > batas_riwayat:
        sisa = len(urut) - batas_riwayat
        urut = urut.tail(batas_riwayat)
    baris_entri = []
    for _, baris in urut.iterrows():
        baris_entri.append([
            _tanggal(baris.get('tanggal_kejadian')),
            _teks(baris.get('kode_pasal')),
            _uraian(baris),
            _angka(baris.get('poin')),
            _teks(baris.get('petugas')),
        ])
    alur.append(_tabel(['Tanggal', 'Kode', 'Uraian', 'Poin', 'Petugas'], baris_entri,
                       [24 * mm, 18 * mm, 94 * mm, 14 * mm, 30 * mm], gaya, {3: 'RIGHT'}))
    if sisa:
        alur.append(Paragraph(escape(f'dan {sisa} entri lainnya'), gaya['catatan']))

    alur.append(Paragraph('Tanda Tangan', gaya['seksi']))
    alur.append(Spacer(1, 10))
    blok_ttd = [[Paragraph('Orang Tua/Wali', gaya['sel']), Paragraph('Wali Kelas', gaya['sel']),
                 Paragraph('Kepala Sekolah', gaya['sel'])]]
    tabel_ttd = Table(blok_ttd, colWidths=[60 * mm, 60 * mm, 60 * mm])
    tabel_ttd.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 40),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LINEBELOW', (0, 0), (-1, -1), 0, colors.white),
        ('GRID', (0, 0), (-1, 0), 0.4, WARNA_GARIS),
    ]))
    alur.append(tabel_ttd)

    return _bangun(alur, A4, judul)


def rekap_kelas_pdf(rekap_kelas_df, detail_df, kelas, periode_label):
    gaya = _gaya()
    label_kelas = _teks_opsional(kelas)
    judul = f'Rekap Kelas {label_kelas}'.strip()
    alur = _kepala_dokumen(judul, periode_label, gaya)
    rekap = _frame_aman(rekap_kelas_df)
    detail = _frame_aman(detail_df)

    alur.append(Paragraph('Ringkasan per Kelas', gaya['seksi']))
    alur.append(_tabel_kelas(rekap, gaya))

    alur.append(Paragraph(f'Rincian Murid Kelas {label_kelas}'.strip(), gaya['seksi']))
    if label_kelas and not detail.empty and 'kelas' in detail.columns:
        detail = detail[detail['kelas'].astype(str).str.strip() == label_kelas]
    baris = []
    for _, siswa in detail.iterrows():
        try:
            poin_minus = int(siswa.get('poin_minus') or 0)
        except (TypeError, ValueError):
            poin_minus = 0
        baris.append([
            _teks(siswa.get('nis')),
            _teks(siswa.get('nama')),
            _teks(siswa.get('absen')),
            _angka(siswa.get('poin_plus')),
            _angka(siswa.get('poin_minus')),
            _angka(siswa.get('netto')),
            _angka(siswa.get('jumlah_entri')),
            status_peringatan(poin_minus)['label'],
        ])
    alur.append(_tabel(['NIS', 'Nama', 'Absen', 'Poin plus', 'Poin minus', 'Netto', 'Entri',
                        'Status SP'], baris,
                       [22 * mm, 72 * mm, 16 * mm, 24 * mm, 24 * mm, 22 * mm, 22 * mm, 65 * mm],
                       gaya, {3: 'RIGHT', 4: 'RIGHT', 5: 'RIGHT', 6: 'RIGHT'}))
    alur.append(Spacer(1, 6))
    alur.append(Paragraph('Status SP dihitung dari akumulasi poin pelanggaran setiap murid.',
                          gaya['catatan']))

    return _bangun(alur, landscape(A4), judul)


def _baris_ringkasan(ringkasan):
    baris = []
    for kunci, nilai in (ringkasan or {}).items():
        if not pd.api.types.is_scalar(nilai):
            continue
        label = LABEL_RINGKASAN.get(str(kunci), str(kunci).replace('_', ' ').capitalize())
        angka = _angka(nilai) if pd.api.types.is_number(nilai) and not isinstance(nilai, bool) else _teks(nilai)
        baris.append([label, angka])
    return baris


def _baris_legenda():
    baris = []
    for ambang in THRESHOLDS_SP:
        batas = '0 atau lebih' if int(ambang['threshold']) == 0 else f'<= {int(ambang["threshold"])}'
        baris.append([batas, ambang['label']])
    return baris


def rekap_sekolah_pdf(rekap_kelas_df, periode_label, ringkasan):
    gaya = _gaya()
    judul = 'Rekap Sekolah'
    alur = _kepala_dokumen(judul, periode_label, gaya)
    rekap = _frame_aman(rekap_kelas_df)

    alur.append(Paragraph('Ringkasan Sekolah', gaya['seksi']))
    alur.append(_tabel(['Keterangan', 'Nilai'], _baris_ringkasan(ringkasan),
                       [70 * mm, 60 * mm], gaya, {1: 'RIGHT'}))

    alur.append(Paragraph('Rekap per Kelas', gaya['seksi']))
    alur.append(_tabel_kelas(rekap, gaya))

    alur.append(Paragraph('Legenda Ambang Surat Peringatan', gaya['seksi']))
    alur.append(_tabel(['Ambang poin minus', 'Status'], _baris_legenda(), [60 * mm, 120 * mm], gaya))

    return _bangun(alur, landscape(A4), judul)
