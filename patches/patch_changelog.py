#!/usr/bin/env python3
"""
Setzt Version 0.2.0 und traegt einen Changelog in die Spec ein.
Beseitigt zugleich die rpmlint-Meldung "no-changelogname-tag".
"""

import sys

P = '/home/mersdk/harbour-fgview/rpm/harbour-fgview.spec'

CHANGELOG = '''
%changelog
* Mon Aug 24 2026 Sebastian Matkovich <smatkovi@users.noreply.github.com> - 0.2.0-1
- Vollstaendig geladenes Archiv wird erkannt und direkt entpackt
- Fortschrittsanzeige beim Entpacken, gespeist aus der Verzeichnisgroesse
- Restzeit (ETA) aus aria2s Ausgabe uebernommen
- Fortschritt wird aus stderr gelesen, nicht nur aus stdout
- Sekundentakt haelt die Anzeige waehrend des Downloads aktuell
- aria2 und fgfs werden beim Schliessen der App sauber beendet
- Sandboxing=Disabled in der .desktop, sonst startet die App nicht
  ueber das Anwendungsgitter
- Requires auf fgfs-sailfish, curl und aria2
- Oberflaeche auf Englisch, Texte in qsTr() fuer Uebersetzungen

* Mon Aug 24 2026 Sebastian Matkovich <smatkovi@users.noreply.github.com> - 0.1.1-1
- Mirror-Aufloesung ueber curl statt QNetworkAccessManager: Qt 5.6 auf
  Sailfish OS ist gegen OpenSSL 1.0 gebaut und scheitert auf Systemen
  mit 1.1/3.x still an HTTPS
- SourceForge beantwortet aria2-Anfragen auf die /download-Weiterleitung
  mit 403; gegen die aufgeloeste Mirror-Adresse geht Segmentierung
- Selbstzuweisung der FgRuntime-Property behoben, die alle Bindings
  der Startseite ins Leere laufen liess

* Mon Aug 24 2026 Sebastian Matkovich <smatkovi@users.noreply.github.com> - 0.1.0-1
- Erste Fassung
- Zeigt die von FlightGear ueber Shared Memory gelieferten Frames an
- Neigungssteuerung fuer Quer- und Hoehenruder mit Kalibrierung auf
  die aktuelle Lage
- Gashebel, selbstzentrierendes Seitenruder, Fahrwerk, Klappen, Bremse
- Steuerbefehle per UDP an FlightGears generic-Protokoll
- FGData wird beim ersten Start mit aria2 nachgeladen
'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if '%changelog' in s:
        print("Changelog bereits vorhanden - bitte manuell ergaenzen")
        return 1

    s = s.replace('Version:    0.1.0', 'Version:    0.2.0', 1)
    s = s.replace('Release:    2', 'Release:    1', 1)
    s = s.replace('Release:    1', 'Release:    1', 1)
    s = s.rstrip() + '\n' + CHANGELOG

    open(P, 'w').write(s)
    print("Version 0.2.0-1, Changelog eingetragen")
    return 0


if __name__ == '__main__':
    sys.exit(main())
