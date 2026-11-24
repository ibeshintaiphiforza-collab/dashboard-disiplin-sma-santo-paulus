# LAPORAN AUDIT — Dashboard Disiplin & Prestasi SMA Katolik Santo Paulus Jember

Tanggal audit: 2026-11-18. Mode: READ-ONLY. Cakupan: struktur, logika disiplin, DB, keamanan, importer, UI/UX, PDF, tes, performa, kesiapan PHP (tidak ada folder PHP).

## Ringkasan Eksekutif
Aplikasi Streamlit matang: 148 tes lulus, logika ambang SP tersentralisasi di `core/thresholds.py`, import transaksional dengan dedup by ID e-Guru, dan backup/restore yang rapi. Tidak ada SQL injection (semua query berparameter) dan tidak ada kredensial hardcode. Temuan terpenting bersifat integritas data (kode pasal tidak dinormalisasi case → 1 entri `pb-54` jadi "tanpa_pasal"), ketidakseragaman istilah "siswa" yang masih bocor di beberapa label/tabel, serta beberapa kode mati dan ambang penghargaan yang belum punya pengujian batas. Keamanan baik untuk penggunaan lokal, namun perlu dicatat bila dibuka ke 0.0.0.0 (tanpa autentikasi, satu operator).

**Skor kesehatan proyek: 82 / 100**

## Tabel Temuan

| ID | Tingkat | Area | File:baris | Masalah | Dampak | Saran |
|---|---|---|---|---|---|---|
| T1 | TINGGI | DB/Integritas | importer.py:296-297; db.py:15-24 | Kode pasal tidak dinormalisasi case (tidak `.upper()`). Ada 1 baris `pb-54` (jurnal id 43845) yang tidak match `PB-54` di tabel pasal. | Entri jadi "tanpa_pasal": subkategori/kategori null, keluar dari semua agregasi prestasi, anomali poin tak terdeteksi. | Normalisasi `kode_pasal` ke uppercase di `normalize_record`; bersihkan baris `pb-54` yang ada. |
| T2 | SEDANG | Konsistensi UI | pages/3_🗂️_Olah_Data.py:67; pages/2_🔎_Analisis.py:105 | Istilah "siswa" masih dipakai: tab "Per Siswa" dan nama tabel ekspor/kolom `siswa_berisiko`; core/theme.py:493 "capaian siswa". | Tidak konsisten dengan keputusan "murid". | Ganti label tampilan jadi "Per Murid"/"murid_berisiko" (kode internal boleh tetap, yang wajib seragam adalah teks tampil/ekspor). |
| T3 | SEDANG | Kode mati | importer.py:309-310; db.py:82 | Kode mati: `if ref['mode_poin']=='manual' and poin==0: pass` (tanpa efek); `migrasi_rollback_import` baris 82 `... if False else None`. | Kebingungan maintainer; kesan ada logika yang tidak aktif. | Hapus cabang mati, ganti komentar yang menjelaskan keputusan "poin 0 sah untuk manual". |
| T4 | SEDANG | Kebersihan | cek_tingkat.py:1-16; data/disiplin.db.bak-sebelum-pisah-absen | Skrip debug `cek_tingkat.py` dan backup pra-migrasi tersisa di data/. | File yatim; backup lama di `data/` tidak ikut rotasi/`backups/`. | Hapus `cek_tingkat.py`; pindahkan `.bak-sebelum-pisah-absen` ke `backups/` atau hapus. |
| T5 | SEDANG | Tes/Logika | penghargaan.py:10-13; tests/test_penghargaan.py | `BATAS_TINGKAT` penghargaan (2501/2001/1501/1000; 4501/4001/3501/3000) tidak berasal dari `thresholds`/konfigurasi sekolah dan nilai ambang batas bawah belum diuji (mis. apakah 1000 = tingkat IV atau di bawahnya). | Risiko ambang penghargaan tidak sesuai data resmi; belum ada tes untuk titik batas bawah tiap tingkat. | Konfirmasi ambang penghargaan dari Buku Prestasi; tambah tes off-by-one batas bawah (999/1000, 3000/3001, dst). |
| T6 | RENDAH | DB/Impor | importer.py:330-345; db.py:27-43 | `id_eguru`/`id` jurnal adalah PK `INTEGER PRIMARY KEY` tapi 400 baris lama ber-`import_id NULL`; tidak ada `UNIQUE` index pada `id_eguru` (dedup hanya lewat `ON CONFLICT(id) DO NOTHING` pada PK). | Rollback import hanya bisa menyasar import ber-`import_id`; entri lama tak terlacak asal impor. Dedup andal hanya pada PK, bukan id e-Guru bila PK berbeda. | Tambah kolom/tabel penanda asal impor untuk data lama; dokumentasikan bahwa `id` = id e-Guru. |
| T7 | RENDAH | Keamanan/Jaringan | .streamlit/config.toml:9-10; start_server.bat:3 | Server dijalankan `streamlit run` tanpa `--server.address` eksplisit; bila nanti dibuka 0.0.0.0 tidak ada autentikasi (keputusan: satu operator tanpa login). | Risiko akses tak sah ke data pribadi murid bila diekspos ke LAN sekolah. | Tetap `127.0.0.1` untuk sekarang; dokumentasikan wajib autentikasi sebelum 0.0.0.0. |
| T8 | RENDAH | Konsistensi | BLUEPRINT.md:155-158 vs pages/ | Struktur folder BLUEPRINT (5 halaman, `Profil_Siswa`) tidak cocok aktual (6 halaman, `Master_Murid` + `Profil_Murid`). | Dokumentasi desain kedaluwarsa. | Perbarui BLUEPRINT.md daftar halaman. |
| T9 | RENDAH | Performa | session.py:58-73; theme.py:45-57 | `logo-sekolah.png` (~878 KB) di-embed base64 ke HTML tiap rerun; `load_referensi_pasal` hanya seed bila tabel kosong (perubahan CSV tak termuat ulang). | Beban rerun ringan tapi membengkak; referensi pasal tidak sinkron bila CSV diperbarui. | Pakai versi ringan untuk UI (seperti logo-pdf); tambah mekanisme reload referensi eksplisit. |

