# Audit Rumus Perhitungan

Mode audit BACA-SAJA. Tidak ada file yang diubah, tes dijalankan, atau aplikasi dijalankan.

File yang diaudit: `core/thresholds.py`, `core/analytics.py`, `core/dashboard.py`, `core/importer.py` (bagian poin/tingkat), `core/penghargaan.py`, `cek_tingkat.py`, `pages/` (bagian yang menghitung).

## 1. Daftar Rumus

| # | Nama metrik | Rumus (kata/matematika) | file:baris | Contoh |
|---|---|---|---|---|
| 1 | Total poin pelanggaran | Σ poin negatif (poin < 0) | `analytics.py:283` (clip upper=0 lalu sum) | -50, -30 → -80 |
| 2 | Total poin prestasi/penghargaan | Σ poin positif (poin > 0) | `analytics.py:282` (clip lower=0 lalu sum) | +20,+40 → +60 |
| 3 | Poin dukungan orang tua | Σ poin subkategori `dukungan_orang_tua` | `analytics.py:286` | +10,+10 → +20 |
| 4 | Poin neto / Rapor Poin | Σ semua poin (plus + minus) | `analytics.py:284` | +60 −80 → −20 |
| 5 | Poin plus/minus per entri (rekap) | `poin.clip(lower=0)` / `clip(upper=0)` | `analytics.py:162-163` | — |
| 6 | Ambang SP (status peringatan) | poin_minus ≤ threshold (urutan turun) | `thresholds.py:1-13` | ≤0 hijau, ≤−300 SP I, ≤−400 SP II, ≤−500 SP III, ≤−600 Dewan |
| 7 | Tingkat SP | `None` jika mutlak<300; else status_peringatan(−total) | `thresholds.py:16-19` | 350 → SP I |
| 8 | Aturan naik tingkat (weekly) | `peringkat_ini > peringkat_lalu` pada kumulatif mutlak | `analytics.py:737` | SP I→SP II |
| 9 | Pelanggaran Berulang | groupby nis+kode_pasal, `jumlah_entri ≥ minimal(2)`, poin<0 | `analytics.py:325-342` | 2 entri pasal sama |
| 10 | Pareto / konsentrasi | `persen = total_poin_mutlak / Σtotal ×100`; kumulatif=cumsum | `analytics.py:557-567` | 3 murid = 80% |
| 11 | Siswa penyumbang (Pareto hitung) | jumlah murid dengan `persen_kumulatif ≥ ambang` | `analytics.py:571-577` | ambang 50/80 |
| 12 | Peta panas pasal×kelas | pivot `sum(nilai)`, nilai=1 (jumlah) atau `|poin|`; top 15 pasal | `analytics.py:580-594` | — |
| 13 | Ringkasan mingguan | kejadian=Σcount, poin=Σ|poin|; selisih=ini−lalu; %=selisih/lalu×100 | `analytics.py:680-686` | 10 vs 8 → +2 (+25%) |
| 14 | Kandidat penghargaan — tingkat | total prestasi ≥ batas minimum per kelompok | `penghargaan.py:32-37,10-13` | Akademik≥1000=IV |
| 15 | Kandidat penghargaan — syarat | `total_pelanggaran(abs) ≤ batas(150)`; piala = tingkat I & pelanggaran=0 | `penghargaan.py:119-121` | — |
| 16 | Rata-rata pelanggaran per kelas | `poin_minus / jumlah_rombel` (round 2) | `analytics.py:487-488` | −300/3 = −100.0 |
| 17 | Persen kumulatif (Pareto) | `persen.cumsum()` | `analytics.py:567` | — |
| 18 | Eskalasi tahapan | map kode→posisi; `tahap=idxmax`, `di_tahap_tertinggi = tahap==len` | `analytics.py:357-375` | ME-07 = tahap maks |
| 19 | Komposisi poin | pelanggaran=`|poin|`, prestasi=clip≥0 | `dashboard.py:56-57` | — |
| 20 | Kumulatif poin (grafik) | groupby tanggal lalu `cumsum()` terpisah untuk pelanggaran dan prestasi | `analytics.py:317-318` | — |

## 2. Aturan Khusus & Pengecualian

- **PB-16/PB-39 poin 0 sah**: `importer.py:303-311` — mode `fixed` otomatis isi poin_default jika poin kosong; mode `manual` poin 0 sah (komentar baris 310).
- **Tanda poin vs arah_tanda**: `importer.py:308` — `poin × arah_tanda < 0` → error "Tanda poin tidak sesuai pasal".
- **Poin beda default (fixed)** jadi warning, bukan error: `importer.py:311`.
- **Dedup ID e-Guru**: `importer.py:249-258,342-343` — ID sudah ada dilewati (`ON CONFLICT(id) DO NOTHING`, baris 385); ID ≤ 0 → error.
- **Dedup kunci NIS+tanggal+pasal**: warning (bukan blokir), `importer.py:315-322`.
- **Filter tanggal**: `analytics.py:80-105` — `tanggal_kejadian` di-coerce; tanggal < 2000 dianggap error saat import (`importer.py:287-289`).
- **Tingkat kelas**: regex `^(10|11|12)-` dari kelas, fallback "lainnya" (`analytics.py:439-442`).
- **Normalisasi kelas/absen**: pisah "10-A 12" → kelas + absen (`analytics.py:52-67`).
- **Tanpa kategori/subkategori** → diisi `tanpa_pasal` (`analytics.py:205-206`, dll).
- **Dukungan orang tua ditambahkan ke kelompok** hanya jika dipilih: `penghargaan.py:107-108`.

