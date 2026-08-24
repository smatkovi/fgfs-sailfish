%global __requires_exclude ^libOpenGL\\.so|^libEGL_mesa\\.so|^libGLdispatch\\.so|^libgallium
%global __provides_exclude ^lib.*\\.so.*$
%define debug_package %{nil}
%define __strip /bin/true

Name:       fgfs-sailfish
Summary:    FlightGear flight simulator runtime for Sailfish OS
Version:    2020.3.19
Release:    1
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

mkdir -p %{buildroot}/opt/fgfs/share
cat > %{buildroot}/opt/fgfs/share/fgtouch.xml <<'PROTOEOF'
<?xml version="1.0" encoding="UTF-8"?>
<PropertyList>
  <generic>
    <input>
      <line_separator>newline</line_separator>
      <var_separator>,</var_separator>
      <chunk><name>aileron</name><node>/controls/flight/aileron</node><type>float</type></chunk>
      <chunk><name>elevator</name><node>/controls/flight/elevator</node><type>float</type></chunk>
      <chunk><name>rudder</name><node>/controls/flight/rudder</node><type>float</type></chunk>
      <chunk><name>throttle</name><node>/controls/engines/engine[0]/throttle</node><type>float</type></chunk>
      <chunk><name>brake</name><node>/controls/gear/brake-parking</node><type>float</type></chunk>
      <chunk><name>flaps</name><node>/controls/flight/flaps</node><type>float</type></chunk>
      <chunk><name>gear</name><node>/controls/gear/gear-down</node><type>bool</type></chunk>
    </input>
  </generic>
</PropertyList>
PROTOEOF

%files
%defattr(-,root,root,-)
/opt/fgfs
/opt/mesa-zink

%changelog
* Mon Aug 24 2026 Sebastian <smatkovi@github> - 2020.3.19-1
- Erste Fassung: FlightGear, OSG, SimGear, PLIB, Mesa-Zink, glvnd
