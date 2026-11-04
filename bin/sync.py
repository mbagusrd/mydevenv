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
    "5.6": ("php56.test", "php56:9000", "php56"),
    "7.4": ("php74.test", "php74:9000", "php74"),
    "8.2": ("php82.test", "php82:9000", "php82"),
    "8.3": ("php83.test", "php83:9000", "php83"),
    "8.4": ("php84.test", "php84:9000", "php84"),
}
CONFIG_FILE = BASE_DIR / "config" / "settings.json"
DEFAULT_PHP_VER = "8.2"

def normalize_php_version(ver):
    ver = str(ver).strip()
    mapping = {
        "5": "5.6",
        "56": "5.6",
        "5.6": "5.6",
        "7": "7.4",
        "74": "7.4",
        "7.4": "7.4",
        "8": "8.2",
        "82": "8.2",
        "8.2": "8.2",
        "83": "8.3",
        "8.3": "8.3",
        "84": "8.4",
        "8.4": "8.4",
    }
    return mapping.get(ver)

def get_settings():
    if CONFIG_FILE.exists():
        try:
            import json
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_settings(data):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    import json
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def get_current_php_version():
    data = get_settings()
    ver = normalize_php_version(data.get("default_php", DEFAULT_PHP_VER))
    if ver in PHP_STACKS:
        return ver
    return DEFAULT_PHP_VER

def set_current_php_version(ver):
    norm = normalize_php_version(ver)
    if not norm or norm not in PHP_STACKS:
        return False
    data = get_settings()
    data["default_php"] = norm
    save_settings(data)
    return True

def get_enabled_projects():
    data = get_settings()
    enabled = data.get("enabled_projects", [])
    if isinstance(enabled, list):
        return set(enabled)
    return set()

ALL_CUSTOM_CONTAINERS = ["postgres", "mongo"]

def get_enabled_containers():
    data = get_settings()
    enabled = data.get("enabled_containers", [])
    if isinstance(enabled, list):
        return set(enabled)
    return set()

def set_container_enabled(service_name, enabled=True):
    data = get_settings()
    current = set(data.get("enabled_containers", []))
    if enabled:
        current.add(service_name)
    else:
        current.discard(service_name)
    data["enabled_containers"] = sorted(list(current))
    save_settings(data)

def get_docker_compose_up_cmd():
    enabled = get_enabled_containers()
    cmd = ["docker", "compose"]
    for svc in enabled:
        if svc in ALL_CUSTOM_CONTAINERS:
            cmd.extend(["--profile", svc])
    cmd.extend(["up", "-d"])
    return cmd

