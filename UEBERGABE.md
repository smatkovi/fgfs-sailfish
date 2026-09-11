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

## Behobener Fehler: schwarze Zifferblätter

**Ursache: `GL_QUADS` gibt es unter OpenGL ES nicht.** Der AC3D-Lader
(`src/osgPlugins/ac/ac3d.cpp`) erzeugte aus jedem `SURF` mit vier `refs`
ein `GL_QUADS`-Primitiv. Ein Zeichenaufruf mit diesem Modus rasterisiert
unter GLES **nichts** — und meldet dabei **keinen GL-Fehler**, weil der
Modus nur auf dem Desktop-Pfad geprüft wird.

Ein Zifferblatt ist genau *ein* vierseitiges `SURF`, fällt also
vollständig aus. Zeiger und die gekrümmten bewegten Teile (Kompassrose,
Horizontkugel) tragen zusätzlich Dreiecke und überlebten deshalb. Das
sah aus wie „feststehend gegen bewegt", war aber „Viereck gegen Dreieck".

Deshalb meldete auch jede frühere Sonde „in Ordnung": Geometrie,
UV-Werte, Attribut-Slot 3, `osg_MultiTexCoord0`, gebundene Textur — alles
war korrekt und alles war wahr. Sie prüfen sämtlich die *Vorbereitung*
des Zeichenaufrufs, nie sein Ergebnis. Ein `glDrawElements` mit
ungültigem Modus durchläuft jede dieser Prüfungen unbeschadet.

### Der Fix

`ffp_gles30.py` auf `src/osgPlugins/ac/ac3d.cpp`:

* `GL_QUADS` → `GL_TRIANGLES`, jedes Viereck (v0,v1,v2,v3) zerlegt in
  (v0,v1,v2) und (v0,v2,v3) — die von der GL-Spezifikation
  vorgeschriebene Zerlegung, also unveränderte Umlaufrichtung;
* `GL_POLYGON` → `GL_TRIANGLE_FAN`, für konvexe Polygone dasselbe
  Primitiv unter einem Namen, den GLES kennt. Konkave Flächen laufen über
  `_toTessellatePolygons` durch `osgUtil::Tessellator` und sind schon
  Dreiecke.

Ausgerollt in `build-gles3` → `/opt/osg-gles3/…` und `build-gles` →
`/opt/osg-gles/…`, Sicherungen je als `osgdb_ac.so.prequads` daneben.
Zink ist nicht betroffen (Desktop-GL kennt `GL_QUADS`) und wurde nicht
angefasst.

**Paket gebaut:** `fgfs-sailfish-gles-2020.3.19-8`. Der Fix wurde dafür
auch in die Ziel-Bäume unter `/srv/mer/targets/…/opt/osg-gles{,3}/`
eingespielt — das RPM packt aus dem **Ziel**, nicht vom Telefon, sonst
wäre das alte Plugin ins Paket gewandert. Gegengeprüft durch Entpacken
des fertigen RPM und Vergleich gegen die frisch gebauten Plugins.
Installiert ist auf dem Telefon noch `-7`; die Plugins dort sind von Hand
auf den gefixten Stand kopiert.

### Belege

Nachvollziehbar in `BEFUNDE.md` (B3–B6). Kurz:

* minimaler Testfall auf `asi.ac`: vorher 240 gezeichnete Pixel, nachher
  **91 204** — der Wert, der sich aus Bounding-Box und Projektion
  vorausberechnen lässt, vor der Messung bestimmt und exakt getroffen;
* A/B im Simulator, identische Szene und identische Shader, getauscht nur
  `osgdb_ac.so`: schwarze Zifferblätter gegen vollständige Skalen;
* der künstliche Horizont funktioniert in beiden Läufen — die erwartete
  Signatur, denn seine triangulierte Kugel war nie betroffen.

### Werkzeuge, die dabei entstanden sind

Im Arbeitsverzeichnis auf dem Telefon:

| Datei | Zweck |
|---|---|
| `osg-model-test.cpp` | überarbeitet: Kamera aus der Bounding-Box, Modi `tex`/`tc`/`solid`/`quad`, Ausgabe der Primitiv-Modi |
| `build-model-test.sh` | Rundlauf Telefon → Container → bauen → zurück |
| `ppmstat.py` | wertet PPM als Text aus; warnt, wenn mehrere Renderings identisch sind |
| `ppm2png.py` | PPM → PNG mit Ausschnitt und Vergrößerung, ohne PIL |
| `probe_frag.py` | Shader-Sonden idempotent ein- und ausbauen |

