%global __requires_exclude ^libOpenGL\\.so|^libEGL_mesa\\.so|^libGLdispatch\\.so|^libgallium
%global __provides_exclude ^lib.*\\.so.*$
%define debug_package %{nil}
%define __strip /bin/true

Name:       fgfs-sailfish
Summary:    FlightGear flight simulator runtime for Sailfish OS
Version:    2020.3.19
Release:    3
License:    GPLv2+
Group:      Amusements/Games
URL:        https://github.com/smatkovi/fgfs-sailfish
Source0:    %{name}-%{version}.tar.gz
Source1:    fgfs-run
Source2:    fgfs-scenery
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

# One entry point for all three backends, plus the scenery downloader it
# calls when a region is requested.  Both live in the zink package because
# it is the one every installation has.
install -m 0755 %{SOURCE1} %{buildroot}/opt/fgfs/bin/fgfs-run
install -m 0755 %{SOURCE2} %{buildroot}/opt/fgfs/bin/fgfs-scenery

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
* Thu Sep 03 2026 Sebastian <smatkovi@github> - 2020.3.19-3
- fgfs-run selects DrawThreadPerContext for the GLES backends; the update
  phase then overlaps with the draw. FGFS_THREADING overrides. Zink stays
  single-threaded, untested there

* Mon Aug 31 2026 Sebastian <smatkovi@github> - 2020.3.19-2
- fgfs-run: one entry point for the zink, gles2 and gles3 backends, each
  with its own library paths and environment; ZINK_DESCRIPTORS=lazy is the
  default for zink
- fgfs-run --region=LAT,LON[,RADIUS] fetches the scenery for that area
  before starting
- fgfs-scenery: TerraSync download for a region, walking the .dirindex
  files and handing the file list to aria2c, resumable and re-runnable
  (existing files are checked against their SHA1)
- SimGear: gz read errors no longer take the process down with them; the
  error path built a std::string from a null pointer while reporting

* Mon Aug 24 2026 Sebastian <smatkovi@github> - 2020.3.19-1
- Erste Fassung: FlightGear, OSG, SimGear, PLIB, Mesa-Zink, glvnd
