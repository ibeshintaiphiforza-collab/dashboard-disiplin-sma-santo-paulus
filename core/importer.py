import csv
import io
import re
from datetime import datetime
from pathlib import Path

import chardet
import pandas as pd

from core.db import get_conn, pisah_kelas_absen


FIELDS = ['timestamp_input', 'tanggal_kejadian', 'nis', 'nama_siswa', 'kelas', 'absen',
          'kode_pasal', 'poin', 'judul', 'keterangan', 'petugas']

MASTER_FIELDS = ['nis', 'nama', 'kelas', 'absen']

TAHUN_MINIMUM = 2000
TANGGAL_MINIMUM = datetime(TAHUN_MINIMUM, 1, 1)


def text_value(value):
    return '' if value is None or pd.isna(value) else str(value).strip()


def integer(value, allow_zero=False):
    value = text_value(value)
    if not re.fullmatch(r'[+-]?\d+', value):
        raise ValueError('Harus bilangan bulat')
    result = int(value)
    if allow_zero and result == 0:
        return result
    if not -(2 ** 63) <= result < 2 ** 63:
        raise ValueError('Di luar batas integer SQLite')
    return result


def gabung_kelas_absen(kelas, absen):
    kelas, absen = text_value(kelas), text_value(absen)
    if not kelas:
        return '', absen
    bersih, dari_kelas = pisah_kelas_absen(kelas)
    if dari_kelas and (not absen or absen.zfill(2) == dari_kelas):
        return bersih, dari_kelas
    return kelas, absen


class PasteEguruParser:
    @staticmethod
    def parse_paste(text):
        lines = text.replace('\r\n', '\n').splitlines()
        records = []
        position = 0
        while position < len(lines):
            line = lines[position].strip()
            if not line or line.startswith('#\tID\t') or line == 'masukan tanggal':
                position += 1
                continue
            header = line.split('\t')
            if len(header) != 6 or position + 2 >= len(lines):
                raise ValueError(f'Baris paste {position + 1} tidak terbaca: {line}')
            detail = lines[position + 1].strip().split('\t')
            if len(detail) != 4 or not header[0].isdigit():
                raise ValueError(f'Baris paste {position + 1} tidak terbaca: {line}')
            idx, ident, timestamp, date, nis, kelas_gabungan = header
            nama, kode, poin, title = detail
            title_parts = title.rsplit(' ', 1)
            kelas, absen = pisah_kelas_absen(kelas_gabungan)
            records.append(dict(zip(FIELDS, [
                None if timestamp == '(not set)' else timestamp,
                date.rstrip(','), nis, nama, kelas, absen or '', kode, poin,
                title_parts[0], lines[position + 2].strip(),
                title_parts[1] if len(title_parts) == 2 else ''
            ]), id_eguru=ident, index=idx))
            position += 3
        if not records:
            raise ValueError('Tidak ada record paste yang terbaca')
        return records

    @staticmethod
    def parse_csv(source):
        if isinstance(source, (str, Path)):
            raw = Path(source).read_bytes()
        elif isinstance(source, bytes):
            raw = source
        else:
            raw = source.getvalue() if hasattr(source, 'getvalue') else source.read()
        encoding = 'utf-8-sig'
        try:
            content = raw.decode(encoding)
        except UnicodeDecodeError:
            content = raw.decode(chardet.detect(raw)['encoding'] or 'cp1252')
        try:
            dialect = csv.Sniffer().sniff(content[:8192], delimiters=',;\t')
            reader = csv.DictReader(io.StringIO(content), dialect=dialect, strict=True)
            headers = reader.fieldnames or []
            if len(headers) != len(set(headers)):
                raise ValueError('Kolom CSV duplikat')
            if 'id' in headers and 'id_eguru' in headers:
                raise ValueError('Gunakan hanya id atau id_eguru')
            required = {'tanggal_kejadian', 'nis', 'nama_siswa', 'kelas', 'kode_pasal', 'judul'}
            if not required.issubset(headers):
                raise ValueError('Kolom wajib CSV: ' + ', '.join(sorted(required)))
            records = []
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f'Jumlah kolom tidak sesuai pada baris {reader.line_num}')
                row['id_eguru'] = row.pop('id', row.get('id_eguru', ''))
                row['kelas'], row['absen'] = gabung_kelas_absen(row['kelas'], row.get('absen'))
                records.append(row)
            if not records:
                raise ValueError('CSV kosong')
            return records
        except csv.Error as exc:
            raise ValueError(f'CSV tidak valid: {exc}') from exc