def set_project_enabled(project_name, enabled=True):
    data = get_settings()
    current = set(data.get("enabled_projects", []))
    if enabled:
        current.add(project_name)
    else:
        current.discard(project_name)
    data["enabled_projects"] = sorted(list(current))
    save_settings(data)

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
    curr_ver = get_current_php_version()
    _, default_fpm, _ = PHP_STACKS[curr_ver]

    # 1. Base dashboards for root domains (support both dir listing and php script execution)
    dash_conf = "# Dashboards for root domains\n"
    # Helper to generate server block for dashboard
    def build_dashboard_server(server_name, fpm_pass):
        return f"""server {{
    listen 80;
    server_name {server_name};
    root /srv;
    index index.php index.html;
    autoindex on;

    location / {{
        try_files $uri $uri/ @subfolder;
    }}

    location @subfolder {{
        # 1. Nested subfolder with /public/ anywhere (e.g. /a/b/public/foo/bar)
        rewrite ^(/.+/public)/?(.*)$ $1/index.php?$query_string last;

        # 2. Subfolder directly under root
        rewrite ^/([^/]+)/?(.*)$ /$1/index.php?$query_string last;
    }}

    # Handle fastcgi for any .php inside nested folders (including /public/)
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

    dash_conf += build_dashboard_server("php.test", default_fpm)
    for ver, (domain, fpm_pass, _) in PHP_STACKS.items():
        dash_conf += build_dashboard_server(domain, fpm_pass)

    (VHOST_DIR / "00-dashboards.conf").write_text(dash_conf, encoding="utf-8")

    # 2. Vhost per enabled project
    all_projects = scan_projects()
    enabled_set = get_enabled_projects()
    active_projects = [p for p in all_projects if p in enabled_set]
    projects_dir = get_host_mount_dir()
    for f in VHOST_DIR.glob("project-*.conf"):
        f.unlink(missing_ok=True)

    for p in active_projects:
        proj_dir = projects_dir / p
        has_public = (proj_dir / "public").is_dir()
        doc_root = f"/srv/{p}/public" if has_public else f"/srv/{p}"

        conf = f"# Config for project: {p}\n"
        # Default alias <project>.test pointing to active default PHP-FPM
        conf += f"""server {{
    listen 80;
    server_name {p}.test;
    root {doc_root};
    index index.php index.html;

    location / {{
        try_files $uri $uri/ /index.php?$query_string;
    }}

    location ~ \\.php$ {{
        fastcgi_pass {default_fpm};
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME $realpath_root$fastcgi_script_name;
        include fastcgi_params;
    }}
}}
"""
        for ver, (base_domain, fpm_pass, _) in PHP_STACKS.items():
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

    print(f"[OK] Nginx configs generated ({len(active_projects)}/{len(all_projects)} project aktif).")

def sync_hosts_file():
    hosts_path = get_hosts_path()
    all_projects = scan_projects()
    enabled_set = get_enabled_projects()
    active_projects = [p for p in all_projects if p in enabled_set]

    # Target domains that SHOULD be in hosts
    target_domains = ["php.test"]
    for _, (domain, _, _) in PHP_STACKS.items():
        target_domains.append(domain)
    for p in active_projects:
        target_domains.append(f"{p}.test")
        for _, (domain, _, _) in PHP_STACKS.items():
            target_domains.append(f"{p}.{domain}")

    target_set = set(target_domains)

    try:
        current_hosts = hosts_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"[ERROR] Gagal baca {hosts_path}: {e}")
        return False

    # Check if hosts needs cleaning of disabled project domains
    lines = current_hosts.splitlines()
    cleaned_lines = []
    stack_base_domains = [dom for _, (dom, _, _) in PHP_STACKS.items()] + ["test"]
    needs_rewrite = False

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            cleaned_lines.append(line)
            continue
        parts = stripped.split()
        if len(parts) >= 2 and parts[0] in ["127.0.0.1", "::1"]:
            host_name = parts[1].lower()
            # If domain ends with .test or any PHP stack domain
            is_stack_domain = host_name == "php.test" or any(host_name.endswith(f".{d}") or host_name == d for d in stack_base_domains) or host_name.endswith(".test")
            if is_stack_domain and host_name not in target_set:
                needs_rewrite = True
                continue
        cleaned_lines.append(line)

    entries_to_add = []
    current_hosts_check = "\n".join(cleaned_lines) if needs_rewrite else current_hosts
    for d in target_domains:
        line = f"127.0.0.1 {d}"
        if line not in current_hosts_check:
            entries_to_add.append(line)

    if needs_rewrite or entries_to_add:
        if entries_to_add:
            cleaned_lines.append("\n# MyDevEnv Portable Stack")
            cleaned_lines.extend(entries_to_add)
        new_content = "\n".join(cleaned_lines).rstrip() + "\n"
        try:
            hosts_path.write_text(new_content, encoding="utf-8")
            print(f"[OK] File hosts diperbarui ({len(active_projects)} project aktif).")
        except PermissionError:
            print(f"[WARN] Izin ditolak tulis ke {hosts_path}.")
            print("Jalankan terminal sebagai Administrator (Windows) atau gunakan sudo (Linux/Mac).")
            if entries_to_add:
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
    stack_domains = ["php.test", "php5.test", "php7.test", "php8.test", "php56.test", "php74.test", "php82.test", "php83.test", "php84.test"]

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

    print("[INFO] Mengunduh dan build Docker images (compose pull + build)...")
    subprocess.run(["docker", "compose", "pull", "--ignore-buildable"], cwd=BASE_DIR)
    subprocess.run(["docker", "compose", "build"], cwd=BASE_DIR)

    generate_nginx_configs()
    sync_hosts_file()

    print("\n[SELESAI] Setup berhasil disiapkan.")
    ask_start = input("Jalankan stack container sekarang? [Y/n]: ").strip().lower()
    if ask_start in ["", "y", "yes"]:
        subprocess.run(get_docker_compose_up_cmd(), cwd=BASE_DIR)
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
    all_projects = scan_projects()
    enabled_set = get_enabled_projects()
    curr_ver = get_current_php_version()
    print(f"\n--- Versi PHP Default Aktif: PHP {curr_ver} ({PHP_STACKS[curr_ver][2]}) ---")
    print("--- Dashboard Utama ---")
    print(f"Default (PHP {curr_ver}) : http://php.test")
    for ver, (dom, _, _) in PHP_STACKS.items():
        print(f"PHP {ver} Index       : http://{dom}")

    print("\n--- Project Subdomains ---")
    active_projects = [p for p in all_projects if p in enabled_set]
    if not active_projects:
        print("(Tidak ada project aktif. Aktifkan lewat menu 'Manage Project Domain')")
        return

    for p in active_projects:
        print(f"[{p}]")
        print(f"  Default (PHP {curr_ver}) : http://{p}.test")
        for ver, (dom, _, _) in PHP_STACKS.items():
            print(f"  PHP {ver}             : http://{p}.{dom}")
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
    curr_ver = get_current_php_version()
    default_service = PHP_STACKS[curr_ver][2]

    cmds = [
        ("php", default_service, "php"),
        ("php84", "php84", "php"),
        ("php83", "php83", "php"),
        ("php82", "php82", "php"),
        ("php8", default_service if curr_ver.startswith("8.") else "php82", "php"),
        ("php74", "php74", "php"),
        ("php7", "php74", "php"),
        ("php56", "php56", "php"),
        ("php5", "php56", "php"),
        ("composer", default_service, "composer"),
        ("artisan", default_service, "php artisan"),
        ("mysql", "mariadb", "mysql"),
        ("mysqldump", "mariadb", "mysqldump"),
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
            '    if defined REL (\n'
            '        set "REL=' + '!REL:\\=/!' + '"\n'
            '        set "WORKDIR=/srv!REL!"\n'
            '    )\n'
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
            'WIN_CURR="$(pwd -W 2>/dev/null || cygpath -w "$CURR" 2>/dev/null || echo "$CURR")"\n'
            'WIN_CURR="${WIN_CURR//\\\\//}"\n'
            'if [[ "$CURR" == "$HOST_DIR"* ]]; then\n'
            '    REL="${CURR#$HOST_DIR}"\n'
            '    WORKDIR="/srv${REL}"\n'
            'elif [[ "$WIN_CURR" == "$HOST_DIR"* ]]; then\n'
            '    REL="${WIN_CURR#$HOST_DIR}"\n'
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
    print("     Perintah: php, php82, php74, php56, composer, artisan, mysql, mysqldump")
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
    curr_ver = get_current_php_version()
    default_service = PHP_STACKS[curr_ver][2]

    content = f"""@echo off
