# BLUEPRINT — Dashboard Disiplin dan Prestasi
## SMA Katolik Santo Paulus Jember

> Dokumen perancangan sistem. Versi 1.1 — November 2026
>
> **Keputusan terkonfirmasi (16/11/2026):**
> 1. e-Guru TIDAK punya ekspor CSV → data masuk via **copy-paste manual** dari halaman web
> 2. Daftar lengkap kode pasal + poin baku **tersedia** (akan diimport sebagai referensi)
> 3. Ambang poin SP/pembinaan **tersedia** (akan dikonfigurasi sesuai data sekolah)
> 4. **Satu operator** — tanpa login multi-user untuk sementara

---

## 1. Latar Belakang

Data poin disiplin (pelanggaran) dan prestasi siswa saat ini tercatat di sistem e-Guru
(`smak-tatibsi-jurnal`) dalam bentuk jurnal per baris — ribuan entri (2900+ baris, 30+ halaman).
Sistem tersebut baik untuk *pencatatan*, namun belum menyediakan:

- **Visualisasi** agregat (per kelas, per pasal, per bulan, per petugas)
- **Analisis** tren dan deteksi dini siswa berisiko
- **Olah data** massal (pembersihan, koreksi, rekap, ekspor)
- **Import massal** dari CSV untuk input kolektif

Proyek ini membangun aplikasi pendamping (companion app) yang membaca ekspor data
dari e-Guru dan menyajikan dashboard, analisis, serta alat olah data.

---

## 2. Ringkasan Solusi

| Aspek | Keputusan |
|---|---|
| Jenis aplikasi | Web app lokal (dapat di-deploy ke jaringan sekolah) |
| Framework UI | **Streamlit** (Python) — cepat dibangun, cocok untuk dashboard data |
| Pengolahan data | **pandas** |
| Penyimpanan | **SQLite** (file `data/disiplin.db`) — tanpa server database |
| Visualisasi | **Plotly** (interaktif) |
| Sumber data | Import CSV (ekspor dari e-Guru / input manual petugas) |
| Ekspor | CSV, Excel (`.xlsx`), PDF rekap (opsional fase 2) |

---

## 3. Model Data

### 3.1 Tabel `jurnal` (inti — cermin struktur e-Guru)

| Kolom | Tipe | Keterangan | Contoh |
|---|---|---|---|
| `id` | INTEGER PK | ID unik (pakai ID e-Guru bila ada) | 45093 |
| `timestamp_input` | DATETIME | Waktu entri dicatat | 2026-11-13 07:51:48 |
| `tanggal_kejadian` | DATE | Tanggal kejadian sebenarnya | 2026-11-13 |
| `nis` | TEXT | Nomor Induk Siswa | 12539 |
| `nama_siswa` | TEXT | Nama lengkap | marco genio |
| `kelas` | TEXT | Kelas + nomor absen | 12-K2 21 |
| `kode_pasal` | TEXT | Kode kategori | ME-02 |
| `poin` | INTEGER | Negatif = pelanggaran, positif = prestasi | -50 |
| `judul` | TEXT | Judul singkat | terlambat i |
| `keterangan` | TEXT | Uraian lengkap + rujukan pasal | murid terlambat ... pasal 14 |
| `petugas` | TEXT | Username pencatat | 11claudia139 |
| `sumber` | TEXT | `import_csv` / `manual` | import_csv |

### 3.2 Tabel `siswa` (master, diturunkan dari jurnal atau diimport terpisah)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `nis` | TEXT PK | NIS |
| `nama` | TEXT | Nama |
| `kelas` | TEXT | Kelas saat ini (10-1 … 12-S2) |
| `angkatan` | TEXT | Tahun masuk (opsional) |

### 3.3 Tabel `pasal` (referensi kode) — DATA LENGKAP TERSEDIA ✅

Sumber: `data/referensi_pasal.csv` (178 kode **lengkap dengan poin baku**, final 16/11/2026).

