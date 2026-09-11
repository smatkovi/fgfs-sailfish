#!/bin/bash
# Pro1x (SFOS 5.0, glibc 2.30, GCC 10): OSG GLES3 against the 5.0 target plus
# the standalone model test - does the renderer draw on the Adreno 610?
# GNU Make, because the 5.0 tooling has no ninja.  Stops at the first error.
set -u
T50=SailfishOS-5.0.0.62-aarch64
TOOL50=/srv/mer/toolings/SailfishOS-5.0.0.62
J=$(nproc)
LOG=~/sfos50-osg-build.log
fail() { echo "FEHLER: $*"; tail -25 "$LOG"; echo OSG50-FEHLER; exit 1; }
cd ~
mkcache() {
  grep -E '^[A-Za-z_][A-Za-z0-9_]*:(BOOL|STRING|PATH|FILEPATH)=' "$1" \
  | grep -v -E '^CMAKE_(C|CXX|ASM|LINKER|AR|RANLIB|NM|OBJCOPY|OBJDUMP|READELF|STRIP|ADDR2LINE|DLLTOOL|MT|RC|MAKE_PROGRAM|COMMAND|GENERATOR)' \
  | grep -v -E '_(LIBRARY|LIBRARIES|INCLUDE_DIR|INCLUDE_DIRS|EXECUTABLE|DIR|LIBRARY_RELEASE|LIBRARY_DEBUG)(_[A-Z]+)?:' \
  | grep -v '5\.2\.0\.15' \
  | sed -E 's/^([^:]+):([A-Z]+)=(.*)$/set(\1 "\3" CACHE \2 "" FORCE)/'
  # The GLES and EGL locations were set by hand in the working build and
  # are target-relative (/usr/include, /usr/lib64), so they hold for 5.0.
  grep -E '^(OPENGL|EGL)[A-Za-z0-9_]*:(PATH|FILEPATH|STRING)=' "$1" | grep -v 'NOTFOUND' \
  | sed -E 's/^([^:]+):([A-Z]+)=(.*)$/set(\1 "\3" CACHE \2 "" FORCE)/'
}
O=~/OpenSceneGraph-OpenSceneGraph-3.6.5
B=$O/build-gles3-sfos50
[ "${SKIP_CONFIGURE:-0}" = 1 ] || { rm -rf $B; mkdir -p $B; }
[ "${SKIP_CONFIGURE:-0}" = 1 ] || mkcache $O/build-gles3/CMakeCache.txt > $B/init.cmake
[ "${SKIP_CONFIGURE:-0}" = 1 ] || cat >> $B/init.cmake <<EOC
set(CMAKE_C_COMPILER_LAUNCHER "$TOOL50/usr/bin/ccache" CACHE STRING "" FORCE)
set(CMAKE_CXX_COMPILER_LAUNCHER "$TOOL50/usr/bin/ccache" CACHE STRING "" FORCE)
EOC
echo "== OSG konfigurieren ($(wc -l < $B/init.cmake) Optionen)"
if [ "${SKIP_CONFIGURE:-0}" != 1 ]; then
  sb2 -t $T50 cmake -S $O -B $B -G "Unix Makefiles" -C $B/init.cmake > $LOG 2>&1 || fail "cmake"
else
  : > $LOG
fi
grep -E 'OPENGL_PROFILE|Configuring done|Generating done' $LOG | tail -3
echo "== OSG bauen (-j$J)"
(cd $B && sb2 -t $T50 make -j$J >> $LOG 2>&1) || fail "make"
echo "== OSG installieren ins 5.0-Ziel"
# sdk-install mode looks for make in the target, which has none: stage it
# in plain sb2 mode and copy the tree into the target rootfs as root.
STAGE=~/stage50-osg; rm -rf $STAGE
(cd $B && sb2 -t $T50 make install DESTDIR=$STAGE >> $LOG 2>&1) || fail "make install"
ls -d $STAGE/opt/osg-gles3 >/dev/null || fail "staging tree missing"
echo "STAGE-BEREIT $STAGE"
[ "${STAGE_ONLY:-0}" = 1 ] && { echo OSG50-STAGED; exit 0; }
L=$(ls /srv/mer/targets/$T50/opt/osg-gles3/lib*/libosg.so.3.6.5 | head -1)
ls -la $L
echo "glibc/libstdc++ benoetigt: $(objdump -T $L | grep -o 'GLIBC_[0-9.]*\|GLIBCXX_[0-9.]*' | sort -uV | awk -F_ '{v[$1]=$0} END{for(k in v) printf "%s ", v[k]}')"
echo "== Modelltest"
LIBDIR=$(dirname $L | sed "s#/srv/mer/targets/$T50##")
sb2 -t $T50 g++ -std=c++11 -O1 ~/osg-model-test.cpp -I/opt/osg-gles3/include -L$LIBDIR \
    -losg -losgDB -losgUtil -losgGA -losgText -losgViewer -lOpenThreads -o ~/osg-model-test-sfos50 >> $LOG 2>&1 || fail "model test"
echo "Modelltest benoetigt: $(objdump -T ~/osg-model-test-sfos50 | grep -o 'GLIBC_[0-9.]*\|GLIBCXX_[0-9.]*' | sort -uV | awk -F_ '{v[$1]=$0} END{for(k in v) printf "%s ", v[k]}')"
(cd /srv/mer/targets/$T50/opt && tar czf ~/osg-gles3-sfos50.tar.gz osg-gles3)
ls -la ~/osg-gles3-sfos50.tar.gz ~/osg-model-test-sfos50
echo OSG50-FERTIG
