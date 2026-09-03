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

# Both core types are ARMv8.2-A with fp16 and dotprod, so this runs on the
# A55 as well as the A78 the scheduler prefers.  Measured gain is small
# (cull 4.4 -> 3.5 ms) but costs nothing.
CPU="-O3 -march=armv8.2-a+fp16+dotprod -mtune=cortex-a78 -fno-plt"
GLES="-DSG_GLES2 -include $SG_SRC/simgear/screen/gles_compat.h"

echo "== OSG (GLES3)"
sb2 -t $TARGET cmake -S "$OSG_SRC" -B "$OSG_SRC/build-gles3" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/osg-gles3 \
  -DOPENGL_PROFILE=GLES3 -DOSG_WINDOWING_SYSTEM=None \
  -DCMAKE_C_FLAGS="$CPU" -DCMAKE_CXX_FLAGS="$CPU" \
  -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=ON

echo "== SimGear (GLES3)"
sb2 -t $TARGET cmake -S "$SG_SRC" -B "$SG_SRC/build-gles3" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/osg-gles3 \
  -DCMAKE_PREFIX_PATH=/opt/osg-gles3 \
  -DCMAKE_C_FLAGS="$CPU $GLES" -DCMAKE_CXX_FLAGS="$CPU $GLES" \
  -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=ON

echo "== FlightGear (GLES3)"
sb2 -t $TARGET cmake -S "$FG_SRC" -B "$FG_SRC/build-gles3" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/fgfs-gles3 \
  -DCMAKE_PREFIX_PATH=/opt/osg-gles3 \
  -DCMAKE_C_FLAGS="$CPU $GLES" -DCMAKE_CXX_FLAGS="$CPU $GLES" \
  -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=ON

echo "== fertig - die uebrigen Optionen (Windowing, Sound, ...) bleiben, wie sie"
echo "   in den vorhandenen build-gles3/CMakeCache.txt stehen; dieses Skript"
echo "   setzt nur die Flags, die sonst verloren gehen."
