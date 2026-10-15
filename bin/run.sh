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
    alias)
        python3 bin/sync.py --alias || python bin/sync.py --alias
        ;;
    php)
        shift
        docker compose exec php82 php "$@"
        ;;
    composer)
        shift
        docker compose exec php82 composer "$@"
        ;;
    menu)
        python3 bin/sync.py || python bin/sync.py
        ;;
    *)
        echo "Penggunaan: ./bin/run.sh [setup|up|down|restart|sync|repair|uninstall|ps|exec|alias|php|composer]"
        ;;
esac
