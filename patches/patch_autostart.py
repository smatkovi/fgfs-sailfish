#!/usr/bin/env python3
"""
Autostart-Knopf und korrigierte Bremse fuer harbour-fgview.

- Telnet-Client (Port 5401) in ControlSender
- startEngine() fahert die volle Sequenz ab: Tankwahlhaehne, Batterie,
  Magnete, Gemisch, Primer, Anlasser - und schaltet den Anlasser nach
  sechs Sekunden wieder aus
- Bremse setzt Parkbremse und beide Radbremsen
- Gashebel schreibt auf current-engine statt engine[0]
"""

import sys

CPP  = '/home/mersdk/harbour-fgview/src/harbour-fgview.cpp'
QML  = '/home/mersdk/harbour-fgview/qml/pages/FlightPage.qml'
SPEC = '/home/mersdk/fgfs-sailfish/rpm/fgfs-sailfish.spec'

INC_OLD = '#include <QUdpSocket>'
INC_NEW = '#include <QUdpSocket>\n#include <QTcpSocket>'

PROP_OLD = '    Q_PROPERTY(bool  tiltActive READ tiltActive WRITE setTiltActive NOTIFY changed)'
PROP_NEW = '''    Q_PROPERTY(bool  tiltActive READ tiltActive WRITE setTiltActive NOTIFY changed)
    Q_PROPERTY(bool  cranking   READ cranking   NOTIFY changed)
    Q_PROPERTY(bool  engineOn   READ engineOn   NOTIFY changed)'''

GET_OLD = '    bool  tiltActive() const { return _tiltActive; }'
GET_NEW = '''    bool  tiltActive() const { return _tiltActive; }
    bool  cranking() const { return _cranking; }
    bool  engineOn() const { return _engineOn; }'''

SLOT_OLD = '''    /* Aktuelle Lage als Nullpunkt uebernehmen - so kann man auch
       im Liegen fliegen. */
    void calibrate()'''

SLOT_NEW = '''    /* Vollstaendige Startsequenz ueber FlightGears Telnet-Kanal.
       Das generic-Protokoll kann nur die Achsen setzen; Tankwahl,
       Batterie und Primer brauchen Property-Zugriff. */
    void startEngine()
    {
        if (_cranking) return;

        QStringList cmds;
        cmds << "set /controls/fuel/tank[0]/fuel_selector true"
             << "set /controls/fuel/tank[1]/fuel_selector true"
             << "set /controls/switches/master-bat true"
             << "set /controls/switches/master-alt true"
             << "set /controls/switches/master-avionics true"
             << "set /controls/switches/magnetos 3"
             << "set /controls/engines/current-engine/mixture 1.0"
             << "set /controls/engines/current-engine/throttle 0.25"
             << "set /controls/engines/engine[0]/primer 5"
             << "set /controls/gear/brake-parking 0"
             << "set /controls/switches/starter true";
        sendTelnet(cmds);

        _cranking = true;
        _throttle = 0.25;
        emit changed();

        QTimer::singleShot(6000, this, [this]{
            sendTelnet(QStringList()
                       << "set /controls/switches/starter false");
            _cranking = false;
            _engineOn = true;
            emit changed();
        });
    }

    void stopEngine()
    {
        sendTelnet(QStringList()
                   << "set /controls/engines/current-engine/mixture 0.0"
                   << "set /controls/switches/magnetos 0"
                   << "set /controls/switches/starter false");
        _cranking = false;
        _engineOn = false;
        emit changed();
    }

    /* Aktuelle Lage als Nullpunkt uebernehmen - so kann man auch
       im Liegen fliegen. */
    void calibrate()'''

# Bremse: Parkbremse plus beide Radbremsen
PACKET_OLD = '''                                _gearDown ? 1 : 0);'''
PACKET_NEW = '''                                _gearDown ? 1 : 0);'''

