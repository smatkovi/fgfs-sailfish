# FlightGear auf Sailfish OS — Übergabe

Stand: 9. September 2026. Dieses Dokument fasst zusammen, wo das Projekt
steht, wie die Umgebung bedient wird und welcher Fehler offen ist. Es ist
für jemanden geschrieben, der die Arbeit übernimmt und den bisherigen
Verlauf nicht kennt.

## Was das Projekt ist

FlightGear 2020.3.19 läuft auf einem Jolla Phone 2026 (Sailfish OS 5.2,
Mali-G610, OpenGL ES 3.2). Der Simulator rendert offscreen, die App
`harbour-fgview` zeigt das Bild und steuert über ein UDP-Protokoll und
Telnet.

Erreicht: Gelände mit Texturen, Start- und Rollbahn, Himmel, Wolken,
Cockpit, Motorstart, Steuerung über Neigungssensor und Regler,
Einstellungsseite, rund 31 ms pro Bild auf der Wiener Szenerie.

## Umgebung

| | |
|---|---|
| Telefon | `defaultuser@JollaPhone2026`, Backends unter `/opt/fgfs` (Zink), `/opt/fgfs-gles`, `/opt/fgfs-gles3` |
| Host | `sebastian@192.168.1.21`, Repos unter `~/fgfs-sailfish` und `~/harbour-fgview` |
| Container | Docker `ba82fa4d3804`, Benutzer `mersdk`; vom Host mit `tmux attach -t fg` erreichbar |
| Quellen im Container | `~/OpenSceneGraph-OpenSceneGraph-3.6.5`, `~/simgear-2020.3.19`, `~/flightgear-2020.3.19`, jeweils `build-gles3/` |
| Ziel | `/srv/mer/targets/SailfishOS-5.2.0.15-aarch64` |

Beim Einsteigen in die tmux-Sitzung erscheinen Steuerzeichen; einmal Enter
drücken, bevor der erste Befehl abgesetzt wird.

## Arbeitsweise

* Änderungen an fremden Quellen (OSG, SimGear) werden **nicht** von Hand
  editiert, sondern als Python-Skripte geschrieben, die einen eindeutigen
  Anker suchen und ersetzen. Sie heißen `ffp_gles<N>.py` (OSG) bzw.
  `sg_*.py` (SimGear) und sind idempotent. Nie `sed` oder `perl`.
* Kommentare und Commit-Nachrichten auf Englisch, Gespräch auf Deutsch.
* Vor jedem SimGear- oder FlightGear-Bau müssen die Desktop-OSG-Header aus
  dem Weg: `/srv/.../opt/fgfs/include/osg` nach `osg.desktop` umbenennen,
  danach zurück. Sonst wird gegen die falschen Header gebaut.
* Die GLES3-Bäume werden mit `configure-gles3.sh` aus dem Repo
  konfiguriert. Dort stehen die `-DSG_GLES2`- und GL-Konstanten-Flags, die
  sonst nur im CMake-Cache leben und beim Neukonfigurieren verlorengehen.
  **Kein LTO, keine CPU-Flags** — beides wurde gemessen und brachte nichts.
* Bibliotheken kommen per `docker cp` auf den Host und per `rsync` aufs
  Telefon. Kein SSH-Alias mehr benutzen, sondern `sebastian@192.168.1.21`.

## Diagnosewerkzeuge im Baum

Alle hinter Umgebungsvariablen, im Normalbetrieb kostenlos:

| Variable | Wirkung |
|---|---|
| `FGFS_GLES_TIMING=1` | Cull-, Draw- und Frame-Zeiten, auch im Draw-Thread |
| `FGFS_GLES_FAT=1` | schaltet die Lean-Optimierung ab (Vergleichsmessung) |
| `FGFS_NO_PBO=1` | blockierender Readback statt PBO |
| `FGFS_THREADING=…` | Threading-Modus überschreiben |
| `FGFS_DUMP_EVERY=N`, `FGFS_DUMP_PATH=…` | jedes N-te Bild als PPM ablegen |
| `OSG_GLES_DUMP_SHADERS=<dir>` | konvertierte Shader mit Original ablegen |
| `OSG_GLES_DEBUG_MINVERTS`, `_MAXLOG`, `_TEXNAME` | Drawables protokollieren, nach Textur filterbar |
| `OSG_GLES_DEBUG_ATTRSTATE=1` | GL nach dem Zustand des Texturkoordinaten-Attributs fragen |
| `OSG_GLES_DEBUG_ATTRLOC=1` | Attributposition im gebundenen Programm gegen Dispatch-Slot |
| `OSG_GLES_DEBUG_SETARRAY=1` | welchen Weg `setArray` nimmt |
| `OSG_GLES_DEBUG_TEXEL`, `_TEXCOORD`, `_MAGENTA` | Shader-Sonden |
| `SG_TECHNIQUE_PROBE=1`, `SG_TEXPARAM_PROBE=1` | SimGear: Technikwahl und Texturparameter |
| `SG_NO_OPTIMIZE=merge,index,vertex,flatten,share` | einzelne Optimizer-Durchgänge abschalten |

## Offener Fehler: schwarze Zifferblätter

