# FlightGear auf Sailfish OS

Portierung von FlightGear 2020.3.19 auf Sailfish OS, getestet auf dem
Jolla Phone 2026 (jp2601, Mali-G610 MC2, SFOS 5.2).

Der Kern des Ganzen: Sailfish OS hat kein Desktop-OpenGL. Die GPU
spricht nur OpenGL ES über libhybris und den proprietären
Vendor-Blob. FlightGear und OpenSceneGraph brauchen aber Desktop-GL
samt Fixed-Function-Pipeline — `glBegin`, Matrix-Stack, Display-Listen.

Der Weg dorthin führt über **Mesa Zink**: Zink übersetzt OpenGL nach
Vulkan, und Vulkan ist über libhybris verfügbar. Ergebnis auf dem
jp2601:

```
GL_VERSION:  3.2 (Compatibility Profile) Mesa 24.2.8
GL_RENDERER: zink Vulkan 1.3(Mali-G610 MC2 (ARM_PROPRIETARY))
```

Damit läuft die klassische FlightGear-Renderpipeline. ALS und der neue
Compositor sind nicht nutzbar (siehe Einschränkungen), aber die will
man auf einem Tile-Based Renderer ohnehin nicht.

## Aufbau

```
FlightGear  ->  OpenSceneGraph  ->  libglvnd  ->  Mesa/Zink
                      |                              |
              GraphicsWindowEGL                   Vulkan
                      |                              |
                  FBO + Readback              libhybris  ->  Mali-Blob
                      |
              Shared Memory  ->  harbour-fgview (Silica)
```

Die Präsentation läuft **nicht** direkt: Zinks Kopper scheitert beim
Erzeugen der Swapchain mit `VK_ERROR_SURFACE_LOST_KHR`, weil hybris'
WSI intern ein ANativeWindow erwartet und mit einer von Mesa
verwalteten `wl_surface` nichts anfangen kann. Stattdessen rendert
OSG offscreen in ein FBO, der Inhalt wird per `glReadPixels` in ein
Shared-Memory-Segment geschrieben, und eine Silica-App zeigt ihn an.

Anzeige und Steuerung: https://github.com/smatkovi/harbour-fgview

## Die Eingriffe

### mesa/platform_wayland.c

Mesa 24.2.8, `src/egl/drivers/dri2/platform_wayland.c`.

Vor der Zink-Initialisierung prüft Mesa auf `wl_drm` beziehungsweise
`zwp_linux_dmabuf` und bricht ab, wenn beides fehlt. Lipstick bietet
weder das eine noch das andere an — es teilt GPU-Buffer über hybris'
eigene Erweiterung `android_wlegl`.

Die Prüfung ist an dieser Stelle sachlich falsch: Kopper präsentiert
über `VK_KHR_wayland_surface`, also die Vulkan-Swapchain, und braucht
dmabuf gar nicht. Nur `dri2_set_WL_bind_wayland_display` weiter unten
tut das, und die ist bereits separat abgesichert.

```c
   if (disp->Options.Zink) {
-     if (!dri2_initialize_wayland_drm_extensions(dri2_dpy) && !disp->Options.ForceSoftware)
-        goto cleanup;
+     /* kopper presents via VK_KHR_wayland_surface; wl_drm/dmabuf not required */
+     dri2_initialize_wayland_drm_extensions(dri2_dpy);
   }
```

Ohne diesen Einzeiler wird Zink nie aktiviert und Mesa fällt auf
Softpipe zurück. Upstream-Kandidat: die Bedingung ist auf jedem
Gerät ohne dmabuf falsch, nicht nur auf diesem.

Build-Konfiguration:

```
meson setup build \
  -Dprefix=/opt/mesa-zink -Dlibdir=lib64 \
  -Dgallium-drivers=zink,softpipe \
  -Dvulkan-drivers= -Dplatforms=wayland \
  -Dglx=disabled -Dgbm=disabled -Ddri3=enabled \
  -Degl=enabled -Dgles1=disabled -Dgles2=enabled -Dopengl=true \
  -Dshared-glapi=enabled -Dglvnd=enabled \
  -Dllvm=disabled -Dvideo-codecs= -Dbuildtype=release
```

