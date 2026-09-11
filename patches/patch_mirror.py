#!/usr/bin/env python3
"""
Baut in FgRuntime eine Aufloesung der SourceForge-Weiterleitung ein.

Hintergrund: SourceForge beantwortet Anfragen von aria2 auf die
/download-Seite mit 403, unabhaengig von User-Agent und Anzahl der
Verbindungen. curl kommt durch. Deshalb holen wir die endgueltige
Mirror-Adresse mit QNetworkAccessManager (folgt Weiterleitungen) und
uebergeben erst diese an aria2 - gegen den Mirror ist Segmentierung
erlaubt.
"""

import sys

P = '/home/mersdk/harbour-fgview/src/fgruntime.h'

INC_OLD = '''#include <QProcessEnvironment>'''
INC_NEW = '''#include <QProcessEnvironment>
#include <QNetworkAccessManager>
#include <QNetworkRequest>
#include <QNetworkReply>
#include <QUrl>'''

# downloadData() aufteilen: erst aufloesen, dann laden
DL_OLD = '''    void downloadData()
    {
        if (busy()) return;

        const QString archive = _root + "/fgdata.txz";

        _status = tr("Downloading base data (about 1.7 GB)…");
        _progress = 0;
        emit progressChanged();
        emit stateChanged();

        const QString url =
            "https://sourceforge.net/projects/flightgear/files/"
            "release-2020.3/FlightGear-2020.3.19-data.txz/download";
'''

DL_NEW = '''    void downloadData()
    {
        if (busy() || _resolving) return;

        _status = tr("Looking up mirror…");
        _progress = 0;
        emit progressChanged();
        emit stateChanged();

        const QUrl start(
            "https://sourceforge.net/projects/flightgear/files/"
            "release-2020.3/FlightGear-2020.3.19-data.txz/download");

        QNetworkRequest req(start);
        req.setAttribute(QNetworkRequest::FollowRedirectsAttribute, true);
        req.setRawHeader("User-Agent", "Mozilla/5.0");
        req.setMaximumRedirectsAllowed(10);

        _resolving = true;
        QNetworkReply* rep = _nam.head(req);
        connect(rep, &QNetworkReply::finished, this, [this, rep, start]() {
            _resolving = false;
            QUrl final = rep->url();
            const QVariant redir = rep->attribute(
                QNetworkRequest::RedirectionTargetAttribute);
            if (redir.isValid()) {
                const QUrl r = redir.toUrl();
                if (!r.isEmpty()) final = start.resolved(r);
            }
            rep->deleteLater();

            if (rep->error() != QNetworkReply::NoError && final == start) {
                _status = tr("Could not reach the download server (%1)")
                          .arg(rep->errorString());
                emit progressChanged();
                emit stateChanged();
                return;
            }
            startAria(final.toString());
        });
    }

    void startAria(const QString& url)
    {
        _status = tr("Downloading base data (about 1.7 GB)…");
        emit progressChanged();
        emit stateChanged();
'''

# den alten aria2-Start auf die uebergebene URL umstellen
ARIA_OLD = '''                  << "-d" << _root
                  << "-o" << "fgdata.txz"
                  << url);
    }'''

ARIA_NEW = '''                  << "-d" << _root
                  << "-o" << "fgdata.txz"
                  << url);
        if (!_dl.waitForStarted(3000)) {
            _status = tr("aria2c could not be started. "
                         "Is the aria2 package installed?");
            emit progressChanged();
            emit stateChanged();
        }
    }'''

MEM_OLD = '''    QString _root;
    QProcess _dl, _tar, _sim;'''
MEM_NEW = '''    QString _root;
    QProcess _dl, _tar, _sim;
    QNetworkAccessManager _nam;
    bool _resolving = false;'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if '_resolving' in s:
        print("bereits gepatcht")
        return 0

    for old, new, label in ((INC_OLD, INC_NEW, "Includes"),
                            (DL_OLD, DL_NEW, "downloadData/startAria"),
                            (ARIA_OLD, ARIA_NEW, "Startpruefung"),
                            (MEM_OLD, MEM_NEW, "Member")):
        if old not in s:
            print("FEHLER: Muster nicht gefunden:", label)
            return 1
        s = s.replace(old, new, 1)
        print("gepatcht:", label)

    open(P, 'w').write(s)
    print("fertig - danach: QT += network ist in der .pro bereits gesetzt")
    return 0


if __name__ == '__main__':
    sys.exit(main())