| Kolom | Tipe | Keterangan | Contoh |
|---|---|---|---|
| `kode` | TEXT PK | Kode pasal (`code`) | ME-02 |
| `kategori` | TEXT | `kind`: prestasi / pelanggaran | pelanggaran |
| `subkategori` | TEXT | `subcategory`: pengelompokan analisis | pelanggaran_terhadap_kerajinan |
| `deskripsi` | TEXT | `label`: uraian + rujukan pasal tatib | Murid terlambat masuk sekolah untuk pertama kali. Pasal 14. |
| `poin_default` | INTEGER | `default_points`: poin baku resmi | -50 |
| `arah_tanda` | INTEGER | `expected_sign`: +1 prestasi, -1 pelanggaran | -1 |
| `mode_poin` | TEXT | `points_mode`: `fixed` (poin baku) / `manual` (poin diinput per kejadian) | fixed |

**Subkategori (dari data resmi) — dipakai sebagai dimensi utama grafik:**

| Subkategori | Prefiks | Rentang poin |
|---|---|---|
| `prestasi_akademik` | PA | +75 … +1800 |
| `prestasi_humaniora` | PB | 0 … +1500 |
| `dukungan_orang_tua` | PC | +50 … +300 |
| `pelanggaran_sangat_berat` | MA | -600 (semua) |
| `pelanggaran_berat` | MB | -100 … -600 |
| `pelanggaran_ringan` | MC | -20 … -50 |
| `pelanggaran_terhadap_kerapian` | MD | -10 … -50 |
| `pelanggaran_terhadap_kerajinan` | ME | -30 … -50 |
| `pelanggaran_terhadap_kebersihan` | MF | -30 … -50 |
| `pelanggaran_terhadap_peraturan_perpustakaan` | MH | -25 (semua) |

**Taksonomi kode lengkap (dari data resmi):**

| Prefiks | Kategori | Jumlah | Cakupan |
|---|---|---|---|
| `PA` | Prestasi akademik/lomba | 48 | Juara internasional s.d. peserta kabupaten (Pasal 35–39) |
| `PB` | Prestasi non-lomba | 55 | PASKIBRA, jurnalistik, OSIS, pengurus kelas, perpustakaan, kerja sosial, literasi, pelayanan keagamaan (Pasal 40–66) |
| `PC` | Apresiasi keterlibatan **orang tua** | 8 | Pasal 67–74 |
| `MA` | Pelanggaran sangat berat | 6 | Pelecehan, narkoba, kekerasan, pidana (Pasal 80–84, 32–33) |
| `MB` | Pelanggaran berat | 29 | Perkelahian, pencurian, bullying, pemalsuan, membolos, merokok, HP tanpa izin (Pasal 85–108, 126) |
| `MC` | Pelanggaran ketertiban | 3 | Makan di kelas, buku hilang, di kelas saat istirahat |
| `MD` | Pelanggaran penampilan/seragam | 10 | Rambut, seragam, atribut, sepatu, aksesori (Pasal 111–125) |
| `ME` | Pelanggaran kehadiran/kedisiplinan harian | 12 | Terlambat i–vi+, tidak bawa buku PD, bolos upacara/ekskul |
| `MF` | Pelanggaran kebersihan | 4 | Mengotori sarana, sampah, corat-coret (Pasal 131–134) |
| `MH` | Pelanggaran perpustakaan | 3 | Pasal 135b |