`softpipe` muss mitgebaut werden: der Loader betritt den swrast-Zweig
und braucht dessen Einsprungpunkte, bevor Zink sich davorschieben
kann. `dri3=enabled` ist trotz des Namens nötig — daran hängt die
gesamte Kopper-Infrastruktur, nicht nur X11-DRI3.

Ein weiterer Fix in `src/loader/loader_wayland_helper.c`: fehlende
Includes für `clock_gettime` und `timespec_sub_saturate`, upstream
inzwischen behoben.

### libglvnd

Mesa baut `libGL.so.1` nur zusammen mit GLX. Ohne X11 fehlt damit
die Bibliothek, die `glMatrixMode` und die übrigen Desktop-Symbole
exportiert — `libglapi` enthält nur Dispatch-Infrastruktur.

libglvnd 1.7.0 liefert stattdessen `libOpenGL.so.0`, die dieselben
Symbole bereitstellt und ohne GLX auskommt:

```
meson setup build -Dprefix=/opt/mesa-zink -Dlibdir=lib64 \
  -Dx11=disabled -Dglx=disabled -Degl=true -Dgles1=false -Dgles2=true
```

Danach Mesa mit `-Dglvnd=enabled` neu bauen, damit es sich als
EGL-Vendor registriert (`libEGL_mesa.so.0` plus
`share/glvnd/egl_vendor.d/50_mesa.json`).

### osg/GraphicsWindowEGL.cpp

Neue Datei für `src/osgViewer/`. OSG bringt kein EGL-Backend mit; mit
`OSG_WINDOWING_SYSTEM=None` gebaut, gibt es überhaupt kein
Fenstersystem, und FlightGears `WindowBuilder::makeDefaultTraits`
dereferenziert einen Nullzeiger.

Die Klasse implementiert `WindowingSystemInterface` und
`osgViewer::GraphicsWindow` auf EGL:

* `eglBindAPI(EGL_OPENGL_API)` — Desktop-GL, nicht GLES
* Config mit `EGL_OPENGL_BIT` und `EGL_WINDOW_BIT`
* surfaceless Kontext (`EGL_KHR_surfaceless_context`)
* eigenes FBO als Renderziel, angemeldet über
  `GraphicsContext::setDefaultFboId()` — ohne das rendert OSG nach
  Framebuffer 0, den es hier nicht gibt, und alles bleibt schwarz
* `swapBuffersImplementation()` liest per `glReadPixels` aus und
  schreibt in ein Shared-Memory-Segment (seqlock, doppelt gepuffert)

Eintrag in `src/osgViewer/CMakeLists.txt` im `ELSE()`-Zweig von
„Windowing system not supported".

OSG-Konfiguration — die `OSG_GL_*`-Schalter sind zwingend, sonst
kompiliert OSG die Fixed-Function-Pfade weg:

```
cmake -B build -G Ninja \
  -DCMAKE_INSTALL_PREFIX=/opt/fgfs \
  -DOPENGL_PROFILE=GL2 -DOSG_WINDOWING_SYSTEM=None \
  -DOSG_GL1_AVAILABLE=ON -DOSG_GL2_AVAILABLE=ON \
  -DOSG_GLES1_AVAILABLE=OFF -DOSG_GLES2_AVAILABLE=OFF \
  -DOSG_GL_DISPLAYLISTS_AVAILABLE=ON \
  -DOSG_GL_FIXED_FUNCTION_AVAILABLE=ON \
  -DOSG_GL_MATRICES_AVAILABLE=ON \
  -DOSG_GL_VERTEX_FUNCS_AVAILABLE=ON \
  -DOSG_GL_VERTEX_ARRAY_FUNCS_AVAILABLE=ON \
  -DOPENGL_gl_LIBRARY=/opt/mesa-zink/lib64/libOpenGL.so.0 \
  -DOPENGL_INCLUDE_DIR=/opt/mesa-zink/include
```

### simgear/

SimGear 2020.3.19.

