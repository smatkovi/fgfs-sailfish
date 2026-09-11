#!/usr/bin/env python3
"""
Ersetzt den deutschen Changelog durch eine englische Fassung
und setzt die Version auf 0.2.1.
"""

import re, sys

P = '/home/mersdk/harbour-fgview/rpm/harbour-fgview.spec'

CHANGELOG = '''%changelog
* Mon Aug 24 2026 Sebastian Matkovich <smatkovi@users.noreply.github.com> - 0.2.1-1
- Simulator output is captured and shown on a log page in the app
- Notable lines (scenery loading, JSBSim init, trim) surface in the
  status line, so the two-minute startup is no longer a blank wait
- Full output written to ~/.local/share/harbour-fgview/fgfs.log
- Child processes terminated on aboutToQuit instead of in the
  destructor, where Qt had already torn down the QProcess objects
  and left orphaned fgfs instances behind

* Mon Aug 24 2026 Sebastian Matkovich <smatkovi@users.noreply.github.com> - 0.2.0-1
- A fully downloaded archive is detected and extraction starts
  immediately instead of downloading again
- Progress bar during extraction, derived from the growing directory
- Remaining time (ETA) taken from aria2 output
- Progress read from stderr, not just stdout
- One-second tick keeps the display alive while downloading
- aria2 and fgfs shut down when the app closes
- Sandboxing=Disabled in the .desktop file; without it the app does
  not launch from the application grid
- Requires on fgfs-sailfish, curl and aria2
- Interface in English, strings wrapped in qsTr() for translations

* Mon Aug 24 2026 Sebastian Matkovich <smatkovi@users.noreply.github.com> - 0.1.1-1
- Mirror resolution via curl instead of QNetworkAccessManager: Qt 5.6
  on Sailfish OS is built against OpenSSL 1.0 and fails silently on
  HTTPS with 1.1/3.x on the system
- SourceForge answers aria2 requests to the /download redirect with
  403; segmentation works against the resolved mirror address
- Fixed a self-assignment of the FgRuntime property that left every
  binding on the start page evaluating to null

* Mon Aug 24 2026 Sebastian Matkovich <smatkovi@users.noreply.github.com> - 0.1.0-1
- First release
- Displays frames delivered by FlightGear through shared memory
- Tilt steering for ailerons and elevator, calibrated to the current
  device position
- Throttle lever, self-centering rudder, gear, flaps, brake
- Controls sent over UDP to FlightGear's generic protocol
- FGData downloaded on first start using aria2
'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    s = re.sub(r'^Version:\s+\S+$', 'Version:    0.2.1', s, count=1, flags=re.M)

    idx = s.find('%changelog')
    if idx < 0:
        print("FEHLER: kein %changelog gefunden")
        return 1
    s = s[:idx] + CHANGELOG

    open(P, 'w').write(s)
    print("Changelog auf Englisch, Version 0.2.1")
    return 0


if __name__ == '__main__':
    sys.exit(main())