> **Validasi aktif sejak awal:**
> 1. **Tanda poin wajib cocok** dengan `arah_tanda` (kode `M*` berpoin positif atau
>    `P*` berpoin negatif = error input)
> 2. **Poin ≠ poin_default** resmi → ditandai *warning anomali* di Olah Data
>    (bukan error, karena ada kasus poin kelipatan/penyesuaian, mis. PA-13 tercatat
>    775 vs juara 10 besar, PB-53 ×jumlah tugas) — hanya berlaku untuk kode
>    `mode_poin = fixed`
> 3. **PB-16 dan PB-39 bermode `manual`** (`poin_default = 0` disengaja): nilai
>    poinnya **diinput manual per kejadian** oleh petugas, bukan dari poin baku.
>    Konsekuensi di sistem:
>    - Validasi anomali poin **dinonaktifkan** untuk kedua kode ini (nilai berapa pun
>      yang positif dianggap sah)
>    - Pada form input/import, bila poin kosong untuk kode `manual` → **error**
>      (wajib diisi), bukan auto-isi 0
>    - Kode `fixed` dengan poin kosong → auto-isi `poin_default` seperti biasa
>
> **Catatan skala poin:** poin prestasi resmi jauh lebih besar (s.d. +1800) daripada
> pelanggaran (maks. -600). KPI dan leaderboard menampilkan **poin** dan **frekuensi**
> secara terpisah agar perbandingan adil.

**Catatan khusus `PC-*` (apresiasi orang tua):** poinnya milik keterlibatan orang tua,
bukan perilaku siswa — di dashboard & analisis ditampilkan sebagai kategori terpisah
agar tidak mencampuri leaderboard prestasi siswa (dapat di-toggle).

### 3.4 Tabel `import_log`

| Kolom | Keterangan |
|---|---|
| `id`, `waktu`, `nama_file`, `jumlah_baris`, `berhasil`, `gagal`, `duplikat`, `user` | Audit jejak import |

---

## 4. Arsitektur & Struktur Folder

```
DASHBOARD DISIPLIN DAN PRESTASI/
├── Beranda.py                  # Entry point Streamlit (halaman Beranda/Dashboard)
├── pages/
│   ├── 1_📊_Dashboard.py       # Dashboard utama
│   ├── 2_🔎_Analisis.py        # Analisis mendalam
│   ├── 3_🛠️_Olah_Data.py       # Edit, bersihkan, rekap, ekspor
│   ├── 4_📥_Import_CSV.py      # Import massal
│   └── 5_👤_Profil_Siswa.py    # Rapor poin per siswa
├── core/
│   ├── db.py                   # Koneksi & skema SQLite
│   ├── importer.py             # Parser + validator CSV
│   ├── analytics.py            # Fungsi agregasi & analisis
│   └── export.py               # Ekspor CSV/Excel
├── data/
│   ├── disiplin.db             # Database SQLite (auto-generate)
│   └── contoh_import.csv       # Template CSV
├── assets/                     # Logo sekolah, styling
├── requirements.txt
└── BLUEPRINT.md                # Dokumen ini
```

---

## 5. Spesifikasi Fitur

### 5.1 Modul 1 — Dashboard Disiplin dan Prestasi

**Filter global (sidebar):** rentang tanggal, tingkat (10/11/12), kelas, kategori
(pelanggaran/prestasi), kode pasal, petugas.

**Kartu ringkasan (KPI):**
- Total entri pelanggaran & total entri prestasi (periode terpilih)
- Total poin minus & total poin plus
- Jumlah siswa terlibat pelanggaran / berprestasi
- Rata-rata poin per siswa

**Grafik:**
1. **Tren bulanan/mingguan** — line chart jumlah pelanggaran vs prestasi
2. **Top 10 jenis pelanggaran** — bar chart (terlambat, seragam, buku hilang, dst.)
3. **Top 10 jenis prestasi** — bar chart
4. **Perbandingan antar kelas** — bar chart poin minus & plus per kelas
5. **Heatmap hari × jam** input pelanggaran (pola keterlambatan)
6. **Distribusi per petugas pencatat** — siapa mencatat apa dan berapa banyak

**Leaderboard:**
- 🏆 Top 20 siswa poin prestasi tertinggi
- ⚠️ Top 20 siswa poin pelanggaran terbanyak (watchlist)

### 5.2 Modul 2 — Analisis Data