`canvas/ShivaVG/src/shDefs.h` — inkludiert unter Linux pauschal
`GL/glx.h`. Entfernt, GLX wird dort nicht benutzt.

`canvas/ShivaVG/src/shExtensions.c` — ruft `glXGetProcAddress`.
Ersetzt durch `eglGetProcAddress`, gleiche Signatur.

`scene/viewer/Compositor.hxx` — fehlendes `#include <array>`. GCC 13
zieht es nicht mehr indirekt herein.

Konfiguration mit `-DENABLE_SOUND=ON -DUSE_AEONWAVE=OFF`; AeonWave
gibt es auf SFOS nicht, OpenAL schon (Paket heißt `OpenAL`, groß
geschrieben).

### plib/

PLIB aus dem SourceForge-Git (`git.code.sf.net/p/libplib/code`).
FlightGear braucht daraus `pu` und `puaux`.

`src/util/ul.h` — `#define UL_GLX` in allen drei Plattform-Zweigen
auskommentiert.

`src/ssg/ssg.cxx` — `glXGetCurrentContext()` durch
`eglGetCurrentContext() != EGL_NO_CONTEXT` ersetzt, Include auf
`EGL/egl.h` umgestellt.

`src/fnt/fntTXF.cxx`, `src/pui/pu.cxx` — GLX-Includes auf EGL.

`src/Makefile` — Modul `pw` aus `SUBDIRS` entfernt. Das ist PLIBs
eigene X11-Fensterverwaltung, wird nicht gebraucht und lässt sich
nicht sinnvoll portieren.

Symlink nötig, damit configure `-lGL` findet:

```
ln -s /opt/mesa-zink/lib64/libOpenGL.so.0 /opt/mesa-zink/lib64/libGL.so
ln -s /opt/mesa-zink/lib64/libOpenGL.so.0 /opt/mesa-zink/lib64/libGL.so.1
```

### FlightGear

`CMakeLists.txt` — `find_package(X11 REQUIRED)` auskommentiert.

`src/GUI/new_gui.cxx` — `#include "GL/glx.h"` (mit Anführungszeichen,
nicht spitzen Klammern) auf `EGL/egl.h` umgestellt.

Konfiguration mit `-DENABLE_QT=OFF`, dazu
`-DCMAKE_EXE_LINKER_FLAGS="-L/opt/mesa-zink/lib64 -Wl,-rpath-link,/opt/mesa-zink/lib64 -lEGL"`.

## Laufzeitumgebung

Mesa darf **niemals** global vor hybris' EGL landen, sonst ist das
Telefon unbedienbar. Nur für fgfs setzen:

```sh
export LD_LIBRARY_PATH=/opt/mesa-zink/lib64:/opt/fgfs/lib
export __EGL_VENDOR_LIBRARY_DIRS=/opt/mesa-zink/share/glvnd/egl_vendor.d
export EGL_PLATFORM=wayland
export MESA_LOADER_DRIVER_OVERRIDE=zink
export XDG_RUNTIME_DIR=/run/display
export WAYLAND_DISPLAY=wayland-0
unset GALLIUM_DRIVER
```

`GALLIUM_DRIVER` muss ungesetzt sein: sobald die Variable existiert,
überspringt Mesas EGL die Zink-Aktivierung (`eglapi.c`, Zeile 704).

## Einschränkungen

Die Mali-G610 unterstützt `shaderClipDistance` nicht. Ohne
`gl_ClipDistance` deckelt Mesa das Compatibility-Profil bei GL 3.2,
obwohl die Hardware mehr kann — Tessellation, Compute-Shader und DSA
sind als Extensions verfügbar, nur nicht über die Versionsnummer.
Für FlightGears klassische Pipeline (GL 2.1) reicht das mit Reserve.

`fillModeNonSolid` fehlt ebenfalls: kein Wireframe-Modus.

S3TC ist trotz fehlender Hardware-Unterstützung nutzbar — Mesa
dekomprimiert DXT in Software, FlightGears DDS-Scenery lädt also
unverändert.

