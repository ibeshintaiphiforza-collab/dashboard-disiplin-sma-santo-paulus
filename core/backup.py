"""Cadangan dan pulihan basis data disiplin menggunakan sqlite3 backup API."""
import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from core.db import DB_PATH

DEFAULT_BACKUP_DIR = Path(__file__).resolve().parent.parent / 'backups'
DEFAULT_ROTATION_KEEP = 14
POLA_BACKUP = ['disiplin-*.db', 'disiplin-prerestore-*.db']
KONFIG_EKSTERNAL = Path(__file__).resolve().parent.parent / 'data' / 'backup_config.json'
EKSTERNAL_KEEP = 14
PESAN_EKSTERNAL_TIDAK_ADA = 'Folder eksternal tidak tersedia, backup lokal tetap aman.'


def baca_folder_eksternal(konfig_path=KONFIG_EKSTERNAL):
    try:
        with open(konfig_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        nilai = (data or {}).get('folder_eksternal') or ''
        return str(nilai).strip()
    except (OSError, ValueError):
        return ''


def tulis_folder_eksternal(folder, konfig_path=KONFIG_EKSTERNAL):
    konfig_path = Path(konfig_path)
    konfig_path.parent.mkdir(parents=True, exist_ok=True)
    with open(konfig_path, 'w', encoding='utf-8') as f:
        json.dump({'folder_eksternal': str(folder or '').strip()}, f, ensure_ascii=False, indent=2)


def stempel_waktu():
    return datetime.now().strftime('%Y%m%d-%H%M%S')


def daftar_backup(backup_dir=DEFAULT_BACKUP_DIR):
    backup_dir = Path(backup_dir)
    if not backup_dir.exists():
        return []
    files = sorted(backup_dir.glob('disiplin-*.db'), key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def ukuran_berkas(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def format_ukuran(byte_count):
    for satuan in ['B', 'KB', 'MB', 'GB']:
        if byte_count < 1024:
            return f'{byte_count:.0f} {satuan}'
        byte_count /= 1024
    return f'{byte_count:.2f} TB'


def integritas_db(db_path):
    db_path = Path(db_path)
    if not db_path.exists():
        return False
    con = sqlite3.connect(str(db_path))
    try:
        baris = con.execute('PRAGMA integrity_check').fetchone()
        return baris is not None and baris[0] == 'ok'
    except sqlite3.Error:
        return False
    finally:
        con.close()


def rotasi_backup(backup_dir=DEFAULT_BACKUP_DIR, keep=DEFAULT_ROTATION_KEEP):
    backup_dir = Path(backup_dir)
    if not backup_dir.exists():
        return []
    berkas = []
    for pola in POLA_BACKUP:
        berkas.extend(backup_dir.glob(pola))
    berkas = sorted(berkas, key=lambda p: p.stat().st_mtime, reverse=True)
    dihapus = []
    for berkas_lama in berkas[int(keep):]:
        try:
            berkas_lama.unlink()
            dihapus.append(berkas_lama)
        except OSError:
            pass
    return dihapus


def backup_db(db_path=DB_PATH, backup_dir=DEFAULT_BACKUP_DIR, keep=DEFAULT_ROTATION_KEEP):
    db_path = Path(db_path)
    backup_dir = Path(backup_dir)
    if not db_path.exists():
        raise FileNotFoundError(f'Database sumber tidak ditemukan: {db_path}')
    backup_dir.mkdir(parents=True, exist_ok=True)
    keluar = backup_dir / f'disiplin-{stempel_waktu()}.db'

    sumber = sqlite3.connect(str(db_path))
    tujuan = sqlite3.connect(str(keluar))
    try:
        sumber.backup(tujuan)
    finally:
        tujuan.close()
        sumber.close()

    if not integritas_db(keluar):
        keluar.unlink(missing_ok=True)
        raise RuntimeError(f'Backup gagal pemeriksaan integritas: {keluar}')

    dihapus = rotasi_backup(backup_dir, keep=keep)
    try:
        pesan_eksternal = salin_ke_eksternal(keluar)
    except Exception:
        pesan_eksternal = PESAN_EKSTERNAL_TIDAK_ADA
    return keluar, dihapus, pesan_eksternal


def salin_ke_eksternal(path_backup, konfig_path=KONFIG_EKSTERNAL, keep=EKSTERNAL_KEEP):
    path_backup = Path(path_backup)
    folder = baca_folder_eksternal(konfig_path)
    if not folder:
        return ''
    tujuan_dir = Path(folder)
    if not tujuan_dir.is_dir():
        return PESAN_EKSTERNAL_TIDAK_ADA

    tujuan = tujuan_dir / path_backup.name
    sementara = tujuan_dir / (path_backup.name + '.tmp')
    try:
        shutil.copy2(str(path_backup), str(sementara))
        if not integritas_db(sementara):
            sementara.unlink(missing_ok=True)
            return f'Salinan eksternal gagal pemeriksaan integritas: {path_backup.name}'
        os.replace(str(sementara), str(tujuan))
    except OSError:
        try:
            sementara.unlink(missing_ok=True)
        except OSError:
            pass
        return PESAN_EKSTERNAL_TIDAK_ADA

    berkas = sorted(tujuan_dir.glob('disiplin-*.db'), key=lambda p: p.stat().st_mtime, reverse=True)
    for lama in berkas[int(keep):]:
        try:
            lama.unlink()
        except OSError:
            pass
    return f'Salinan eksternal berhasil: {tujuan}'


def restore_db(backup_path, db_path=DB_PATH, confirmed=False, pre_backup_dir=DEFAULT_BACKUP_DIR):
    backup_path = Path(backup_path)
    db_path = Path(db_path)
    if not backup_path.exists():
        raise FileNotFoundError(f'Berkas cadangan tidak ditemukan: {backup_path}')
    if not confirmed:
        raise ValueError('Restore memerlukan konfirmasi (confirmed=True).')

    cadangan_prerestore = None
    if db_path.exists():
        pr_dir = Path(pre_backup_dir)
        pr_dir.mkdir(parents=True, exist_ok=True)
        cadangan_prerestore = pr_dir / f'disiplin-prerestore-{stempel_waktu()}.db'
        shutil.copy2(str(db_path), str(cadangan_prerestore))
        if not integritas_db(cadangan_prerestore):
            cadangan_prerestore.unlink(missing_ok=True)
            cadangan_prerestore = None
            raise RuntimeError('Cadangan pra-restore gagal integritas; restore dibatalkan.')

    sementara = db_path.with_name(db_path.name + '.restore-tmp')
    shutil.copy2(str(backup_path), str(sementara))
    if not integritas_db(sementara):
        sementara.unlink(missing_ok=True)
        raise RuntimeError('Restore gagal pemeriksaan integritas; DB asli tidak diubah.')
    try:
        os.replace(str(sementara), str(db_path))
    except (PermissionError, OSError):
        sementara.unlink(missing_ok=True)
        raise RuntimeError('Database sedang dipakai. Hentikan aplikasi (tutup start_server.bat) lalu ulangi restore.')
    return cadangan_prerestore, True


if __name__ == '__main__':
    berkas, dihapus, pesan_eksternal = backup_db()
    print(f'Backup berhasil: {berkas}')
    if dihapus:
        print(f'Rotasi: {len(dihapus)} cadangan lama dihapus.')
    if pesan_eksternal:
        print(pesan_eksternal)
