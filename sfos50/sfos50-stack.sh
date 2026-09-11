#!/bin/bash
# Pro1x (SFOS 5.0): plib, SimGear GLES3, FlightGear GLES3 against the 5.0
# target.  Runs as mersdk in the SDK container; the parts that write into
# the target rootfs go through sfos50-root-copy.sh (as root, called by the
# host driver between the stages).  STAGE= selects plib|simgear|flightgear.
set -u
T50=SailfishOS-5.0.0.62-aarch64
TOOL50=/srv/mer/toolings/SailfishOS-5.0.0.62
J=$(nproc)
STAGE_NAME=$1
LOG=~/sfos50-$STAGE_NAME.log
fail() { echo "FEHLER: $*"; tail -30 "$LOG"; echo STACK50-FEHLER-$STAGE_NAME; exit 1; }
: > $LOG
mkcache() {
  grep -E '^[A-Za-z_][A-Za-z0-9_]*:(BOOL|STRING|PATH|FILEPATH)=' "$1" \
  | grep -v -E '^CMAKE_(C|CXX|ASM|LINKER|AR|RANLIB|NM|OBJCOPY|OBJDUMP|READELF|STRIP|ADDR2LINE|DLLTOOL|MT|RC|MAKE_PROGRAM|COMMAND|GENERATOR)' \
  | grep -v -E '_(LIBRARY|LIBRARIES|INCLUDE_DIR|INCLUDE_DIRS|EXECUTABLE|DIR|LIBRARY_RELEASE|LIBRARY_DEBUG)(_[A-Z]+)?:' \
  | grep -v '5\.2\.0\.15' \
  | sed -E 's/^([^:]+):([A-Z]+)=(.*)$/set(\1 "\3" CACHE \2 "" FORCE)/'
  grep -E '^(OPENGL|EGL)[A-Za-z0-9_]*:(PATH|FILEPATH|STRING)=' "$1" | grep -v 'NOTFOUND' \
  | sed -E 's/^([^:]+):([A-Z]+)=(.*)$/set(\1 "\3" CACHE \2 "" FORCE)/'
}
launcher() {
  cat <<EOC
set(CMAKE_C_COMPILER_LAUNCHER "$TOOL50/usr/bin/ccache" CACHE STRING "" FORCE)
set(CMAKE_CXX_COMPILER_LAUNCHER "$TOOL50/usr/bin/ccache" CACHE STRING "" FORCE)
set(CMAKE_PREFIX_PATH "/opt/osg-gles3;/opt/fgfs" CACHE STRING "" FORCE)
EOC
}
SG_DEFS="-DSG_GLES2 -DGL_FOG=0x0B60 -DGL_STENCIL=0x1802 -DGL_EXP=0x0800 -DGL_EXP2=0x0801 -DGL_ALPHA_TEST=0x0BC0 -DGL_LIGHTING=0x0B50 -DGL_FOG_MODE=0x0B65 -DGL_FOG_DENSITY=0x0B62 -DGL_FOG_START=0x0B63 -DGL_FOG_END=0x0B64 -DGL_FOG_COLOR=0x0B66 -DGL_LINEAR=0x2601"
FG_DEFS="-DSG_GLES2 -DGL_FOG=0x0B60 -DGL_STENCIL=0x1802 -DGL_EXP=0x0800 -DGL_EXP2=0x0801 -DGL_ALPHA_TEST=0x0BC0 -DGL_LIGHTING=0x0B50"

cmake_tree() {  # name src cflags cxxflags
  local S=$2 B=$2/build-gles3-sfos50
  [ "${SKIP_CONFIGURE:-0}" = 1 ] || {
    rm -rf $B; mkdir -p $B
    { mkcache $S/build-gles3/CMakeCache.txt; launcher
      echo "set(CMAKE_C_FLAGS \"$3\" CACHE STRING \"\" FORCE)"
      echo "set(CMAKE_CXX_FLAGS \"$4\" CACHE STRING \"\" FORCE)"; } > $B/init.cmake
    echo "== $1 konfigurieren ($(wc -l < $B/init.cmake) Optionen)"
    sb2 -t $T50 cmake -S $S -B $B -G "Unix Makefiles" -C $B/init.cmake >> $LOG 2>&1 || fail "cmake $1"
  }
  echo "== $1 bauen (-j$J)"
  (cd $B && sb2 -t $T50 make -j$J >> $LOG 2>&1) || fail "make $1"
  rm -rf ~/stage50-$1
  (cd $B && sb2 -t $T50 make install DESTDIR=$HOME/stage50-$1 >> $LOG 2>&1) || fail "make install $1"
}