Die Bildrate liegt derzeit bei etwa 5 fps bei 1024×768. Der
Flaschenhals ist der synchrone `glReadPixels`, der auf einem Tiler
die Pipeline zum Flush zwingt. PBO-Pingpong und eine kleinere
Auflösung sollten das deutlich verbessern.

## Offen

* Zero-Copy statt Readback. `VK_ANDROID_external_memory_android_hardware_buffer`,
  `VK_EXT_external_memory_dma_buf` und `VK_KHR_external_semaphore_fd`
  sind auf dem Gerät vorhanden. Zinks dmabuf-Export scheitert
  allerdings daran, dass der swrast-Einstieg `zink_create_screen`
  den `drm_fd` hart auf -1 setzt und damit keine Modifier aushandeln
  kann.
* `VK_ERROR_SURFACE_LOST_KHR` bei hybris' Vulkan-WSI mit fremden
  `wl_surface`-Objekten — wäre ein Bug-Report an libhybris wert.
* Adreno-Geräte (Xperia 10 V): Vulkan 1.1.128 ist vorhanden, der
  Stack aber ungetestet.

## Lizenz

Die Patches folgen der Lizenz des jeweiligen Projekts: Mesa MIT,
OSG LGPL-artig (OSGPL), SimGear und FlightGear GPLv2+, PLIB LGPL.

## Nativer GLES-Zweig

Neben dem Zink-Weg existiert ein zweiter Bau, der ohne Mesa auskommt:
OpenSceneGraph in den Profilen GLES2 und GLES3, direkt auf dem
EGL-Stack des Geräts. Er ist als eigenes Paket
(`fgfs-sailfish-gles`) verpackt und in harbour-fgview auswählbar.

Kurz gesagt: er läuft, bringt aber keinen Gewinn und kostet einiges.
Interessant sind vor allem die drei Fehler, die auf dem Weg dorthin
gefunden wurden.

### Was dabei entfällt

Alles, was die Fixed-Function-Pipeline braucht:

- ShivaVG und damit der Canvas — die Glascockpit-Anzeigen
- die PUI-Oberfläche: Menüs, Dialoge, Knöpfe
- das HUD
- das 2D-Panel
- die VASI/PAPI-Anflugbefeuerung
- `tr.cxx`, der Tile-Renderer für hochauflösende Screenshots

Dazu kommt, dass FlightGears Effect-Shader in Desktop-GLSL 1.20
geschrieben sind und `gl_TexCoord`, `gl_LightSource` und `gl_Fog`
benutzen. Unter GLES scheitern sie an der Sprachversion:

```
Language version '120' unknown, this compiler only supports up to
version '320 es'
```

Betroffen sind unter anderem `default.vert`, `default.frag` und
`ubershader` — also die Shader, die alles Sichtbare zeichnen. Ohne
eine Konvertierung der Shader in FGData bleibt das Bild leer.

### Drei Fehler, die dabei zutage kamen

**TLS-Kollision mit Bionic.** Der Mali-Treiber legt den aktuellen
GL-Kontext in Bionics TLS-Slot 3 ab, also bei `TP+24`. Auf aarch64
beginnt der statische TLS-Block bei `TP+16`, und das Hauptprogramm
bekommt ihn vor allen Bibliotheken — `libtls-padding.so` kann daran
nichts ändern, auch nicht per `LD_PRELOAD`. FlightGears eigene
`thread_local`-Variablen landen damit genau auf den Bionic-Slots und
überschreiben den Kontextzeiger; `glViewport` liest ihn danach als
`0x6f00000000`, also mit auf null gesetzter unterer Hälfte, und der
Treiber stürzt ab.

Behoben durch ein 128-Byte-Feld als erste TLS-Variable im ersten
Objekt des Hauptprogramms (`flightgear/gles_stubs.cxx`). Das dürfte
jede hybris-Portierung einer nativen GLES-Anwendung betreffen.

