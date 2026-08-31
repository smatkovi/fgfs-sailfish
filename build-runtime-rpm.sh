#!/bin/bash
# build-runtime-rpm.sh
#
# Schnuert /opt/mesa-zink und /opt/fgfs (ohne FGData) zu einem
# installierbaren RPM. Im SDK-Container ausfuehren:
#
#   bash build-runtime-rpm.sh
#
# Ergebnis: ~/fgfs-sailfish/RPMS/fgfs-sailfish-<version>-1.aarch64.rpm

set -e

TARGET=SailfishOS-5.2.0.15-aarch64
VERSION=2020.3.19
NAME=fgfs-sailfish
WORK=$HOME/$NAME

echo "== Verzeichnisse anlegen"
rm -rf "$WORK"
mkdir -p "$WORK"/{rpm,SOURCES,RPMS}

echo "== Laufzeit aus dem Target packen (ohne FGData)"
sb2 -t $TARGET -m sdk-install -R tar czf /home/mersdk/$NAME/SOURCES/$NAME-$VERSION.tar.gz \
    -C / \
    --exclude='opt/fgfs/lib/FlightGear' \
    --exclude='opt/fgfs/include' \
    --exclude='opt/mesa-zink/include' \
    --exclude='*.a' \
    opt/fgfs opt/mesa-zink

ls -lh "$WORK/SOURCES/$NAME-$VERSION.tar.gz"

echo "== Starter und Szenerie-Werkzeug in die Quellen legen"
cp "$(dirname "$0")/bin/fgfs-run" "$(dirname "$0")/bin/fgfs-scenery" "$WORK/SOURCES/"
chmod 0755 "$WORK/SOURCES/fgfs-run" "$WORK/SOURCES/fgfs-scenery"

echo "== Spec schreiben"
cat > "$WORK/rpm/$NAME.spec" <<'SPEC'
%global __requires_exclude ^libOpenGL\\.so|^libEGL_mesa\\.so|^libGLdispatch\\.so|^libgallium
%global __provides_exclude ^lib.*\\.so.*$
%define debug_package %{nil}
%define __strip /bin/true

Name:       fgfs-sailfish
Summary:    FlightGear flight simulator runtime for Sailfish OS
Version:    2020.3.19
Release:    2
License:    GPLv2+
Group:      Amusements/Games
URL:        https://github.com/smatkovi/fgfs-sailfish
Source0:    %{name}-%{version}.tar.gz
BuildArch:  aarch64
AutoReqProv: no

Requires:   OpenAL
Requires:   libcurl
Requires:   aria2
Requires:   boost-system

%description
FlightGear 2020.3.19 nebst OpenSceneGraph, SimGear und einem
Mesa-Zink-Stack, der Desktop-OpenGL ueber Vulkan auf der GPU
bereitstellt.

Enthaelt NICHT die Basisdaten (FGData, rund 1,7 GB). Diese werden
von der Anwendung harbour-fgview beim ersten Start heruntergeladen
und unter $HOME/.local/share/harbour-fgview/fgdata abgelegt.

Nach der Installation startet der Simulator ueber harbour-fgview.
Fuer den Betrieb von der Kommandozeile siehe /opt/fgfs/bin/fgfs-env.

%prep
%setup -q -c

%build

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}
cp -a opt %{buildroot}/

mkdir -p %{buildroot}/opt/fgfs/bin
cat > %{buildroot}/opt/fgfs/bin/fgfs-env <<'ENVEOF'
#!/bin/bash
# Umgebung fuer den Zink-Grafikstack auf SailfishOS.
# Nur fuer fgfs setzen, niemals global - Mesa wuerde sonst
# hybris' libEGL fuer alle Anwendungen verdecken.
export LD_LIBRARY_PATH=/opt/mesa-zink/lib64:/opt/fgfs/lib
export __EGL_VENDOR_LIBRARY_DIRS=/opt/mesa-zink/share/glvnd/egl_vendor.d
export EGL_PLATFORM=wayland
export MESA_LOADER_DRIVER_OVERRIDE=zink
export XDG_RUNTIME_DIR=/run/display
export WAYLAND_DISPLAY=wayland-0
unset GALLIUM_DRIVER
exec /opt/fgfs/bin/fgfs "$@"
ENVEOF
chmod 0755 %{buildroot}/opt/fgfs/bin/fgfs-env

install -m 0755 %{_sourcedir}/fgfs-run %{buildroot}/opt/fgfs/bin/fgfs-run
install -m 0755 %{_sourcedir}/fgfs-scenery %{buildroot}/opt/fgfs/bin/fgfs-scenery

%files
%defattr(-,root,root,-)
/opt/fgfs
/opt/mesa-zink

%changelog
* Mon Aug 24 2026 Sebastian <smatkovi@github> - 2020.3.19-1
- Erste Fassung: FlightGear, OSG, SimGear, PLIB, Mesa-Zink, glvnd
SPEC

echo "== RPM bauen"
cd "$WORK"
tar xzf "SOURCES/$NAME-$VERSION.tar.gz" -C . 2>/dev/null || true
mb2 -t $TARGET build || {
    echo
    echo "mb2 hat einen Fehler gemeldet. Haeufigste Ursache:"
    echo "  - Quelltarball muss unter SOURCES/ liegen"
    echo "  - AutoReqProv/no noetig, weil die Bibliotheken aus /opt kommen"
    exit 1
}

ls -lh "$WORK"/RPMS/*.rpm
