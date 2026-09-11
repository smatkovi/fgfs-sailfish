#!/bin/sh
# check-qml.sh - load each QML page with qmlscene and report what breaks.
#
#   check-qml.sh <pages-dir> [Page ...]
#
# Why this exists: the app swallows QML errors.  Running harbour-fgview with
# a deliberately broken page prints nothing at all - not on stdout, not in
# the journal - because it is started through the Sailfish booster.  Two
# rounds of "I checked, it loads" therefore proved nothing.
#
# This harness was itself checked against a known-bad file first: with a
# bogus type in a page it prints
#     Type AirportCountryPage unavailable
#     VoelligUnbekannterTyp is not a type
# and without it prints nothing.  A silent pass means something only because
# the noisy fail was demonstrated.
#
# Pages that import harbour.fgview are covered through stub QML types under
# qmlstubs/ - same members, no behaviour.  That checks the page's syntax and
# every binding against a type of the right shape; it does not check that the
# real C++ type behaves as the page expects.

set -u

DIR=${1:?usage: check-qml.sh <pages-dir> [Page ...]}
shift

if [ $# -gt 0 ]; then
    PAGES="$*"
else
    PAGES=$(cd "$DIR" && ls *.qml 2>/dev/null | sed 's/\.qml$//' | grep -v '^ZZHarness$')
fi

# Stub QML versions of the types the application registers in C++
# (FgRuntime, ControlSender, FrameItem).  Without them qmlscene cannot even
# parse the two pages that use them, and those would go unchecked - which is
# exactly where the riskiest edits were.
STUBS=${STUBS:-$HOME/fgfs-work/qmlstubs}

WORK=$(mktemp -d)
cp "$DIR"/*.qml "$WORK"/ 2>/dev/null

status=0
for pg in $PAGES; do
    [ -f "$WORK/$pg.qml" ] || { printf '%-22s %s\n' "$pg" "no such file"; status=1; continue; }


    cat > "$WORK/ZZHarness.qml" <<EOF
import QtQuick 2.6
import Sailfish.Silica 1.0
ApplicationWindow {
    initialPage: Component { $pg { } }
    Component.onCompleted: quitTimer.start()
    Timer { id: quitTimer; interval: 2000; onTriggered: Qt.quit() }
}
EOF

    out=$(QML2_IMPORT_PATH="$STUBS" qmlscene "$WORK/ZZHarness.qml" 2>&1 |
          grep -viE 'MEMPROF|EGL:|EGLDisplay|mali|hybris|namespace|selinux|large_page_conf' |
          grep -iE 'error|unavailable|is not a type|Cannot assign|Duplicate|is not defined|Unable to')

    if [ -z "$out" ]; then
        printf '%-22s %s\n' "$pg" "ok"
    else
        printf '%-22s %s\n' "$pg" "PROBLEMS:"
        echo "$out" | sed 's/^/    /'
        status=1
    fi
done

rm -rf "$WORK"
exit $status
