#!/bin/bash
# configure-gles3.sh - the complete cmake configuration of the three GLES3
# build trees.  Run in the SDK container after the sources are unpacked and
# patched; then build OSG, SimGear, FlightGear in that order.
#
# The -DSG_GLES2 / -include flags select the GLES code paths in SimGear and
# FlightGear (fixed-function calls become no-ops, missing GL constants get
# defined).  They used to live only in the CMake cache, and one cmake call
# that replaced CMAKE_CXX_FLAGS lost them.  Now they are here.
#
# Before building SimGear or FlightGear the desktop OSG headers in
# /opt/fgfs/include/osg must be out of the way (rename to osg.desktop), or
# GL/gl.h is pulled in.  build-gles3.sh does that around each build.
set -e

TARGET=${TARGET:-SailfishOS-5.2.0.15-aarch64}
OSG_SRC=${OSG_SRC:-$HOME/OpenSceneGraph-OpenSceneGraph-3.6.5}
SG_SRC=${SG_SRC:-$HOME/simgear-2020.3.19}
FG_SRC=${FG_SRC:-$HOME/flightgear-2020.3.19}

# No LTO and no CPU flags: measured, they brought nothing (cull 4.4 -> 3.5 ms,
# rest unchanged), and the LTO round cost a day.  The GL constants below are
# what SimGear and FlightGear need under GLES, defined one by one exactly as
# the GLES2 trees have them.  NOT -include gles_compat.h for everything: that
# header is meant for tr.cxx alone, and forcing it into every file changed
# how SimGear builds terrain tiles - the runway came out with constant
# texture coordinates.
CPU=""
SG_DEFS="-DSG_GLES2 -DGL_FOG=0x0B60 -DGL_STENCIL=0x1802 -DGL_EXP=0x0800 -DGL_EXP2=0x0801 -DGL_ALPHA_TEST=0x0BC0 -DGL_LIGHTING=0x0B50 -DGL_FOG_MODE=0x0B65 -DGL_FOG_DENSITY=0x0B62 -DGL_FOG_START=0x0B63 -DGL_FOG_END=0x0B64 -DGL_FOG_COLOR=0x0B66 -DGL_LINEAR=0x2601"
FG_DEFS="-DSG_GLES2 -DGL_FOG=0x0B60 -DGL_STENCIL=0x1802 -DGL_EXP=0x0800 -DGL_EXP2=0x0801 -DGL_ALPHA_TEST=0x0BC0 -DGL_LIGHTING=0x0B50"

echo "== OSG (GLES3)"
sb2 -t $TARGET cmake -S "$OSG_SRC" -B "$OSG_SRC/build-gles3" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/osg-gles3 \
  -DOPENGL_PROFILE=GLES3 -DOSG_WINDOWING_SYSTEM=None \
  -DCMAKE_C_FLAGS="$CPU" -DCMAKE_CXX_FLAGS="$CPU" \
  -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=OFF

echo "== SimGear (GLES3)"
sb2 -t $TARGET cmake -S "$SG_SRC" -B "$SG_SRC/build-gles3" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/osg-gles3 \
  -DCMAKE_PREFIX_PATH=/opt/osg-gles3 \
  -DCMAKE_C_FLAGS="-DSG_GLES2" -DCMAKE_CXX_FLAGS="$SG_DEFS" \
  -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=OFF

echo "== FlightGear (GLES3)"
sb2 -t $TARGET cmake -S "$FG_SRC" -B "$FG_SRC/build-gles3" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/fgfs-gles3 \
  -DCMAKE_PREFIX_PATH=/opt/osg-gles3 \
  -DCMAKE_C_FLAGS="" -DCMAKE_CXX_FLAGS="$FG_DEFS" \
  -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=OFF

echo "== fertig - die uebrigen Optionen (Windowing, Sound, ...) bleiben, wie sie"
echo "   in den vorhandenen build-gles3/CMakeCache.txt stehen; dieses Skript"
echo "   setzt nur die Flags, die sonst verloren gehen."
