#!/usr/bin/env bash
# Script de sincronización periódica e ingesta de inventario para SoloTono

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR" || exit 1

LOG_FILE="$DIR/scraper_cron.log"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

echo "==========================================================" >> "$LOG_FILE"
echo "[$TIMESTAMP] Iniciando sincronización periódica de inventario SoloTono" >> "$LOG_FILE"
echo "==========================================================" >> "$LOG_FILE"

# Ejecutar scraping completo con matching e historial de precios
PYTHONPATH=scraper scraper/.venv/bin/python3 -m solotono scrape --all >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
FINISH_TIME=$(date "+%Y-%m-%d %H:%M:%S")

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$FINISH_TIME] Sincronización completada exitosamente." >> "$LOG_FILE"
else
    echo "[$FINISH_TIME] Error en la sincronización (Código de salida: $EXIT_CODE)." >> "$LOG_FILE"
fi

exit $EXIT_CODE