**`glGetIntegerv` ohne aktuellen Kontext.** `FGRenderer::update()` in
`renderer_compositor.cxx` fragt `GL_MAX_TEXTURE_SIZE` ab, läuft aber
in der Hauptschleife ohne aktuellen GL-Kontext. Desktop-Treiber
liefern dort Unsinn — der Code fängt das mit einer Bereichsprüfung ab
und der Kommentar im Original erwähnt es sogar. Der Mali-Blob stürzt
stattdessen ab. Die Abfrage steht jetzt hinter einer Kontextprüfung.

**Kein `EGL_KHR_surfaceless_context`.** Der Blob bietet es nicht an,
`eglMakeCurrent` mit `EGL_NO_SURFACE` bringt ihn um. `GraphicsWindowEGL`
legt deshalb eine Pbuffer-Surface an; gerendert wird weiterhin ins FBO.

### Zero-Copy und warum es nativ zunächst nicht ging

Der dmabuf-Weg über `/dev/dma_heap/system` funktioniert nur unter
Zink: hybris-EGL kennt kein `EGL_EXT_image_dma_buf_import`, der
Simulator kann den Puffer also gar nicht als Renderziel benutzen. Er
schreibt trotzdem die Metadaten ins Segment, und der Presenter sieht
einen Puffer, in den nie jemand zeichnet — schwarzes Bild. Die nativen
Backends benutzen deshalb den Readback-Pfad.

Es gibt aber einen Weg, der unter allen Backends trägt:
`EGL_HYBRIS_native_buffer2`. Die Funktionen sind vorhanden, auch wenn
sie weder in Headern noch im Symbolexport auftauchen — `eglGetProcAddress`
liefert sie. Damit lässt sich ein Puffer in einem Prozess anlegen, mit
`eglHybrisSerializeNativeBuffer` beschreiben, die Beschreibung über
einen Unix-Socket übergeben und im anderen Prozess mit
`eglHybrisCreateRemoteBuffer` wiederherstellen.

Bemerkenswert: das umgeht die Gralloc-Hürde. `hybris_gralloc_initialize`
schlägt auf Geräten mit AIDL-Allocator fehl, weil libhybris nur HIDL
kennt — der EGL-Pfad kommt trotzdem an den Allokator heran.

Die Testprogramme unter `tools/` belegen beides:

- `hybshare.c` — Puffer anlegen, serialisieren, im zweiten Prozess
  wiederherstellen, per CPU beschreiben und im ersten lesen
- `hybgl.c` — dasselbe, aber der zweite Prozess rendert mit der GPU
  hinein (EGLImage über `EGL_NATIVE_BUFFER_HYBRIS`, als
  FBO-Farbattachment)
- `hybprovider.c` — stellt einen Puffer für den Simulator bereit und
  schreibt heraus, was hineingezeichnet wurde

`GraphicsWindowEGL` nimmt diesen Weg, sobald `FGFS_HYB_SOCKET` gesetzt
ist. Der Presenter besitzt dann den Puffer und kann ihn als Textur
importieren, statt ihn zu kopieren.

### Messwerte

Jolla Phone 2026, 1024x768, ufo und c172p bei LOWW. Die Streuung
zwischen Läufen ist beträchtlich — das Gerät drosselt thermisch, und
Unterschiede unter etwa fünf Bildern sind nicht aussagekräftig.

| | ufo | c172p |
|---|---|---|
| Zink, Zero-Copy, Fence, `ZINK_DESCRIPTORS=lazy` | 47 | 11 |
| GLES2, Readback, `glFlush` | 37 | 11 |
| GLES3, Readback, `glFlush` | 44 | — |

`ZINK_DESCRIPTORS=lazy` ist unter Zink rund 30 Prozent wert (8,5 auf
11 bei der c172p). Renderoptionen dagegen nicht: mit abgeschalteten
Shadern, Wolken und auf 3 km reduzierter Sicht liefert die c172p 10
statt 11 Bilder. Die Zeit steckt nicht im Zeichnen, sondern in der
Zahl der Zeichenaufrufe und Zustandswechsel des Flugzeugmodells —
und die ist in beiden Welten dieselbe.

Wer die Cessna flüssig fliegen will, muss am Modell ansetzen, nicht am
Grafikstack.
