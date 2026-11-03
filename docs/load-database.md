# Memuat database ke deployment Docker

Jalankan perintah server dari direktori yang berisi `compose.yaml` dan `.env`.
Gunakan image yang sudah dipublikasikan dengan utilitas `/app/backup.py`.
Tidak diperlukan source code aplikasi di server.

## 1. Buat snapshot pada mesin sumber

Pastikan path menunjuk database aktif. Hentikan penulisan aplikasi selama
migrasi akhir agar perubahan berikutnya tidak tertinggal.

```sh
mkdir -p backups
python3 scripts/backup.py data/task-queue.sqlite3 backups/migration.sqlite3
```

Script menggunakan SQLite online backup sehingga snapshot mencakup data yang
masih berada di WAL. Script memeriksa integritas dan foreign key, lalu menampilkan
project, revision, dan jumlah entitas. Simpan output untuk perbandingan.
Jangan menyalin file database aktif secara langsung tanpa WAL.

Kirim `migration.sqlite3` melalui SCP/SFTP ke `backups/migration.sqlite3` di
direktori deployment server. File ini mengandung seluruh data aplikasi.

## 2. Muat snapshot ke volume kosong

Siapkan `.env`, token, dan sertifikat sesuai README. Pull image, lalu pastikan
aplikasi berhenti sebelum memuat database:

```sh
docker compose pull
docker compose stop
docker compose run --rm --no-deps --user root --entrypoint python \
  -v "$PWD/backups:/backups:ro" task-queue \
  -c 'import os; from backup import backup; backup("/backups/migration.sqlite3", "/data/task-queue.sqlite3"); os.chown("/data/task-queue.sqlite3", 10001, 10001)'
docker compose up -d
docker compose exec -T task-queue python -m backend.healthcheck
```

Perintah memeriksa snapshot hasil restore dan memperbaiki pemilik file agar
aplikasi UID `10001` dapat menulis. Destination yang sudah ada akan ditolak;
prosedur ini tidak menimpa database.

Bandingkan output project/revision/jumlah entitas dengan snapshot sumber.
Login melalui UI, periksa task dan project, lalu uji akses MCP. Aplikasi membuat
project `default` saat startup jika belum ada.

## 3. Jika volume tujuan sudah berisi database

Gunakan volume baru untuk mempertahankan database lama sebagai rollback:

1. Jalankan `docker compose stop`.
2. Buat `restore-volume.yaml` di direktori deployment:

   ```yaml
   volumes:
     task-queue-data:
       name: taskqueue-restored-20261103
   ```

3. Pilih nama volume unik yang belum digunakan. Jalankan perintah pada langkah 2
   dengan mengganti setiap `docker compose` menjadi
   `docker compose -f compose.yaml -f restore-volume.yaml`.
4. Gunakan kedua file tersebut juga untuk semua operasi deployment berikutnya.

Untuk rollback, hentikan deployment dengan kedua file, lalu jalankan
`docker compose up -d` tanpa override agar kembali ke volume awal. Penulisan
setelah perpindahan tidak otomatis tersalin ke database lama.
Jangan menjalankan `down -v` selama volume lama masih diperlukan.

## Backup dari server

Utilitas backup sudah tersedia dalam image:

```sh
mkdir -p backups
docker compose exec -T task-queue python /app/backup.py \
  /data/task-queue.sqlite3 /data/snapshot-20261103.sqlite3
docker compose cp task-queue:/data/snapshot-20261103.sqlite3 backups/snapshot-20261103.sqlite3
```

Gunakan nama baru setiap backup. File yang sudah ada tidak akan ditimpa.
Simpan salinan di luar server. Snapshot tersebut dapat dimuat kembali dengan
prosedur yang sama.