doskey php=docker compose -f "{compose_file}" exec {default_service} php $*
doskey php84=docker compose -f "{compose_file}" exec php84 php $*
doskey php83=docker compose -f "{compose_file}" exec php83 php $*
doskey php82=docker compose -f "{compose_file}" exec php82 php $*
doskey php8=docker compose -f "{compose_file}" exec {default_service if curr_ver.startswith("8.") else "php82"} php $*
doskey php74=docker compose -f "{compose_file}" exec php74 php $*
doskey php7=docker compose -f "{compose_file}" exec php74 php $*
doskey php56=docker compose -f "{compose_file}" exec php56 php $*
doskey php5=docker compose -f "{compose_file}" exec php56 php $*
doskey composer=docker compose -f "{compose_file}" exec {default_service} composer $*
doskey artisan=docker compose -f "{compose_file}" exec {default_service} php artisan $*
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
        print("  - php            : PHP 8.2 (default)")
        print("  - php82/8        : PHP 8.2")
        print("  - php74/7        : PHP 7.4")
        print("  - php56/5        : PHP 5.6")
        print("  - composer       : Composer CLI (PHP 8.2)")
        print("  - artisan        : PHP Artisan CLI")
        print("  - mysql          : MySQL CLI (MariaDB)")
        print("  - mysqldump      : MySQL Dump CLI (MariaDB)")
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

