#!/usr/bin/env python3
"""Traegt den 0.3.0-Eintrag oben im Changelog ein und setzt die Version."""

import re, sys

P = '/home/mersdk/harbour-fgview/rpm/harbour-fgview.spec'

ENTRY = '''%changelog
* Mon Aug 24 2026 Sebastian Matkovich <smatkovi@users.noreply.github.com> - 0.3.0-1
- Engine start button. FlightGear's generic protocol can only set the
  control axes, so fuel selectors, battery, magnetos and primer are set
  over the telnet channel (port 5401), which fgfs now opens
- Brake button also releases the wheel brakes, not just the parking
  brake — they are separate properties and the aircraft would not roll
  with the wheel brakes still applied
- Throttle now writes to current-engine instead of engine[0]; the c172p
  reads the former, so the lever had no effect on engine power
- Cockpit controls translated to English

'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if '0.3.0-1' in s:
        print("Eintrag bereits vorhanden")
        return 0

    s = re.sub(r'^Version:\s+\S+$', 'Version:    0.3.0', s, count=1, flags=re.M)
    s = s.replace('%changelog\n', ENTRY, 1)
    open(P, 'w').write(s)
    print("Changelog 0.3.0 eingetragen, Version gesetzt")
    return 0


if __name__ == '__main__':
    sys.exit(main())