**Warnung zum alten Testfall.** Die ursprüngliche Fassung von
`osg-model-test.cpp` setzte nie eine Kamera. Ohne Manipulator bleibt die
View-Matrix die Einheitsmatrix, die Kamera sitzt im Modell, und jedes
Bild kommt als reine Hintergrundfarbe heraus — was sich als „flache
Texturkoordinaten" lesen lässt und beinahe zu einer Scheinbestätigung
geführt hätte. Siehe `BEFUNDE.md`, B3.

## Behobener Fehler: undurchsichtiges Cockpitglas (Katana)

Belegkette in `BEFUNDE.md` P24–P38; die Kurzfassung:

* Die Haube ist ein `EffectGeode` **ohne Effekt** (P36). SimGear mit
  Compositor schreibt jeden Shaderpfad `Shaders/x` zu
  `Compositor/Shaders/x` um, ohne Rückfall; das Katana-Glas
  (`glassrain.eff`) braucht `Shaders/glass-ALS.vert`, das nur im
  klassischen Baum liegt. Der Technikbau wirft, `makeEffect` liefert
  null, der Geode verliert Effekt *und* State-Set und geht den normalen
  Cull-Pfad: Rückfallprogramm, `GL_BLEND` von der Wurzel geerbt = aus (P37).
* Der Fehler stand nur im **FG_HOME-Log** (`~/.fgfs/fgfs.log`); die Konsole
  filtert `WARN:general`. Merken: bei "silent failure" zuerst dort suchen.
* Fix `sg_shader_fallback.py` (SimGear `Effect.cxx`): klassischer Pfad als
  Rückfall; eine nicht baubare Technik wird einzeln fallengelassen statt
  den ganzen Effekt zu kippen. Messung P38: Haube mit Effekt, glass-ALS
  kompiliert sogar unter GLES, `blend=1`.
* Ausgeliefert in `fgfs-sailfish-gles-2020.3.19-10` — probenfrei gebaut:
  die Sondendateien aus dem Tarball wiederhergestellt (`touch` nicht
  vergessen, sonst hält ninja die alten Objekte für aktuell), dann nur die
  echten Patches `sg_gles_technique.py`, `sg_geode_stateset.py`,
  `sg_shader_fallback.py` (`shipbuild3.sh` im Container).

Lehren aus der Suche (P31–P35): die geladene `.eff` liegt unter
`fgdata/Compositor/Effects/`, nicht `fgdata/Effects/`; `SG_LOG` legt intern
einen Stream namens `os` an — eine Sonde mit eigenem `os` loggt leere
Zeilen; `State::getStateSetStack()` zeigt nicht den vollständigen
angewandten Zustand.

## Triebwerkstart für alle Flugzeuge (App 0.9.6)

`startEngine()` schickt ein Nasal-Skript über den Telnet-Kanal
(`--allow-nasal-from-sockets` wird mitgegeben): für jedes Triebwerk mit
wertbehaftetem `/engines/engine[i]/running` (FlightGear legt sechs leere
Knoten für jedes Flugzeug an) Magnetos/Gemisch/Primer *und* Cutoff aus,
Starter an; die Starter bleiben je Triebwerk bis `running`, höchstens 90 s
— eine JSBSim-Turbine bricht den Start ab, sobald der Starter fällt, und die
alten acht Sekunden reichten nur für Kolbenmotoren. Beim A320 wird
zusätzlich `acconfig.taxi()` gerufen (APU → Bleed → beide Triebwerke, wie
die FADEC es verlangt). Gas geht an `engine[0..7]`; die Protokolldatei
`fgtouch.xml` schreibt jetzt die App selbst. Testgeschirr: `enginetest.py
<Flugzeug> [s]` — startet fgfs wie die App, schickt dasselbe Skript (aus
dem C++-Quelltext gelesen) und beobachtet `running` je Triebwerk.

## Behobener Fehler: Canvas-Displays leer unter GLES (A320 & Co.)

Belegkette P39–P41. Zwei Ursachen übereinander:

* Die GLES-Bäume ersetzten ShivaVG (OpenVG, spricht OpenGL 1.x) durch
  No-op-Stubs (`vgu_stubs.c`) — Text und Bilder erschienen, alle Linien
  und Flächen fehlten. `sg_canvas_gles.py` baut ShivaVG unverändert wieder
  mit und legt einen Shim darunter (`ShivaVG/src/shGLES.h/.c`): genau die
  benutzte GL-1.1-Teilmenge auf ES2 (Matrixstapel, Immediate Mode als
  Dreieckslisten, Client-Arrays auf VAO 0, 1D-Texturen als N×1, TexGen im
  eigenen Shader). `CanvasPath` übergibt OSGs Matrizen und ruft danach
  `dirtyAllModes/Attributes/VertexArrays()`; das reicht, die Außenszene
  bleibt sauber.