case $STAGE_NAME in
plib)
  # Same configuration as the 5.2 build: desktop GL headers only for
  # declarations (the static libs reference GLES2 functions alone), taken
  # from the 5.2 target's mesa-zink tree.
  rm -rf ~/plib-sfos50 ~/gl-headers50 && cp -a ~/plib ~/plib-sfos50 && mkdir -p ~/gl-headers50 \
    && cp -a /srv/mer/targets/SailfishOS-5.2.0.15-aarch64/opt/mesa-zink/include/GL ~/gl-headers50/ || fail "copy"
  cd ~/plib-sfos50
  sb2 -t $T50 make distclean >> $LOG 2>&1
  echo "== plib konfigurieren"
  # configure insists on linking glNewList from libGL.  The static libs
  # need no GL library at all, so answer the check and let -lGL resolve to
  # GLESv2 for the remaining link tests.
  mkdir -p ~/gl-headers50/lib && ln -sf /usr/lib64/libGLESv2.so ~/gl-headers50/lib/libGL.so
  ac_cv_lib_GL_glNewList=yes \
  sb2 -t $T50 ./configure --prefix=/opt/fgfs "CPPFLAGS=-I$HOME/gl-headers50 -DSG_GLES2" LDFLAGS=-L$HOME/gl-headers50/lib \
      --disable-ssg --disable-ssgaux --disable-pw \
      CC="$TOOL50/usr/bin/ccache gcc" CXX="$TOOL50/usr/bin/ccache g++" >> $LOG 2>&1 || fail "configure plib"
  echo "== plib bauen"
  sb2 -t $T50 make -j$J >> $LOG 2>&1 || fail "make plib"
  rm -rf ~/stage50-plib
  sb2 -t $T50 make install DESTDIR=$HOME/stage50-plib >> $LOG 2>&1 || fail "make install plib"
  ls ~/stage50-plib/opt/fgfs/lib/libplibpu.a >/dev/null || fail "plib stage"
  # SG_GLES2 turns PUI's immediate-mode calls into no-ops (gles_compat.h);
  # without it fgfs does not link.  SSG does not compile that way, and
  # FlightGear uses only ul, sg, fnt, pu and puaux, so SSG and PW stay out.  Same GL references as the 5.2 libraries?
  for l in ul sg fnt pu puaux; do
    a=$(nm -u ~/stage50-plib/opt/fgfs/lib/libplib$l.a | grep -o ' gl[A-Z][A-Za-z0-9]*' | sort -u | tr '\n' ' ')
    b=$(nm -u /srv/mer/targets/SailfishOS-5.2.0.15-aarch64/opt/fgfs/lib/libplib$l.a | grep -o ' gl[A-Z][A-Za-z0-9]*' | sort -u | tr '\n' ' ')
    [ "$a" = "$b" ] || fail "plib $l GL-Referenzen weichen ab: 5.0 [$a] 5.2 [$b]"
  done
  # ul.h includes it under SG_GLES2, and make install does not know it
  install -m 0644 ~/plib-sfos50/src/util/gles_compat.h ~/stage50-plib/opt/fgfs/include/plib/ || fail "gles_compat.h"
  ;;
simgear)   cmake_tree simgear ~/simgear-2020.3.19 "-DSG_GLES2" "$SG_DEFS" ;;
flightgear) cmake_tree flightgear ~/flightgear-2020.3.19 "" "$FG_DEFS"
  F=$HOME/stage50-flightgear/opt/fgfs-gles3/bin/fgfs
  ls -la $F || fail "fgfs missing"
  echo "fgfs benoetigt: $(objdump -T $F | grep -o 'GLIBC_[0-9.]*\|GLIBCXX_[0-9.]*' | sort -uV | awk -F_ '{v[$1]=$0} END{for(k in v) printf "%s ", v[k]}')"
  ;;
esac
echo STACK50-OK-$STAGE_NAME
