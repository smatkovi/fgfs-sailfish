%global __requires_exclude ^libosg|^libOpenThreads|^libSimGear
%global __provides_exclude ^lib.*\\.so.*$
%define debug_package %{nil}
%define __strip /bin/true

Name:       fgfs-sailfish-gles
Summary:    FlightGear native GLES backends for Sailfish OS
Version:    2020.3.19
Release:    3
License:    GPLv2+
Group:      Amusements/Games
URL:        https://github.com/smatkovi/fgfs-sailfish
Source0:    %{name}-%{version}.tar.gz
BuildArch:  aarch64
AutoReqProv: no

Requires:   fgfs-sailfish

%description
FlightGear built against OpenSceneGraph in GLES2 and GLES3 profiles.
These run directly on the device EGL stack, without Mesa or Zink, but
lack the PUI menus, the HUD, the canvas glass-cockpit displays and the
VASI/PAPI approach lights, all of which need the fixed-function
pipeline. Selectable from harbour-fgview.

%prep
%setup -q -c

%build

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}
cp -a opt %{buildroot}/

%files
%defattr(-,root,root,-)
/opt/osg-gles
/opt/osg-gles3
/opt/fgfs-gles
/opt/fgfs-gles3

%changelog
* Mon Aug 31 2026 Sebastian <smatkovi@github> - 2020.3.19-3
- OSG: desktop GLSL 1.20 effect shaders are rewritten to GLSL ES on load,
  including the fixed-function built-ins (gl_LightSource, gl_Fog,
  gl_FrontMaterial, gl_TexCoord); Light, Material, LightModel, Fog and
  TexMat feed those values in as osg_* uniforms.  ES 3.00 is the target
  when the driver hands out an ES 3.x context, ES 1.00 otherwise
- OSG: same-stage shaders are merged into one shader object per stage,
  which GLES requires and FlightGear's effects rely on
- OSG: no generic texture compression on GLES.  The version test passes on
  an ES 3.x context and would pick GL_COMPRESSED_*_ARB, which ES does not
  have - every terrain texture came out black
- OSG: the texture coordinate and vertex attribute dispatcher lists only
  ever grow, and Geometry grows them to what the drawable needs.  Scene
  geometry with more units than the current VertexArrayState held read
  past the end of the vector
- Terrain, runways and clouds now render under GLES3 with textures, sun
  and fog

* Fri Aug 28 2026 Sebastian <smatkovi@github> - 2020.3.19-1
- First build: native GLES2 and GLES3 stacks alongside the Zink one
- Needs a 128-byte TLS pad as the first thread-local in the main
  binary: the Mali driver keeps its GL context in Bionic TLS slot 3
  (TP+24), which FlightGear's own thread_local variables would
  otherwise overwrite
- Needs a pbuffer surface because the driver has no
  EGL_KHR_surfaceless_context
