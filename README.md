# MyDevEnv Portable Stack

Development stack portabel berbasis Docker Compose + Nginx dynamic vhost.
Mendukung multi-versi PHP (5.6, 7.4, 8.2) dan multi-database (MariaDB, PostgreSQL, MongoDB).
Berjalan di Windows, macOS, dan Linux.

## Struktur Folder
```text
mydevenv/
├── bin/
│   ├── run.bat         # CLI runner Windows
│   ├── run.sh          # CLI runner Linux/Mac
│   └── sync.py         # Generator vhost + updater hosts OS (interaktif)
├── config/
│   ├── nginx/conf.d/   # Auto-generated server blocks Nginx
│   └── php/            # Custom PHP INI configuration (custom.ini)
├── data/               # Persistent database storage
│   ├── mongo/
│   ├── mysql/
│   └── pgsql/
├── projects/           # Folder project PHP Anda (atau custom via .env)
│   └── demo/           # Project contoh
├── .env.example        # Template konfigurasi path project host
└── docker-compose.yml  # Service definitions
```

## Stack Service & Port
- Nginx: Port `80`, `443`
- PHP 5.6 FPM: Internal `php56:9000`
- PHP 7.4 FPM: Internal `php74:9000`
- PHP 8.2 FPM: Internal `php82:9000`
- MariaDB: Port `3306` (User: `root`, Pass: `root`)
- PostgreSQL (Opsional): Port `5432` (User: `root`, Pass: `root`)
- MongoDB (Opsional): Port `27017`

> **Catatan**: PostgreSQL dan MongoDB default berstatus nonaktif (menggunakan Docker Compose profile `postgres` & `mongo`) agar hemat RAM dan CPU. Aktifkan sesuai kebutuhan.

## Cara Penggunaan

### 1. Menjalankan Stack
Windows:
```cmd
bin\run.bat up
```

macOS / Linux:
```bash
chmod +x bin/run.sh
./bin/run.sh up
```

### 2. Mengelola Custom Container (PostgreSQL & MongoDB)
Secara default `postgres` dan `mongo` tidak dijalankan saat `up`.

Untuk mengaktifkan/menonaktifkan container:
- **Menu interaktif**: jalankan `run` lalu pilih menu **8** (`Manage Custom Containers`), atau:
  ```cmd
  bin\run.bat container
  ```
- **CLI langsung**:
  ```cmd
  bin\run.bat start postgres
  bin\run.bat stop postgres
  bin\run.bat start mongo
  bin\run.bat stop mongo
  ```
Status container yang diaktifkan tersimpan di `config/settings.json` (`enabled_containers`) sehingga otomatis ikut dijalankan saat `bin\run.bat up`.

### 3. Menambah Project Baru
Buat subfolder di dalam `projects/`:
```text
projects/
├── demo/
├── simpanpinjam/
└── app-laravel/ (dengan folder public/)
```

### 4. Sinkronisasi Domain & Hosts
Secara default, domain project (`<project>.test`) **tidak otomatis aktif** agar hosts & nginx tetap bersih.
Domain utama stack (`php.test`, `php5.test`, `php7.test`, `php8.test`) tetap aktif di awal.

Untuk mengaktifkan/menonaktifkan domain project secara manual:
- **Menu interaktif**: jalankan `run` lalu pilih menu **7** (`Manage Project Domain`), atau:
  ```cmd
  bin\run.bat domain
  ```
- **CLI langsung**:
  ```cmd
  bin\run.bat enable <nama_project>
  bin\run.bat disable <nama_project>
  ```
- **Sync ulang**:
  ```cmd
  bin\run.bat sync
  ```

### 5. Akses URL di Browser
Project yang telah diaktifkan dapat diakses via:
- `http://<project>.test` -> jalan di PHP default yang sedang dipilih
- `http://<project>.php5.test` -> jalan di PHP 5.6
- `http://<project>.php7.test` -> jalan di PHP 7.4
- `http://<project>.php8.test` -> jalan di PHP 8.2 / 8.3 / 8.4

Dashboard direktori root:
- `http://php5.test`
- `http://php7.test`
- `http://php8.test`

### 6. Menjalankan Command PHP dari Docker (Alias CLI)
Disediakan menu setup alias agar dapat menjalankan PHP & Composer container langsung dari terminal host:

```cmd
bin\run.bat alias
```
atau jalankan `bin\run.bat` lalu pilih menu **9** (Setup Command Alias PHP).

Opsi alias yang tersedia:
1. **Pasang ke User PATH Windows** (Rekomendasi - perintah `php`, `php82`, `php74`, `php56`, `composer`, `artisan` aktif di CMD/PowerShell/Git Bash).
2. **Generate Script Wrapper** (di folder `bin/aliases/`).
3. **Pasang Doskey AutoRun** (khusus CMD).
4. **Pasang ke `~/.bashrc`** (Git Bash / Linux / macOS).

Shortcut via runner langsung:
```cmd
bin\run.bat php -v
bin\run.bat composer --version
```