def parse_master_siswa(text):
    lines = text.replace('\r\n', '\n').splitlines()
    records = []
    for position, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        columns = [part.strip() for part in line.split('\t')]
        if len(columns) == 1:
            columns = [part.strip() for part in re.split(r'\s{2,}', line)]
        if len(columns) != 4 or not all(columns[:3]):
            raise ValueError(f'Baris master {position + 1} tidak terbaca: {line}')
        nis, nama, kelas, absen = columns
        if nis.lower() in ('nis', 'no', '#'):
            continue
        records.append(dict(zip(MASTER_FIELDS, [nis, nama, kelas, absen])))
    if not records:
        raise ValueError('Tidak ada record master yang terbaca')
    return records


def parse_master_csv(source):
    if isinstance(source, (str, Path)):
        raw = Path(source).read_bytes()
    elif isinstance(source, bytes):
        raw = source
    else:
        raw = source.getvalue() if hasattr(source, 'getvalue') else source.read()
    try:
        content = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        content = raw.decode(chardet.detect(raw)['encoding'] or 'cp1252')
    try:
        dialect = csv.Sniffer().sniff(content[:8192], delimiters=',;\t')
        reader = csv.DictReader(io.StringIO(content), dialect=dialect, strict=True)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise ValueError('Kolom CSV duplikat')
        if not set(MASTER_FIELDS).issubset(headers):
            raise ValueError('Kolom wajib CSV: ' + ', '.join(MASTER_FIELDS))
        records = []
        for row in reader:
            if None in row or any(row.get(field) is None for field in MASTER_FIELDS):
                raise ValueError(f'Jumlah kolom tidak sesuai pada baris {reader.line_num}')
            records.append({field: text_value(row[field]) for field in MASTER_FIELDS})
        if not records:
            raise ValueError('CSV kosong')
        return records
    except csv.Error as exc:
        raise ValueError(f'CSV tidak valid: {exc}') from exc


class MasterSiswaValidator:
    @staticmethod
    def normalize_record(record, seen=None):
        result = {field: text_value(record.get(field)) for field in MASTER_FIELDS}
        result['nama'] = result['nama'].upper()
        errors, warnings = [], []
        if not re.fullmatch(r'\d{4,5}', result['nis']):
            errors.append('NIS wajib 4-5 digit')
        if not result['nama']:
            errors.append('Nama kosong')
        if not re.fullmatch(r'(10|11|12)-[A-Z0-9]+', result['kelas']):
            errors.append('Format kelas tidak valid')
        if not re.fullmatch(r'\d{2}', result['absen']):
            errors.append('Absen wajib 2 digit')
        if result['nis'] in (seen or set()):
            warnings.append('NIS duplikat dalam data ini')
        return result, errors, warnings

    def validate_record(self, record, seen=None):
        _, errors, warnings = self.normalize_record(record, seen)
        return errors, warnings


def preview_master(records):
    validator = MasterSiswaValidator()
    seen = set()
    preview = []
    for record in records:
        normalized, errors, warnings = validator.normalize_record(record, seen)
        seen.add(normalized['nis'])
        preview.append(dict(normalized, errors=errors, warnings=warnings))
    return preview