1. **Analisis tren:** pergerakan pelanggaran per pasal per bulan; deteksi lonjakan
   (mis. keterlambatan naik setelah libur)
2. **Analisis residivis:** siswa dengan pelanggaran berulang pada pasal yang sama
   (terlambat i → ii → … → vi), dengan eskalasi tingkat
3. **Siswa berisiko (early warning):** skor kumulatif poin minus melewati ambang
   (konfigurable, mis. -100 / -200 / -300) → daftar untuk pembinaan BK
4. **Analisis keseimbangan:** rasio prestasi vs pelanggaran per siswa/kelas —
   identifikasi siswa yang poin minusnya besar tapi aktif berprestasi (atau sebaliknya)
5. **Analisis per angkatan/tingkat:** perbandingan perilaku kelas 10 vs 11 vs 12
6. **Analisis pasal:** pasal mana paling sering dilanggar; efektivitas sanksi
   (apakah pelanggaran berulang menurun setelah eskalasi poin)
7. **Statistik petugas:** volume pencatatan per petugas, jam aktif pencatatan

### 5.3 Modul 3 — Olah Data

1. **Tabel data interaktif:** cari, filter, sortir seluruh jurnal; edit inline per sel
2. **Deteksi & pembersihan:**
   - Duplikat (NIS + tanggal + pasal sama)
   - NIS tidak dikenal / tidak ada di master siswa
   - Poin tidak sesuai `poin_default` pasal (anomali input)
   - Tanggal kejadian > tanggal input (data janggal)
3. **Operasi massal:** hapus terpilih, ubah kelas (naik kelas/mutasi), koreksi kode pasal
4. **Rekap otomatis:**
   - Rekap per siswa (total poin, rincian) → untuk rapor sikap/surat panggilan
   - Rekap per kelas per periode → untuk wali kelas
   - Rekap semester/tahunan
5. **Ekspor:** hasil filter/rekap ke CSV & Excel; satu klik "Rekap Wali Kelas" per kelas

### 5.4 Modul 4 — Import Massal (CSV & Copy-Paste e-Guru)

> **Penting:** e-Guru TIDAK menyediakan ekspor CSV. Karena itu modul ini punya
> **dua jalur masuk**:

#### Jalur A — Paste Langsung dari e-Guru (jalur utama)

Operator membuka halaman jurnal e-Guru (per-page=100), blok seluruh tabel
(Ctrl+A / drag), copy (Ctrl+C), lalu **paste ke textarea** di aplikasi.

**Format paste terkonfirmasi** (diuji pada contoh asli 100 record,
`data/contoh_paste_eguru.txt`, hasil: **100/100 terekstrak** ✅):

- Satu record = **2 baris fisik**:
  - Baris 1 (TAB-separated): `#  ID  TanggalInput  Tanggal,  NIS  Kelas Absen` lalu
    pindah baris di tengah kolom Data Siswa
  - Baris 2: `nama siswa  TAB  Kode  TAB  Poin  TAB  judul + username petugas` lalu
    baris keterangan panjang
- `Tanggal Input` bisa berisi **`(not set)`** → simpan NULL
- Tanggal kejadian berformat **`DD-MM-YYYY,`** (ada koma buntut) → dinormalisasi
- **Username petugas menempel di akhir kolom judul** (mis. `terlambat i 40Eli48`)
  → dipisah dengan regex token terakhir; daftar petugas dikelola agar akurat
- NIS 4–5 digit; kelas berpola `10-4 28` (angka) atau `12-K2 05` (huruf+angka)
- Header tabel, baris `masukan tanggal`, dan kolom Actions dibuang otomatis

Pola inti parser (sudah teruji di PowerShell/Python sama):
```regex
^\s*(\d+)\t(\d{5})\t(\(not set\)|[\d:\- ]+)\t(\d{2}-\d{2}-\d{4}),\t(\d{4,5})\t((?:10|11|12)-[A-Z0-9]+ \d{2})\n(.+?)\t((?:PA|PB|PC|MA|MB|MC|MD|ME|MF|MH)-\d{2})\t(-?\d+)\t(.+?)\n([^\t\n]+)
```

