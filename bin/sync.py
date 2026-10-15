import os
import re
import sys
import shutil
import platform
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECTS_DIR = BASE_DIR / "projects"
VHOST_DIR = BASE_DIR / "config" / "nginx" / "conf.d"
DATA_DIR = BASE_DIR / "data"

PHP_STACKS = {
    "5": ("php5.test", "php56:9000"),
    "7": ("php7.test", "php74:9000"),
    "8": ("php8.test", "php82:9000"),
}

def get_hosts_path():
    if platform.system() == "Windows":
        return Path(r"C:\Windows\System32\drivers\etc\hosts")
    return Path("/etc/hosts")

def check_docker():
    try:
        res = subprocess.run(["docker", "info"], capture_output=True, text=True)
        return res.returncode == 0
    except Exception:
        return False

def ensure_directories():
    for sub in ["projects", "config/nginx/conf.d", "config/php", "data/mysql", "data/pgsql", "data/mongo"]:
        (BASE_DIR / sub).mkdir(parents=True, exist_ok=True)

def scan_projects():
    ensure_directories()
    p_dir = get_host_mount_dir()
    if not p_dir.exists():
        return []
    return [p.name for p in p_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]

def generate_nginx_configs():
    VHOST_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Base dashboards for root domains (support both dir listing and php script execution)
    dash_conf = "# Dashboards for root domains\n"
    for ver, (domain, fpm_pass) in PHP_STACKS.items():
        dash_conf += f"""server {{
    listen 80;
    server_name {domain};
    root /srv;
    index index.php index.html;
    autoindex on;

    location / {{
        try_files $uri $uri/ @subfolder;
    }}

    location @subfolder {{
        rewrite ^/([^/]+)/?(.*)$ /$1/index.php?$query_string last;
    }}

    location ~ \\.php(/|$) {{
        fastcgi_split_path_info ^(.+\\.php)(/.+)$;
        fastcgi_pass {fpm_pass};
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME $realpath_root$fastcgi_script_name;
        fastcgi_param PATH_INFO $fastcgi_path_info;
        include fastcgi_params;
    }}
}}
"""
    (VHOST_DIR / "00-dashboards.conf").write_text(dash_conf, encoding="utf-8")

    # 2. Vhost per project
    projects = scan_projects()
    projects_dir = get_host_mount_dir()
    for f in VHOST_DIR.glob("project-*.conf"):
        f.unlink(missing_ok=True)

    for p in projects:
        proj_dir = projects_dir / p
        has_public = (proj_dir / "public").is_dir()
        doc_root = f"/srv/{p}/public" if has_public else f"/srv/{p}"

        conf = f"# Config for project: {p}\n"
        for ver, (base_domain, fpm_pass) in PHP_STACKS.items():
            domain = f"{p}.{base_domain}"
            conf += f"""server {{
    listen 80;
    server_name {domain};
    root {doc_root};
    index index.php index.html;

    location / {{
        try_files $uri $uri/ /index.php?$query_string;
    }}

    location ~ \\.php$ {{
        fastcgi_pass {fpm_pass};
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME $realpath_root$fastcgi_script_name;
        include fastcgi_params;
    }}
}}
"""
        (VHOST_DIR / f"project-{p}.conf").write_text(conf, encoding="utf-8")

    print(f"[OK] Nginx configs generated ({len(projects)} project).")

def sync_hosts_file():
    hosts_path = get_hosts_path()
    projects = scan_projects()

    domains = []
    for _, (domain, _) in PHP_STACKS.items():
        domains.append(domain)
        for p in projects:
            domains.append(f"{p}.{domain}")

    try:
        current_hosts = hosts_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"[ERROR] Gagal baca {hosts_path}: {e}")
        return False

    entries_to_add = []
    for d in domains:
        line = f"127.0.0.1 {d}"
        if line not in current_hosts:
            entries_to_add.append(line)

    if entries_to_add:
        try:
            with open(hosts_path, "a", encoding="utf-8") as f:
                f.write("\n# MyDevEnv Portable Stack\n" + "\n".join(entries_to_add) + "\n")
            print(f"[OK] {len(entries_to_add)} domain ditambahkan ke {hosts_path}")
        except PermissionError:
            print(f"[WARN] Izin ditolak tulis ke {hosts_path}.")
            print("Jalankan terminal sebagai Administrator (Windows) atau gunakan sudo (Linux/Mac).")
            print("Domain manual yang perlu ditambahkan:")
            for item in entries_to_add:
                print(f"  {item}")
            return False
    else:
        print("[OK] File hosts sudah sinkron.")
    return True

