#!/bin/sh
# Round-trip osg-model-test.cpp: phone -> host -> container -> build -> back.
#
# The build has to happen in the SDK container; the run has to happen on the
# phone, because that is where the Mali driver is. This script does the whole
# cycle so a source edit is one command away from a new measurement.

set -e

HOST=sebastian@192.168.1.21
CONTAINER=ba82fa4d3804
SRC=osg-model-test.cpp
BIN=osg-model-test

cd "$(dirname "$0")"

echo "-- uploading $SRC"
rsync -a "$SRC" "$HOST:Downloads/"
ssh "$HOST" "docker cp ~/Downloads/$SRC $CONTAINER:/home/mersdk/"

echo "-- compiling in the container"
ssh "$HOST" "docker exec $CONTAINER bash -lc '
    cd /home/mersdk &&
    sb2 -t SailfishOS-5.2.0.15-aarch64 g++ -std=c++11 -O1 $SRC \
        -I/opt/osg-gles3/include -L/opt/osg-gles3/lib \
        -losg -losgDB -losgUtil -losgGA -losgText -losgViewer -lOpenThreads \
        -o $BIN 2>&1 | tail -30 &&
    ls -l $BIN'"

echo "-- fetching the binary"
ssh "$HOST" "docker cp $CONTAINER:/home/mersdk/$BIN ~/Downloads/"
rsync -a "$HOST:Downloads/$BIN" /tmp/
chmod +x "/tmp/$BIN"
ls -l "/tmp/$BIN"
echo "-- ready: /tmp/$BIN"