def action_switch_php(target_ver=None):
    if not target_ver:
        curr_ver = get_current_php_version()
        print("\n==========================================")
        print("       SWITCH DEFAULT VERSI PHP           ")
        print("==========================================")
        print(f"Versi saat ini: PHP {curr_ver} ({PHP_STACKS[curr_ver][2]})")
        print("Dampak switch:")
        print("  - CLI: perintah `php`, `composer`, `artisan` mengarah ke versi ini")
        print("  - FPM: domain `php.test` dan `<project>.test` mengarah ke versi ini")
        print("------------------------------------------")
        print("1. PHP 5.6 (php56)")
        print("2. PHP 7.4 (php74)")
        print("3. PHP 8.2 (php82 - official alpine)")
        print("4. PHP 8.3 (php83 - official alpine)")
        print("5. PHP 8.4 (php84 - official alpine)")
        print("0. Batal / Kembali")
        print("------------------------------------------")
        choice = input("Pilih versi target [0-5]: ").strip()
        mapping = {"1": "5.6", "2": "7.4", "3": "8.2", "4": "8.3", "5": "8.4"}
        if choice in mapping:
            target_ver = mapping[choice]
        elif choice == "0":
            return
        else:
            print("Pilihan tidak valid.")
            return

    norm_ver = normalize_php_version(target_ver)
    if not norm_ver or norm_ver not in PHP_STACKS:
        print(f"[ERROR] Versi PHP '{target_ver}' tidak dikenal. Pilihan: 5.6, 7.4, 8.2, 8.3, 8.4")
        return

    set_current_php_version(norm_ver)
    svc = PHP_STACKS[norm_ver][2]
    print(f"\n[INFO] Versi PHP default dialihkan ke PHP {norm_ver} ({svc}).")

    # Update alias scripts
    generate_alias_scripts()

    # Update nginx configs & reload
    generate_nginx_configs()
    sync_hosts_file()
    reload_nginx()

    print(f"[OK] Default PHP CLI dan FPM sekarang aktif di PHP {norm_ver} ({svc})!")

