import sqlite3
import pandas as pd
import re
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "disiplin.db"

def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS pasal (
        kode TEXT PRIMARY KEY,
        kategori TEXT NOT NULL,
        subkategori TEXT NOT NULL,
        deskripsi TEXT NOT NULL,
        poin_default INTEGER NOT NULL,
        arah_tanda INTEGER NOT NULL,
        mode_poin TEXT NOT NULL DEFAULT 'fixed'
    )
    """)
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS jurnal (
        id INTEGER PRIMARY KEY,
        timestamp_input TEXT,
        tanggal_kejadian TEXT NOT NULL,
        nis TEXT NOT NULL,
        nama_siswa TEXT NOT NULL,
        kelas TEXT NOT NULL,
        absen TEXT,
        kode_pasal TEXT NOT NULL,
        poin INTEGER NOT NULL,
        judul TEXT NOT NULL,
        keterangan TEXT,
        petugas TEXT,
        sumber TEXT NOT NULL DEFAULT 'manual',
        FOREIGN KEY (kode_pasal) REFERENCES pasal(kode)
    )
    """)
    
    c.execute("CREATE INDEX IF NOT EXISTS idx_jurnal_nis ON jurnal(nis)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_jurnal_tanggal ON jurnal(tanggal_kejadian)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_jurnal_kode ON jurnal(kode_pasal)")
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS siswa (
        nis TEXT PRIMARY KEY,
        nama TEXT NOT NULL,
        kelas TEXT NOT NULL,
        angkatan TEXT,
        absen TEXT
    )
    """)
    
    conn.commit()
    pastikan_kolom_absen(conn, 'siswa')
    migrasi_absen_jurnal(conn)
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS import_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        waktu TEXT NOT NULL,
        nama_file TEXT,
        jumlah_baris INTEGER NOT NULL,
        berhasil INTEGER NOT NULL,
        gagal INTEGER NOT NULL,
        duplikat INTEGER NOT NULL,
        user TEXT
    )
    """)
    
    conn.commit()
    conn.close()


KELAS_GABUNGAN = re.compile(r'((?:10|11|12)-[A-Z0-9]+) (\d{2})')


def pisah_kelas_absen(kelas):
    nilai = '' if kelas is None else str(kelas).strip()
    cocok = KELAS_GABUNGAN.fullmatch(nilai)
    if cocok:
        return cocok.group(1), cocok.group(2)
    return nilai, None


def pastikan_kolom_absen(conn, tabel):
    columns = {row[1] for row in conn.execute(f'PRAGMA table_info({tabel})')}
    if 'absen' not in columns:
        conn.execute(f'ALTER TABLE {tabel} ADD COLUMN absen TEXT')
        conn.commit()


def migrasi_absen_jurnal(conn):
    pastikan_kolom_absen(conn, 'jurnal')
    isolation = conn.isolation_level
    conn.isolation_level = None
    try:
        conn.execute('BEGIN IMMEDIATE')
        try:
            diubah = 0
            rows = conn.execute("SELECT id, kelas, absen FROM jurnal WHERE kelas LIKE '% %'").fetchall()
            for ident, kelas, absen in rows:
                cocok = KELAS_GABUNGAN.fullmatch(kelas or '')
                if not cocok:
                    continue
                if absen not in (None, '') and absen != cocok.group(2):
                    continue
                conn.execute('UPDATE jurnal SET kelas = ?, absen = ? WHERE id = ?',
                             (cocok.group(1), cocok.group(2), ident))
                diubah += 1
            conn.execute('COMMIT')
            return diubah
        except Exception:
            conn.execute('ROLLBACK')
            raise
    finally:
        conn.isolation_level = isolation


def load_referensi_pasal():
    mapping = {
        'code': 'kode', 'kind': 'kategori', 'subcategory': 'subkategori',
        'label': 'deskripsi', 'default_points': 'poin_default',
        'expected_sign': 'arah_tanda', 'points_mode': 'mode_poin'
    }
    conn = get_conn()
    try:
        with conn:
            columns = {row[1] for row in conn.execute('PRAGMA table_info(pasal)')}
            for source, target in mapping.items():
                if source in columns and target not in columns:
                    conn.execute(f'ALTER TABLE pasal RENAME COLUMN "{source}" TO "{target}"')
            if conn.execute('SELECT COUNT(*) FROM pasal').fetchone()[0] == 0:
                ref_path = Path(__file__).parent.parent / 'data' / 'referensi_pasal.csv'
                df = pd.read_csv(ref_path).rename(columns=mapping)
                fields = list(mapping.values())
                if df['kode'].duplicated().any():
                    raise ValueError(f'Referensi pasal tidak valid: {ref_path.name} memuat kode duplikat')
                if df[fields].isna().any().any():
                    raise ValueError(f'Referensi pasal tidak valid: {ref_path.name} memuat sel kosong')
                conn.executemany(
                    f"INSERT INTO pasal ({','.join(fields)}) VALUES (?,?,?,?,?,?,?)",
                    df[fields].itertuples(index=False, name=None)
                )
                jumlah = conn.execute('SELECT COUNT(*) FROM pasal').fetchone()[0]
                if jumlah != len(df):
                    raise ValueError(f'Seeding pasal tidak cocok: {jumlah} baris tersimpan dari {len(df)} baris file referensi')
    finally:
        conn.close()

def get_conn():
    return sqlite3.connect(DB_PATH, timeout=30)

def execute_query(query, params=None):
    conn = get_conn()
    if params:
        result = pd.read_sql_query(query, conn, params=params)
    else:
        result = pd.read_sql_query(query, conn)
    conn.close()
    return result
