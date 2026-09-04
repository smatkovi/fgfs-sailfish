%global __requires_exclude ^libosg|^libOpenThreads|^libSimGear
%global __provides_exclude ^lib.*\\.so.*$
%define debug_package %{nil}
%define __strip /bin/true

Name:       fgfs-sailfish-gles
Summary:    FlightGear native GLES backends for Sailfish OS
Version:    2020.3.19
Release:    6
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
* Fri Sep 04 2026 Sebastian <smatkovi@github> - 2020.3.19-6
- realize() hands the EGL context back again, unconditionally. The -5
  build had it behind a switch left over from a test, and the draw thread
  crashed at start with an empty GL function table

* Fri Sep 04 2026 Sebastian <smatkovi@github> - 2020.3.19-5
- Built with the GLES2 trees' configuration again: no LTO, no CPU flags,
  the GL constants defined one by one. The -4 build forced gles_compat.h
  into every file and SimGear's terrain tiles came out with constant
  texture coordinates; the runway was white. configure-gles3.sh records
  the working configuration

* Thu Sep 03 2026 Sebastian <smatkovi@github> - 2020.3.19-4
- OSG: GL modes and glHint targets that do not exist under ES are no
  longer applied. Every one of them was rejected by the driver and raised
  INVALID_ENUM, and OSG checked for the error after each attempt; about
  ten thousand round trips per run. Frame time 48 -> 37 ms, picture
  unchanged. FGFS_GLES_FAT=1 restores the old behaviour for comparison
- OSG: realize() hands the EGL context back, so OSG's threaded modes can
  bind it on the draw thread; before, eglMakeCurrent failed there with
  EGL_BAD_ACCESS and the GL function table came up empty
- OSG: the PBO readback path is enabled under ES 3, mapping with
  glMapBufferRange. FGFS_NO_PBO=1 forces the blocking readback
- OSG: FGFS_GLES_TIMING=1 logs cull, draw and frame times and the number
  of modes, attributes and drawables per frame, on both the single-thread
  and the draw-thread path
- SimGear: FGFS_BTG_OPTIMIZE=1 runs osgUtil::Optimizer on terrain tiles
  (measured: no effect, terrain shares little state; left as a switch)
- Built with -O3 -march=armv8.2-a+fp16+dotprod -mtune=cortex-a78 and LTO
  (measured: cull 4.4 -> 3.5 ms, nothing else); configure-gles3.sh
  records the full configuration
- With fgfs-run's DrawThreadPerContext the update phase overlaps with the
  draw: 34 ms per frame on the Vienna scenery, from 48 at the start of
  this round

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
