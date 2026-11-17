CATATAN LANJUTAN — Dashboard Disiplin & Prestasi SMA Katolik Santo Paulus Jember
Tanggal: 2026-11-16 (malam)

STATUS SAAT INI
- Semua 111 test lulus (python -m unittest discover -s tests), compile bersih (python -X utf8 -m compileall app.py core pages tests).
- Aplikasi berjalan di http://127.0.0.1:8501 (streamlit, headless).
- Database: data/disiplin.db — siswa 652, jurnal 400 (ID 40839–41270, periode 20 Juli – 13 Agustus 2026), pasal 178 lengkap dengan poin baku & mode_poin.
- Backup database: data/disiplin.db.bak-sebelum-pisah-absen (belum dihapus, aman).

PERBAIKAN TERBARU (malam ini)
1. Entri ID 41141 (jesselyn alicia faith, PC-05) yang bertanggal 1970-01-01 sudah diperbaiki menjadi 2026-08-04. Tidak ada lagi entri bertanggal 1970.
2. Validasi impor tanggal diperkuat (core/importer.py):
   - Tanggal kejadian kosong / '-' / '0000-00-00' / '(not set)' -> error "Tanggal kejadian wajib diisi".
   - Tanggal kejadian sebelum tahun 2000 (mis. 01-01-1970) -> error "Tanggal kejadian tidak wajar ... periksa kembali tanggal asli di e-Guru".
   - Berlaku untuk jalur paste e-Guru maupun upload CSV. Test: tests/test_import.py::test_tanggal_tidak_wajar_ditolak.
3. Grafik tren bulanan (Dashboard + Analisis) dan grafik Analisis per Kelas dan Tingkat sekarang pakai label bulan terbaca manusia ('Jul 2026', 'Agu 2026') dan sumbu X diforce kategori (`type='category'`). Ini mencegah Plotly menampilkan tahun buatan (mis. 2010) sebagai skala waktu.
   - core/analytics.py: tambah NAMA_BULAN + label_bulan(nilai).
   - core/dashboard.py: gambar_tren_bulanan pake label + type='category'.
   - core/analytics_charts.py: fig_tren dan fig_tingkat pake label + type='category'.
   - Test: tests/test_analytics_charts.py (label_bulan + dashboard trend category), tests/test_import.py (tanggal tidak wajar).
4. Logo sekolah dipasang di kepala dokumen PDF (core/pdf.py):
   - Logo + teks identitas berdampingan dalam tabel header.
   - Memakai assets/logo-pdf.png (164x220, 55 KB) agar PDF ringan; jatuh ke logo-sekolah.png bila tidak ada.
   - PDF rekap sekolah turun dari ~1,4 MB menjadi ~77 KB dengan logo tetap tertanam.
   - Bila berkas logo hilang, PDF tetap dibuat tanpa logo (tidak error).
   - Test: tests/test_pdf.py::PdfLogoTestCase (3 test).

