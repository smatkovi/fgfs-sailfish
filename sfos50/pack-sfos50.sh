#!/bin/bash
# pack-sfos50.sh - the three RPMs for Sailfish OS 5.0 (glibc 2.30), run in
# the SDK container after sfos50-stack.sh has put plib, SimGear and
# FlightGear into the 5.0 target.  Everything is taken from the 5.2 specs
# and sources; only the tree list and the release suffix differ.
set -e
T50=SailfishOS-5.0.0.62-aarch64
REPO=$HOME/fgfs-sailfish
S50=$HOME/sfos50
OUT=$HOME/rpms-sfos50
rm -rf $OUT; mkdir -p $OUT

echo "== fgfs-sailfish (5.0: starter, scenery tool, protocol)"
W=$HOME/rpmbuild50-fgfs-sailfish; rm -rf $W; mkdir -p $W/rpm
# same release number as the 5.2 fgfs-sailfish, with the suffix, so a
# repack after a change there is a newer package here too
R52=$(sed -n 's/^Release:[[:space:]]*//p' $REPO/fgfs-sailfish.spec | head -1)
sed "s/^Release:.*/Release:    $R52.sfos50/" $S50/fgfs-sailfish-sfos50.spec > $W/rpm/fgfs-sailfish.spec
grep -m1 '^Release' $W/rpm/fgfs-sailfish.spec
install -m 0755 $REPO/bin/fgfs-run $REPO/bin/fgfs-scenery $W/rpm/
install -m 0644 $REPO/share/fgtouch.xml $W/rpm/
(cd $W && mb2 -t $T50 build) || true
cp $W/RPMS/*.rpm $OUT/

echo "== fgfs-sailfish-gles (5.0: GLES3 trees only)"
W=$HOME/rpmbuild50-fgfs-sailfish-gles; rm -rf $W; mkdir -p $W/rpm $W/SOURCES
V=$(sed -n 's/^Version:[[:space:]]*//p' $REPO/fgfs-sailfish-gles.spec | head -1)
python3 - $REPO/fgfs-sailfish-gles.spec $W/rpm/fgfs-sailfish-gles.spec <<'PY'
import re, sys
s = open(sys.argv[1]).read()
s = re.sub(r'^(Release:\s*)(\S+)', lambda m: m.group(1) + m.group(2) + '.sfos50', s, count=1, flags=re.M)
for tree in ('osg-gles', 'fgfs-gles'):
    line = 'cp -a opt/%s ' % tree
    s = '\n'.join(l for l in s.split('\n') if not l.startswith(line))
s = s.replace('FlightGear built against OpenSceneGraph in GLES2 and GLES3 profiles.',
              'FlightGear built against OpenSceneGraph in the GLES3 profile, for\nSailfish OS 5.0 (glibc 2.30).')
assert 'cp -a opt/osg-gles3' in s and 'cp -a opt/fgfs-gles3' in s and 'opt/osg-gles ' not in s
open(sys.argv[2], 'w').write(s)
PY
sb2 -t $T50 -m sdk-install -R tar czf $W/SOURCES/fgfs-sailfish-gles-$V.tar.gz -C / \
    --exclude='opt/*/include' --exclude='*.a' --exclude='opt/*/lib*/pkgconfig' \
    opt/osg-gles3 opt/fgfs-gles3
ls -lh $W/SOURCES/*.tar.gz
(cd $W && tar xzf SOURCES/fgfs-sailfish-gles-$V.tar.gz -C . && mb2 -t $T50 build) || true
cp $W/RPMS/*.rpm $OUT/

echo "== harbour-fgview (5.0)"
W=$HOME/fgview-build50; rm -rf $W; mkdir -p $W
(cd $HOME/fgview-build && tar cf - --exclude=RPMS --exclude='*.o' --exclude='moc_*' --exclude=Makefile --exclude=harbour-fgview.moc --exclude=./harbour-fgview --exclude=./.qmake.stash .) | (cd $W && tar xf -)
sed_release() { python3 -c "import re,sys; p=sys.argv[1]; s=open(p).read(); s=re.sub(r'^(Release:\s*)(\S+)', lambda m: m.group(1)+m.group(2).split('.sfos50')[0]+'.sfos50', s, count=1, flags=re.M); open(p,'w').write(s)" "$1"; }
sed_release $W/rpm/harbour-fgview.spec
# on 5.0 the GLES3 trees are the only simulator there is (no Zink), and
# the app starts with that backend
python3 - $W/rpm/harbour-fgview.spec <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
if 'Requires:   fgfs-sailfish-gles' not in s:
    s = s.replace('Requires:   fgfs-sailfish >= 2020.3.19-9\n',
                  'Requires:   fgfs-sailfish >= 2020.3.19-9\nRequires:   fgfs-sailfish-gles\n', 1)
    assert 'Requires:   fgfs-sailfish-gles' in s
    open(p, 'w').write(s)
PY
grep -m1 '^Release' $W/rpm/harbour-fgview.spec
(cd $W && mb2 -t $T50 --no-fix-version build) || true
cp $W/RPMS/harbour-fgview-*.rpm $OUT/

echo "== glibc/libstdc++ versions needed"
cd $OUT
for r in *.rpm; do
  d=$(mktemp -d); (cd $d && rpm2cpio $OUT/$r | cpio -idm --quiet)
  v=$(find $d -type f \( -name '*.so*' -o -perm -u+x \) -exec objdump -T {} \; 2>/dev/null \
      | grep -o 'GLIBC_[0-9.]*\|GLIBCXX_[0-9.]*' | sort -uV | awk -F_ '{v[$1]=$0} END{for(k in v) printf "%s ", v[k]}')
  echo "$r: $v"; rm -rf $d
done
ls -lh $OUT
echo PACK50-FERTIG
