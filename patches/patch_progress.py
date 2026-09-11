#!/usr/bin/env python3
"""
Drei Ergaenzungen in FgRuntime:

1. Ist das Archiv bereits vollstaendig (Groesse stimmt, keine
   .aria2-Steuerdatei), wird der Download uebersprungen und direkt
   entpackt.
2. Waehrend des Entpackens laeuft eine Fortschrittsanzeige, gespeist
   aus der wachsenden Verzeichnisgroesse.
3. Aus aria2s Ausgabe wird zusaetzlich die Restzeit uebernommen.
"""

import sys

P = '/home/mersdk/harbour-fgview/src/fgruntime.h'

INC_OLD = '#include <QTimer>'
INC_NEW = '#include <QTimer>\n#include <QDirIterator>'

# --- 1. vollstaendiges Archiv erkennen ------------------------------
SKIP_OLD = '''        if (busy() || _resolving) return;

        _status = tr("Looking up mirror…");'''

SKIP_NEW = '''        if (busy() || _resolving) return;

        /* Archiv schon vollstaendig? Dann direkt entpacken. */
        const QString archive = _root + "/fgdata.txz";
        if (QFileInfo(archive).size() == ARCHIVE_BYTES
            && !QFileInfo::exists(archive + ".aria2")) {
            _progress = 100;
            _speed.clear();
            emit progressChanged();
            extractArchive();
            return;
        }

        _status = tr("Looking up mirror…");'''

# --- Entpacken in eigene Methode ------------------------------------
EXTRACT_OLD = '''        _status = tr("Extracting base data…");
        _progress = 100;
        _speed.clear();
        emit progressChanged();

        QDir().mkpath(fgRoot());
        /* Das Archiv enthaelt ein Verzeichnis "fgdata" - eine Ebene
           abschneiden, damit es direkt in fgRoot landet. */
        _tar.start("tar", QStringList()
                   << "xf" << _root + "/fgdata.txz"
                   << "-C" << fgRoot()
                   << "--strip-components=1");
    }'''

EXTRACT_NEW = '''        extractArchive();
    }

    void extractArchive()
    {
        _status = tr("Extracting base data…");
        _progress = 0;
        _speed.clear();
        emit progressChanged();
        emit stateChanged();

        QDir().mkpath(fgRoot());
        /* Das Archiv enthaelt ein Verzeichnis "fgdata" - eine Ebene
           abschneiden, damit es direkt in fgRoot landet. */
        _tar.start("tar", QStringList()
                   << "xf" << _root + "/fgdata.txz"
                   << "-C" << fgRoot()
                   << "--strip-components=1");
        _tar.waitForStarted(3000);
        _extractTick.start();
        emit stateChanged();
    }

    /* Fortschritt beim Entpacken aus der wachsenden Verzeichnisgroesse.
       Vollstaendig entpackt sind es rund 2,7 GB. */
    void updateExtractProgress()
    {
        if (_tar.state() == QProcess::NotRunning) {
            _extractTick.stop();
            return;
        }
        quint64 bytes = 0;
        QDirIterator it(fgRoot(), QDir::Files | QDir::NoDotAndDotDot,
                        QDirIterator::Subdirectories);
        int guard = 0;
        while (it.hasNext() && ++guard < 40000) {
            it.next();
            bytes += quint64(it.fileInfo().size());
        }
        _progress = int(qMin<quint64>(99, bytes * 100 / EXTRACTED_BYTES));
        _speed = QString("%1 / %2 GB")
                 .arg(bytes / 1.0e9, 0, 'f', 1)
                 .arg(EXTRACTED_BYTES / 1.0e9, 0, 'f', 1);
        emit progressChanged();
    }'''

# --- 3. ETA mitlesen ------------------------------------------------
ETA_OLD = '''        auto d = reDl.match(out);
        if (d.hasMatch()) {
            _speed = d.captured(1) + "/s";
        }
        if (m.hasMatch() || d.hasMatch()) emit progressChanged();'''

ETA_NEW = '''        static const QRegularExpression reEta("ETA:([0-9dhms]+)");

        auto d = reDl.match(out);
        auto e = reEta.match(out);
        if (d.hasMatch()) {
            _speed = d.captured(1) + "/s";
            if (e.hasMatch())
                _speed += "  ETA " + e.captured(1);
        }
        if (m.hasMatch() || d.hasMatch()) emit progressChanged();'''

# --- Konstanten und Timer -------------------------------------------
MEM_OLD = '''    QProcess _dl, _tar, _sim, _resolve;
    QTimer _heartbeat;'''

MEM_NEW = '''    static const qint64  ARCHIVE_BYTES   = 1789370768LL;
    static const quint64 EXTRACTED_BYTES = 2705459200ULL;

    QProcess _dl, _tar, _sim, _resolve;
    QTimer _heartbeat;
    QTimer _extractTick;'''

TIMER_OLD = '''        _heartbeat.setInterval(1000);'''

TIMER_NEW = '''        _extractTick.setInterval(2000);
        connect(&_extractTick, &QTimer::timeout,
                this, &FgRuntime::updateExtractProgress);

        _heartbeat.setInterval(1000);'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if 'ARCHIVE_BYTES' in s:
        print("bereits gepatcht")
        return 0

    steps = (
        (INC_OLD,     INC_NEW,     "Include QDirIterator"),
        (MEM_OLD,     MEM_NEW,     "Konstanten und Timer"),
        (TIMER_OLD,   TIMER_NEW,   "Timer-Verbindung"),
        (SKIP_OLD,    SKIP_NEW,    "vollstaendiges Archiv erkennen"),
        (EXTRACT_OLD, EXTRACT_NEW, "Entpacken mit Fortschritt"),
        (ETA_OLD,     ETA_NEW,     "ETA auswerten"),
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