TEMA GELAP PREMIUM — SUDAH SELESAI DITERAPKAN
- .streamlit/config.toml: base dark, primaryColor #C9A227, latar #12100E, teks #F2EDE4, font sans serif.
- core/theme.py: palet (emas #C9A227, prestasi #4E9E7E, pelanggaran #C2543F, netral #8A7F6D, teks #F2EDE4/A99E8D), inject_css(), header_halaman(), sidebar_brand(), kartu_kpi(), hero_beranda(), kartu_tautan(), tampilkan_logo_75().
- core/chart_theme.py: template custom 'disiplin_gelap' (latar transparan, grid #2E2823, colorway emas/hijau/merah), terapkan_tata_letak(), terapkan_sumbu().
- core/analytics_charts.py: 10 fungsi grafik (residivis, eskalasi, early warning, pasal, tingkat, kelas, petugas, tren, hari) menggunakan template gelap.
- Semua halaman (Dashboard, Analisis, Olah Data, Master Siswa, Profil Siswa) memanggil inject_css + sidebar_brand + header_halaman.
- KPI menggunakan st.metric (diformasikan sebagai kartu premium via CSS theme) agar test app.metric tetap berjalan.
- Logo 75 Tahun ditampilkan hanya antara 2026-08-01 s.d. 2027-07-31 (fungsi tampilkan_logo_75).

ASET LOGO (sudah disalin ke assets/)
- assets/logo-sekolah.png (956×1286, RGBA transparan) — logo utama untuk UI
- assets/logo-75.png (3544×3544, RGBA transparan) — logo 75 tahun
- assets/logo-pdf.png (164×220, 55 KB) — versi ringan khusus header PDF
Kedua file asli juga ada di D:\IBECERDAZZ\TIM DISIPLIN\FOTO\SMP KATOLIK INDRA PRASTA\ dan D:\IBECERDAZZ\TIM DISIPLIN\DASHBOARD-DISIPLIN-SUPABASE\.

FITUR YANG SUDAH ADA
1. Import CSV (paste e-Guru atau upload CSV), validasi, deteksi duplikat by ID e-Guru, transaksional.
2. Master Siswa (paste TAB atau CSV, upsert by NIS, kolom absen terpisah).
3. Olah Data (tabel terfilter global, deteksi anomali, rekap per siswa/kelas/subkategori, ekspor CSV+Excel, hapus terpilih).
4. Dashboard (Plotly: pie, tren, top 10 kode, poin per kelas, heatmap hari×jam, treemap subkategori, leaderboard Top 20 prestasi & pelanggaran dengan status SP).
5. Analisis (residivis, eskalasi pasal bertingkat, early warning dengan ambang SP, per pasal/tingkat/kelas/petugas, tren bulanan, hari).
6. Profil Siswa (rapor per siswa, grafik kumulatif, timeline, unduh rapor PDF).
7. Laporan PDF (rapor siswa, rekap kelas, rekap sekolah — lapisan terang untuk cetak, sudah berlogo sekolah di kepala dokumen).
8. Filter global periode (sidebar): tanggal, tingkat, kelas, kategori, kode pasal, petugas.

AMBANG SP (resmi, dari user)
- SP I ≤ -300, SP II ≤ -400, SP III ≤ -500, Rapat Dewan Guru ≤ -600. core/thresholds.py.

KEPUTUSAN YANG TELAH DIAKUI
- Logo 75 Tahun dipakai antara 1 Agustus 2026 – 31 Juli 2027 (selanjutnya hanya logo utama).
- Latar tema: GELAP (navy/cokelat tua + emas), bukan terang.
- PC (dukungan orang tua) dihitung PENUH sebagai prestasi (ikut PB), tidak dikecualikan.
- Duplikat deteksi by ID e-Guru; kombinasi NIS+tanggal+pasal yang sama tapi ID berbeda = sah (mis. PB-46 kegiatan berbeda).

PEKERJAAN YANG BELUM SELESAI / OPSIONAL (besok atau nanti)
- Melengkapi impor jurnal e-Guru ke seluruh periode (saat ini 400 entri, 20 Juli – 13 Agustus 2026).
- Mode terang toggle (saat ini hanya gelap).
- Percantik landing page lebih lanjut.
- Logo 75 Tahun di dalam PDF (saat ini PDF hanya memakai logo utama).
- Pertimbangkan optimasi ukuran logo sidebar (logo-sekolah.png 878 KB di-embed base64 ke HTML setiap rerun).

PERINTAH PENTING
- Jalankan test: python -m unittest discover -s tests
- Jalankan aplikasi: python -m streamlit run app.py --server.port 8501 --server.address 127.0.0.1 --server.headless true
  (sudah persistent; cukup buka http://127.0.0.1:8501, tekan Ctrl+F5 jika perlu muat ulang)
- Jangan hapus assets/logo-*.png dan data/disiplin.db.

Jika ingin melanjutkan, saran prioritas: (1) logo di PDF, (2) melengkapi impor data historis, atau (3) perbaiki/percantik landing page. Silakan pilih.

---
UPDATE 2026-11-17 (Tahap 0–3 selesai, menunggu konfirmasi untuk Tahap 4)
- TAHAP 0: Server nyala dan stabil di http://127.0.0.1:8501. Bukti: _stcore/health = "ok", root = 200 OK. start_server.bat dibuat di root (tidak ada virtualenv). Proses Streamlit dipertahankan agar jendela tidak tertutup.
- TAHAP 1: .gitignore dibuat (data/*.db, data/*.bak*, *.db-journal, __pycache__/, *.pyc, .venv/, venv/, backups/, .kilo/, .streamlit/secrets.toml). Variabel residivis di pages/2_Analisis.py diganti nama jadi pelanggaran_berulang (kosmetik, tanpa perubahan perilaku). Tes: 120 lulus, compile bersih.
- TAHAP 2: core/backup.py dibuat (sqlite3 backup API, stempel waktu, rotasi 14 terbaru, restore dengan konfirmasi + cadangan pra-restore, PRAGMA integrity_check setelah backup/restore). Bagian "Cadangan Basis Data" ditambahkan ke halaman Olah Data (tombol Backup Sekarang, daftar cadangan, Restore 2 langkah). backup_db.bat dibuat untuk Task Scheduler. tests/test_backup.py ditambahkan (7 tes). Tes total: 120 lulus, compile bersih. Cadangan manual sebelum perubahan: backups/disiplin-SEBELUM-TAHAP2-<ts>.db.
- TAHAP 3: Uji import batch besar pada salinan DB (data/disiplin.db tidak disentuh, sudah dihapus setelah uji): 301 entri valid -> tersimpan 300, duplikat id_eguru 1 dilewati, waktu 0,05 detik. Preview 6 entri cacat -> semua ditolak (tanggal kosong, tanggal <2000, kode tak dikenal, nama/judul kosong). Temuan: PB-16/PB-39 poin 0 DITOLAK importer (core/importer.py:303-304) meski blueprint menyatakan "poin 0 sah" — pertimbangkan perubahan aturan bisnis hanya setelah konfirmasi. NIS tidak dikenal tidak ditolak importer (ditangkap deteksi_anomali nanti).

RINCian file yang diubah (Tahap 0–3):
- .gitignore (baru)
- start_server.bat (baru)
- backup_db.bat (baru)
- core/backup.py (baru)
- pages/3_Olah_Data.py (tambah bagian Cadangan Basis Data)
- pages/2_Analisis.py (rename variabel residivis -> pelanggaran_berulang)
- tests/test_backup.py (baru)

Belum dikerjakan (menunggu konfirmasi Tahap 4+): autentikasi ringan, akses jaringan 0.0.0.0, auto-start boot, melengkapi impor historis, risolusi konflik poin 0 PB-16/PB-39.


## Status sesi perbaikan review
- Sesi perbaikan review selesai.
- Restore kini atomik dan memberi pesan jelas bila database terkunci.
- Rollback import tersedia (core/analytics.py: rollback_import_terakhir).
- Keputusan poin 0 sah untuk PB-16/PB-39 ditetapkan.
- Temuan unique index dan penolakan duplikat ditunda karena butuh keputusan.
