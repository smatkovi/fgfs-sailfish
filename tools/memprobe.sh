#!/bin/sh
# memprobe.sh - what does one simulator run cost in memory that is never
# given back?
#
#   memprobe.sh <label> [seconds]
#
# Records the kernel's memory counters before the run and again after the
# process is gone, so the difference is what survived the process. Reading
# every counter rather than just "used" is the point: which one grows says
# where the memory went, and "used" alone cannot distinguish a driver
# allocation from page cache.

set -u

LABEL=${1:-run}
SECS=${2:-90}

snap() {
    echo "--- $1"
    grep -E '^(MemTotal|MemFree|MemAvailable|Buffers|Cached|SwapCached|SwapTotal|SwapFree|Shmem|Slab|SReclaimable|SUnreclaim|KernelStack|PageTables|VmallocUsed|Mapped|AnonPages):' /proc/meminfo
    # The size column is decimal (%08zu in the kernel), only flags and mode
    # are hex. Parsing it as hex inflated the total to 4.5 GB when it is 244 MB.
    printf 'DmaBufTotal:    %s kB\n' "$(sudo awk 'NR>2 && $1 ~ /^[0-9]+$/ {s+=$1} END {print int(s/1024)}' /sys/kernel/debug/dma_buf/bufinfo 2>/dev/null || echo 0)"
    printf 'DmaBufCount:    %s\n' "$(sudo awk 'NR>2 && $1 ~ /^[0-9]+$/ {n++} END {print n+0}' /sys/kernel/debug/dma_buf/bufinfo 2>/dev/null || echo 0)"
    # From /proc, never from busybox "ps -o rss": that reports a total of
    # about 800 MB where /proc/*/statm sums to 8.5 GB over the same
    # processes. Believing ps produced a phantom kernel memory leak.
    printf 'ProcRssSum:     %s kB\n' "$(sudo awk '{s+=$2} END {print int(s*4)}' /proc/[0-9]*/statm 2>/dev/null)"
    printf 'ProcCount:      %s\n' "$(ps 2>/dev/null | grep -c .)"
}

OUT=/tmp/memprobe-$LABEL.txt
: > "$OUT"

snap "vorher" >> "$OUT"

/opt/fgfs/bin/fgfs-run --backend=gles3 --aircraft=c172p --airport=LOWW \
    --disable-sound --timeofday=noon > /tmp/memprobe-$LABEL.log 2>&1 &
PID=$!

i=0; while [ $i -lt "$SECS" ]; do i=$((i+1)); sleep 1; done

snap "waehrend" >> "$OUT"

kill $PID 2>/dev/null
pkill fgfs 2>/dev/null
i=0; while [ $i -lt 5 ]; do i=$((i+1)); sleep 1; done
pkill -9 fgfs 2>/dev/null
# generous settling time: the point is what is still gone once everything
# that could be reclaimed has been
i=0; while [ $i -lt 15 ]; do i=$((i+1)); sleep 1; done

snap "nachher" >> "$OUT"
cat "$OUT"
exit 0