def clean_hosts_file():
    hosts_path = get_hosts_path()
    try:
        content = hosts_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"[ERROR] Gagal baca {hosts_path}: {e}")
        return False

    lines = content.splitlines()
    cleaned = []
    stack_domains = ["php5.test", "php7.test", "php8.test"]

    for line in lines:
        if "# Flyenv Portable Stack" in line or "# MyDevEnv Portable Stack" in line:
            continue
        if any(dom in line for dom in stack_domains):
            continue
        cleaned.append(line)

    new_content = "\n".join(cleaned) + "\n"
    if new_content != content:
        try:
            hosts_path.write_text(new_content, encoding="utf-8")
            print(f"[OK] Domain stack dibersihkan dari {hosts_path}")
        except PermissionError:
            print(f"[WARN] Gagal update {hosts_path}. Butuh hak akses Administrator/sudo.")
            return False
    else:
        print("[OK] Hosts file sudah bersih dari entri stack.")
    return True

def reload_nginx():
    cmd = ["docker", "compose", "exec", "nginx", "nginx", "-s", "reload"]
    res = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
    if res.returncode == 0:
        print("[OK] Nginx reloaded.")
    else:
        print("[INFO] Nginx reload dilewati (container belum running).")

def action_setup():
    print("\n--- Menjalankan Setup MyDevEnv Stack ---")
    if not check_docker():
        print("[ERROR] Docker Desktop belum aktif atau tidak berjalan.")
        print("Silakan buka aplikasi Docker Desktop di Windows terlebih dahulu.")
        return False

    for sub in ["projects", "config/nginx/conf.d", "data/mysql", "data/pgsql", "data/mongo"]:
        (BASE_DIR / sub).mkdir(parents=True, exist_ok=True)
    print("[OK] Struktur direktori siap.")

    print("[INFO] Mengunduh Docker images (compose pull)...")
    subprocess.run(["docker", "compose", "pull"], cwd=BASE_DIR)

    generate_nginx_configs()
    sync_hosts_file()

    print("\n[SELESAI] Setup berhasil disiapkan.")
    ask_start = input("Jalankan stack container sekarang? [Y/n]: ").strip().lower()
    if ask_start in ["", "y", "yes"]:
        subprocess.run(["docker", "compose", "up", "-d"], cwd=BASE_DIR)
        reload_nginx()
        list_urls()
    return True

def action_repair():
    print("\n--- Menjalankan Repair MyDevEnv Stack ---")
    if not check_docker():
        print("[ERROR] Docker Desktop belum aktif. Buka Docker Desktop terlebih dahulu.")
        return False

    for sub in ["projects", "config/nginx/conf.d", "data/mysql", "data/pgsql", "data/mongo"]:
        (BASE_DIR / sub).mkdir(parents=True, exist_ok=True)

    generate_nginx_configs()
    sync_hosts_file()

    print("[INFO] Merestart container Nginx...")
    subprocess.run(["docker", "compose", "restart", "nginx"], cwd=BASE_DIR)

    print("\n[STATUS CONTAINER]")
    subprocess.run(["docker", "compose", "ps"], cwd=BASE_DIR)
    print("\n[SELESAI] Repair selesai.")
    return True

def action_uninstall():
    print("\n==========================================")
    print("        UNINSTALL MYDEVENV PORTABLE STACK ")
    print("==========================================")
    print("PERINGATAN: Tindakan ini akan menghentikan container")
    print("dan menghapus entri domain dari hosts file OS.")
    confirm = input("Lanjutkan uninstall? [y/N]: ").strip().lower()
    if confirm not in ["y", "yes"]:
        print("Uninstall dibatalkan.")
        return

    print("[INFO] Menghentikan container...")
    subprocess.run(["docker", "compose", "down"], cwd=BASE_DIR)

    clean_hosts_file()

    for f in VHOST_DIR.glob("*.conf"):
        f.unlink(missing_ok=True)
    print("[OK] File vhost Nginx dibersihkan.")

    ask_db = input("Hapus data database lokal (folder data/)? [y/N]: ").strip().lower()
    if ask_db in ["y", "yes"]:
        for item in DATA_DIR.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                item.mkdir(parents=True, exist_ok=True)
        print("[OK] Data DB dibersihkan.")

    print("\n[SELESAI] MyDevEnv stack berhasil di-uninstall.")