def action_manage_projects():
    while True:
        all_projects = scan_projects()
        enabled_set = get_enabled_projects()
        print("\n==========================================")
        print("         MANAGE PROJECT DOMAIN (.test)    ")
        print("==========================================")
        if not all_projects:
            print("(Tidak ada project ditemukan di folder projects/)")
            print("------------------------------------------")
            print("0. Kembali")
            input("Tekan Enter untuk kembali...")
            return

        print("Pilih nomor project untuk toggle AKTIF / NONAKTIF:")
        for idx, p in enumerate(all_projects, 1):
            status = "[AKTIF]    " if p in enabled_set else "[NONAKTIF] "
            print(f" {idx:2d}. {status} {p}")
        print("------------------------------------------")
        print(" A. Aktifkan SEMUA project")
        print(" D. Nonaktifkan SEMUA project")
        print(" 0. Simpan & Kembali")
        print("------------------------------------------")
        choice = input("Pilih menu/nomor project: ").strip()

        if choice == "0":
            break
        elif choice.lower() == "a":
            for p in all_projects:
                set_project_enabled(p, True)
            generate_nginx_configs()
            sync_hosts_file()
            reload_nginx()
            print("[OK] Semua project diaktifkan.")
        elif choice.lower() == "d":
            for p in all_projects:
                set_project_enabled(p, False)
            generate_nginx_configs()
            sync_hosts_file()
            reload_nginx()
            print("[OK] Semua project dinonaktifkan.")
        elif choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(all_projects):
                target_p = all_projects[idx - 1]
                new_state = target_p not in enabled_set
                set_project_enabled(target_p, new_state)
                generate_nginx_configs()
                sync_hosts_file()
                reload_nginx()
                state_str = "diaktifkan" if new_state else "dinonaktifkan"
                print(f"[OK] Project '{target_p}' berhasil {state_str}.")
            else:
                print("Nomor project tidak valid.")
        else:
            print("Pilihan tidak valid.")

def action_manage_containers():
    while True:
        enabled_set = get_enabled_containers()
        print("\n==========================================")
        print("         MANAGE CUSTOM CONTAINERS         ")
        print("==========================================")
        print("Pilih nomor container untuk toggle AKTIF / NONAKTIF:")
        for idx, svc in enumerate(ALL_CUSTOM_CONTAINERS, 1):
            status = "[AKTIF]    " if svc in enabled_set else "[NONAKTIF] "
            print(f" {idx:2d}. {status} {svc}")
        print("------------------------------------------")
        print(" A. Aktifkan SEMUA container opsional")
        print(" D. Nonaktifkan SEMUA container opsional")
        print(" 0. Simpan & Kembali")
        print("------------------------------------------")
        choice = input("Pilih menu/nomor container: ").strip()

        if choice == "0":
            break
        elif choice.lower() == "a":
            for svc in ALL_CUSTOM_CONTAINERS:
                set_container_enabled(svc, True)
                subprocess.run(["docker", "compose", "--profile", svc, "up", "-d", svc], cwd=BASE_DIR)
            print("[OK] Semua container opsional diaktifkan dan dijalankan.")
        elif choice.lower() == "d":
            for svc in ALL_CUSTOM_CONTAINERS:
                set_container_enabled(svc, False)
                subprocess.run(["docker", "compose", "stop", svc], cwd=BASE_DIR)
            print("[OK] Semua container opsional dinonaktifkan dan dihentikan.")
        elif choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(ALL_CUSTOM_CONTAINERS):
                target_svc = ALL_CUSTOM_CONTAINERS[idx - 1]
                new_state = target_svc not in enabled_set
                set_container_enabled(target_svc, new_state)
                if new_state:
                    subprocess.run(["docker", "compose", "--profile", target_svc, "up", "-d", target_svc], cwd=BASE_DIR)
                    print(f"[OK] Container '{target_svc}' berhasil diaktifkan dan dijalankan.")
                else:
                    subprocess.run(["docker", "compose", "stop", target_svc], cwd=BASE_DIR)
                    print(f"[OK] Container '{target_svc}' berhasil dinonaktifkan dan dihentikan.")
            else:
                print("Nomor container tidak valid.")
        else:
            print("Pilihan tidak valid.")

