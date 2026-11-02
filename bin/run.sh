#!/usr/bin/env bash
set -e
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

CMD="${1:-menu}"

case "$CMD" in
    up)
        docker compose up -d
        python3 bin/sync.py --auto || python bin/sync.py --auto
        ;;
    down)
        docker compose down
        ;;
    restart)
        docker compose restart
        ;;
    sync)
        python3 bin/sync.py --sync || python bin/sync.py --sync
        ;;
    setup)
        python3 bin/sync.py --setup || python bin/sync.py --setup
        ;;
    repair)
        python3 bin/sync.py --repair || python bin/sync.py --repair
        ;;
    uninstall)
        python3 bin/sync.py --uninstall || python bin/sync.py --uninstall
        ;;
    ps)
        docker compose ps
        ;;
    exec)
        shift
        docker compose exec "$@"
        ;;
    switch|use)
        shift
        python3 bin/sync.py --switch "$@" || python bin/sync.py --switch "$@"
        ;;
    alias)
        python3 bin/sync.py --alias || python bin/sync.py --alias
        ;;
    php)
        shift
        PHP_VER="8.2"
        if [ -f "config/settings.json" ]; then
            PARSED_VER=$(grep -o '"default_php"[^,]*' config/settings.json | sed -E 's/.*"([0-9.]+)".*/\1/')
            [ -n "$PARSED_VER" ] && PHP_VER="$PARSED_VER"
        fi
        SERVICE="php82"
        [ "$PHP_VER" = "5.6" ] || [ "$PHP_VER" = "5" ] && SERVICE="php56"
        [ "$PHP_VER" = "7.4" ] || [ "$PHP_VER" = "7" ] && SERVICE="php74"
        [ "$PHP_VER" = "8.2" ] || [ "$PHP_VER" = "8" ] && SERVICE="php82"
        [ "$PHP_VER" = "8.3" ] && SERVICE="php83"
        [ "$PHP_VER" = "8.4" ] && SERVICE="php84"
        docker compose exec "$SERVICE" php "$@"
        ;;
    composer)
        shift
        PHP_VER="8.2"
        if [ -f "config/settings.json" ]; then
            PARSED_VER=$(grep -o '"default_php"[^,]*' config/settings.json | sed -E 's/.*"([0-9.]+)".*/\1/')
            [ -n "$PARSED_VER" ] && PHP_VER="$PARSED_VER"
        fi
        SERVICE="php82"
        [ "$PHP_VER" = "5.6" ] || [ "$PHP_VER" = "5" ] && SERVICE="php56"
        [ "$PHP_VER" = "7.4" ] || [ "$PHP_VER" = "7" ] && SERVICE="php74"
        [ "$PHP_VER" = "8.2" ] || [ "$PHP_VER" = "8" ] && SERVICE="php82"
        [ "$PHP_VER" = "8.3" ] && SERVICE="php83"
        [ "$PHP_VER" = "8.4" ] && SERVICE="php84"
        docker compose exec "$SERVICE" composer "$@"
        ;;
    mysql)
        shift
        docker compose exec mariadb mysql "$@"
        ;;
    mysqldump)
        shift
        docker compose exec mariadb mysqldump "$@"
        ;;
    menu)
        python3 bin/sync.py || python bin/sync.py
        ;;
    *)
        echo "Penggunaan: ./bin/run.sh [setup|up|down|restart|sync|switch|repair|uninstall|ps|exec|alias|php|composer|mysql|mysqldump]"
        ;;
esac
