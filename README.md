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
- PostgreSQL: Port `5432` (User: `root`, Pass: `root`)
- MongoDB: Port `27017`

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

### 2. Menambah Project Baru
Buat subfolder di dalam `projects/`:
```text
projects/
├── demo/
├── simpanpinjam/
└── app-laravel/ (dengan folder public/)
```

### 3. Sinkronisasi Domain & Hosts
Jalankan script sync interaktif (jalankan terminal dengan Administrator / sudo agar dapat update file `hosts`):
```cmd
python bin\sync.py
```
Pilih opsi **1** (Sync Total).

### 4. Akses URL di Browser
Setiap project otomatis dapat diakses dengan ketiga versi PHP:
- `http://demo.php5.test` -> jalan di PHP 5.6
- `http://demo.php7.test` -> jalan di PHP 7.4
- `http://demo.php8.test` -> jalan di PHP 8.2

Dashboard direktori root:
- `http://php5.test`
- `http://php7.test`
- `http://php8.test`

### 5. Menjalankan Command PHP dari Docker (Alias CLI)
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
