#!/usr/bin/env python3
"""
Macht die Startmeldungen des Simulators sichtbar.

- fgfs' Ausgabe wird abgefangen statt ans Terminal weitergereicht
- die letzten Zeilen stehen als Property simLog fuer QML bereit
- interessante Zeilen (Terrain, JSBSim, Nasal, FATAL) landen zusaetzlich
  in der Statuszeile
- alles wird nach ~/.local/share/harbour-fgview/fgfs.log geschrieben
"""

import sys

P = '/home/mersdk/harbour-fgview/src/fgruntime.h'

PROP_OLD = '''    Q_PROPERTY(QString speed       READ speed       NOTIFY progressChanged)'''
PROP_NEW = '''    Q_PROPERTY(QString speed       READ speed       NOTIFY progressChanged)
    Q_PROPERTY(QString simLog      READ simLog      NOTIFY simLogChanged)'''

GET_OLD = '''    QString speed() const { return _speed; }'''
GET_NEW = '''    QString speed() const { return _speed; }
    QString simLog() const { return _simLog; }'''

# Ausgabe abfangen statt weiterreichen
FWD_OLD = '''        _sim.setProcessChannelMode(QProcess::ForwardedChannels);'''
FWD_NEW = '''        _sim.setProcessChannelMode(QProcess::MergedChannels);
        _simLog.clear();
        emit simLogChanged();'''

# Verbindung im Konstruktor
CONN_OLD = '''        _extractTick.setInterval(2000);'''
CONN_NEW = '''        connect(&_sim, &QProcess::readyReadStandardOutput,
                this, &FgRuntime::onSimOutput);

        _extractTick.setInterval(2000);'''

# Auswertung
SLOT_OLD = '''    void onDownloadOutput()'''
SLOT_NEW = '''    void onSimOutput()
    {
        const QString chunk = QString::fromUtf8(_sim.readAllStandardOutput());
        if (chunk.isEmpty()) return;

        /* alles mitschreiben, damit man nach einem Absturz nachsehen kann */
        if (!_logFile.isOpen()) {
            _logFile.setFileName(_root + "/fgfs.log");
            _logFile.open(QIODevice::WriteOnly | QIODevice::Truncate);
        }
        if (_logFile.isOpen()) {
            _logFile.write(chunk.toUtf8());
            _logFile.flush();
        }

        /* die letzten Zeilen fuer die Anzeige vorhalten */
        _simLog += chunk;
        const int maxChars = 4000;
        if (_simLog.size() > maxChars)
            _simLog = _simLog.right(maxChars);
        emit simLogChanged();

        /* aussagekraeftige Zeilen in die Statuszeile heben */
        const QStringList lines = chunk.split('\\n', QString::SkipEmptyParts);
        for (const QString& raw : lines) {
            const QString l = raw.trimmed();
            if (l.contains("FATAL") || l.contains("unable to create")) {
                _status = l;
                emit progressChanged();
            } else if (l.contains("Loading tile")
                       || l.contains("Scenery loaded")
                       || l.contains("initializing JSBsim")
                       || l.contains("Trim complete")
                       || l.contains("Splash screen")
                       || l.contains("Welcome aboard")) {
                _status = l.section(']', 1).trimmed();
                if (_status.isEmpty()) _status = l;
                emit progressChanged();
            }
        }
    }

    void onDownloadOutput()'''

MEM_OLD = '''    QTimer _heartbeat;
    QTimer _extractTick;'''
MEM_NEW = '''    QTimer _heartbeat;
    QTimer _extractTick;
    QString _simLog;
    QFile _logFile;'''

SIG_OLD = '''signals:
    void stateChanged();
    void progressChanged();'''
SIG_NEW = '''signals:
    void stateChanged();
    void progressChanged();
    void simLogChanged();'''

INC_OLD = '''#include <QDirIterator>'''
INC_NEW = '''#include <QDirIterator>
#include <QFile>'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if 'simLogChanged' in s:
        print("bereits gepatcht")
        return 0

    steps = (
        (INC_OLD,  INC_NEW,  "Include QFile"),
        (PROP_OLD, PROP_NEW, "Property simLog"),
        (GET_OLD,  GET_NEW,  "Getter"),
        (FWD_OLD,  FWD_NEW,  "Ausgabe abfangen"),
        (CONN_OLD, CONN_NEW, "Signalverbindung"),
        (SLOT_OLD, SLOT_NEW, "onSimOutput"),
        (MEM_OLD,  MEM_NEW,  "Member"),
        (SIG_OLD,  SIG_NEW,  "Signal"),
    )

    for old, new, label in steps:
        if old not in s:
            print("FEHLER: Muster nicht gefunden:", label)
            return 1
        s = s.replace(old, new, 1)
        print("gepatcht:", label)

    open(P, 'w').write(s)
    print("fertig")
    return 0


if __name__ == '__main__':
    sys.exit(main())