Langkah parser:
1. Ekstrak per record: `ID, tanggal input, tanggal kejadian, NIS, kelas+absen,
   nama siswa, kode pasal, poin, judul, petugas, keterangan`
2. Pisahkan username petugas dari akhir judul
3. Tampilkan hasil parse sebagai tabel preview + hitung record yang gagal parse
   (ditampilkan mentah untuk koreksi manual)
4. Deteksi duplikat by **ID e-Guru** → paste halaman yang sama dua kali aman (skip)

> Dengan per-page=100 dan ±30 halaman, seluruh histori (±3000 record) selesai
> dalam ±30 kali copy-paste. Import rutin selanjutnya hanya halaman terbaru.

#### Jalur B — Upload File CSV

Untuk input kolektif baru (mis. daftar keterlambatan hasil razia pagi) yang disusun
di Excel lalu disimpan sebagai CSV.

**Alur:**
```
Paste teks / Upload CSV → Parse & Preview → Mapping kolom (CSV saja) → Validasi → Laporan → Konfirmasi → Simpan
```

1. **Upload:** menerima `.csv` (delimiter `,`, `;`, atau TAB terdeteksi otomatis;
   encoding UTF-8/Windows-1252 terdeteksi otomatis)
2. **Mapping kolom:** pengguna mencocokkan kolom CSV → kolom sistem (disimpan sebagai
   preset agar import berikutnya sekali klik)
3. **Validasi per baris sebelum simpan (berlaku untuk kedua jalur):**
   - NIS wajib ada & numerik
   - Tanggal valid (dukung format `YYYY-MM-DD` dan `DD-MM-YYYY`)
   - Kode pasal dikenal (warning bila tidak ada di tabel `pasal`)
   - Poin integer; bila kosong → isi `poin_default` pasal
   - Duplikat terhadap database (ID sama, atau NIS+tanggal+pasal sama) → tandai
4. **Laporan pra-simpan:** ✅ valid / ⚠️ warning / ❌ error per baris; baris error bisa
   diunduh kembali sebagai CSV untuk diperbaiki
5. **Mode simpan:** *tambah saja* (skip duplikat) / *tambah & perbarui* (upsert by ID)
6. **Template CSV** disediakan untuk diunduh:

```csv
id,timestamp_input,tanggal_kejadian,nis,nama_siswa,kelas,kode_pasal,poin,judul,keterangan,petugas
45093,2026-11-13 07:51:48,2026-11-13,12539,marco genio,12-K2 21,ME-02,-50,terlambat i,murid terlambat masuk sekolah untuk pertama kali. pasal 14.,11claudia139
```

7. **Import pendukung:** CSV master siswa & **CSV referensi pasal** (menu terpisah) —
   data lengkap kode pasal + poin baku dari sekolah dimuat di sini sekali di awal
8. **Audit:** setiap import tercatat di `import_log`; ada tombol **rollback import terakhir**

---

## 6. Halaman Tambahan — Profil Siswa

Cari siswa by NIS/nama → tampilkan:
- Identitas + kelas
- Saldo poin berjalan (plus, minus)
- Timeline semua entri (kronologis)
- Grafik poin kumulatif per bulan
- Tombol ekspor "Rapor Poin" individu (untuk orang tua/BK)

---

## 7. Aturan Bisnis Penting

1. **Poin negatif = pelanggaran, poin positif = prestasi** (konsisten dengan e-Guru)
2. Ambang pembinaan dikonfigurasi di halaman pengaturan — nilai akan diisi dari
   **data ambang resmi sekolah yang sudah tersedia** (dimuat saat setup awal)