def show_menu():
    while True:
        curr_ver = get_current_php_version()
        enabled_count = len([p for p in scan_projects() if p in get_enabled_projects()])
        enabled_containers_count = len(get_enabled_containers())
        print("\n==========================================")
        print(f"  MYDEVENV STACK CONTROL [PHP: {curr_ver}]")
        print(f"  Project Domain Aktif   : {enabled_count} project")
        print(f"  Container Opsional     : {enabled_containers_count}/{len(ALL_CUSTOM_CONTAINERS)} aktif")
        print("==========================================")
        print("1. Setup Baru (Inisialisasi + Pull + Sync)")
        print("2. Start Stack (up)")
        print("3. Stop Stack (down)")
        print("4. Restart Stack")
        print("5. Sync Domain & Hosts")
        print("6. Switch Versi PHP (CLI & FPM Default)")
        print("7. Manage Project Domain (Aktifkan / Matikan Domain .test)")
        print("8. Manage Custom Containers (Aktifkan / Matikan Postgres, Mongo)")
        print("9. Repair Stack (Rebuild config + Restart)")
        print("10. Status Container (ps)")
        print("11. Setup Command Alias PHP (Docker CLI)")
        print("12. Uninstall Stack")
        print("0. Keluar")
        print("------------------------------------------")
        choice = input("Pilih menu [0-12]: ").strip()

        if choice == "1":
            action_setup()
        elif choice == "2":
            subprocess.run(get_docker_compose_up_cmd(), cwd=BASE_DIR)
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
            action_switch_php()
        elif choice == "7":
            action_manage_projects()
        elif choice == "8":
            action_manage_containers()
        elif choice == "9":
            action_repair()
        elif choice == "10":
            subprocess.run(["docker", "compose", "ps"], cwd=BASE_DIR)
        elif choice == "11":
            action_alias()
        elif choice == "12":
            action_uninstall()
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
        elif arg in ["--enable", "enable"]:
            if len(sys.argv) > 2:
                proj = sys.argv[2]
                set_project_enabled(proj, True)
                generate_nginx_configs()
                sync_hosts_file()
                reload_nginx()
                print(f"[OK] Project '{proj}' diaktifkan.")
            else:
                action_manage_projects()
        elif arg in ["--disable", "disable"]:
            if len(sys.argv) > 2:
                proj = sys.argv[2]
                set_project_enabled(proj, False)
                generate_nginx_configs()
                sync_hosts_file()
                reload_nginx()
                print(f"[OK] Project '{proj}' dinonaktifkan.")
            else:
                action_manage_projects()
        elif arg in ["--projects", "projects", "--domain", "domain"]:
            action_manage_projects()
        elif arg in ["--container", "container", "--containers", "containers"]:
            action_manage_containers()
        elif arg in ["--start-container", "start-container", "--start", "start"]:
            if len(sys.argv) > 2:
                svc = sys.argv[2].lower()
                if svc in ALL_CUSTOM_CONTAINERS:
                    set_container_enabled(svc, True)
                    subprocess.run(["docker", "compose", "--profile", svc, "up", "-d", svc], cwd=BASE_DIR)
                    print(f"[OK] Container '{svc}' diaktifkan dan dijalankan.")
                else:
                    print(f"[ERROR] Container '{svc}' tidak dikenal. Pilihan: {', '.join(ALL_CUSTOM_CONTAINERS)}")
            else:
                action_manage_containers()
        elif arg in ["--stop-container", "stop-container", "--stop", "stop"]:
            if len(sys.argv) > 2:
                svc = sys.argv[2].lower()
                if svc in ALL_CUSTOM_CONTAINERS:
                    set_container_enabled(svc, False)
                    subprocess.run(["docker", "compose", "stop", svc], cwd=BASE_DIR)
                    print(f"[OK] Container '{svc}' dinonaktifkan dan dihentikan.")
                else:
                    print(f"[ERROR] Container '{svc}' tidak dikenal. Pilihan: {', '.join(ALL_CUSTOM_CONTAINERS)}")
            else:
                action_manage_containers()
        elif arg in ["--up-custom", "up-custom"]:
            subprocess.run(get_docker_compose_up_cmd(), cwd=BASE_DIR)
        elif arg in ["--alias", "alias"]:
            action_alias()
        elif arg in ["--switch", "switch", "use"]:
            target = sys.argv[2] if len(sys.argv) > 2 else None
            action_switch_php(target)
        else:
            show_menu()
    else:
        show_menu()
