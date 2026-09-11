#!/bin/sh
# perfrun.sh - one timed simulator run, summarised as numbers.
#
#   perfrun.sh <label> [VAR=VALUE ...]
#
# Starts the c172p at LOWW, lets it settle, samples the timing output for a
# fixed window, kills it, and prints a summary. Everything about the run is
# identical between invocations except the environment given on the command
# line, so two labels can be compared directly.
#
# Why a fixed settle time: the first seconds are scenery paging and shader
# compilation, which are one-off costs and would otherwise dominate whatever
# is being compared.

set -u

LABEL=$1
shift

SETTLE=${SETTLE:-60}      # seconds to ignore at the start
WINDOW=${WINDOW:-45}      # seconds to sample
OUT=/tmp/perf-$LABEL.log

rm -f "$OUT"
# FGOPTS adds simulator options; the environment still comes from "$@", so
# a run can vary either side without a second copy of this script.
env FGFS_GLES_TIMING=1 "$@" \
    /opt/fgfs/bin/fgfs-run --backend=gles3 \
    --aircraft=c172p --airport=LOWW --disable-sound --timeofday=noon \
    ${FGOPTS:-} \
    > "$OUT" 2>&1 &
PID=$!

i=0
while [ $i -lt $SETTLE ]; do i=$((i+1)); sleep 1; done
MARK=$(wc -l < "$OUT")
i=0
while [ $i -lt $WINDOW ]; do i=$((i+1)); sleep 1; done

# fgfs-run ends in "exec", so $PID is the simulator itself and this alone
# is enough. The pkill is a safety net for runs started some other way.
#
# Plain "pkill fgfs" - neither -x nor -f. On busybox both are traps:
#   -f matches the whole command line, so it also matches the shell running
#      this script, because the script lives under ~/fgfs-work;
#   -x compares the whole command line for equality rather than the process
#      name, so it matches nothing at all and silently does nothing.
# Without a flag busybox matches the process name, which is what is wanted.
# Verified: pgrep fgfs finds the process, pgrep -x fgfs does not.
kill $PID 2>/dev/null
pkill fgfs 2>/dev/null
i=0
while [ $i -lt 3 ]; do i=$((i+1)); sleep 1; done
kill -9 $PID 2>/dev/null
pkill -9 fgfs 2>/dev/null
i=0
while [ $i -lt 3 ]; do i=$((i+1)); sleep 1; done
left=$(pgrep fgfs | grep -c .)
if [ "$left" != "0" ]; then
    echo "WARNUNG: $left Simulator(en) laufen noch - die naechste Messung waere verfaelscht" >&2
fi

echo "== $LABEL   (env: $*)"
tail -n +"$MARK" "$OUT" > /tmp/perf-window-$LABEL.log
python3 "$HOME/fgfs-work/perfstat.py" /tmp/perf-window-$LABEL.log
exit 0