3. Data tidak pernah dihapus permanen oleh import; hanya operasi eksplisit pengguna
4. Periode akademik: semester ganjil (Jul–Des) & genap (Jan–Jun) sebagai preset filter

---

## 8. Teknologi & Dependensi

```
streamlit        # UI web
pandas           # olah data
plotly           # grafik interaktif
openpyxl         # ekspor Excel
chardet          # deteksi encoding CSV
```

Python ≥ 3.10. Jalankan dengan: `streamlit run Beranda.py`

---

## 9. Tahapan Pengembangan (Roadmap)

| Fase | Lingkup | Estimasi |
|---|---|---|
| **1 — Fondasi** | Skema DB, **parser copy-paste e-Guru**, import CSV + validasi, muat referensi pasal & ambang dari data sekolah | hari 1 |
| **2 — Dashboard** | KPI, grafik tren, top pelanggaran/prestasi, leaderboard | hari 1–2 |
| **3 — Olah Data** | Tabel interaktif, deteksi duplikat/anomali, rekap, ekspor | hari 2–3 |
| **4 — Analisis** | Residivis, early warning, analisis pasal & petugas | hari 3–4 |
| **5 — Profil & polesan** | Profil siswa, rollback import, pengaturan ambang, styling | hari 4–5 |

---

## 10. Pertimbangan Keamanan & Privasi

- Data siswa adalah data pribadi → aplikasi berjalan lokal/jaringan internal sekolah,
  **tidak** dipublikasikan ke internet
- File `disiplin.db` dan CSV sumber tidak dibagikan keluar tim disiplin
- Satu operator, tanpa login (sesuai keputusan); login multi-user ditunda ke fase lanjut

---

## 11. Status Konfirmasi (SELESAI — 16/11/2026)

| # | Pertanyaan | Jawaban | Dampak desain |
|---|---|---|---|
| 1 | Ekspor CSV dari e-Guru? | **Tidak ada — copy manual** | Modul import dibuat 2 jalur: **paste langsung** (utama) + upload CSV |
| 2 | Daftar kode pasal + poin baku | **Tersedia** | Dimuat ke tabel `pasal` saat setup; validasi poin aktif sejak awal |
| 3 | Ambang SP/pembinaan | **Tersedia** | Early warning memakai ambang resmi sekolah |
| 4 | Multi-user? | **Satu operator dulu** | Tanpa login; arsitektur tetap siap ditambah login nanti |

---

## 12. Data yang Perlu Diserahkan ke Pengembang Sebelum Fase 1

1. ~~Daftar kode pasal~~ ✅ **LENGKAP 16/11/2026** — tersimpan di
   `data/referensi_pasal.csv` (178 kode: PA 48, PB 55, PC 8, MA 6, MB 29, MC 3,
   MD 10, ME 12, MF 4, MH 3) — **termasuk subkategori dan poin baku resmi**
2. **Ambang poin pembinaan** (batas SP1, SP2, panggilan orang tua, dst.) — *menunggu*
3. ~~Contoh hasil copy-paste tabel e-Guru~~ ✅ **DITERIMA 16/11/2026** — tersimpan di
   `data/contoh_paste_eguru.txt` (100 record, ID 40839–40938); parser prototipe
   teruji **100/100 record terekstrak**
4. (Opsional) **Master daftar siswa** (NIS, nama, kelas) bila ada, agar validasi NIS
   dan fitur naik kelas akurat — *menunggu*

**Catatan tambahan dari contoh paste:**
- Kolom `Tanggal Input` di e-Guru dapat berisi `(not set)` → skema `timestamp_input`
  harus nullable
- NIS dapat 4 digit (data lama) — validasi NIS: 4–5 digit numerik
- Terdapat entri ganda yang sah (siswa+tanggal+pasal sama, mis. PB-46 ID 40856 &
  40859 dengan kegiatan berbeda) → deteksi duplikat utama by **ID e-Guru**, bukan
  kombinasi NIS+tanggal+pasal (kombinasi itu hanya warning)
