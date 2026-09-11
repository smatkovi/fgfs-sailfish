#!/bin/bash
# Fetch and install the Sailfish OS 5.0.0.62 SDK tooling and aarch64 target
# (glibc 2.30, GCC 10 - what the F(x)tec Pro1x runs) next to the 5.2 ones.
set -e
V=5.0.0.62
BASE=https://releases.sailfishos.org/sdk/targets
# not "sfos50": that is where these scripts and the 5.0 spec live
D=~/Downloads/sdk50-dl
mkdir -p $D && cd $D
for f in Sailfish_OS-$V-Sailfish_SDK_Tooling-i486.tar.7z Sailfish_OS-$V-Sailfish_SDK_Target-aarch64.tar.7z; do
  if [ ! -f "$f" ] || ! md5sum -c "$f.md5sum" >/dev/null 2>&1; then
    curl -sf -o "$f.md5sum" "$BASE/$f.md5sum"
    curl -sfL -C - -o "$f" "$BASE/$f"
  fi
  md5sum -c "$f.md5sum"
done
df -h / | tail -1
docker cp $D ba82fa4d3804:/home/mersdk/sdk50-dl
docker exec -u root ba82fa4d3804 chown -R mersdk /home/mersdk/sdk50-dl
docker exec ba82fa4d3804 bash -lc "
  sdk-assistant tooling list | grep -q SailfishOS-$V || sdk-assistant -y tooling create SailfishOS-$V ~/sdk50-dl/Sailfish_OS-$V-Sailfish_SDK_Tooling-i486.tar.7z
  sdk-assistant target list | grep -q SailfishOS-$V-aarch64 || sdk-assistant -y target create --tooling SailfishOS-$V SailfishOS-$V-aarch64 ~/sdk50-dl/Sailfish_OS-$V-Sailfish_SDK_Target-aarch64.tar.7z
  sdk-assistant list
  sb2 -t SailfishOS-$V-aarch64 -m sdk-install -R rpm -q glibc libstdc++ gcc qt5-qtcore boost-devel 2>&1 | tail -5
"
# the archives are in the container now; the host copy is not needed
rm -rf $D
docker exec ba82fa4d3804 rm -rf /home/mersdk/sdk50-dl
df -h / | tail -1
echo SDK50-FERTIG
