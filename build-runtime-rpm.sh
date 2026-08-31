#!/bin/bash
# build-runtime-rpm.sh
#
# Packs the installed runtime trees into RPMs, using the spec files from this
# repository - no second copy of the spec inside this script.  Run in the SDK
# container, from the checkout:
#
#   bash build-runtime-rpm.sh            # both packages
#   bash build-runtime-rpm.sh zink       # only the Mesa/Zink one
#   bash build-runtime-rpm.sh gles       # only the native GLES one
#
# Result: ~/rpmbuild-<name>/RPMS/<name>-<version>-<release>.aarch64.rpm

set -e

TARGET=${TARGET:-SailfishOS-5.2.0.15-aarch64}
REPO=$(cd "$(dirname "$0")" && pwd)
WHICH=${1:-all}

specversion() { sed -n 's/^Version:[[:space:]]*//p' "$1" | head -1; }
specrelease() { sed -n 's/^Release:[[:space:]]*//p' "$1" | head -1; }

# $1 package name, $2 spec file, $3.. the /opt trees to pack
build_one() {
    local name=$1 spec=$2; shift 2
    local version release work
    version=$(specversion "$spec")
    release=$(specrelease "$spec")
    # NOT $HOME/$name: a checkout of this repository is usually called
    # fgfs-sailfish, and the rm -rf below would delete it.
    work=${BUILDROOT:-$HOME/rpmbuild-$name}
    if [ "$(readlink -f "$work")" = "$(readlink -f "$REPO")" ]; then
        echo "Bauverzeichnis $work ist das Repository - abgebrochen" >&2
        exit 1
    fi

    echo
    echo "=================================================================="
    echo "== $name $version-$release"
    echo "=================================================================="

    for tree in "$@"; do
        if ! sb2 -t $TARGET -m sdk-install -R test -d "/$tree"; then
            echo "== $tree fehlt im Target - $name wird uebersprungen"
            return 0
        fi
    done

    rm -rf "$work"
    mkdir -p "$work"/{rpm,SOURCES,RPMS}

    echo "== Laufzeit aus dem Target packen (ohne FGData)"
    sb2 -t $TARGET -m sdk-install -R tar czf "$work/SOURCES/$name-$version.tar.gz" \
        -C / \
        --exclude='opt/fgfs/lib/FlightGear' \
        --exclude='opt/*/include' \
        --exclude='*.a' \
        "$@"
    ls -lh "$work/SOURCES/$name-$version.tar.gz"

    echo "== Starter und Szenerie-Werkzeug in die Quellen legen"
    # mb2 looks for Source1/Source2 next to the spec, in rpm/, not in SOURCES/
    install -m 0755 "$REPO/bin/fgfs-run" "$REPO/bin/fgfs-scenery" "$work/SOURCES/"
    install -m 0755 "$REPO/bin/fgfs-run" "$REPO/bin/fgfs-scenery" "$work/rpm/"

    echo "== Spec aus dem Repository uebernehmen"
    cp "$spec" "$work/rpm/$name.spec"

    echo "== RPM bauen"
    cd "$work"
    tar xzf "SOURCES/$name-$version.tar.gz" -C . 2>/dev/null || true
    # mb2 runs a test-suite and prune step after the build; both fail here
    # (no test suites, no source package) long after the RPM is written, so
    # the exit status is not a verdict on the build.  Judge by the artefact.
    mb2 -t $TARGET build || true
    if ! ls "$work"/RPMS/*.rpm >/dev/null 2>&1; then
        echo
        echo "Kein RPM entstanden. Haeufigste Ursachen:"
        echo "  - Quelltarball muss unter SOURCES/ liegen"
        echo "  - Source1/Source2 muessen neben der Spec in rpm/ liegen"
        echo "  - AutoReqProv: no noetig, weil die Bibliotheken aus /opt kommen"
        exit 1
    fi
    ls -lh "$work"/RPMS/*.rpm
}

case "$WHICH" in
    zink|all)
        build_one fgfs-sailfish "$REPO/fgfs-sailfish.spec" opt/fgfs opt/mesa-zink
        ;;&
    gles|all)
        build_one fgfs-sailfish-gles "$REPO/fgfs-sailfish-gles.spec" \
                  opt/osg-gles opt/osg-gles3 opt/fgfs-gles opt/fgfs-gles3
        ;;&
    zink|gles|all) ;;
    *)
        echo "Aufruf: $0 [zink|gles|all]" >&2
        exit 2
        ;;
esac

echo
echo "== fertig"
ls -lh "$HOME"/rpmbuild-fgfs-sailfish*/RPMS/*.rpm 2>/dev/null || true
