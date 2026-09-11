#!/usr/bin/env python3
"""
Zeitmessung in FrameItem.

Misst getrennt, wie lange die einzelnen Abschnitte dauern, und gibt
alle zwei Sekunden einen Durchschnitt aus. Damit ist klar, wo die
Zeit hingeht, statt es zu vermuten.

  poll     - Header pruefen, aus dem dmabuf ins QImage kopieren
  texture  - createTextureFromImage
  node     - Rest von updatePaintNode
  wait     - Zeit zwischen zwei neuen Frames im Segment
"""

import sys

P = '/home/mersdk/harbour-fgview/src/harbour-fgview.cpp'

INC_OLD = '#include <QTimer>'
INC_NEW = '#include <QTimer>\n#include <QElapsedTimer>'

# --- poll() messen ---------------------------------------------------
POLL_OLD = '''    void poll()
    {
        if (!_base && !openShm()) return;'''
POLL_NEW = '''    void poll()
    {
        if (!_base && !openShm()) return;
        QElapsedTimer t; t.start();'''

POLL_END_OLD = '''        _lastSeq = s1;
        ++_framesSinceTick;
        update();'''
POLL_END_NEW = '''        _lastSeq = s1;
        ++_framesSinceTick;

        _tPoll += t.nsecsElapsed();
        ++_nPoll;
        if (_report.elapsed() > 2000) {
            const double f = 1.0e6;   /* ns -> ms */
            qWarning("FGVIEW timing: poll %.1f ms  tex %.1f ms  node %.1f ms  "
                     "(%d Frames in 2 s)",
                     _nPoll  ? _tPoll  / f / _nPoll  : 0.0,
                     _nTex   ? _tTex   / f / _nTex   : 0.0,
                     _nNode  ? _tNode  / f / _nNode  : 0.0,
                     _nPoll);
            _tPoll = _tTex = _tNode = 0;
            _nPoll = _nTex = _nNode = 0;
            _report.restart();
        }

        update();'''

# --- updatePaintNode messen ------------------------------------------
NODE_OLD = '''        if (_image.isNull()) { delete old; return nullptr; }'''
NODE_NEW = '''        if (_image.isNull()) { delete old; return nullptr; }
        QElapsedTimer tn; tn.start();'''

TEX_OLD = '''            QSGTexture* fresh = window()->createTextureFromImage(
                _image, QQuickWindow::TextureIsOpaque);
            delete _texture;
            _texture = fresh;
            node->setTexture(_texture);
        }'''
TEX_NEW = '''            QElapsedTimer tt; tt.start();
            QSGTexture* fresh = window()->createTextureFromImage(
                _image, QQuickWindow::TextureIsOpaque);
            _tTex += tt.nsecsElapsed();
            ++_nTex;
            delete _texture;
            _texture = fresh;
            node->setTexture(_texture);
        }'''

RET_OLD = '''        node->setRect((sw - dw) / 2.0, (sh - dh) / 2.0, dw, dh);
        return node;'''
RET_NEW = '''        node->setRect((sw - dw) / 2.0, (sh - dh) / 2.0, dw, dh);
        _tNode += tn.nsecsElapsed();
        ++_nNode;
        return node;'''

MEM_OLD = '''    QTimer  _poll, _fpsTimer;'''
MEM_NEW = '''    QTimer  _poll, _fpsTimer;
    qint64  _tPoll = 0, _tTex = 0, _tNode = 0;
    int     _nPoll = 0, _nTex = 0, _nNode = 0;
    QElapsedTimer _report;'''

CTOR_OLD = '''        _fpsTimer.start(1000);'''
CTOR_NEW = '''        _fpsTimer.start(1000);
        _report.start();'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if '_tPoll' in s:
        print("bereits gepatcht")
        return 0

    for old, new, label in (
        (INC_OLD,      INC_NEW,      "QElapsedTimer"),
        (MEM_OLD,      MEM_NEW,      "Zaehler"),
        (CTOR_OLD,     CTOR_NEW,     "Report-Timer"),
        (POLL_OLD,     POLL_NEW,     "poll Start"),
        (POLL_END_OLD, POLL_END_NEW, "poll Ende und Ausgabe"),
        (NODE_OLD,     NODE_NEW,     "node Start"),
        (TEX_OLD,      TEX_NEW,      "Texturzeit"),
        (RET_OLD,      RET_NEW,      "node Ende"),
    ):
        if old not in s:
            print("FEHLER: Muster nicht gefunden:", label)
            return 1
        s = s.replace(old, new, 1)
        print("gepatcht:", label)

    open(P, 'w').write(s)
    print("\nfertig - App neu bauen")
    return 0


if __name__ == '__main__':
    sys.exit(main())
