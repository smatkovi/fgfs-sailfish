#!/bin/bash
# root part: copy the staged OSG tree into the SFOS 5.0 target rootfs
set -e
T=/srv/mer/targets/SailfishOS-5.0.0.62-aarch64
rm -rf $T/opt/osg-gles3
cp -a /home/mersdk/stage50-osg/opt/osg-gles3 $T/opt/
chown -R root:root $T/opt/osg-gles3
ls -la $T/opt/osg-gles3/lib*/libosg.so.3.6.5
