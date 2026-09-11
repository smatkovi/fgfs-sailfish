#!/usr/bin/env python3
"""
Grafik-Backend auswaehlbar machen.

Drei Stacks liegen nebeneinander installiert:

  zink   /opt/fgfs        + /opt/mesa-zink   Desktop-GL ueber Mesa/Zink
                                             auf Vulkan. Vollstaendig:
                                             GUI, HUD, Canvas, PAPI.
  gles2  /opt/fgfs-gles   + /opt/osg-gles    nativ auf hybris-EGL, ohne
  gles3  /opt/fgfs-gles3  + /opt/osg-gles3   GUI, HUD, Canvas und PAPI.

Die Auswahl kommt aus der Oberflaeche; zink bleibt die Voreinstellung,
weil nur dieser Stack alle Anzeigen mitbringt.
"""

import sys

RT = '/home/mersdk/harbour-fgview/src/fgruntime.h'
QML = '/home/mersdk/harbour-fgview/qml/pages/StartPage.qml'


def patch_runtime():
    s = open(RT, encoding='utf-8', errors='surrogateescape').read()
    if '_backend' in s:
        print('fgruntime.h: schon gepatcht')
        return True

    old_sig = ('    void startSim(const QString& aircraft = "c172p",\n'
               '                  const QString& airport  = "LOWW")\n'
               '    {\n'
               '        if (simRunning() || !dataReady()) return;\n')
    new_sig = ('    void startSim(const QString& aircraft = "c172p",\n'
               '                  const QString& airport  = "LOWW",\n'
               '                  const QString& backend  = "zink")\n'
               '    {\n'
               '        if (simRunning() || !dataReady()) return;\n'
               '\n'
               '        _backend = backend;\n')
    if old_sig not in s:
        print('FEHLER: startSim-Signatur nicht gefunden')
        return False
    s = s.replace(old_sig, new_sig, 1)

    old_env = '''        QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
        env.insert("LD_LIBRARY_PATH", "/opt/mesa-zink/lib64:/opt/fgfs/lib");
        env.insert("__EGL_VENDOR_LIBRARY_DIRS",
                   "/opt/mesa-zink/share/glvnd/egl_vendor.d");
        env.insert("EGL_PLATFORM", "wayland");
        env.insert("MESA_LOADER_DRIVER_OVERRIDE", "zink");
        env.insert("XDG_RUNTIME_DIR", "/run/display");
        env.insert("WAYLAND_DISPLAY", "wayland-0");
        env.insert("FGFS_SHM", "1");
        env.remove("GALLIUM_DRIVER");'''

    new_env = '''        QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
        env.insert("XDG_RUNTIME_DIR", "/run/display");
        env.insert("WAYLAND_DISPLAY", "wayland-0");
        env.insert("FGFS_SHM", "1");
        env.remove("GALLIUM_DRIVER");

        QString binary;
        if (backend == "gles2" || backend == "gles3") {
            /* Nativ auf hybris-EGL: kein Mesa, kein Zink. Dafuer
               ohne GUI, HUD, Canvas und Anflugbefeuerung. */
            const QString root = (backend == "gles3")
                               ? QStringLiteral("/opt/osg-gles3")
                               : QStringLiteral("/opt/osg-gles");
            env.insert("LD_LIBRARY_PATH", root + "/lib");
            env.insert("OSG_LIBRARY_PATH", root + "/lib/osgPlugins-3.6.5");
            binary = (backend == "gles3")
                   ? QStringLiteral("/opt/fgfs-gles3/bin/fgfs")
                   : QStringLiteral("/opt/fgfs-gles/bin/fgfs");
        } else {
            env.insert("LD_LIBRARY_PATH", "/opt/mesa-zink/lib64:/opt/fgfs/lib");
            env.insert("__EGL_VENDOR_LIBRARY_DIRS",
                       "/opt/mesa-zink/share/glvnd/egl_vendor.d");
            env.insert("EGL_PLATFORM", "wayland");
            env.insert("MESA_LOADER_DRIVER_OVERRIDE", "zink");
            /* Descriptor-Verwaltung: bringt bei Modellen mit vielen
               Zustandswechseln rund 30 Prozent. */
            env.insert("ZINK_DESCRIPTORS", "lazy");
            binary = QStringLiteral("/opt/fgfs/bin/fgfs");
        }'''

    if old_env not in s:
        print('FEHLER: Umgebungsblock nicht gefunden')
        return False
    s = s.replace(old_env, new_env, 1)

    old_start = '        _sim.start("/opt/fgfs/bin/fgfs", QStringList()'
    new_start = '        _sim.start(binary, QStringList()'
    if old_start not in s:
        print('FEHLER: Startaufruf nicht gefunden')
        return False
    s = s.replace(old_start, new_start, 1)

    # Member ergaenzen - vor der schliessenden Klammer der Klasse
    old_mem = '    QProcess _sim;'
    if old_mem in s:
        s = s.replace(old_mem, '    QProcess _sim;\n    QString  _backend;', 1)
    else:
        print('HINWEIS: _sim-Member nicht gefunden, _backend nicht angelegt')

    open(RT, 'w', encoding='utf-8', errors='surrogateescape').write(s)
    print('fgruntime.h: gepatcht')
    return True


def patch_qml():
    s = open(QML, encoding='utf-8', errors='surrogateescape').read()
    if 'backendBox' in s:
        print('StartPage.qml: schon gepatcht')
        return True

    anchor = '''                ComboBox {
                    id: airportBox'''
    box = '''                ComboBox {
                    id: backendBox
                    label: qsTr("Graphics backend")
                    currentIndex: 0
                    menu: ContextMenu {
                        MenuItem { text: qsTr("Zink (complete)") }
                        MenuItem { text: qsTr("GLES2 (native)") }
                        MenuItem { text: qsTr("GLES3 (native)") }
                    }
                    property var ids: ["zink", "gles2", "gles3"]
                }

                Label {
                    x: Theme.horizontalPageMargin
                    width: parent.width - 2 * Theme.horizontalPageMargin
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.fontSizeExtraSmall
                    color: Theme.secondaryColor
                    visible: backendBox.currentIndex > 0
                    text: qsTr("The native backends run without Mesa, but "
                             + "have no menus, HUD, glass cockpit displays "
                             + "or approach lights.")
                }

'''
    if anchor not in s:
        print('FEHLER: airportBox nicht gefunden')
        return False
    s = s.replace(anchor, box + anchor, 1)

    open(QML, 'w', encoding='utf-8', errors='surrogateescape').write(s)
    print('StartPage.qml: Auswahl ergaenzt')
    return True


def main():
    ok = patch_runtime() and patch_qml()
    if ok:
        print('\nNoch von Hand: der startSim-Aufruf in StartPage.qml')
        print('braucht backendBox.ids[backendBox.currentIndex] als')
        print('drittes Argument.')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
