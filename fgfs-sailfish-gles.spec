%global __requires_exclude ^libosg|^libOpenThreads|^libSimGear
%global __provides_exclude ^lib.*\\.so.*$
%define debug_package %{nil}
%define __strip /bin/true

%define fgdir /home/.system/fgfs

Name:       fgfs-sailfish-gles
Summary:    FlightGear native GLES backends for Sailfish OS
Version:    2020.3.19
Release:    13
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
mkdir -p %{buildroot}%{fgdir}
# The trees are built into the target's /opt and only moved here, at
# packaging time, so nothing about the OSG or FlightGear build changes.
#
# Why not /opt: it lives on the root filesystem, which has 9.5 GB in total
# and, with Android app support taking 2.3 GB of it, about 1.9 GB free.
# These four trees are 793 MB of that. /home is a 218 GB partition with
# 180 GB free, and /home/.system is where Sailfish already keeps system
# data that does not belong on root - .appsupport and .zypp-cache are
# there.
#
# An upgrade moves them by itself: rpm installs the new location first and
# then removes the files of the old version, and the /opt copies are in the
# old version only. No script, and nothing left behind.
cp -a opt/osg-gles     %{buildroot}%{fgdir}/
cp -a opt/osg-gles3    %{buildroot}%{fgdir}/
cp -a opt/fgfs-gles    %{buildroot}%{fgdir}/
cp -a opt/fgfs-gles3   %{buildroot}%{fgdir}/

%files
%defattr(-,root,root,-)
%{fgdir}

%changelog
* Sat Sep 12 2026 Sebastian <smatkovi@github> - 2020.3.19-13
- The VASI/PAPI approach lights are drawn under GLES. FlightGear paints
  them as GL_POINTs in immediate mode, sized by a point sprite effect -
  none of which exists under OpenGL ES, so the lights were missing. They
  are now ordinary geometry in the scene: one camera-facing quad per light
  with a round sprite, its size following the distance so a light stays a
  few pixels wide from miles out, and a cull callback that writes the
  colour every frame - red below the glide path, white above, nothing when
  seen from behind. That is how X-Plane and MSFS draw their airport lights
  too (sg_vasi_gles.py; BEFUNDE P55). Measured on the LOWW 29 approach:
  four red lights from below the path, four white from above.
- The lights hang in a plain geode instead of under the point sprite
  effect: with that effect nothing reached the raster, whatever the
  geometry said.

* Fri Sep 11 2026 Sebastian <smatkovi@github> - 2020.3.19-12
- AI flight plans that end with an EOF marker after END load again. FGData's
  KSFO_depart_south_28L.xml, the only plan of the aircraft_demo scenario,
  does, and FlightGear refused it ("Flightplan missing END node"): the 737
  was created but stayed at 0/0 without speed. Waypoints named EOF are now
  skipped while reading (fg_aiplan_eof.py). Measured: the aircraft departs
  28L and climbs through 5400 ft at 320 kt within a minute.

* Fri Sep 11 2026 Sebastian <smatkovi@github> - 2020.3.19-11
- Canvas vector paths draw under GLES: the glass-cockpit displays (A320
  PFD/ND/ECAM and every other Canvas instrument) were blank except for
  text and images, because the GLES trees replaced ShivaVG - which speaks
  OpenGL 1.x - with no-op stubs. ShivaVG is compiled again on a small
  shim (shGLES.h/.c) that implements exactly the fixed-function subset it
  uses on ES2: a matrix stack, immediate mode as triangle lists, client
  arrays on the default VAO, 1D textures as Nx1 textures, texgen and the
  texture matrix in a shader of its own. CanvasPath hands it OSG's
  matrices and marks OSG's state dirty afterwards (sg_canvas_gles.py).
- OSG: renderbuffers get sized internal formats under GLES. The canvas
  attaches its packed depth/stencil buffer with the unsized GL_DEPTH_STENCIL,
  which ES rejects; the FBO was incomplete, OSG fell back to the window
  framebuffer, and without a stencil buffer ShivaVG painted every path as
  its bounding box (ffp_gles32.py; BEFUNDE.md P39-P41).
- The ES2 trees are rebuilt from the same sources and carry the same
  fixes (glass effect fallback, canvas, renderbuffer formats).

* Fri Sep 11 2026 Sebastian <smatkovi@github> - 2020.3.19-10
- SimGear: an aircraft effect no longer vanishes because one of its shaders
  is missing. With compositor support SimGear rewrites every shader path
  Shaders/x to Compositor/Shaders/x and gave up when that file did not
  exist; aircraft effects are written against the classic tree, so the
  Katana's canopy effect (glassrain.eff, Shaders/glass-ALS.vert) failed to
  build, makeEffect returned null, and the canopy was left as an
  EffectGeode without an effect and without its state set - drawn through
  the plain cull path with no blending, hence opaque. Now the classic
  location is tried when the Compositor/ one is missing, and a technique
  that still cannot be built is dropped with a log line instead of taking
  the whole effect (and the fixed-function technique) down with it.
  Measured on the Katana: the canopy geodes get their effect, are drawn
  with the glass shader and GL_BLEND on (BEFUNDE.md P33-P38).
- The diagnostic probes of the glass investigation are not compiled in;
  the shipped SimGear is the patched pristine source.

* Thu Sep 10 2026 Sebastian <smatkovi@github> - 2020.3.19-9
- The four GLES trees now live under /home/.system/fgfs instead of /opt.
  They are 793 MB, and the root filesystem has 1.9 GB free of 9.5 GB, most
  of the rest being Android app support; /home has 180 GB free. Nothing in
  the trees referred to /opt at run time - the only absolute paths were in
  seventeen pkg-config files, which are build metadata - so this is a move
  of the packaging, not of the build.
- Upgrading moves them without a script: rpm writes the new location and
  then removes the previous version's files, which are the /opt ones.

* Thu Sep 10 2026 Sebastian <smatkovi@github> - 2020.3.19-8
- OSG: the AC3D loader emitted GL_QUADS and GL_POLYGON, neither of which
  exists under GLES. A draw call with such a mode rasterises nothing and
  reports no GL error, so the surface silently disappeared. Quads are now
  split into the two triangles GL_QUADS is specified to decompose into,
  and polygons become triangle fans, both keeping the vertex order and so
  the winding. This is what made the c172p's instrument dials black: a
  dial face is a single four-cornered SURF, so it vanished entirely,
  while needles and the curved moving parts carry triangles too and
  survived - which made the fault look like it followed "fixed versus
  moving" when it followed "quad versus triangle"

* Fri Sep 04 2026 Sebastian <smatkovi@github> - 2020.3.19-7
- OSG: geometry without a shader gets a built-in one - vertex colour,
  times the texture on unit 0 if there is one. GLES draws nothing without
  a program, and FlightGear's sky dome, HUD and 2D panel have none; the
  sky was black
- OSG: 1D textures under GLES. The shader converter turns sampler1D into
  sampler2D and texture1D(s, x) into texture2D(s, vec2(x, 0.5)), and
  Texture1D::apply uploads the image as a 2D texture of height 1. Fields
  and forests (crop.frag, forest.frag) rendered black before
- OSG: "const float X = SOME_INT;" gets a float() constructor, which GLSL
  ES accepts as a constant expression
- 50 of the 52 default effect shaders now pass GLSL ES 3.00 validation

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