def list_urls():
    projects = scan_projects()
    print("\n--- Dashboard Utama ---")
    for ver, (dom, _) in PHP_STACKS.items():
        print(f"PHP {ver} Index : http://{dom}")

    print("\n--- Project Subdomains ---")
    if not projects:
        print("(Belum ada subfolder di projects/)")
        return

    for p in projects:
        print(f"[{p}]")
        for ver, (dom, _) in PHP_STACKS.items():
            print(f"  PHP {ver} : http://{p}.{dom}")
        print()

ALIASES_DIR = BASE_DIR / "bin" / "aliases"

def get_host_mount_dir():
    # 1. Cek file .env
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("PROJECTS_DIR="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    p = Path(val)
                    if not p.is_absolute():
                        p = (BASE_DIR / p).resolve()
                    if p.exists():
                        return p
        except Exception:
            pass

    # 2. Cek compose file
    compose_file = BASE_DIR / "docker-compose.yml"
    if compose_file.exists():
        try:
            content = compose_file.read_text(encoding="utf-8")
            m = re.search(r'-\s+([^:\s]+):/srv', content)
            if m:
                raw_path = m.group(1).strip()
                if raw_path.startswith("${") and ":-" in raw_path:
                    raw_path = raw_path.split(":-", 1)[1].rstrip("}")
                p = (BASE_DIR / raw_path).resolve()
                if p.exists():
                    return p
        except Exception:
            pass
    return (BASE_DIR / "projects").resolve()

def generate_alias_scripts():
    ALIASES_DIR.mkdir(parents=True, exist_ok=True)
    host_mount = get_host_mount_dir()
    host_mount_str = str(host_mount)
    host_len = len(host_mount_str)
    compose_file = str(BASE_DIR / "docker-compose.yml")

    cmds = [
        ("php", "php82", "php"),
        ("php82", "php82", "php"),
        ("php8", "php82", "php"),
        ("php74", "php74", "php"),
        ("php7", "php74", "php"),
        ("php56", "php56", "php"),
        ("php5", "php56", "php"),
        ("composer", "php82", "composer"),
        ("artisan", "php82", "php artisan"),
    ]

    for name, service, exe in cmds:
        # Windows batch wrapper (.bat)
        bat_content = (
            "@echo off\n"
            "setlocal enabledelayedexpansion\n\n"
            f'set "COMPOSE_FILE={compose_file}"\n'
            f'set "SERVICE={service}"\n'
            f'set "HOST_DIR={host_mount_str}"\n'
            'set "WORKDIR=/srv"\n'
            'set "CURR=%CD%"\n\n'
            f'if /i "%CURR:~0,{host_len}%"=="%HOST_DIR%" (\n'
            f'    set "REL=%CURR:~{host_len}%"\n'
            '    set "REL=' + '!REL:\\=/!' + '"\n'
            '    set "WORKDIR=/srv!REL!"\n'
            ")\n\n"
            f'docker compose -f "%COMPOSE_FILE%" exec -w "!WORKDIR!" %SERVICE% {exe} %*\n'
            "exit /b %errorlevel%\n"
        )
        (ALIASES_DIR / f"{name}.bat").write_text(bat_content, encoding="utf-8")

        # Bash / POSIX shell wrapper (Git Bash, WSL, Linux, Mac)
        sh_content = (
            "#!/usr/bin/env bash\n"
            f'COMPOSE_FILE="{Path(compose_file).as_posix()}"\n'
            f'SERVICE="{service}"\n'
            f'HOST_DIR="{host_mount.as_posix()}"\n'
            'WORKDIR="/srv"\n\n'
            'CURR="$(pwd -P)"\n'
            'if [[ "$CURR" == "$HOST_DIR"* ]]; then\n'
            '    REL="${CURR#$HOST_DIR}"\n'
            '    WORKDIR="/srv${REL}"\n'
            "fi\n\n"
            f'docker compose -f "$COMPOSE_FILE" exec -w "$WORKDIR" "$SERVICE" {exe} "$@"\n'
        )
        sh_file = ALIASES_DIR / name
        sh_file.write_text(sh_content, encoding="utf-8")
        try:
            sh_file.chmod(0o755)
        except Exception:
            pass

    print(f"\n[OK] Script wrapper alias berhasil dibuat di: {ALIASES_DIR}")
    print("     Perintah: php, php82, php74, php56, composer, artisan")
    return True

def install_to_user_path():
    generate_alias_scripts()
    aliases_path_str = str(ALIASES_DIR.resolve())

    if platform.system() == "Windows":
        cmd = [
            "powershell", "-NoProfile", "-Command",
            f"""
            $target = '{aliases_path_str}';
            $oldPath = [Environment]::GetEnvironmentVariable('Path', 'User');
            $parts = ($oldPath -split ';') | Where-Object {{ $_.Trim() -ne '' }};
            if ($parts -notcontains $target) {{
                $newPath = ($parts + $target) -join ';';
                [Environment]::SetEnvironmentVariable('Path', $newPath, 'User');
                Write-Output 'ADDED'
            }} else {{
                Write-Output 'ALREADY_EXISTS'
            }}
            """
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        out = res.stdout.strip()
        if "ADDED" in out:
            print(f"[OK] {aliases_path_str} berhasil ditambahkan ke User PATH Windows.")
            print("[INFO] Buka terminal baru (CMD/PowerShell/Git Bash) agar PATH aktif.")
        elif "ALREADY_EXISTS" in out:
            print(f"[OK] {aliases_path_str} sudah terdaftar di User PATH.")
        else:
            print(f"[WARN] Status update PATH: {out} {res.stderr.strip()}")
    else:
        install_to_bashrc()

def uninstall_from_user_path():
    aliases_path_str = str(ALIASES_DIR.resolve())
    if platform.system() == "Windows":
        cmd = [
            "powershell", "-NoProfile", "-Command",
            f"""
            $target = '{aliases_path_str}';
            $oldPath = [Environment]::GetEnvironmentVariable('Path', 'User');
            $parts = ($oldPath -split ';') | Where-Object {{ $_.Trim() -ne '' -and $_ -ne $target }};
            $newPath = $parts -join ';';
            [Environment]::SetEnvironmentVariable('Path', $newPath, 'User');
            Write-Output 'REMOVED'
            """
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        print(f"[OK] {aliases_path_str} dihapus dari User PATH.")

        subprocess.run(["reg", "delete", r"HKCU\Software\Microsoft\Command Processor", "/v", "AutoRun", "/f"],
                       capture_output=True, text=True)
    print("[OK] Uninstall alias selesai.")

def install_doskey_autorun():
    generate_alias_scripts()
    doskey_file = ALIASES_DIR / "doskey_aliases.cmd"
    compose_file = str(BASE_DIR / "docker-compose.yml")
    content = f"""@echo off
doskey php=docker compose -f "{compose_file}" exec php82 php $*
doskey php82=docker compose -f "{compose_file}" exec php82 php $*
doskey php74=docker compose -f "{compose_file}" exec php74 php $*
doskey php56=docker compose -f "{compose_file}" exec php56 php $*
doskey composer=docker compose -f "{compose_file}" exec php82 composer $*
doskey artisan=docker compose -f "{compose_file}" exec php82 php artisan $*
"""
    doskey_file.write_text(content, encoding="utf-8")
    print(f"[OK] File doskey dibuat: {doskey_file}")

    if platform.system() == "Windows":
        cmd = ["reg", "add", r"HKCU\Software\Microsoft\Command Processor", "/v", "AutoRun", "/t", "REG_SZ", "/d", str(doskey_file), "/f"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print("[OK] Doskey macro didaftarkan ke Windows CMD AutoRun.")
        else:
            print(f"[WARN] Gagal update registry AutoRun: {res.stderr.strip()}")

def install_to_bashrc():
    generate_alias_scripts()
    bashrc_path = Path.home() / ".bashrc"
    aliases_path_str = ALIASES_DIR.resolve().as_posix()
    line_export = f'export PATH="{aliases_path_str}:$PATH"'

    try:
        content = bashrc_path.read_text(encoding="utf-8") if bashrc_path.exists() else ""
        if line_export not in content:
            with open(bashrc_path, "a", encoding="utf-8") as f:
                f.write(f"\n# MyDevEnv PHP Aliases\n{line_export}\n")
            print(f"[OK] Alias path ditambahkan ke {bashrc_path}")
            print("     Jalankan: source ~/.bashrc")
        else:
            print(f"[OK] Alias path sudah ada di {bashrc_path}")
    except Exception as e:
        print(f"[ERROR] Gagal menulis ke {bashrc_path}: {e}")

def action_alias():
    while True:
        print("\n==========================================")
        print("      SETUP COMMAND ALIAS PHP (DOCKER)    ")
        print("==========================================")
        print("Perintah alias yang disediakan:")
        print("  - php      : PHP 8.2 (default)")
        print("  - php82/8  : PHP 8.2")
        print("  - php74/7  : PHP 7.4")
        print("  - php56/5  : PHP 5.6")
        print("  - composer : Composer CLI (PHP 8.2)")
        print("  - artisan  : PHP Artisan CLI")
        print("------------------------------------------")
        print("1. Pasang Alias ke User PATH Windows (Rekomendasi - CMD/PowerShell/Git Bash)")
        print("2. Generate File Script Alias Saja (bin/aliases)")
        print("3. Pasang Doskey AutoRun (Khusus CMD)")
        print("4. Pasang ke ~/.bashrc (Git Bash / Linux / macOS)")
        print("5. Hapus Alias dari User PATH & AutoRun")
        print("0. Kembali ke Menu Utama")
        print("------------------------------------------")
        choice = input("Pilih menu [0-5]: ").strip()

        if choice == "1":
            install_to_user_path()
        elif choice == "2":
            generate_alias_scripts()
        elif choice == "3":
            install_doskey_autorun()
        elif choice == "4":
            install_to_bashrc()
        elif choice == "5":
            uninstall_from_user_path()
        elif choice == "0":
            break
        else:
            print("Pilihan tidak valid.")

def show_menu():
    while True:
        print("\n==========================================")
        print("     MYDEVENV PORTABLE STACK CONTROL      ")
        print("==========================================")
        print("1. Setup Baru (Inisialisasi + Pull + Sync)")
        print("2. Start Stack (up)")
        print("3. Stop Stack (down)")
        print("4. Restart Stack")
        print("5. Sync Domain & Hosts (Project baru)")
        print("6. Repair Stack (Rebuild config + Restart)")
        print("7. Status Container (ps)")
        print("8. Uninstall Stack")
        print("9. Setup Command Alias PHP (Docker CLI)")
        print("0. Keluar")
        print("------------------------------------------")
        choice = input("Pilih menu [0-9]: ").strip()

        if choice == "1":
            action_setup()
        elif choice == "2":
            subprocess.run(["docker", "compose", "up", "-d"], cwd=BASE_DIR)
            generate_nginx_configs()
            sync_hosts_file()
            reload_nginx()
            list_urls()
        elif choice == "3":
            subprocess.run(["docker", "compose", "down"], cwd=BASE_DIR)
        elif choice == "4":
            subprocess.run(["docker", "compose", "restart"], cwd=BASE_DIR)
        elif choice == "5":
            generate_nginx_configs()
            sync_hosts_file()
            reload_nginx()
            list_urls()
        elif choice == "6":
            action_repair()
        elif choice == "7":
            subprocess.run(["docker", "compose", "ps"], cwd=BASE_DIR)
        elif choice == "8":
            action_uninstall()
        elif choice == "9":
            action_alias()
        elif choice == "0":
            sys.exit(0)
        else:
            print("Pilihan tidak valid.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ["--setup", "setup"]:
            action_setup()
        elif arg in ["--repair", "repair"]:
            action_repair()
        elif arg in ["--uninstall", "uninstall"]:
            action_uninstall()
        elif arg in ["--sync", "--auto", "sync"]:
            generate_nginx_configs()
            sync_hosts_file()
            reload_nginx()
        elif arg in ["--alias", "alias"]:
            action_alias()
        else:
            show_menu()
    else:
        show_menu()
