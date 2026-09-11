#!/bin/bash
# root part: merge a staged tree into the SFOS 5.0 target rootfs
set -e
T=/srv/mer/targets/SailfishOS-5.0.0.62-aarch64
S=/home/mersdk/stage50-$1
cp -a $S/. $T/
find $S -mindepth 1 -printf '%P\n' | sed "s#^#$T/#" | xargs -d '\n' chown -h root:root
echo ROOTCOPY-OK-$1