BRAKE_OLD = '    void setBrake(qreal v)    { _brake = clamp01(v);    emit changed(); }'
BRAKE_NEW = '''    void setBrake(qreal v)
    {
        _brake = clamp01(v);
        /* Radbremsen liegen ausserhalb des generic-Protokolls */
        const QString b = QString::number(_brake, 'f', 2);
        sendTelnet(QStringList()
                   << "set /controls/gear/brake-left " + b
                   << "set /controls/gear/brake-right " + b);
        emit changed();
    }'''

HELPER_OLD = '''    static qreal clamp01(qreal v) { return qBound(0.0, v, 1.0); }'''
HELPER_NEW = '''    /* Kurzlebige Verbindung pro Befehlssatz - der Telnet-Kanal von
       FlightGear haelt keine Sitzung ueber laengere Zeit sauber. */
    void sendTelnet(const QStringList& cmds)
    {
        QTcpSocket* sock = new QTcpSocket(this);
        connect(sock, &QTcpSocket::connected, this, [sock, cmds]{
            for (const QString& c : cmds)
                sock->write((c + "\\r\\n").toUtf8());
            sock->flush();
            QTimer::singleShot(400, sock, [sock]{
                sock->disconnectFromHost();
                sock->deleteLater();
            });
        });
        connect(sock, &QTcpSocket::disconnected, sock, &QObject::deleteLater);
        sock->connectToHost(QHostAddress::LocalHost, 5401);
    }

    static qreal clamp01(qreal v) { return qBound(0.0, v, 1.0); }'''

MEM_OLD = '''    bool  _gearDown = true;
    bool  _tiltActive = false;'''
MEM_NEW = '''    bool  _gearDown = true;
    bool  _tiltActive = false;
    bool  _cranking = false;
    bool  _engineOn = false;'''

# Knopf in der Oberflaeche
BTN_OLD = '''        Button {
            width: parent.width
            text: qsTr("Brake")'''
BTN_NEW = '''        Button {
            width: parent.width
            text: ctl.cranking ? qsTr("Cranking…")
                               : (ctl.engineOn ? qsTr("Engine off")
                                               : qsTr("Start engine"))
            color: ctl.cranking ? Theme.highlightColor : Theme.primaryColor
            onClicked: {
                if (ctl.cranking) return
                if (ctl.engineOn) ctl.stopEngine()
                else ctl.startEngine()
            }
        }

        Button {
            width: parent.width
            text: qsTr("Brake")'''

# Protokoll: throttle auf current-engine
PROTO_OLD = '<node>/controls/engines/engine[0]/throttle</node>'
PROTO_NEW = '<node>/controls/engines/current-engine/throttle</node>'


def patch(path, pairs):
    try:
        s = open(path).read()
    except FileNotFoundError:
        print("  FEHLT:", path); return False
    for old, new, what in pairs:
        if old == new:
            continue
        if old not in s:
            print("  Muster nicht gefunden:", what); return False
        s = s.replace(old, new, 1)
        print("  ok:", what)
    open(path, 'w').write(s)
    return True


def main():
    print("ControlSender:")
    ok = patch(CPP, [
        (INC_OLD,    INC_NEW,    "QTcpSocket"),
        (PROP_OLD,   PROP_NEW,   "Properties"),
        (GET_OLD,    GET_NEW,    "Getter"),
        (BRAKE_OLD,  BRAKE_NEW,  "Bremse mit Radbremsen"),
        (SLOT_OLD,   SLOT_NEW,   "startEngine/stopEngine"),
        (HELPER_OLD, HELPER_NEW, "sendTelnet"),
        (MEM_OLD,    MEM_NEW,    "Member"),
    ])

    print("Oberflaeche:")
    patch(QML, [(BTN_OLD, BTN_NEW, "Startknopf")])

    print("Protokoll:")
    patch(SPEC, [(PROTO_OLD, PROTO_NEW, "throttle auf current-engine")])

    print()
    print("Beide Pakete neu bauen. Auf dem Geraet danach:")
    print("  cp /opt/fgfs/share/fgtouch.xml \\")
    print("     ~/.local/share/harbour-fgview/fgdata/Protocol/")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