## Hasil Tes
`python -m unittest discover -s tests` → **148 lulus, 1 dilewati (skipped), 0 gagal** (10.8 detik). Compile bersih.

## 5 Prioritas Perbaikan
1. Normalisasi `kode_pasal` ke uppercase + bersihkan `pb-54` (T1) — **kecil**.
2. Seragamkan istilah "murid" di seluruh label/ekspor yang tampil (T2) — **kecil**.
3. Hapus kode mati di importer.py & db.py (T3) — **kecil**.
4. Konfirmasi + tes batas ambang penghargaan `BATAS_TINGKAT` (T5) — **sedang**.
5. Bersihkan file yatim & backup lama; perbarui BLUEPRINT (T4, T8) — **kecil**.

## Yang Sudah Baik
1. Ambang SP resmi tersentralisasi di `core/thresholds.py` (satu sumber), dipakai konsisten oleh `status_peringatan`, PDF, dan ringkasan mingguan.
2. Logika PB-16/PB-39 (mode manual, poin 0 sah) terimplementasi benar di importer (wajib isi, anomali dinonaktifkan).
3. Impor transaksional (BEGIN IMMEDIATE/ROLLBACK), dedup by ID e-Guru `ON CONFLICT DO NOTHING`, dedup NIS+tanggal+pasal hanya warning.
4. Backup/restore atomik via sqlite3 backup API, rotasi 14, integrity_check, cadangan pra-restore, salinan eksternal.
5. Tidak ada SQL injection (semua query berparameter); tidak ada kredensial hardcode; data pribadi tidak bocor ke log.
