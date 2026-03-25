#!/bin/bash
# ============================================================
# Splinter MOTD Banner
# Place in /etc/update-motd.d/10-splinter (chmod +x)
# Or source from /etc/profile.d/splinter-motd.sh
# ============================================================

R=$'\033[0m'
B=$'\033[1m'
DM=$'\033[2m'
DG=$'\033[38;5;22m'
CY=$'\033[36m'
BC=$'\033[38;5;51m'
BL=$'\033[38;5;33m'
GR=$'\033[38;5;240m'

echo ""
echo "  ${CY}      ┌──────────────────┐${R}"
echo "  ${CY}  ────┤${DG}░░░░░░░░░░░░░░░░░░${CY}├────        ${B}${BL}           _ _       _            ${R}"
echo "  ${CY}  ····┤${DG}░░░${BC}●${DG}░░░░${BC}●${DG}░░░░${BC}●${DG}░░░░${CY}├····        ${B}${BL} ___ _ __ | (_)_ __ | |_ ___ _ __ ${R}"
echo "  ${CY}      ├──────────────────┤            ${B}${BL}/ __| '_ \\| | | '_ \\| __/ _ \\ '__|${R}"
echo "  ${CY}  ────┤${DG}░░░░░░░░░░░░░░░░░░${CY}├────        ${B}${BL}\\__ \\ |_) | | | | | | ||  __/ |   ${R}"
echo "  ${CY}  ····┤${DG}░░░░${BC}●${DG}░░░${BC}●${DG}░░░░${BC}●${DG}░░░░${CY}├····        ${B}${BL}|___/ .__/|_|_|_| |_|\\__\\___|_|   ${R}"
echo "  ${CY}      ├──────────────────┤            ${B}${BL}    |_|${BC}_${R}"
echo "  ${CY}  ────┤${DG}░░░░░░░░░░░░░░░░░░${CY}├────${R}"
echo "  ${CY}  ····┤${DG}░░░${BC}●${DG}░░░░░${BC}●${DG}░░░${BC}●${DG}░░░░${CY}├····"
echo "  ${CY}      └────────┬─────────┘${R}"
echo "  ${DG}            ╭──╯${R}"
echo "  ${DG}          ╭─╯${R}"

# System info
HOSTNAME=$(hostname -f 2>/dev/null || hostname)
UPTIME=$(uptime -p 2>/dev/null || uptime | sed 's/.*up /up /' | sed 's/,.*load.*//')
LOAD=$(cat /proc/loadavg 2>/dev/null | awk '{print $1, $2, $3}')
MEM_TOTAL=$(free -h 2>/dev/null | awk '/Mem:/{print $2}')
MEM_USED=$(free -h 2>/dev/null | awk '/Mem:/{print $3}')
DISK_USAGE=$(df -h / 2>/dev/null | awk 'NR==2{print $3 "/" $2 " (" $5 ")"}')

echo ""
echo "  ${GR}─────────────────────────────────────────────────────────${R}"
printf "  ${GR}%-9s${R} %s\n" "Host" "$HOSTNAME"
printf "  ${GR}%-9s${R} %s\n" "Uptime" "$UPTIME"
printf "  ${GR}%-9s${R} %s\n" "Load" "$LOAD"
printf "  ${GR}%-9s${R} %s\n" "Memory" "$MEM_USED / $MEM_TOTAL"
printf "  ${GR}%-9s${R} %s\n" "Disk /" "$DISK_USAGE"

# GPU info (if nvidia-smi available)
if command -v nvidia-smi &>/dev/null; then
    GPU_COUNT=$(nvidia-smi --query-gpu=count --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 | sed 's/^ *//')
    GPU_USED=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | awk '{s+=$1}END{printf "%.0f",s/1024}')
    GPU_TOTAL=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | awk '{s+=$1}END{printf "%.0f",s/1024}')
    printf "  ${GR}%-9s${R} %s\n" "GPUs" "${GPU_COUNT}x ${GPU_NAME} (${GPU_USED}/${GPU_TOTAL} GB)"
fi

echo "  ${GR}─────────────────────────────────────────────────────────${R}"
echo ""