def save_master_siswa(records, filename, confirmed=False, user='operator'):
    if not confirmed:
        raise ValueError('Konfirmasi eksplisit diperlukan')
    conn = get_conn()
    conn.isolation_level = None
    try:
        conn.execute('BEGIN IMMEDIATE')
        try:
            preview = preview_master(records)
            if not preview or any(row['errors'] for row in preview):
                raise ValueError('Import dibatalkan: ada record tidak valid')
            existing = {row[0] for row in conn.execute('SELECT nis FROM siswa')}
            inserted = updated = 0
            for row in preview:
                conn.execute(
                    'INSERT INTO siswa (nis,nama,kelas,absen) VALUES (?,?,?,?) '
                    'ON CONFLICT(nis) DO UPDATE SET nama=excluded.nama, kelas=excluded.kelas, absen=excluded.absen',
                    [row[field] for field in MASTER_FIELDS]
                )
                if row['nis'] in existing:
                    updated += 1
                else:
                    inserted += 1
                    existing.add(row['nis'])
            conn.execute(
                'INSERT INTO import_log (waktu,nama_file,jumlah_baris,berhasil,gagal,duplikat,user) VALUES (?,?,?,?,?,?,?)',
                (datetime.now().isoformat(timespec='seconds'), filename, len(records), inserted, 0, updated, user)
            )
            conn.execute('COMMIT')
            return inserted, updated
        except Exception:
            conn.execute('ROLLBACK')
            raise
    finally:
        conn.close()