* Danach kamen die Pfade als gefüllte Bounding-Boxen: kein Stencil. Der
  Canvas hängt `PACKED_DEPTH_STENCIL_BUFFER` mit dem unsized
  `GL_DEPTH_STENCIL` an, das `glRenderbufferStorage` unter GLES ablehnt →
  FBO unvollständig → OSG rendert still ins Fenster (ohne Stencil).
  `ffp_gles32.py` übersetzt in OSGs `RenderBuffer::createObject` die
  unsized Formate in sized (`GL_DEPTH24_STENCIL8`).

Verifikation: A320-Frame mit PFD-Horizont, Bändern, ND-Rose, ECAM-Bögen.
Nicht abgedeckt: Gradienten-/Muster-Paints (im A320 nicht sichtbar
nötig). Werkzeuge: `canvastest.py` (Start wie die App, Strom über das
Start-Skript, Frames alle 30 s), `shmdump.py` (Frame aus
`/dev/shm/fgfs-frame` als PNG, `--flip`), `pngstat.py`. Die PNGs lassen
sich hier direkt ansehen — das ersetzt die Sichtprüfung am Gerät.

## Szenerie-Vorabprüfung (App 0.9.9, fgfs-sailfish -9)

Vor jedem Start prüft die App **offline**, ob die Szenerie um den
Abflughafen da ist, und lädt nur, wenn nicht.

* `fgfs-scenery` merkt sich fertige Regionen in
  `<target>/.fgsync-regions` (Rechteck + Teilbäume) — nur wenn jeder
  angeforderte Index gelesen *und* alles geladen wurde. `--check --lat
  --lon [--margin]` beantwortet ohne Netz, ob eine vermerkte Region den
  Flughafen deckt, und prüft zusätzlich, ob die Terrain-Kachel­verzeichnisse
  wirklich existieren.
* **Die App ruft `fgfs-scenery` selbst auf**, als eigenen QProcess
  (`beginScenery` → `--check`, bei Bedarf Abruf, dann `launchSim`).
  Nicht über `fgfs-run`: `startSim()` startet die FlightGear-Binärdatei
  direkt, und FlightGear bricht bei einer unbekannten Option sofort ab —
  ein `--region` dort hätte den Start unbenutzbar gemacht (P42/1).
  `stopSim()` beendet den Szenerie-Prozess zuerst; das Python-Skript
  reicht SIGTERM an sein `aria2c` weiter.
* Koordinaten sind an ihr ICAO gebunden (`airportCoordsIcao`): ein mit
  0.9.6 gewählter Flughafen hat keine, und ohne diese Bindung hätte die
  App für *jeden* solchen Flughafen Wien geladen.
* Abruf nur **Terrain,Objects** — die beiden nach Kacheln gefilterten
  Bäume (22 Indizes, 45 s für LOWW). Airports und Models sind Weltbäume
  mit tausenden Indizes; sie mit anzufordern hielt einen Start 20 Minuten
  (P43). `--check` liefert 2, wenn Kacheln da sind, aber kein Vermerk:
  dann startet der Simulator sofort.
* Einstellungen → „Update scenery in flight": FlightGears eigenes
  TerraSync (`--enable-terrasync`, Spiegel per
  `/sim/terrasync/http-server` vorgegeben, weil die DNS-NAPTR-Suche
  mobil scheitert). Gemessen (P44): Innsbruck-Kacheln nach 60 s,
  Nachbarkacheln gleich mit. Aus per Vorgabe.
* Einstellungen → „Real weather": `--enable-real-weather-fetch` statt
  `--disable-…` (METAR vom Netz, auch im Flug; aus per Vorgabe).
* `fgfs-run --region` macht dasselbe für den Kommandozeilen-Gebrauch;
  `FGFS_SCENERY_REFRESH=1` bzw. der Einstellungs-Schalter „Refresh scenery
  on every start" erzwingt den Abgleich mit den Servern.

Sieben echte Fehler dieser Funktion wurden vor dem Ausliefern gefunden und
behoben — siehe BEFUNDE P42, insbesondere: ein Lauf, in dem jeder Index
404 lieferte, vermerkte die Region als fertig; die Float-Schrittweite
verlor die östlichste Kachelspalte; `%.4f` rundete das Rechteck nach
innen, sodass die Prüfung direkt nach erfolgreichem Abruf scheiterte.

## App 0.9.7: Szenerie vor dem Start, geordnete Telnet-Befehle

