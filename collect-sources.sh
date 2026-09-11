#!/bin/bash
# collect-sources.sh - gather the OSG and SimGear files changed for the GLES
# port into a tarball, in the flat layout this repository uses (osg/<basename>,
# simgear/<basename>).  Run in the SDK container:
#
#   bash collect-sources.sh            # -> ~/fgfs-changed-sources.tar.gz
#
# Copy the result to the host and unpack it over the working copy:
#
#   docker cp <container>:/home/mersdk/fgfs-changed-sources.tar.gz ~/Downloads/
#   tar xzf ~/Downloads/fgfs-changed-sources.tar.gz -C ~/fgfs-sailfish
#
# The point is that the published sources match the binaries in the RPMs, so
# the diagnostic probes that are compiled into them are part of this.
set -e

OSG=${OSG:-$HOME/OpenSceneGraph-OpenSceneGraph-3.6.5}
SG=${SG:-$HOME/simgear-2020.3.19}
OUT=$HOME/fgfs-changed-sources
STAMP=$HOME/fgfs-changed-sources.tar.gz

osg_files="
include/osg/State
include/osg/Program
src/osg/State.cpp
src/osg/Shader.cpp
src/osg/Program.cpp
src/osg/Light.cpp
src/osg/Material.cpp
src/osg/LightModel.cpp
src/osg/Fog.cpp
src/osg/TexMat.cpp
src/osg/Texture2D.cpp
src/osg/GLExtensions.cpp
src/osg/Geometry.cpp
src/osg/VertexArrayState.cpp
src/osg/VertexAttribDivisor.cpp
src/osgViewer/GraphicsWindowEGL.cpp
src/osg/Hint.cpp
src/osg/Texture1D.cpp
src/osgViewer/Renderer.cpp
src/osgPlugins/ac/ac3d.cpp
src/osg/FrameBufferObject.cpp
"

sg_files="
simgear/io/lowlevel.cxx
simgear/misc/strutils.cxx
simgear/scene/tgdb/SGReaderWriterBTG.cxx
simgear/screen/gles_compat.h
simgear/scene/material/Effect.cxx
simgear/scene/material/Technique.cxx
simgear/scene/model/model.cxx
simgear/canvas/elements/CanvasPath.cxx
simgear/canvas/ShivaVG/src/shDefs.h
simgear/canvas/ShivaVG/src/shExtensions.c
simgear/canvas/ShivaVG/src/shGLES.h
simgear/canvas/ShivaVG/src/shGLES.c
simgear/canvas/CMakeLists.txt:canvas-CMakeLists.txt
"

rm -rf "$OUT"
mkdir -p "$OUT/osg" "$OUT/simgear"

missing=0
for f in $osg_files; do
    if [ -f "$OSG/$f" ]; then
        cp "$OSG/$f" "$OUT/osg/$(basename "$f")"
        echo "  osg/$(basename "$f")"
    else
        echo "  FEHLT: $OSG/$f" >&2
        missing=1
    fi
done
for entry in $sg_files; do
    # "path:name" stores the file under name (canvas/CMakeLists.txt would
    # otherwise collide with any other CMakeLists.txt)
    f=${entry%%:*}; name=${entry#*:}; [ "$name" = "$entry" ] && name=$(basename "$f")
    if [ -f "$SG/$f" ]; then
        cp "$SG/$f" "$OUT/simgear/$name"
        echo "  simgear/$name"
    else
        echo "  FEHLT: $SG/$f" >&2
        missing=1
    fi
done

[ $missing -eq 0 ] || { echo "Es fehlen Dateien - Pfade ueber OSG= und SG= setzen" >&2; exit 1; }

tar czf "$STAMP" -C "$OUT" osg simgear
rm -rf "$OUT"
echo
ls -lh "$STAMP"
echo "Enthalten:"
tar tzf "$STAMP" | sed 's/^/  /'
