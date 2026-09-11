#!/bin/bash
# sfos50-osg.sh - after the "osg" stage of sfos50-driver.sh has put the
# OSG GLES3 tree into the 5.0 target: which glibc/libstdc++ versions it
# needs, and the standalone model test built against it (does the renderer
# draw on the device?).  The build itself is sfos50-stack.sh osg; this used
# to build too, but then tested and packed whatever tree was in the target
# before, not the one just built.
set -u
T50=SailfishOS-5.0.0.62-aarch64
LOG=~/sfos50-osg-test.log
fail() { echo "FEHLER: $*"; tail -25 "$LOG"; echo OSG50-TEST-FEHLER; exit 1; }
: > $LOG
L=$(ls /srv/mer/targets/$T50/opt/osg-gles3/lib*/libosg.so.3.6.5 2>/dev/null | head -1)
[ -n "$L" ] || fail "no OSG in the 5.0 target - run sfos50-driver.sh with STAGES=osg first"
S=$(ls ~/stage50-osg/opt/osg-gles3/lib*/libosg.so.3.6.5 2>/dev/null | head -1)
if [ -n "$S" ] && ! cmp -s "$S" "$L"; then
  fail "the target's libosg differs from ~/stage50-osg - the root copy did not run"
fi
ls -la $L
echo "glibc/libstdc++ benoetigt: $(objdump -T $L | grep -o 'GLIBC_[0-9.]*\|GLIBCXX_[0-9.]*' | sort -uV | awk -F_ '{v[$1]=$0} END{for(k in v) printf "%s ", v[k]}')"
echo "== Modelltest"
LIBDIR=$(dirname $L | sed "s#/srv/mer/targets/$T50##")
sb2 -t $T50 g++ -std=c++11 -O1 ~/osg-model-test.cpp -I/opt/osg-gles3/include -L$LIBDIR \
    -losg -losgDB -losgUtil -losgGA -losgText -losgViewer -lOpenThreads -o ~/osg-model-test-sfos50 >> $LOG 2>&1 || fail "model test"
echo "Modelltest benoetigt: $(objdump -T ~/osg-model-test-sfos50 | grep -o 'GLIBC_[0-9.]*\|GLIBCXX_[0-9.]*' | sort -uV | awk -F_ '{v[$1]=$0} END{for(k in v) printf "%s ", v[k]}')"
(cd /srv/mer/targets/$T50/opt && tar czf ~/osg-gles3-sfos50.tar.gz osg-gles3)
ls -la ~/osg-gles3-sfos50.tar.gz ~/osg-model-test-sfos50
echo OSG50-TEST-FERTIG
