%global __requires_exclude ^libOpenGL\\.so|^libEGL_mesa\\.so|^libGLdispatch\\.so|^libgallium
%global __provides_exclude ^lib.*\\.so.*$
%define debug_package %{nil}
%define __strip /bin/true

Name:       fgfs-sailfish
Summary:    FlightGear flight simulator runtime for Sailfish OS
Version:    2020.3.19
Release:    10
License:    GPLv2+
Group:      Amusements/Games
URL:        https://github.com/smatkovi/fgfs-sailfish
Source0:    %{name}-%{version}.tar.gz
Source1:    fgfs-run
Source2:    fgfs-scenery
Source3:    fgtouch.xml
BuildArch:  aarch64
AutoReqProv: no

# AutoReqProv is off, so this list has to be complete: it is what the
# binaries load on the device (LD_TRACE_LOADED_OBJECTS, resolved with rpm -qf).
Requires:   OpenAL
Requires:   libcurl
Requires:   libpng
Requires:   freetype
Requires:   fontconfig
Requires:   expat
Requires:   zlib
Requires:   bzip2-libs
Requires:   xz-libs
Requires:   dbus-libs
Requires:   openssl-libs
Requires:   libhybris-libEGL
Requires:   libhybris-libGLESv2
Requires:   boost-system
# fgfs-scenery
Requires:   python3-base
Requires:   aria2

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
install -m 0644 %{SOURCE3} %{buildroot}/opt/fgfs/share/fgtouch.xml


%files
%defattr(-,root,root,-)
/opt/fgfs
/opt/mesa-zink

%changelog
* Fri Sep 11 2026 Sebastian <smatkovi@github> - 2020.3.19-10
- AI flight plans that end with an EOF marker after END load again
  (aircraft_demo's KSFO_depart_south_28L.xml was refused with "Flightplan
  missing END node" and its 737 never moved); fg_aiplan_eof.py, same fix
  as fgfs-sailfish-gles -12.

* Fri Sep 11 2026 Sebastian <smatkovi@github> - 2020.3.19-9
- fgfs-scenery --check exits 2 when the tiles are on the disk but no
  finished run is on record (scenery fetched before there were records);
  fgfs-run starts at once in that case. The fetch is back to Terrain and
  Objects, the two trees organised by tile: Airports and Models are
  world-wide, and walking their thousands of indexes held a start for
  twenty minutes.

* Fri Sep 11 2026 Sebastian <smatkovi@github> - 2020.3.19-8
- fgfs-scenery remembers finished regions (<target>/.fgsync-regions) and
  answers --check offline: is the box around --lat/--lon covered by a run
  that read every index and downloaded everything? A run that lost a
  mirror halfway or whose aria2c failed records nothing and is repeated.
- fgfs-run --region asks that check before it goes to the mirrors: with the
  scenery on record it starts at once, offline too; otherwise it fetches
  Terrain, Objects, Airports and Models around the airport and says so on
  stdout ("Szenerie ... vorhanden / geladen / fehlgeschlagen"), which the
  app turns into its status line. FGFS_SCENERY_REFRESH=1 forces the
  comparison with the servers.

* Thu Sep 10 2026 Sebastian <smatkovi@github> - 2020.3.19-7
- fgfs-run finds the GLES trees under /home/.system/fgfs, where
  fgfs-sailfish-gles-9 puts them, and still accepts /opt so that a system
  with the new starter and the old runtime keeps working. Zink itself stays
  in /opt: it is 135 MB, and fgfs-run, fgfs-scenery and fgtouch.xml live
  there and are referred to by absolute path from several places.

* Thu Sep 10 2026 Sebastian <smatkovi@github> - 2020.3.19-6
- fgfs-run: the GLES backends now default to
  OSG_VERTEX_BUFFER_HINT=VERTEX_ARRAY_OBJECT. Draw is CPU bound on
  per-drawable attribute setup rather than on fill rate - rendering a
  quarter of the pixels leaves draw time unchanged - and there are about
  a thousand draw calls per frame, so carrying that setup in a vertex
  array object instead of repeating it per call pays off. Measured on
  LOWW with the c172p on a freshly booted device: frame 74.1 -> 66.6 ms,
  draw 39.3 -> 31.3 ms. Set OSG_VERTEX_BUFFER_HINT=NO_PREFERENCE to get
  the old behaviour back

* Thu Sep 03 2026 Sebastian <smatkovi@github> - 2020.3.19-5
- fgtouch.xml ships from the repository; eighth field sends the throttle
  to current-engine as well, which the cockpit lever's animation reads.
  The inline copy that used to overwrite it during install is gone

* Thu Sep 03 2026 Sebastian <smatkovi@github> - 2020.3.19-4
- fgfs-run: flight model at 60 Hz for the GLES backends, FGFS_MODEL_HZ
  overrides

* Thu Sep 03 2026 Sebastian <smatkovi@github> - 2020.3.19-3
- Requires completed from what the binaries actually load; AutoReqProv is
  off, and the old list would have failed on a device without libpng,
  freetype, fontconfig, expat or the hybris EGL libraries
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