Die runden Instrumente der c172p (Fahrtmesser, Höhenmesser, Variometer …)
zeigen ein schwarzes Zifferblatt. Die Zeiger, die Rahmen, das Panel, die
Funkgeräte und alles andere sind in Ordnung. Betroffen sind die
**feststehenden** Flächen; bewegte Teile (Kugel des Horizonts,
Kompassrose) funktionieren.

### Was gemessen ist

Im echten Fragment-Shader (`Compositor/Shaders/Default/default.frag`, per
Datei-Edit auf `fract(osg_TexCoord[0].st)` umgestellt) lesen die
betroffenen Flächen **Texturkoordinate (0,0)**; der Texel dort ist hell.
Alles davor ist nachweislich korrekt:

* das Modell (`asi.ac`) hat saubere UV-Werte;
* `osgDB` lädt drei Drawables mit je so vielen Texturkoordinaten wie Ecken
  und plausiblen Werten (mit dem minimalen Testfall geprüft, ohne
  FlightGear);
* die Geometrie trägt zur Zeichenzeit `texUnits=1 tex0=N size=2 bind=4`;
* GL meldet Slot 3 als aktiviert, Größe 2, ohne Fehler;
* das gebundene Programm hat `osg_MultiTexCoord0` ebenfalls auf Slot 3;
* die richtige Textur ist gebunden;
* Shader laufen auf diesen Flächen (Magenta-Test).

### Ausgeschlossen

NPOT-Texturen · Cubemap-Spiegelung · Lightmaps und ihr Faktor ·
Technik-Prädikate · fehlende StateSets am Geode · schrumpfende
Dispatcher-Listen · Attributbindungen · Texturmatrix im Effekt-Shader ·
Client-Arrays gegen Puffer-Objekte (`OSG_VERTEX_BUFFER_HINT`) ·
Lean-Modus · Beleuchtung · Modell-Optimizer (`MERGE_GEOMETRY`,
`INDEX_MESH`, `VERTEX_*`) · Rückfall-Shader · `unref-image-data` ·
Materialanimation.

### Nächster Schritt

Der minimale Testfall `osg-model-test.cpp` liegt bereit: er lädt ein
Modell nur mit OSG und zeichnet es offscreen, ohne FlightGear, SimGear,
Effekte oder Compositor. Bauen im Container:

```
sb2 -t SailfishOS-5.2.0.15-aarch64 g++ -std=c++11 -O1 osg-model-test.cpp \
  -I/opt/osg-gles3/include -L/opt/osg-gles3/lib \
  -losg -losgDB -losgUtil -losgGA -losgText -losgViewer -lOpenThreads \
  -o osg-model-test
```

Aufruf auf dem Telefon im Verzeichnis des Modells, mit
`LD_LIBRARY_PATH=/opt/osg-gles3/lib:/opt/fgfs/lib` und
`OSG_LIBRARY_PATH=/opt/osg-gles3/lib/osgPlugins-3.6.5`:

```
osg-model-test asi.ac /tmp/a.ppm tex   # normal
osg-model-test asi.ac /tmp/b.ppm tc    # fract(texcoord) statt Farbe
```

Zeigt `tc` dort Verläufe, liefert OSG die Koordinaten korrekt und der
Fehler sitzt in einer Schicht darüber — dann diese einzeln dazunehmen.
Zeigt es auch dort einfarbige Flächen, ist es OSG selbst, und der nächste
Schritt wäre ein GL-Mitschnitt (apitrace oder eine Sonde direkt vor
`glDrawElements`, die `glGetVertexAttribPointerv` und die ersten Bytes
des Zeigers ausgibt).

Ein Nebenfund aus dem Testlauf, der noch zu klären ist: OSG wählt für
diese Geometrie `fgfs_fallback_plain` — die **texturlose** Variante des
eingebauten Rückfall-Programms —, obwohl die Textur unmittelbar davor
hochgeladen und gebunden wurde. Die Entscheidung „texturiert oder nicht"
in `State::applyFallbackProgramIfNeeded` fällt offenbar zu einem
Zeitpunkt, an dem die Textur noch nicht als angewandt gilt. Das erklärt
zwar nicht den Hauptfehler (im Cockpit läuft `default.frag`), ist aber
selbst falsch und gehört korrigiert.

## Noch offen, unabhängig davon

* Zink stürzt mit der c172p nach etwa 40 Sekunden ab (Terminate-Handler);
  mit dem UFO und Basis-Szenerie läuft es.
* `TextureRectangle` gibt es unter ES nicht; der Compositor benutzt sie
  für Render-Ziele und meldet das bei jedem Frame.
* Die Testeingriffe in `Compositor/Shaders/Default/default.frag` und
  `default.vert` auf dem Telefon müssen zurückgesetzt werden
  (`cp <datei>.orig <datei>`), bevor gemessen oder ausgeliefert wird.

## Pakete

Drei RPMs, gebaut im Container:

* `fgfs-sailfish` (Zink-Stack, `fgfs-run`, `fgfs-scenery`, `fgtouch.xml`)
  — `bash build-runtime-rpm.sh zink`
* `fgfs-sailfish-gles` (GLES2- und GLES3-Stack) — `… gles`
* `harbour-fgview` — `cd ~/fgview-build && mb2 -t SailfishOS-5.2.0.15-aarch64 --no-fix-version build`

`AutoReqProv` ist aus, die `Requires` sind daher von Hand gepflegt und
stammen aus dem, was die Binärdateien tatsächlich laden.
