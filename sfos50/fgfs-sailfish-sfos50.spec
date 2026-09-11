%define debug_package %{nil}

# Sailfish OS 5.0 (glibc 2.30), e.g. the F(x)tec Pro1-X: only what the
# native GLES3 stack needs from fgfs-sailfish - the starter, the scenery
# tool and the input protocol.  The Mesa/Zink tree of the 5.2 package is
# built against glibc 2.38 and cannot run here, so it is left out; the app
# then starts with the GLES3 backend.
Name:       fgfs-sailfish
Summary:    FlightGear starter and scenery tool for Sailfish OS 5.0
Version:    2020.3.19
Release:    9.sfos50
License:    GPLv2+
Group:      Amusements/Games
URL:        https://github.com/smatkovi/fgfs-sailfish
Source1:    fgfs-run
Source2:    fgfs-scenery
Source3:    fgtouch.xml
BuildArch:  aarch64
AutoReqProv: no

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
Requires:   python3-base
Requires:   aria2

%description
The FlightGear starter (fgfs-run), the TerraSync scenery tool and the
fgtouch input protocol, for Sailfish OS 5.0. The simulator itself comes
with fgfs-sailfish-gles (GLES3 only on 5.0); the Mesa/Zink backend is not
available on this release.

%prep

%build

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/opt/fgfs/bin %{buildroot}/opt/fgfs/share
install -m 0755 %{SOURCE1} %{buildroot}/opt/fgfs/bin/fgfs-run
install -m 0755 %{SOURCE2} %{buildroot}/opt/fgfs/bin/fgfs-scenery
install -m 0644 %{SOURCE3} %{buildroot}/opt/fgfs/share/fgtouch.xml

%files
%defattr(-,root,root,-)
/opt/fgfs

%changelog
* Fri Sep 11 2026 Sebastian <smatkovi@github> - 2020.3.19-9.sfos50
- First build for Sailfish OS 5.0: starter, scenery tool and protocol only.