class ImportValidator:
    def __init__(self, pasal_ref):
        self.pasal_ref = pasal_ref

    def normalize_record(self, record, existing_ids=None, existing_keys=None, seen_keys=None):
        result = {field: text_value(record.get(field)) for field in FIELDS}
        result['kode_pasal'] = result['kode_pasal'].strip().upper()
        errors, warnings = [], []
        ident = record.get('id_eguru', record.get('id'))
        try:
            result['id_eguru'] = integer(ident) if text_value(ident) else None
            if result['id_eguru'] is not None and result['id_eguru'] <= 0:
                errors.append('ID harus positif')
        except ValueError:
            result['id_eguru'] = None
            errors.append('ID tidak valid')
        if result['id_eguru'] in (existing_ids or set()):
            warnings.append('ID sudah ada; akan dilewati')
        for field in ['nama_siswa', 'judul']:
            if not result[field]:
                errors.append(f'{field} kosong')
        if not re.fullmatch(r'\d{4,5}', result['nis']):
            errors.append('NIS wajib 4-5 digit')
        result['kelas'], result['absen'] = gabung_kelas_absen(result['kelas'], result['absen'])
        result['kelas'] = result['kelas'] or ''
        result['absen'] = result['absen'] or ''
        if not re.fullmatch(r'(10|11|12)-[A-Z0-9]+', result['kelas']):
            errors.append('Format kelas tidak valid')
        if not result['absen']:
            result['absen'] = None
        elif re.fullmatch(r'\d{1,2}', result['absen']):
            result['absen'] = result['absen'].zfill(2)
        else:
            errors.append('Absen wajib 1-2 digit')
        for field, formats in [('tanggal_kejadian', ['%Y-%m-%d', '%d-%m-%Y']),
                               ('timestamp_input', ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d'])]:
            value = result[field]
            if field == 'timestamp_input' and value in ('', '(not set)'):
                result[field] = None
                continue
            if field == 'tanggal_kejadian' and value in ('', '-', '0000-00-00', '(not set)'):
                errors.append('Tanggal kejadian wajib diisi')
                continue
            for fmt in formats:
                try:
                    parsed = datetime.strptime(value, fmt)
                    if field == 'tanggal_kejadian' and parsed < TANGGAL_MINIMUM:
                        errors.append(
                            f'Tanggal kejadian tidak wajar ({value}); periksa kembali tanggal asli di e-Guru')
                        break
                    result[field] = parsed.strftime('%Y-%m-%d' if field == 'tanggal_kejadian' else '%Y-%m-%d %H:%M:%S')
                    break
                except ValueError:
                    pass
            else:
                errors.append(f'{field} tidak valid')
        kode = result['kode_pasal']
        if kode not in self.pasal_ref.index:
            warnings.append('Kode pasal tidak dikenal')
        else:
            ref = self.pasal_ref.loc[kode]
            try:
                if not result['poin'] and ref['mode_poin'] == 'fixed':
                    result['poin'] = int(ref['poin_default'])
                else:
                    result['poin'] = integer(result['poin'], allow_zero=True)
                poin = result['poin']
                if poin * int(ref['arah_tanda']) < 0:
                    errors.append('Tanda poin tidak sesuai pasal')
                # Mode manual: poin 0 sah (PB-16/PB-39)
                if ref['mode_poin'] == 'fixed' and poin != int(ref['poin_default']):
                    warnings.append('Poin berbeda dari poin baku')
            except ValueError:
                errors.append('Poin wajib bilangan bulat; mode manual wajib diisi')
        kunci = (result['nis'], result['tanggal_kejadian'], result['kode_pasal'])
        if all(kunci):
            if kunci in (existing_keys or set()):
                warnings.append('Duplikat NIS+tanggal+pasal dengan data tersimpan')
            elif kunci in (seen_keys or set()):
                warnings.append('Duplikat NIS+tanggal+pasal dalam data ini')
            if seen_keys is not None:
                seen_keys.add(kunci)
        return result, errors, warnings

    def validate_record(self, record, existing_ids=None):
        _, errors, warnings = self.normalize_record(record, existing_ids)
        return errors, warnings


def preview_records(records, conn):
    ref = pd.read_sql_query('SELECT * FROM pasal', conn).set_index('kode')
    validator = ImportValidator(ref)
    existing = {row[0] for row in conn.execute('SELECT id FROM jurnal')}
    existing_keys = {(str(row[0]), row[1], row[2])
                     for row in conn.execute('SELECT nis, tanggal_kejadian, kode_pasal FROM jurnal')}
    seen_keys = set()
    preview = []
    for record in records:
        normalized, errors, warnings = validator.normalize_record(
            record, existing, existing_keys, seen_keys)
        ident = normalized['id_eguru']
        if ident is not None:
            existing.add(ident)
        preview.append(dict(normalized, errors=errors, warnings=warnings))
    return preview


def csv_baris_error(preview):
    baris_error = []
    for nomor, row in enumerate(preview, start=1):
        if row['errors']:
            baris_error.append({
                'baris': nomor,
                'nis': row.get('nis', ''),
                'nama': row.get('nama', ''),
                'kelas': row.get('kelas', ''),
                'absen': row.get('absen', ''),
                'kode_pasal': row.get('kode_pasal', ''),
                'tanggal_kejadian': row.get('tanggal_kejadian', ''),
                'poin': row.get('poin', ''),
                'alasan': '; '.join(str(alasan) for alasan in row['errors']),
            })
    return pd.DataFrame(baris_error).to_csv(index=False).encode('utf-8-sig')


def save_import(records, filename, confirmed=False, source='import_csv', user='operator'):
    if not confirmed:
        raise ValueError('Konfirmasi eksplisit diperlukan')
    conn = get_conn()
    conn.isolation_level = None
    try:
        conn.execute('BEGIN IMMEDIATE')
        try:
            preview = preview_records(records, conn)
            if not preview or any(row['errors'] for row in preview):
                raise ValueError('Import dibatalkan: ada record tidak valid')
            conn.execute(
                'INSERT INTO import_log (waktu,nama_file,jumlah_baris,berhasil,gagal,duplikat,user) VALUES (?,?,?,?,?,?,?)',
                (datetime.now().isoformat(timespec='seconds'), filename, len(records), 0, 0, 0, user)
            )
            import_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            saved = duplicates = 0
            for row in preview:
                cursor = conn.execute(
                    f"INSERT INTO jurnal (id,{','.join(FIELDS)},sumber,import_id) VALUES ({','.join(['?'] * (len(FIELDS) + 3))}) ON CONFLICT(id) DO NOTHING",
                    [row['id_eguru']] + [row[field] for field in FIELDS] + [source, import_id]
                )
                saved += cursor.rowcount
                duplicates += 1 - cursor.rowcount
            conn.execute(
                'UPDATE import_log SET berhasil = ?, duplikat = ? WHERE id = ?',
                (saved, duplicates, import_id)
            )
            conn.execute('COMMIT')
            return saved, duplicates
        except Exception:
            conn.execute('ROLLBACK')
            raise
    finally:
        conn.close()
