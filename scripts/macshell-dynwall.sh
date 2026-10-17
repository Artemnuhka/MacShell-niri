#!/bin/sh
set -eu
light=$1; dark=$2; mode=$3; rise=${4:-390}; dusk=${5:-1110}
case "$mode" in
    dynamic) now=$(date +%H:%M | awk -F: '{print $1*60+$2}'); if [ "$now" -ge "$rise" ] && [ "$now" -lt "$dusk" ]; then path=$light; else path=$dark; fi ;;
    light) path=$light ;;
    *) path=$dark ;;
esac
exec python3 "$(dirname -- "$0")/wallpaper.py" "$path"