## 3. Temuan

1. **Status SP dihitung dua cara berbeda**: `status_peringatan(total_poin_minus)` memakai `<=` (thresholds.py:11), sedangkan di Analisis.py:96 kartu "≤ −300" dan :99 `<=` konsisten, **tetapi** `siswa_berisiko` di `analytics.py:394` memakai `<= -abs(ambang)` — dua sumber ambang (−300) hardcode.
2. **Ambang SP hardcode di 3 tempat**: `thresholds.py:1-7` (sumber), `analytics.py:713` (`min` THRESHOLDS), dan teks statis "SP I (-300)…≤ -600" di `Analisis.py:87` serta kartu `≤ -300` di `:96` — risiko meleset bila ambang diubah.
3. **`komposisi_poin` (dashboard.py:51-62) vs rekap poin (analytics.py) tidak konsisten**: komposisi poin menghitung pelanggaran dengan `abs()` berdasarkan kategori string `'pelanggaran'`, sementara rekap memakai `clip`; untuk pasal dengan tanda menyimpang bisa beda hasil.
4. **Tingkat penghargaan tidak di-hardcode konsisten**: `penghargaan.py` punya ambang sendiri (1000–4501) yang terpisah total dari `thresholds.py`; logika "tingkat" dua domain (SP vs prestasi) pakai nama fungsi `tingkat_sp` vs `tingkat_dari_poin`.
5. **Pembagian nol potensial**: `persen` Pareto (`analytics.py:566`) sudah dijaga `if total else 0.0`, tetapi `siswa_penyumbang` (`:577`) membagi `jumlah/len(data)` — aman karena `data.empty` dicek, namun `persen_siswa` saat `len(data)=0` tidak terjangkau.
6. **`rata_rata_pelanggaran` (analytics.py:487-488)**: pembagi memakai `jumlah_rombel` dari master siswa (`peringkat_kelas(df, siswa)`) agar rata-rata mencerminkan seluruh murid sekelas, bukan hanya murid yang punya entri. Bila master kosong, jatuh kembali ke `jumlah_siswa`; rombel 0 menghasilkan `NaN`, bukan `inf`.
7. **Konsistensi `status_peringatan` untuk leaderboard**: `dashboard.py:166` memanggil `status_peringatan(int(nilai))` dengan `nilai` = `Total Poin` **sum negatif**, sudah tepat (<= threshold), namun `tingkat_sp` (`thresholds.py:16`) memakai `-total_mutlak` — dua konvensi tanda berbeda (negatif vs mutlak).
8. **Kasus batas poin tepat di ambang**: `status_peringatan` memakai `<=` sehingga −300 → SP I (bukan hijau); konsisten tapi perlu disadari dokumentasi menyebut "≤ −300" di kartu — sudah cocok.
9. **`pelanggaran_berulang` default `minimal=2`** tapi di panggil tanpa argumen (Analisis.py:60) → benar; namun **tidak mengecualikan poin 0** (hanya `poin<0`), jadi PB-16/PB-39 (poin 0) tidak pernah masuk "berulang" — potensi lubang deteksi.
10. **Duplikasi logika Pareto**: `konsentrasi_pelanggaran` + `siswa_penyumbang` menghitung ulang groupby yang sama; `siswa_penyumbang` memanggil ulang `konsentrasi_pelanggaran` (analytics.py:572).

## 4. Prioritas Perbaikan

1. Sentralkan ambang SP & label ke satu sumber dan hapus hardcode teks "SP I (-300)…≤ -600" serta `≤ -300` di `pages/2_🔎_Analisis.py:87,96`.
2. Satukan konvensi tanda status (negatif vs mutlak) antara `status_peringatan` dan `tingkat_sp` agar tidak ada dua jalur hitung.
3. Perbaiki `komposisi_poin` agar memakai `clip` (konsisten dengan rekap) alih-alih `abs()` berbasis kategori string.
4. Sertakan poin 0 (PB-16/PB-39) dalam deteksi pelanggaran berulang jika memang seharusnya dihitung sebagai kejadian.
5. Dokumentasikan ambang `penghargaan.py` (1000–4501) dan `batas_pelanggaran` (150) sebagai satu blok konfigurasi agar tidak tersebar.