* (Von 0.9.8 abgelöst, siehe oben.) Auf einem frischen Gerät (Xperia 10 V) war nur Wasser zu sehen:
  `~/.fgfs/TerraSync` leer, die App hat nie Szenerie geholt — die auf dem
  Entwicklungstelefon stammte aus `fgfs-run --region` von Hand. Jetzt
  tragen die Flughafenlisten Koordinaten (`make-airports.py`, Einträge
  `[icao, name, bahn, lat, lon]`), die Startseite reicht sie an
  `startSim()` weiter, und fgfs-run bekommt `--region=lat,lon,1`: es ruft
  `fgfs-scenery` (aria2c) für Terrain/Objects/Airports/Models ein Grad
  rundum (~500 MB, danach nur Fehlendes) und startet dann. Die Statuszeile
  zeigt die aria2-Fortschrittszeilen.
* Kamera sprang beim schnellen Wischen zwischen zwei Richtungen: pro
  Befehlssatz eine neue Telnet-Verbindung, und FlightGear bedient seine
  Telnet-Clients in Poll-Reihenfolge — ein älterer Blickwinkel kam nach
  einem neueren an. Jetzt eine dauerhafte Verbindung (`telnetWrite`,
  Antworten werden gelesen und verworfen, damit der Empfangspuffer den
  Simulator nicht blockiert — das war der Grund für die kurzlebigen
  Verbindungen), Wisch-Updates auf eines je 50 ms zusammengefasst.
* Zweitgerät Xperia 10 V: `defaultuser@192.168.1.5`, SSH-Schlüssel liegt
  vor, aber kein passwortloses `sudo` — RPMs dort per `devel-su rpm -Uvh`.

## Lektionen und Szenarien (App 0.10.0)

**Lektionen** = FlightGears Tutorials, die es je Flugzeug gibt (c172p:
vierzehn, vom Preflight bis zum Triebwerksausfall). Knopf „Lessons" auf
der Flugseite → Liste aus `/sim/tutorials` (über den Telnet-Kanal
gelesen), Start per Nasal. Die Anweisungen zeigt FlightGear sonst in
einem PUI-Fenster, das dieser Bau nicht hat — die App liest sie aus
`/sim/tutorials/last-message` (alle 1,5 s) und blendet sie über dem Bild
ein. Vor dem Start wird die Szenerie am Ort der Lektion geholt (die des
c172p spielen in Hilo). Zwei Fallen, beide gemessen (BEFUNDE P45):
* Das Modul ist per Vorgabe aus; nach `io.load_nasal` muss
  `/nasal/tutorial/loaded` gesetzt werden, sonst bleiben alle
  Property-Handles nil.
* `/sim/tutorials/running` ist **1/0**, nicht true/false.

**Szenarien** = FlightGears AI-Szenarien aus `FGData/AI/*.xml` (27
gefunden, 7 mit Flugzeugträger). Auswahl auf der Startseite; bei einem
Träger startet das Flugzeug auf dem Deck (`--carrier` hat in FlightGear
Vorrang vor `--airport`) und die Szenerie wird **am Schiff** geholt, nicht
am Flughafen. AI-Modelle werden nur für ein Szenario eingeschaltet.

**Pause im Hintergrund** (Einstellungen, per Vorgabe an): `/sim/freeze/master`
und `/sim/freeze/clock`, dazu Bildrate auf 2 Hz — FlightGear zeichnet auch
eingefroren weiter, und das ist, was den Akku kostet. Ausgelöst über eine
gebundene Eigenschaft auf `Qt.application.active`, nicht über
`Connections` — ein falscher Signalname dort bleibt still.

## Noch offen, unabhängig davon

* Zink stürzt mit der c172p nach etwa 40 Sekunden ab (Terminate-Handler);
  mit dem UFO und Basis-Szenerie läuft es.
* `TextureRectangle` gibt es unter ES nicht; der Compositor benutzt sie
  für Render-Ziele und meldet das bei jedem Frame.

## Pakete

Drei RPMs, gebaut im Container:

* `fgfs-sailfish` (Zink-Stack, `fgfs-run`, `fgfs-scenery`, `fgtouch.xml`)
  — `bash build-runtime-rpm.sh zink`
* `fgfs-sailfish-gles` (GLES2- und GLES3-Stack) — `… gles`
* `harbour-fgview` — `cd ~/fgview-build && mb2 -t SailfishOS-5.2.0.15-aarch64 --no-fix-version build`

`AutoReqProv` ist aus, die `Requires` sind daher von Hand gepflegt und
stammen aus dem, was die Binärdateien tatsächlich laden.
