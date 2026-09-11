#!/bin/sh
# Minimal test case for the black-dial bug (see BEFUNDE.md, B2).
#
# Renders asi.ac with OSG alone -- no FlightGear, no SimGear, no
# effects, no compositor -- once with the texture and once with
# fract(texcoord) as the colour, then summarises both images as text.
#
# The point is the fork this creates:
#   tc varies   -> OSG delivers coordinates correctly; the fault is in a
#                  layer above, and we add those back one at a time.
#   tc is flat  -> the fault is in OSG itself, and a flat (0,0,*) is the
#                  signature of a disabled vertex attribute array.
#
# Safe to re-run; it only fetches the binary if it is missing.

set -e

BIN=/tmp/osg-model-test
HOST=sebastian@192.168.1.21
CONTAINER=ba82fa4d3804

if [ ! -x "$BIN" ]; then
    echo "-- fetching osg-model-test from the container"
    ssh "$HOST" "docker cp $CONTAINER:/home/mersdk/osg-model-test ~/Downloads/"
    rsync -a "$HOST:Downloads/osg-model-test" /tmp/
    chmod +x "$BIN"
fi

M=$(locate asi.ac 2>/dev/null | head -1)
if [ -z "$M" ]; then
    echo "asi.ac not found via locate -- trying find (slower)"
    M=$(find / -name asi.ac 2>/dev/null | head -1)
fi
if [ -z "$M" ]; then
    echo "FAIL: asi.ac not found anywhere"
    exit 1
fi

echo "-- model: $M"
cd "$(dirname "$M")"
B=$(basename "$M")

LD_LIBRARY_PATH=/opt/osg-gles3/lib:/opt/fgfs/lib
OSG_LIBRARY_PATH=/opt/osg-gles3/lib/osgPlugins-3.6.5
export LD_LIBRARY_PATH OSG_LIBRARY_PATH

echo "-- render 'tex' (normal texturing)"
"$BIN" "$B" /tmp/tex.ppm tex 2>&1 | tail -15

echo "-- render 'tc' (fract(texcoord) as colour)"
"$BIN" "$B" /tmp/tc.ppm tc 2>&1 | tail -15

echo ""
echo "================ ANALYSIS ================"
python3 "$HOME/fgfs-work/ppmstat.py" /tmp/tex.ppm /tmp/tc.ppm
