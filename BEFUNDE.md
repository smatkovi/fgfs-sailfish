# BEFUNDE — schwarze Zifferblätter

Jeder Eintrag: **was die Messung ausschließt** und **welche Annahme die
Messung selbst voraussetzt**. Die zweite Zeile ist die wichtigere: eine
Sonde, deren Voraussetzung nicht gilt, schließt nichts aus, sondern
erzeugt einen Scheinbefund.

Stand: 9. September 2026.

---

## B0 — Werkzeugumgebung: keine Kommandoausführung

**Messung.** `echo hello`, `true`, `/bin/echo test` über das Bash-Werkzeug,
im Vorder- und Hintergrund, mit und ohne Sandbox: alle beenden sich mit
Code 2, ohne jede Ausgabe. Eine Probe, die eine Datei anlegen sollte
(`echo alive > .../probe1.txt`), hat die Datei **nicht** angelegt.

**Was das ausschließt.** Der Kommandotext wird nicht ausgeführt. Die
Shell stirbt davor. Es ist also kein Problem des jeweiligen Befehls, der
Sandbox oder des Verzeichnisses — Umformulieren hilft nicht.

**Vorausgesetzte Annahme.** Dass die Ausgabedatei des
Hintergrundauftrags aussagekräftig ist. Sie wurde geschrieben und enthält
`[exited with code 2]` — damit ist `/tmp/claude-100000/` beschreibbar und
die tmpfs-Quote **nicht** die Ursache (das wäre die andere bekannte
Ursache für genau dieses Symptom).

**Schluss.** Übrig bleibt: es gibt keine echte bash. Claude Code baut
beim Start einen Shell-Schnappschuss, indem es das Profil mit bash
ausliest (`shopt`, `declare -f`); busybox `ash` kann das nicht. Das
erklärt Code 2 ohne Ausgabe.

**Folge für die Fehlersuche.** Alles Messende — Bauen im Container,
Lauf des Simulators, GL-Mitschnitt, der minimale Testfall — steht still,
bis entweder bash vorhanden ist oder die Befehle über `!` aus der
Eingabezeile laufen.

**Nachtrag — zweiter Ausführungspfad geprüft.** Das Monitor-Werkzeug
startet Befehle über eine eigene Route, nicht über die persistente
Shell. Auch dort: Exit 2, keine Ausgabe. Ebenso `locate` selbst als
Befehl (gegen den Verdacht, es liege am jeweiligen Programm).

**Was das ausschließt.** Dass es an einem bestimmten Befehl, an
`locate`, oder an der persistenten Shell allein liegt. Beide
unabhängigen Startwege scheitern identisch → die Ursache liegt darunter,
bei der Shell-Initialisierung selbst.

**Vorausgesetzte Annahme.** Dass Monitor wirklich einen anderen Pfad
nimmt und nicht dieselbe Shell wiederverwendet. Falls es dieselbe ist,
ist das kein zweiter Zeuge, sondern derselbe zweimal gehört — die
Aussagekraft wäre dann geringer, die Schlussfolgerung aber unverändert,
weil schon die Datei-Probe (B0) zeigt, dass der Befehlstext nie erreicht
wird.

---

## B0a — Auch der Dateiweg ist zu

**Messung.** Ohne Shell bleiben nur Lesen/Schreiben mit exakten Pfaden —
kein `ls`, kein `grep`, kein Glob. Versucht und **nicht** gefunden:

* `osg-model-test.cpp` im Arbeitsverzeichnis (laut UEBERGABE.md „liegt
  bereit" — liegt jedenfalls nicht hier),
* `default.frag` unter vier plausiblen FG_ROOT-Pfaden:
  `/opt/fgfs/share/flightgear/…`, `/opt/fgfs/fgdata/…`,
  `/opt/fgfs/share/fgdata/…`, `/home/defaultuser/fgdata/…`.

**Was das ausschließt.** Nur diese vier Pfade. **Nicht**, dass die
Dateien fehlen — FG_ROOT kann anderswo liegen.

**Vorausgesetzte Annahme.** Dass Rateversuche eine Verzeichnissuche
ersetzen. Tun sie nicht: vier Fehlschläge sind bei diesem Suchraum kein
Befund, sondern nur verbrauchte Zeit. Deshalb hier abgebrochen, statt
einen fünften Pfad zu raten.

**Was daraus folgt — und was es wert ist.** Das Telefon *ist* diese
Maschine. Sobald **ein** `find` gelaufen ist, sind Shader-Edits ohne
Shell möglich (Schreiben mit exaktem Pfad geht), und die
Sonden-Reihenfolge aus B1 lässt sich vorbereiten. Nur *starten* lässt
sich der Simulator ohne Shell nicht.

---

## B1 — Widerspruch in der bisherigen Beweiskette (aus UEBERGABE.md, ungemessen)

Kein neuer Messwert, sondern ein Abgleich der schon vorhandenen. Drei
Aussagen aus UEBERGABE.md stehen zusammen nicht:

1. Die betroffenen Flächen lesen Texturkoordinate **(0,0)**.
2. Der Texel bei (0,0) ist **hell**.
3. Die Fläche erscheint **schwarz**.

Aus 1 und 2 folgt eine helle Fläche. Beobachtet wird 3. Mindestens eine
der drei Aussagen misst also etwas anderes, als sie zu messen vorgibt.

**Was das ausschließt.** Nichts — und das ist der Punkt. Es entwertet
aber die Beweiskraft von 1: „liest (0,0)" wurde bisher als Ursache
gelesen. Wenn (0,0) hell ist, kann die Texturkoordinate die Schwärze
**nicht** erklären. Das Schwarz kommt dann aus einer anderen Quelle, und
die Koordinatenspur ist ein Nebenschauplatz — möglicherweise die
irreführende Sonde, nach der ausdrücklich zu suchen ist.

**Vorausgesetzte Annahmen — welche davon kippt, ist zu prüfen:**

* zu 1: dass `fract(osg_TexCoord[0].st)` im umgestellten `default.frag`
  überhaupt die Koordinate **dieser** Fläche zeigt und nicht die einer
  darüberliegenden. Und dass eine einfarbig dunkle Ausgabe „(0,0)"
  bedeutet — sie bedeutet zunächst nur „nahe 0 oder ganzzahlig", denn
  `fract(1.0) == 0.0`, `fract(2.0) == 0.0`. Eine perfekt gekachelte
  Koordinate wäre nicht unterscheidbar von gar keiner.
* zu 1: dass zur Messzeit dasselbe Programm gebunden war wie im
  Normalbetrieb. Der Nebenfund (`fgfs_fallback_plain`) zeigt, dass die
  Programmwahl für diese Geometrie schon einmal anders ausfiel als
  erwartet.
* zu 2: dass „hell bei (0,0)" an der Textur gemessen wurde, die zur
  Zeichenzeit wirklich gebunden ist, und nicht an der Bilddatei auf der
  Platte. Beides kann auseinanderfallen (Mipmap-Stufe, Format­wandlung,
  `unref-image-data`, Kompression).
* zu 3: dass „schwarz" wirklich Schwarz ist und nicht sehr dunkel —
  ein Faktor 0 aus Beleuchtung oder Materialfarbe sähe genauso aus.

**Nächste Prüfung, sobald wieder gemessen werden kann.** Die drei
Aussagen einzeln nachziehen, statt eine vierte Hypothese zu bilden:
Fläche mit konstanter Farbe im Shader übermalen (lebt der Fragment-Pfad
für *diese* Fläche?), dann `texture(tex, vec2(0.5))` fest verdrahtet
(liefert die gebundene Textur überhaupt etwas anderes als Schwarz?),
dann erst wieder die Koordinate. Der zweite Test trennt „falsche
Koordinate" von „falsche/leere Textur" — und genau diese Trennung fehlt
bisher.

**Auflösung des Widerspruchs — B2, siehe unten.** Der Widerspruch
verschwindet, wenn Aussage 2 („(0,0) ist hell") an der Bilddatei statt
an GL gemessen wurde. Dann sind alle drei Beobachtungen zugleich wahr
und zeigen auf **eine** Ursache.

**Verdachtsmoment, noch nicht geprüft.** Eine unter GLES3
unvollständige Textur (kein Mipmap-Satz bei Mipmap-Filter, oder gar
keine an der Einheit gebunden) liefert beim Abtasten **Schwarz**,
unabhängig von der Koordinate. Das würde 2 und 3 zugleich erklären und
1 zum Nebenschauplatz machen. Passt außerdem zum Nebenfund, dass OSG
`fgfs_fallback_plain` — die texturlose Variante — für diese Geometrie
wählt: beide Beobachtungen deuten darauf, dass die Textur zum
Entscheidungszeitpunkt **nicht als angewandt gilt**.

---

## B2 — Arbeitshypothese: das Texturkoordinaten-Attribut ist abgeschaltet

Keine Messung, sondern eine Zusammenführung. Sie erklärt alle drei
Beobachtungen aus B1 mit **einer** Ursache statt mit zweien.

**Der Kern: der V-Ursprung.** GL legt (0,0) in die **untere** linke
Ecke der Textur, ein Bildbetrachter zeigt die **obere** linke. Wer die
Bilddatei öffnet und „bei (0,0) ist es hell" notiert, hat damit
möglicherweise die *obere* linke Ecke beschrieben. Bei einem runden
Zifferblatt auf quadratischer Textur ist die untere linke Ecke der
schwarze Bereich außerhalb des Kreises — oder schlicht der schwarze
Rand. Dann gilt gleichzeitig:

* Koordinate ist konstant (0,0) — beobachtet,
* der Texel bei GL-(0,0) ist **schwarz** — nicht hell,
* die Fläche ist schwarz — beobachtet.

Kein Widerspruch mehr. Und die Schwärze braucht keine zweite Erklärung
(keine unvollständige Textur, keine Beleuchtung, kein Materialfaktor).

**Warum konstant (0,0)?** Ist ein Vertex-Attribut-Array *abgeschaltet*,
liefert GL den generischen Konstantwert des Attributs, und der ist
per Vorgabe **(0,0,0,1)**. Genau (0,0) — nicht „ungefähr", nicht
verrauscht, nicht verschoben. Das ist die charakteristische Signatur
eines abgeschalteten Arrays, und sie passt exakt auf das Messbild.

**Warum nur die feststehenden Flächen?** Bewegte Teile (Kompassrose,
Horizontkugel) hängen unter eigenen Transform-Knoten und werden vom
Optimizer nicht mit dem Rest verschmolzen; sie behalten ihren eigenen
Zeichenpfad. Die feststehenden Flächen sind die, die zusammengefasst
und über einen gemeinsamen, zwischengespeicherten Pfad gezeichnet
werden. Ein Zustand, der einmal falsch gesetzt und dann
wiederverwendet wird, träfe genau diese Teilmenge.

**Was gegen die Hypothese spricht — ehrlich vermerkt.** In
UEBERGABE.md steht: „GL meldet Slot 3 als aktiviert, Größe 2, ohne
Fehler." Das widerspricht der Hypothese direkt. Sie überlebt nur, wenn
diese Sonde etwas anderes befragt hat als den Zustand zur Zeichenzeit.

**Vorausgesetzte Annahme jener Sonde — und damit der Ansatzpunkt.**
Unter GLES3 liegt der Vertex-Array-Zustand in einem **VAO**.
`glGetVertexAttrib*` beantwortet die Frage immer für das **gerade
gebundene** VAO. Fragt die Sonde zu einem Zeitpunkt, an dem ein anderes
(oder das Vorgabe-)VAO gebunden ist als beim tatsächlichen
`glDrawElements`, meldet sie einen Zustand, der mit dem Zeichnen nichts
zu tun hat — sie sagt „aktiviert" über ein VAO, das nie gezeichnet
wird. Das ist der klassische Weg, wie diese Sonde irreführt, und es ist
genau die Art Scheinbefund, auf die zu achten war.

**Diskriminierende Messung — in dieser Reihenfolge:**

1. `probe_frag.py … const` → zeigt Grün? Dann läuft der Fragment-Pfad
   für diese Fläche, und `const`/`tex05` sind aussagekräftig.
2. `probe_frag.py … tex05` → **der entscheidende Test.** Feste
   Koordinate `vec2(0.5)`, also Bildmitte, koordinatenunabhängig.
   * Fläche zeigt jetzt Zifferblatt-Farbe → Textur ist in Ordnung, die
     **Koordinate** ist tot → B2 bestätigt, weiter beim VAO/Attribut.
   * Fläche bleibt schwarz → die **Textur** liefert nichts → B2
     widerlegt, und der Nebenfund `fgfs_fallback_plain` rückt ins
     Zentrum.
3. Erst danach die Koordinate erneut ansehen — und dann **nicht** mit
   `fract()`, sondern roh und mit Vorzeichen sichtbar gemacht, weil
   `fract()` jede ganzzahlige Koordinate auf 0 abbildet und damit
   „kein Array" von „gekachelt" nicht unterscheiden kann.

**Billiger Gegencheck, ganz ohne GL — noch offen.** Die Zifferblatt-Textur öffnen
und die **untere** linke Ecke ansehen. Ist sie schwarz, ist der
V-Ursprung die Erklärung für den Widerspruch und B2 gewinnt stark an
Gewicht — noch bevor der Simulator läuft.

---

## B3 — Der minimale Testfall zeichnet gar nichts (Sonde selbst entlarvt)

**Messung.** `osg-model-test asi.ac … tex` und `… tc`, beide 512×512.
Ergebnis beide Male: **eine einzige Farbe über das ganze Bild**,
rgb(38, 38, 51), 100,0 %. Dazu wiederholt
`ShadeModel::apply — not supported`, `TexEnv::apply — not supported`
und `OpenGL error 'invalid enumerant' at after RenderBin::draw(..)`.

**Was das ausschließt — nichts über Texturkoordinaten.** Und das ist
der Punkt. Die naheliegende Lesart („flach = konstantes Attribut =
B2 bestätigt") ist **falsch**, und zwar aus einem Grund, der in den
Zahlen selbst steht:

> `tex` und `tc` liefern **denselben** Wert.

Läge texturierte Geometrie mit konstanter Koordinate vor, müssten sich
die beiden Modi unterscheiden — `tc` gäbe `fract(0,0)`, also nahezu
Schwarz, nicht rgb(38,38,51). Zwei verschiedene Fragment-Programme, die
aufs Pixel genau dasselbe liefern, zeichnen nichts. rgb(38,38,51) ist
0.15/0.15/0.20 — eine typische **Hintergrund-/Clear-Farbe**.

**Schluss.** Das Bild ist zu 100 % Hintergrund. Die Geometrie ist nicht
im Bild: nicht geladen, nicht im Blickfeld, weggeclippt, oder der
Zeichenaufruf scheitert (die `invalid enumerant`-Fehler nach
`RenderBin::draw` sind ein Kandidat — `ShadeModel` und `TexEnv` sind
Fixed-Function-Reste, die es unter GLES nicht gibt).

**Vorausgesetzte Annahme, die gekippt ist.** Der Testfall setzt
voraus, dass das Modell überhaupt gerendert wird. Solange das nicht
unabhängig belegt ist, kann er über Koordinaten **prinzipiell** nichts
aussagen — er misst dann nur die Hintergrundfarbe. Genau diese
Voraussetzung wurde nie geprüft; UEBERGABE.md nennt als Erwartung
„zeigt `tc` dort Verläufe", ohne einen Fall dafür vorzusehen, dass
gar nichts erscheint.

**Eigene Sonde mitschuldig — korrigiert.** `ppmstat.py` meldete
„COMPLETELY FLAT. A constant vertex attribute looks exactly like this."
Das ist eine Deutung, die die Alternative „nichts gezeichnet"
unterschlägt, und sie hätte mich beinahe zu einer Scheinbestätigung von
B2 geführt. Das Skript vergleicht jetzt mehrere Bilder gegeneinander
und warnt ausdrücklich, wenn sie identisch sind.

**Nächster Schritt.** Nicht weiter über Koordinaten spekulieren,
sondern den Testfall reparieren, bis er nachweislich Dreiecke zeichnet
(z. B. Modell durch ein eingebautes Quad ersetzen, Kamera an der
Bounding-Sphere ausrichten, `invalid enumerant` abstellen). Erst ein
Testfall, der *irgendetwas* zeichnet, kann die Frage aus B2
beantworten. Dafür muss `osg-model-test.cpp` gelesen werden.

---

## B4 — GEFUNDEN: GL_QUADS gibt es unter GLES nicht

**Messung.** Der reparierte minimale Testfall (Kamera aus der Bounding-Box,
siehe B3) auf `asi.ac`, mit Ausgabe der Primitiv-Modi:

```
Needle: verts=9 texcoords=0  [TRIANGLES n=9] [QUADS 0x0007 n=8]
Face:   verts=4 texcoords=4  [QUADS 0x0007 n=4]   tex=[asi.rgb]
```

Gezeichnet werden **240 Pixel**. Die Face-Fläche ist 0.08 × 0.08 und
müsste bei dieser Projektion rund 302 × 302 = 91 000 Pixel bedecken.
Sie erscheint gar nicht. Die 240 Pixel sind die drei Dreiecke der
Needle — vorausberechnet auf ~250 Pixel, gemessen 240.

**Beleg über drei Modi hinweg**, alle mit denselben 240 Pixeln:

* `solid` → grün (eigenes Programm, keine Textur, keine Koordinate)
* `tc` → **schwarz**, weil die Needle *legitim* keine Texturkoordinaten
  hat und damit den generischen Konstantwert (0,0,0,1) bekommt
* `tex` → **weiß**, das Material `DefaultWhite`

Dass `solid` — mit `OVERRIDE`-Programm und abgeschaltetem
`GL_CULL_FACE` — dieselbe Fläche vermissen lässt, schließt Programmwahl,
Textur, Beleuchtung und Rückseitenaussortierung allesamt aus.

**Kontrollfall.** Ein von Hand gebautes Quad mit denselben
Texturkoordinaten, aber als `GL_TRIANGLE_FAN`, zeichnet einen vollen
Rot/Grün-Verlauf über 65 537 Farben. Derselbe Shader, dasselbe OSG,
dieselbe Kamera — nur der Primitiv-Modus unterscheidet sich.

**Ursache.** `GL_QUADS` (0x0007) existiert in OpenGL ES nicht. Der
AC3D-Lader erzeugt es aus jedem `SURF` mit vier `refs`. Der Mali-Treiber
zeichnet dann nichts — **ohne GL-Fehler**, was erklärt, warum die
Fehlerabfragen sauber blieben.

**Warum genau die feststehenden Flächen.** Ein Zifferblatt ist *ein*
Viereck, also fällt es komplett aus. Bewegte Teile (Kompassrose,
Horizontkugel) sind gekrümmte Flächen und werden trianguliert — sie
überleben. Das ist das Muster aus UEBERGABE.md, und es hat nichts mit
„feststehend gegen bewegt" zu tun, sondern mit „Viereck gegen Dreieck".
Die Korrelation war echt, die Erklärung war falsch.

**Was das über die alten Sonden sagt.** Geometrie, UV-Werte,
Attribut-Slot 3, `osg_MultiTexCoord0`, gebundene Textur — alles war
korrekt gemessen und alles war wahr. Sie setzen aber sämtlich voraus,
dass die Fläche *gezeichnet* wird, und prüfen nur die Vorbereitung des
Zeichenaufrufs, nie sein Ergebnis. Ein `glDrawElements` mit ungültigem
Modus durchläuft jede dieser Prüfungen unbeschadet. Das „liest (0,0)"
aus UEBERGABE.md stammt daher von einer *anderen* Fläche — vermutlich
einem texturkoordinatenlosen Teil wie der Needle, das genau diesen
Konstantwert liefert.

**Vorausgesetzte Annahme dieser Messung.** Dass die 240 Pixel wirklich
die Needle sind und nicht ein Rest der Face. Gestützt durch drei
unabhängige Wege: die vorausberechnete Fläche der Needle-Dreiecke
(~250 px gegen 240 gemessen), das `tc`-Schwarz (nur ein Drawable *ohne*
Texcoords kann konstant (0,0) liefern — die Face hat welche), und das
`tex`-Weiß (nur die Needle trägt `DefaultWhite`; die Face trägt eine
Textur).

---

## B5 — Fix bestätigt im minimalen Testfall

**Eingriff.** `ffp_gles30.py` auf `src/osgPlugins/ac/ac3d.cpp`:

* `GL_QUADS` → `GL_TRIANGLES`, jedes Viereck (v0,v1,v2,v3) zerlegt in
  (v0,v1,v2) und (v0,v2,v3) — genau die Zerlegung, die die GL-Spezifikation
  für `GL_QUADS` vorschreibt, also unveränderte Umlaufrichtung;
* `GL_POLYGON` → `GL_TRIANGLE_FAN`, für konvexe Polygone dasselbe
  Primitiv unter einem Namen, den GLES kennt. Konkave Flächen kommen hier
  nie an: der Lader schickt sie über `_toTessellatePolygons` durch
  `osgUtil::Tessellator`, der schon Dreiecke liefert.

Idempotent geprüft: zweiter Lauf meldet „schon aktuell".

**Messung nach dem Fix**, dasselbe Modell, dieselbe Kamera:

| | vorher | nachher |
|---|---|---|
| Primitiv-Modi | `QUADS` 0x0007 | `TRIANGLES` 0x0004 |
| `solid`, gezeichnete Pixel | 240 | **91 204** |
| `tc`, Farben | 2 | **51 344**, R/G über 0..240 |
| `tex`, Farben | 2 | **6 335** |

**Warum die 91 204 zählen.** Das ist keine „sieht besser aus"-Aussage.
Aus der Bounding-Box (0.08 Einheiten) und der Orthogonalprojektion
(0.1358 Einheiten auf 512 Pixel) folgt eine erwartete Kantenlänge von
302 Pixeln, also 91 204 Pixel Fläche. Vorhergesagt **bevor** gemessen
wurde, exakt getroffen. Die Fläche ist damit vollständig da, nicht
teilweise.

**Gegenprobe innerhalb der Messung.** In `tex` bleiben 74,2 %
Hintergrund gegenüber 65,2 % in `solid`. Das ist kein Widerspruch,
sondern erwartbar: das Zifferblatt ist **rund**, die Ecken der
quadratischen Textur sind durchsichtig. Quadrat minus einbeschriebener
Kreis wären ~19 600 Pixel; gemessen sind ~23 700, was zum UV-Bereich
0.05–0.94 statt 0–1 passt.

**Vorausgesetzte Annahme.** Dass der minimale Testfall denselben Pfad
nimmt wie der Simulator — dasselbe `osgdb_ac.so`, dasselbe OSG, dieselbe
GLES3-Bibliothek. Das gilt hier (beide laden aus
`/opt/osg-gles3/lib/osgPlugins-3.6.5`), aber der Simulator schiebt
SimGear-Effekte und den Compositor dazwischen. Solange die Gegenprobe im
Cockpit aussteht, ist bewiesen: die Ursache ist gefunden und im Lader
behoben. **Nicht** bewiesen: dass keine zweite Ursache darüber liegt.

**Alte Sicherung.** `osgdb_ac.so.prequads` liegt neben dem Plugin.

---

## B6 — Gegenprobe im Simulator: A/B am selben Bild

**Aufbau.** Zwei Läufe der c172p in LOWW, gleiche Szene, gleiche Uhrzeit,
gleiche Shader — der **einzige** Unterschied ist `osgdb_ac.so`. Bild je
über `FGFS_DUMP_EVERY=200` abgelegt, Ausschnitt des Instrumentenblocks.

| | altes Plugin | gefixtes Plugin |
|---|---|---|
| Fahrtmesser, Höhenmesser, Wendezeiger, Kurskreisel, Variometer, ADF, Drehzahlmesser | **schwarz**, nur Zeiger sichtbar | vollständige Skalen, Zahlen, Bögen, Beschriftung |
| künstlicher Horizont | funktioniert | funktioniert |

**Warum das den Fix beweist und nicht nur begleitet.** Es wurden zwei
Dinge geändert: das Plugin *und* das Zurücksetzen der Testeingriffe in
`default.frag`/`default.vert`. Der A/B-Lauf trennt beides sauber: in
**beiden** Läufen waren die Shader die unveränderten Originale, getauscht
wurde nur das Plugin. Der Unterschied kann also nur vom Plugin kommen.

**Der Horizont als eingebaute Kontrolle.** Er funktionierte vorher und
nachher. Seine Kugel ist eine gekrümmte, triangulierte Fläche — sie war
nie von `GL_QUADS` betroffen. Ein Fix, der *alles* verändert hätte, wäre
verdächtig; dass genau die vierseitigen Flächen zurückkehren und die
triangulierten unverändert bleiben, ist die erwartete Signatur.

**Vorausgesetzte Annahme.** Dass beide Läufe dasselbe Bild zeigen —
gleiche Kameraposition, gleicher Sonnenstand, kein Wetterunterschied.
Gegeben durch identische Startparameter und dieselbe feste Uhrzeit.

**Nebenbefund, miterledigt.** Die in UEBERGABE.md als offen vermerkten
Testeingriffe in `default.frag` und `default.vert` sind aus den
`.orig`-Sicherungen zurückgesetzt. Der erste Lauf nach dem Fix zeigte
noch das Regenbogenbild — was rückblickend selbst ein Beleg war: die
Zifferblätter zeigten dort **Verläufe** statt einer Fläche, waren also
bereits wieder gezeichnet.

---

## Ausgerollt

| Ort | Stand |
|---|---|
| `src/osgPlugins/ac/ac3d.cpp` im Container | gepatcht durch `ffp_gles30.py` |
| `build-gles3` (GLES3) | neu gebaut, auf `/opt/osg-gles3/…` kopiert |
| `build-gles` (GLES2) | neu gebaut, auf `/opt/osg-gles/…` kopiert |
| Sicherungen | je `osgdb_ac.so.prequads` daneben |
| Zink (`/opt/fgfs/…`) | **nicht angefasst** |

Zink läuft über Desktop-GL, und dort *gibt* es `GL_QUADS`; der Fehler
kann da nicht auftreten. Das ist begründet, aber **nicht gemessen** —
der Zink-Lauf stürzt mit der c172p ohnehin nach ~40 s ab (eigener,
unabhängiger offener Punkt).

**Noch zu tun für Dauerhaftigkeit.** Die Plugins wurden direkt aufs
Telefon kopiert. Für die Auslieferung muss `fgfs-sailfish-gles` neu
gebaut werden, damit der Fix im RPM landet.

---

## B7 — Paket gebaut und Inhalt geprüft

**Gebaut.** `fgfs-sailfish-gles-2020.3.19-8.aarch64.rpm`, 185 MB,
Release von 7 auf 8 erhöht (der Inhalt ändert sich, dieselbe
NVR-Kennung mit anderem Inhalt wäre falsch), Changelog-Eintrag gesetzt.

**Eine Falle, die zugeschnappt wäre.** `build-runtime-rpm.sh` packt die
Bäume aus dem **SDK-Ziel** (`/srv/mer/targets/…`), nicht vom Telefon.
Die gefixten Plugins lagen aber zunächst nur auf dem Telefon. Ohne
zusätzlichen Schritt wäre ein Paket entstanden, das exakt den alten,
fehlerhaften Lader ausliefert — und es hätte sich sauber gebaut,
sauber installiert und den Fehler mitgebracht. Die Plugins wurden
deshalb auch nach `…/opt/osg-gles/` und `…/opt/osg-gles3/` im Ziel
kopiert.

**Gegenprobe, nicht angenommen.** Das fertige RPM wurde mit `rpm2cpio`
entpackt und sein `osgdb_ac.so` byteweise gegen die frisch gebauten
Plugins verglichen — beide Backends: identisch. Damit ist belegt, dass
der Fix im Paket ankommt, statt es aus der Bauprotokollierung zu
schließen.

**Vorausgesetzte Annahme.** Dass die Ziel-Bäume ansonsten dem
entsprechen, was auf dem Telefon läuft. Falls dort unabhängige Drift
liegt, brächte eine Installation des Pakets mehr mit als nur diesen Fix.
Deshalb ist `-8` **gebaut und aufs Telefon gelegt, aber nicht
installiert**; installiert ist weiter `-7` mit von Hand kopierten,
gefixten Plugins.

**Nachtrag — installiert und im Betrieb geprüft.** `-8` ist auf dem
Telefon installiert (`rpm -q` bestätigt `2020.3.19-8`). Beide Plugins
aus dem Paket byteweise gegen die gebauten verglichen: identisch.
Simulatorlauf aus dem installierten Paket: alle Zifferblätter zeigen
ihre Skalen.

Vor der Installation wurden die vier Bäume nach
`/home/defaultuser/opt-gles-backup-vor-rpm8.tar.gz` (278 MB) gesichert,
weil es kein `-7`-Paket zum Zurückrollen mehr gibt — das Bauskript
räumt sein Arbeitsverzeichnis vor jedem Lauf ab. Platzbedarf war die
zweite Sorge: die Bäume belegen 793 MB auf `/`, wo nur 1,9 GB frei
sind; nachgerechnet und geprüft, es blieb reichlich übrig.

---

# Leistung des Grafikstapels

Eigene Messreihe, gleiches Vorgehen: erst messen, wo die Zeit hingeht.
Werkzeug: `perfrun.sh` (fester Einschwing- und Messzeitraum) und
`perfstat.py` (Mediane plus Messreihe, damit Ausreißer sichtbar bleiben
statt im Mittelwert zu verschwinden).

## P0 — Zwei Messfallen, die zuerst zuschnappten

**`pkill -f fgfs` bringt die Messung um, nicht den Simulator.** Das
Arbeitsverzeichnis heißt `fgfs-work`, das Muster passt also auch auf die
eigene Befehlszeile. Erklärt rückblickend jeden Exit-Code 144 in dieser
Sitzung. Seitdem `pkill -x fgfs`.

**Die 21 ms sind ein Übergangszustand, kein Betriebszustand.** Die
Messreihe über 300 s zeigt es unmissverständlich:

```
60 389 56 21 20 338 | 87 84 87 89 92 87 89 88 89 88 84 85 91 ...
   Ladephase          Plateau ab etwa t = 100 s
```

Wer früh misst, misst eine halb geladene Szenerie. Der eingeschwungene
Zustand auf LOWW mit der c172p ist **87 ms (11,4 fps)**, nicht 21 ms und
auch nicht die 31 ms aus UEBERGABE.md. Alle folgenden Messungen laufen
deshalb mit 150 s Einschwingzeit und 90 s Fenster.

## P1 — Wo die Zeit hingeht

Einfädig gemessen, weil nur dieser Pfad cull getrennt ausweist:

| | ms | Anteil |
|---|---|---|
| cull | 10,0 | 9 % |
| draw | 47,4 | 42 % |
| rest (App, FDM, Nasal, Readback) | 54,4 | 49 % |
| frame | 111,7 | 9,0 fps |

Dazu je Bild: **1015 Drawables**, aber nur 55 Modus- und 320
Attributwechsel.

**Was das ausschließt.** Zustandswechsel als Hauptkosten. 320 Wechsel auf
1015 Drawables ist ein gutes Verhältnis — die Lean-Optimierung arbeitet.
Wer hier weiter optimiert, holt nichts.

## P2 — Die GPU ist nicht füllratenbegrenzt

Derselbe Lauf mit **einem Viertel der Pixel** (512×384 statt 1024×768):

| | 1024×768 | 512×384 |
|---|---|---|
| draw | 47,4 | **51,0** |
| rest | 54,4 | 40,8 |

**Was das ausschließt.** Füllrate, Overdraw, Fragment-Shader-Kosten als
Engpass. Draw ändert sich bei einem Viertel der Pixel **nicht** — es
wird sogar minimal größer (Rauschen). Damit ist auch klar, dass „draw"
hier CPU-Zeit für das Absetzen der Befehle misst, nicht GPU-Ausführung.

**Nebenertrag.** „rest" fällt um 13,6 ms, und das ist der einzige
pixelproportionale Anteil — Readback plus der Punkt, an dem die GPU
tatsächlich fertig werden muss. Die GPU-Arbeit liegt also bei grob
13 ms, der Rest von „rest" (~40 ms) ist FlightGear-Logik.

**Vorausgesetzte Annahme.** Dass `--geometry` wirklich die
Renderauflösung ändert und nicht nur das Fenster skaliert. Gestützt
durch den Readback-Anteil, der genau mitskaliert — bei bloßer Skalierung
bliebe er gleich.

## P3 — Der Hebel: Zustand pro Zeichenaufruf

Wenn draw CPU-gebunden und pro Aufruf teuer ist, sind die Vertex-Arrays
der Verdächtige. Der minimale Testfall aus B4 hatte `vbo=0` gemeldet —
Client-Arrays, bei denen der Treiber je Aufruf kopiert.

Einfädig, sonst identisch:

| `OSG_VERTEX_BUFFER_HINT` | cull | draw | rest | frame |
|---|---|---|---|---|
| (nicht gesetzt) | 10,0 | 47,4 | 54,4 | 111,7 |
| `VERTEX_BUFFER_OBJECT` | 8,8 | 43,0 | 45,8 | 97,0 |
| `VERTEX_ARRAY_OBJECT` | 9,9 | **36,1** | 48,2 | **94,2** |

Im echten, mehrfädigen Betriebsmodus, gleiches Protokoll:

| | draw | rest | frame | fps |
|---|---|---|---|---|
| Grundlinie | 44,4 | 42,5 | 87,5 | 11,4 |
| `VERTEX_ARRAY_OBJECT` | **34,9** | 37,6 | **72,4** | **13,8** |

**17 % schneller, draw allein −21 %**, durch eine Umgebungsvariable.

**Bildprüfung, nicht nur Zeitmessung.** Ein Bild aus dem VAO-Lauf
abgelegt und angesehen: Cockpit, Zifferblätter mit Skalen, Gelände,
Bahn, Bäume, Himmel — alles korrekt. Schneller und falsch wäre kein
Gewinn, und VAO-Zustandsverwaltung ist genau die Art Umstellung, bei der
so etwas passieren kann.

**Vorausgesetzte Annahme.** Dass beide Läufe dieselbe Szene zeigen.
Gleiche Startparameter, gleiche feste Uhrzeit, gleiche Einschwingzeit —
die Wolkenlage unterscheidet sich sichtbar, was auf einen Rest an
Variabilität hindeutet. Der Unterschied von 15 ms liegt aber weit über
der Streuung der Messreihen (Grundlinie 73–104, VAO 61–80).

## P4 — Was danach noch offen ist

Nach VAO steht es etwa 35 ms draw gegen 38 ms rest.

* **Drawable-Zahl** ist der verbleibende Draw-Hebel. ~1000 Aufrufe je
  Bild bei ~35 µs Aufwand pro Aufruf; Füllrate ist es nachweislich
  nicht. Weniger, größere Batches wirken hier direkt.
* **~40 ms „rest" sind FlightGear-Logik**, nicht der Grafikstapel — FDM,
  Systeme, Nasal, Eigenschaftsbaum. Das ist inzwischen der größte
  Einzelblock und liegt außerhalb dessen, was am Stapel zu holen ist.
* **`TextureRectangle`** scheitert weiterhin bei jedem Bild (488
  Meldungen je ~70 s). Noch nicht als Leistungsfrage vermessen.

## P5 — ZURÜCKGEZOGEN, siehe P8

*(Die Schlussfolgerung dieses Abschnitts beruht auf einer kaputten Sonde.)*

### ursprünglicher Text

Nach der Messreihe: 10,7 GB von 11,6 GB belegt, 1,1 GB verfügbar, obwohl
**kein** Simulator mehr läuft. Die Prozess-RSS aller 844 Prozesse summiert
sich auf nur ~600 MB — die Lücke ist kernelseitig, vermutlich
Mali-dmabuf, das über die Läufe nicht zurückgegeben wurde.

Das ist heikel für die Reihenfolge: `vao-threaded` lief **vor**
`base-threaded`, also bei geringerem Druck. Wäre der Druck die Ursache
des Unterschieds, wäre die VAO-Verbesserung ein Artefakt.

**Ist sie nicht.** Die Grundlinie wurde zweimal gemessen, früh und spät:

* `kurve`, früh in der Sitzung, Plateau: **87 ms**
* `base-threaded`, ganz am Ende bei maximalem Druck: **87,5 ms**

Zwei Messungen unter sehr verschiedenen Speicherzuständen, 0,5 ms
auseinander. Der Speicherdruck wirkt sich auf die Bildzeit also nicht
messbar aus, und die 15 ms Unterschied zu VAO stehen.

**Trotzdem vermerkt:** vor weiteren Messreihen ist ein Neustart des
Telefons sinnvoll, und das nicht zurückgegebene dmabuf ist selbst einen
eigenen Blick wert.

## P6 — Fest eingebaut, und eine Korrektur an P5

`OSG_VERTEX_BUFFER_HINT=${OSG_VERTEX_BUFFER_HINT:-VERTEX_ARRAY_OBJECT}`
steht jetzt im `gles2|gles3`-Zweig von `bin/fgfs-run`, nach dem Muster
der übrigen Vorgaben dort, also weiter überschreibbar.

**Gegenprobe auf frisch gestartetem Telefon**, gleiches Protokoll:

| | draw | rest | frame | fps |
|---|---|---|---|---|
| `NO_PREFERENCE` (alter Zustand) | 39,3 | 34,8 | 74,1 | 13,5 |
| eingebaute Vorgabe | **31,3** | 34,9 | **66,6** | **15,0** |

**Korrektur.** Das sind **10 %**, nicht die 17 % aus P3. Die
Draw-Reduktion ist stabil (−20 % hier, −21 % dort), aber der Anteil an
der Bildzeit fällt kleiner aus, weil die ganze Maschine nach dem
Neustart schneller ist: die Grundlinie liegt bei 74 ms statt 87,5 ms.

**Damit ist P5 zu revidieren.** Dort hatte ich aus zwei übereinstimmenden
Grundlinienmessungen (87,0 früh, 87,5 spät) geschlossen, der
Speicherdruck wirke sich nicht aus. Das war zu stark: beide Messungen
lagen auf einer bereits belasteten Maschine, sie zeigten also nur, dass
der Zustand *innerhalb* der Sitzung stabil war — nicht, dass er neutral
war. Der Neustart beweist das Gegenteil: dieselbe Grundlinie fällt von
87,5 auf 74,1 ms, die Sitzung lief durchgehend rund 18 % zu langsam.

Die Aussage „VAO hilft" bleibt davon unberührt — sie stützt sich auf
A/B-Paare, die jeweils im selben Maschinenzustand gemessen wurden. Nur
die Prozentzahl war zustandsabhängig, und die richtige ist die vom
sauberen Telefon: **10 % Bildzeit, 20 % Draw-Zeit**.

**Lehre fürs Protokoll.** Vor einer Leistungsmessreihe neu starten, und
absolute Zahlen nur innerhalb einer Reihe vergleichen.

## P7 — ZURÜCKGEZOGEN, siehe P8

*(Es gibt kein Leck. Der Abschnitt beruht auf zwei kaputten Sonden.)*

### ursprünglicher Text

**Messung.** Nach dem Neustart 2,5 GB belegt. Nach etwa 25 Minuten
Messläufen — bei **null** laufenden Simulatoren — 7,0 GB belegt, Load
average 14,5. Ein Kontrollauf aus dem fertig verpackten Zustand ergab
dann 104 ms statt der 66,6 ms, die dieselbe Konfiguration eine halbe
Stunde vorher geliefert hatte.

**Was das ausschließt.** Dass die 104 ms ein Rückschritt durch die
Paketinstallation sind. Die eingebaute Vorgabe ist nachweislich aktiv
(`grep` auf die installierte Datei), die Draw-Zeit liegt bei 40 ms
gegenüber 39,3 ms der *alten* Einstellung auf der sauberen Maschine —
das ganze System ist langsamer, nicht die Einstellung schlechter.

**Was es belegt.** Rund **4,5 GB werden je halbe Stunde Messbetrieb
nicht zurückgegeben**, und zwar an keinen Prozess: die Summe aller
Prozess-RSS bleibt bei einigen hundert MB. Der Speicher kommt erst beim
Neustart zurück, nicht beim Prozessende. Das passt auf kernelseitig
gehaltene Mali-dmabuf-Puffer und auf sonst wenig.

**Vorausgesetzte Annahme.** Dass `free` den Verlust korrekt zuordnet.
Gestützt durch zwei unabhängige Beobachtungen: die Prozess-RSS-Summe
erklärt die Lücke nicht, und der Neustart gibt sie vollständig frei —
beides wäre bei gewöhnlichem Nutzerspeicher anders.

**Folge fürs Protokoll.** Die belastbaren Zahlen dieser Reihe sind die
A/B-Paare, die **unmittelbar nacheinander im selben Maschinenzustand**
gemessen wurden. Für die eingebaute Vorgabe ist das das Paar auf dem
frisch gestarteten Telefon:

| | draw | frame | fps |
|---|---|---|---|
| `NO_PREFERENCE` | 39,3 | 74,1 | 13,5 |
| eingebaute Vorgabe | 31,3 | 66,6 | 15,0 |

Absolute Bildzeiten aus verschiedenen Sitzungsabschnitten sind dagegen
nicht vergleichbar — die 87 ms aus P1/P3, die 74 ms hier und die 104 ms
im Kontrollauf sind derselbe Code auf einer unterschiedlich zugelaufenen
Maschine.

---

## P8 — Es gibt kein Speicherleck. Zwei kaputte Sonden, ein Phantom

Das ist die unangenehmste Stelle dieser Untersuchung: P5 und P7 waren
nicht ungenau, sondern falsch, und beide aus derselben Wurzel — ich habe
busybox-Werkzeugen geglaubt, ohne sie zu prüfen.

### Sonde 1: `pkill -x` beendet nichts

Auf busybox vergleicht `-x` die **ganze Befehlszeile** auf Gleichheit,
nicht den Prozessnamen. `pkill -x fgfs` trifft daher **nie** etwas und
schweigt dabei. Gemessen:

```
pgrep -x fgfs   -> nichts, rc=1
pgrep    fgfs   -> 7145
/proc/7145/comm -> fgfs
```

Ich war auf `-x` ausgewichen, weil `pkill -f fgfs` die eigene
Befehlszeile trifft (das Verzeichnis heißt `fgfs-work`) und die Messung
umbrachte — siehe P0. Der Ausweg war schlimmer als das Problem: statt
das Falsche zu beenden, beendete er gar nichts. Richtig ist auf busybox
`pkill fgfs` **ohne Flag**, das vergleicht den Prozessnamen.

Folge: jeder im Hintergrund gestartete Lauf, den ich mit `pkill -x`
„beendet" habe, lief weiter.

### Sonde 2: `ps -o rss` zählt falsch

```
busybox ps -o rss, Summe über 811 Prozesse:   814 MB
/proc/*/statm,     Summe über dieselben 811: 8567 MB
```

Ein Faktor 10. Auf diese 814 MB hatte ich das Argument gestützt, der
Speicher könne nicht bei Prozessen liegen und müsse deshalb kernelseitig
sein. Mit der richtigen Zahl fällt das Argument in sich zusammen.

### Sonde 3: die dmabuf-Summe war ebenfalls falsch gerechnet

Ich hatte die Größenspalte aus `/sys/kernel/debug/dma_buf/bufinfo` als
Hex gelesen; der Kernel gibt sie als `%08zu` **dezimal** aus (nur `flags`
und `mode` sind hex). Korrekt gerechnet sind es **244 MB in 54
Objekten**, und die größten gehören alle `hybris-gralloc`, also der
Sailfish-Oberfläche. FlightGear hält davon nichts. Selbst die Größe des
vermuteten Lecks war ein Rechenfehler.

### Die eigentliche Messung

Ein `fgfs` mit **2,9 GB** lief noch, während ich „kein Simulator läuft"
protokollierte — gefunden nicht mit `pgrep`, sondern durch direktes Lesen
von `/proc/*/comm`. Nach dem Beenden:

| | vorher | nachher | Differenz |
|---|---|---|---|
| belegt | 7 781 MB | 4 711 MB | **−3 070** |
| RSS-Summe | 8 555 MB | 5 654 MB | −2 901 |
| verfügbar | 4 287 MB | 7 595 MB | +3 308 |

Die freigegebene Menge entspricht dem RSS des Waisenprozesses. **Kein
Leck, kein dmabuf, kein Kernel.** Nur ein Prozess, den ich für beendet
hielt.

### Was das an den Leistungszahlen ändert — und was nicht

**Der „Endstand"-Lauf mit 104 ms ist erklärt und verworfen.** Während
seiner Messung lief die Waise aus dem Bildprüfungslauf mit. Zwei
Simulatoren teilten sich CPU und GPU.

**Das A/B-Paar für VAO ist davon nicht betroffen.** `fgfs-run` endet auf
`exec`, `$PID` ist also der Simulator selbst, und `kill $PID` in
`perfrun.sh` hat immer sauber beendet. Verwaist sind ausschließlich die
Läufe, die ich per Hintergrundbefehl gestartet hatte. Das Paar
(`NO_PREFERENCE` 74,1 ms gegen eingebaut 66,6 ms) lief unmittelbar nach
dem Neustart, vor dem ersten dieser Hintergrundläufe. Es steht.

**Vorausgesetzte Annahme, die hier gekippt ist.** Dass ein Werkzeug,
das eine Frage beantwortet, sie auch richtig beantwortet. `pgrep`
antwortete „kein Prozess", `ps` antwortete „814 MB" — beide zuversichtlich
und beide falsch. Die Lehre ist nicht „busybox ist schlecht", sondern:
**eine negative Antwort ist kein Befund, solange die Sonde nicht an einem
bekannten Positivfall geprüft wurde.** Ein einziges `pgrep fgfs` gegen
einen laufenden Simulator hätte das am ersten Tag aufgedeckt.

### Korrigiert

* `perfrun.sh` und `memprobe.sh` benutzen jetzt `pkill fgfs` ohne Flag
  und warnen, wenn danach noch etwas läuft.
* `memprobe.sh` summiert RSS aus `/proc/*/statm` statt aus `ps`.
* Die dmabuf-Summe wird dezimal gerechnet.

## P9 — Endstand, sauber gemessen

Mit reparierter Prozessbeendigung, null Waisen vor und nach dem Lauf,
5,2 GB freiem Speicher:

```
draw   33,7 ms
rest   34,9 ms
frame  68,5 ms  ->  14,6 fps
Reihe: 67 67 67 73 68 69 69 70 69 70 67 70 68 66
```

Die Streuung von 66–73 ms ist die engste dieser ganzen Reihe — genau das,
was zu erwarten ist, wenn nicht mehr zwei Simulatoren um dieselbe GPU
konkurrieren. Der Wert bestätigt den früheren sauberen Lauf (66,6 ms)
und ersetzt den verworfenen „Endstand" von 104 ms.

**Stand der Leistung, belastbar:**

| | frame | fps |
|---|---|---|
| vorher (`NO_PREFERENCE`) | 74,1 ms | 13,5 |
| ausgeliefert (VAO) | **68,5 ms** | **14,6** |

---

## P10 — Wolken oder Bäume? Eine Zählung entscheidet

**Frage 1: helfen Wolken abschalten?** Gemessen, `--disable-clouds
--disable-clouds3d`: 66,1 ms gegen 68,5 ms. **2,4 ms, also 3,5 %.**
Praktisch nichts.

**Frage 2: wo ansetzen?** Statt zu raten eine Zählung der Drawables mit
`OSG_GLES_DEBUG_MINVERTS=0 OSG_GLES_DEBUG_MAXLOG=4000
OSG_GLES_DEBUG_AFTER=180` — also erst nach vollständigem Laden. Über
rund vier Bilder:

| Textur | Anzahl | Anteil |
|---|---|---|
| `deciduous-alt.png` | 1311 | 33 % |
| `mixed-alt.png` | 1093 | 27 % |
| `stratus_sheet1.rgb` (Wolken) | 191 | 4,8 % |
| `container.rgb` | 180 | 4,5 % |
| Rest (Terminals, Häuser, Flugzeuge …) | je ≤ 59 | |

**60 % aller Drawables sind Bäume.**

**Kreuzprobe, die beide Fragen zugleich beantwortet.** Die Zählung sagt
für Wolken 4,8 % voraus, gemessen wurden 3,5 % Zeitgewinn. Zwei
unabhängige Wege, dasselbe Ergebnis — damit ist auch belegt, dass die
Wolken-Schalter tatsächlich gewirkt haben. Ein Nullergebnis allein hätte
ebenso gut eine wirkungslose Option bedeuten können.

**Vegetation abgeschaltet:**

| | draw | frame | fps |
|---|---|---|---|
| mit Bäumen | 33,7 | 68,5 | 14,6 |
| ohne Bäume | 18,7 | 45,3 | 22,1 |
| ohne Bäume, als Vorgabe im Starter | **17,7** | **40,8** | **24,5** |

Gegenüber dem Stand vor dieser Sitzung: **68,5 → 40,8 ms, 14,6 → 24,5
fps.** Draw fast halbiert, bei 60 % weniger Zeichenaufrufen — die
Zeichenaufruf-These aus P2 sagt genau das voraus.

**Zum Vergleich, gemessen aber NICHT eingebaut** (auf Wunsch bleiben
Auflösung, LOD und alles Weitere unangetastet): eine volle
Minimalkonfiguration mit LOD-Kürzung, ohne KI-Verkehr, Wolken, Gebäude
und Partikel käme auf 30,7 ms / 32,6 fps.

**Eingebaut.** In `bin/fgfs-run`, nach dem Muster der übrigen Vorgaben:

```
set -- "$@" "--prop:/sim/rendering/random-vegetation=${FGFS_TREES:-false}"
```

`FGFS_TREES=true` schaltet sie wieder ein. Bildprüfung: Bäume weg,
Wolken, Gelände, Bahn und Cockpit unverändert.

---

## P11 — Der Icon-Start ging an allem vorbei

**Messung.** `harbour-fgview` ruft **nicht** `fgfs-run` auf. `fgruntime.h`
baut Umgebung und Befehlszeile selbst und startet
`/opt/fgfs-gles3/bin/fgfs` direkt.

**Was das heißt.** Alles, was in `fgfs-run` eingebaut wurde, erreichte den
Start über das Icon nie — insbesondere `OSG_VERTEX_BUFFER_HINT`. Die
Bäume waren dort schon aus, aber über einen anderen Weg
(`vegetation-density=0` aus der Einstellungsseite).

**Vorausgesetzte Annahme, die hier gekippt ist.** Dass ein Fix am
Starter den Nutzer erreicht. Er erreicht nur den, der den Starter
benutzt. Zwei Startwege, die dieselbe Sache unterschiedlich
konfigurieren, sind die eigentliche Fehlerquelle — und die war nicht zu
sehen, solange nur über `fgfs-run` gemessen wurde.

**Behoben.** `OSG_VERTEX_BUFFER_HINT=VERTEX_ARRAY_OBJECT` steht jetzt
auch in `fgruntime.h`.

## P12 — Dichte null ist nicht dasselbe wie Bewuchs aus

**Messung.** `random-vegetation=true` zusammen mit
`vegetation-density=0`, sonst identisch. Zeitreihe über 180 s:

```
t=12s  109 ms
t=92s  798 ms
t=101s  97 ms
t=104s  22.9 ms
t=175s 716 ms     <- und dazwischen 71 s ohne 100 Bilder
```

Gegenüber `random-vegetation=false` im unmittelbar folgenden Lauf:
gleichmäßige 48,7 ms.

**Was das ausschließt.** Dass die beiden Schalter gleichwertig sind. Bei
`random-vegetation=true` läuft die Bewuchsplatzierung beim Kachelladen
weiter, auch wenn die Dichte null ist; die Ladeaussetzer kosten weit
mehr, als die Bäume je ans Zeichnen verloren hätten.

**Vorausgesetzte Annahme.** Dass die Aussetzer vom Bewuchs kommen und
nicht von der Hintergrundlast. Nicht sauber getrennt — der Lauf ist zu
verrauscht für eine Zahl. Für die Richtung reicht er: der Vergleichslauf
danach war gleichmäßig, unter derselben Last.

**Behoben, ohne die Frage weiter auszumessen.** Steht der Regler auf 0,
schickt die App jetzt `random-vegetation=false` mit, statt sich auf die
Dichte zu verlassen.

## P13 — Ton: es lag an XDG_RUNTIME_DIR

**Messung.** `fgfs` ist gegen OpenAL Soft 1.24.3 gelinkt, und diese
Bibliothek hat genau **ein** Backend einkompiliert: `pulse`. Ein
PulseAudio-Client findet seinen Socket über `XDG_RUNTIME_DIR`. Die App
setzt den auf `/run/display` (dort liegt der Wayland-Socket), und dort
gibt es kein `pulse`-Verzeichnis — der Socket liegt unter
`/run/user/100000/pulse/native`.

**Schluss.** Ton konnte nie funktionieren, unabhängig von jeder
FlightGear-Einstellung.

**Behoben.** `PULSE_SERVER` wird aus der eigenen Umgebung abgeleitet,
bevor `XDG_RUNTIME_DIR` für Wayland überschrieben wird — so steht keine
feste Benutzernummer im Quelltext.

**Nachgewiesen, nicht angenommen.** Mit der Änderung erscheint der
Simulator bei PulseAudio:

```
media.name = "Playback Stream"
application.process.binary = "fgfs"
```

**Eine irreführende Sonde unterwegs.** Der erste Testlauf brach mit
„Fatal: failed to connect to the server!" ab, was nach Tonproblem aussah
— es war Wayland. Meine Shell hat `WAYLAND_DISPLAY=../../display/wayland-0`,
einen **relativen** Pfad. Ich hatte `XDG_RUNTIME_DIR` umgesetzt und den
relativen Pfad stehen lassen, damit zeigte er ins Leere. Der Testaufbau
war kaputt, nicht die Sache.

**Kosten, unmittelbares A/B:** 50,5 ms mit Ton gegen 47,8 ms ohne —
**2,7 ms**, etwa so viel wie die Wolken. Vorgabe deshalb aus, mit
Schalter auf der Einstellungsseite.

## P14 — Die Maschine ist nie ruhig

`top` bei null laufenden Simulatoren: nur 57,8 % Leerlauf. Aktiv sind
Androids `surfaceflinger` (8,4 %), `lipstick`, `system_server`,
`com.android.systemui`, Telegram — **und der Claude-Prozess selbst mit
7,2 %**.

**Folge fürs Protokoll.** Absolute Bildzeiten sind nur innerhalb eines
unmittelbaren A/B-Paars vergleichbar. Dieselbe Konfiguration ergab heute
40,8 ms und später 51,0 ms, ohne dass sich an ihr etwas geändert hätte.
Das ist dieselbe Lehre wie in P6 und P8, nur diesmal mit der Ursache
benannt.

## P15 — Zwei-Finger-Zoom kaputt: meine Zieh-Fläche hat ihn erstickt

**Symptom.** Nach dem Einbau der Zieh-Geste ging der Zoom nicht mehr.

**Ursache.** Ich hatte eine `MultiPointTouchArea` über die vorhandene
`PinchArea` gelegt, mit `maximumTouchPoints: 1`, und dazu in den
Quelltext geschrieben: „ein Punkt, damit der Zwei-Finger-Zoom noch zur
PinchArea durchkommt". Das war eine **Annahme, keine Messung** — und sie
ist falsch. Die obere Fläche greift sich den ersten Berührpunkt; die
`PinchArea` braucht aber beide, um eine Geste überhaupt zu erkennen. Mit
nur einem Punkt erkennt sie nichts.

**Behoben.** Ziehen und Zoomen liegen jetzt in **einer** Fläche mit
`maximumTouchPoints: 2`: ein Finger dreht die Blickrichtung, zwei ändern
das Blickfeld. Damit gibt es keinen Wettlauf um die Punkte mehr. Die
`PinchArea` ist weg.

Ein Zoom hält, bis **alle** Finger oben sind — sonst würde das Loslassen
eines Fingers das Ziehen an einer Stelle fortsetzen, an der der andere
Finger nie war, und das Bild spränge.

**Was daran zu lernen ist.** Der Kommentar im Quelltext hat die falsche
Annahme festgeschrieben und damit plausibel aussehen lassen. Eine
Begründung im Code ist keine Prüfung. Geprüft ist jetzt, dass die Seite
lädt; ob die Geste sich richtig anfühlt, kann nur am Gerät beurteilt
werden — das steht ausdrücklich noch aus.

---

## P16 — Meine QML-Prüfung war wertlos, zweimal

**Was ich behauptet hatte.** „Seite lädt sauber, keine QML-Meldung" —
gestützt darauf, dass beim Starten der App mit der jeweiligen Seite als
Startseite nichts auf der Standardausgabe erschien.

**Positivkontrolle, verspätet gemacht.** Eine Seite mit garantiertem
Fehler versehen (`VoelligUnbekannterTyp { }`) und dieselbe Prüfung
laufen lassen: **ebenfalls keine Ausgabe.** Weder auf stdout noch im
Journal, auch nicht mit `QT_LOGGING_RULES='*=true'`. Die App wird über
den Sailfish-Booster gestartet, ihre Ausgabe landet nicht in meiner
Shell.

**Was das ausschließt.** Dass die vorherigen „sauber"-Ergebnisse
irgendetwas bedeuten. Sie waren stumme Sonden — dieselbe Klasse Fehler
wie `pgrep -x` in P8, nur diesmal in meiner eigenen Prüfung.

**Funktionierender Ersatz.** `qt5-qtdeclarative-qmlscene` aus den
Jolla-Quellen installiert und ein Prüfgerüst gebaut, das jede Seite in
ein `ApplicationWindow` hängt und wieder beendet. **Erst am bekannten
Fehlerfall geprüft**, und der wird gemeldet:

```
file:///tmp/qmltest/pages/ZZTest.qml:4 Type AirportCountryPage unavailable
file:///.../AirportCountryPage.qml:11 VoelligUnbekannterTyp is not a type
```

Ohne den Fehler: keine Zeile. Erst dadurch heißt Schweigen etwas.

**Ergebnis mit dem geprüften Prüfer:**

```
AirportCountryPage  ok        FlatButton    ok
AirportListPage     ok        SettingsPage  ok
AirportSizePage     ok
FlightPage          uebersprungen (braucht die C++-Typen der App)
StartPage           uebersprungen (dito)
```

Zwei Seiten sind **nicht** geprüft, und das steht so im Bericht statt
als „ok" durchzurutschen. `check-qml.sh` liegt im Arbeitsverzeichnis.

**Eine Zwischenstufe, die auch nichts taugte.** Der erste Versuch der
Positivkontrolle benutzte `DiesesSymbolGibtEsNicht.foo` als
Bindungsausdruck — auch qmlscene schwieg dazu, weil das ein Laufzeit-
und kein Ladefehler ist. Erst ein unbekannter **Typ** ist ein
Ladefehler. Auch eine Positivkontrolle kann zu schwach sein.

## P17 — AI-Verkehr lässt sich doch begrenzen, aber nur in acht Stufen

**Der Kommentar im App-Code behauptete:** „FlightGear 2020.3 cannot cap
the number." Das stimmt nicht. `TrafficMgr.cxx:330` liest
`/sim/traffic-manager/proportion` (Vorgabe 1.0 in `defaults.xml`) und
verwirft Flugpläne danach.

**Aber die Umsetzung ist grob:**

```c
int randval = rand() & 100;      // & statt %
```

`rand() & 100` liefert nur Werte, deren Bits in 100 (0b1100100)
vorkommen — ausgerechnet: **0, 4, 32, 36, 64, 68, 96, 100**. Acht
Stufen, nicht 0–99. Ein Regler mit „50 %" wäre also gelogen.

Erreichbare Anteile:

| proportion | Anteil |
|---|---|
| 0.00 | 12,5 % |
| 0.10 | 25 % |
| 0.50 | 50 % |
| 0.80 | 75 % |
| 1.00 | 100 % |

**Und 0.0 schaltet nicht ab:** verworfen wird bei `randval > proportion`,
und `randval` kann 0 sein — jeder achte Flugplan käme durch. „Aus" muss
deshalb `enabled=false` setzen.

Die Einstellungsseite bietet jetzt genau diese Stufen an, mit den
tatsächlich erreichbaren Prozentzahlen.

---

## P18 — Prüfer nachgebessert: die riskantesten Seiten waren ausgenommen

In P16 stand: „FlightPage und StartPage übersprungen (brauchen die
C++-Typen der App)". Genau dort lagen die meisten Änderungen — die
Ausnahme war also an der schlechtesten Stelle.

**Behoben.** QML-Attrappen für `FgRuntime`, `ControlSender` und
`FrameItem` unter `qmlstubs/` (gleiche Mitglieder, kein Verhalten), die
`check-qml.sh` über `QML2_IMPORT_PATH` einbindet. Damit werden alle
sieben Seiten geprüft.

**Und wieder am Positivfall belegt**, diesmal an `StartPage` selbst:

```
mit eingebautem Fehler:  Type StartPage unavailable
                         VoelligUnbekannterTyp is not a type
nach Wiederherstellung:  ok
```

**Was das nicht prüft.** Die Attrappen haben die richtige Form, aber
kein Verhalten. Ein Tippfehler in einem Eigenschaftsnamen fällt auf, ein
falsches Argument an `startSim()` nicht.

## P19 — Einstellungen: geprüfte Namen, unveränderte Vorgaben

Für jede neue Einstellung erst der Nachweis, dass es die Eigenschaft
überhaupt gibt, und dann eine Vorgabe, die das bisherige Verhalten
beibehält:

| Einstellung | Eigenschaft / Option | in FG belegt durch | Vorgabe |
|---|---|---|---|
| Gebäude | `/sim/rendering/random-buildings` | `defaults.xml`: `false` | aus |
| Wolken flach | `/environment/clouds/status` | `options.cxx:1770` | an |
| Wolken volumetrisch | `/sim/rendering/clouds3d-enable` | `defaults.xml`: `true` | an |
| Tageszeit | `--timeofday=` | `options.cxx:1801` | noon |
| Sichtweite | `--visibility=` | `options.cxx:1849`, `fgOptVisibilityMeters` | automatisch |
| Bildratenbremse | `/sim/frame-rate-throttle-hz` | `defaults.xml`: `0` | ohne |
| Ruderkopplung | `/controls/flight/auto-coordination` | `controls.cxx:73` | aus |

**Zwei Fallen dabei.** Ruderkopplung liegt unter `/controls/flight/`,
nicht unter `/sim/` — geraten hätte ich falsch. Und Sichtweite ist
**keine** Eigenschaft, sondern eine Option, die eine Umgebungsvorgabe
füllt (`OPTION_FUNC`); als `--prop` gesetzt täte sie nichts.

Das feste `--timeofday=noon` in `fgruntime.h` ist raus, weil es sonst
zweimal auf der Befehlszeile stünde.

---

## P20 — Umzug nach /home, und die Gegenprobe dazu

**Warum.** Die vier GLES-Bäume sind 793 MB. `/` hat 9,5 GB, davon 2,3 GB
allein für Androids App-Unterstützung, und war bei 1,9 GB frei. `/home`
ist 218 GB groß mit 180 GB frei. Neuer Ort: `/home/.system/fgfs` —
dort liegen mit `.appsupport` und `.zypp-cache` schon andere
Systemdaten.

**Was vorher zu prüfen war, statt es zu hoffen.** Ob im Baum etwas auf
`/opt` verweist:

* `RPATH`: keiner zeigt auf `/opt` (ein Plugin trägt einen toten
  Bau-Pfad aus dem Container, der ohnehin nicht existiert);
* Zeichenketten in den Bibliotheken: keine;
* `/opt`-Verweise überhaupt: **17 Dateien, alle `pkg-config`** — reine
  Baumetadaten, zur Laufzeit belanglos.

Damit ist es ein Umzug der Verpackung, nicht des Baus.

**Automatisch beim Update, ohne Skript.** Die Spec legt die Bäume unter
`%{fgdir}` ab; `rpm -U` schreibt zuerst den neuen Ort und entfernt danach
die Dateien der alten Version — und die alten Dateien *sind* die unter
`/opt`. Gemessen:

| | vorher | nachher |
|---|---|---|
| `/` frei | 1,9 GB | **2,6 GB** |
| `/opt/osg-gles*`, `/opt/fgfs-gles*` | vorhanden | **weg** |
| `/home/.system/fgfs` | — | 792,8 MB |

**Gegenprobe, weil `/home` verschlüsselt ist.** Ein LUKS-Gerät könnte
langsamer sein. Dieselben Binärdateien einmal von jedem Ort, unmittelbar
nacheinander:

| Ort | frame |
|---|---|
| `/home/.system/fgfs` (LUKS) | **51,1 ms** |
| `/opt` (Wurzel-Dateisystem) | 56,1 ms |

Kein Nachteil, eher das Gegenteil — plausibel, weil die Bibliotheken
einmal beim Start gelesen und dann zwischengespeichert werden, während
FGData ohnehin schon immer auf `/home` lag.

**Und noch eine Zahl richtiggestellt.** Der erste Lauf nach dem Umzug
ergab 51,3 ms gegenüber 40,8 ms früher am Tag. Das ist **nicht** der
Umzug — das A/B-Paar oben zeigt es — sondern wieder die schwankende
Hintergrundlast aus P14.

**Zink bleibt in `/opt`:** 135 MB, und dort liegen `fgfs-run`,
`fgfs-scenery` und `fgtouch.xml`, auf die von mehreren Stellen mit
festem Pfad verwiesen wird.

**Rückfall eingebaut.** `fgfs-run` und `fgruntime.h` suchen erst
`/home/.system/fgfs`, dann `/opt`. Ein System mit neuem Starter und
altem Laufzeitpaket startet also weiter.

---

## P21 — Flugzeuge: zwei Fehler, die nur der echte Durchlauf zeigt

**Der erste stand schon in der App.** Die Auswahl bot „Piper J3 Cub" mit
der Kennung `j3cub` an. Es gibt sie nicht — weder in FGData noch im
Katalog, wo der Cub `J3Cub` heißt. FGData enthält überhaupt nur c172p
(mit fünf Varianten), `mibs` und `ufo`. Der Menüpunkt startete also
nichts.

**Der zweite war meiner.** Mein Katalogparser nahm die **erste** `<url>`
eines Pakets. Die Probe:

```
URL: .../previews/J3Cub_Preview/splash-j3-fg10001.jpg
unzip: End-of-central-directory signature not found
```

Ein Paket listet erst alle **Varianten** als `<id>`, jede mit
`<preview><url>…jpg</url></preview>`; die Download-Adressen kommen erst
nach `<dir>`. Die erste URL ist also meistens ein Bildschirmfoto.

**Behoben und gegengeprüft**, nicht nur repariert: gesucht wird jetzt die
erste URL, die auf `.zip` endet. Über den ganzen Katalog geprüft —
**648 von 648 Paketen** liefern damit eine Adresse, keines ohne.

**Was das über Prüfen sagt.** Beide Fehler hätte keine Ladeprüfung
gefunden, kein Übersetzer und kein QML-Prüfer. Nur der Durchlauf bis zum
Ende: herunterladen, auspacken, starten, hinsehen.

**Ende-zu-Ende belegt.** J3Cub aus dem Hangar geholt (65,8 MB), nach
`~/.local/share/harbour-fgview/aircraft/` ausgepackt, mit
`--fg-aircraft` gestartet — der Cub steht in Wien, und seine Texturen
werden nachweislich aus dem Downloadverzeichnis gelesen. Die 210
Fehlerzeilen im Protokoll sind ausnahmslos TerraSync-Szenerieobjekte,
nichts vom Flugzeug.

Nebenbei: die Zifferblätter des Cub sind lesbar. Der `GL_QUADS`-Fix aus
B4 wirkt auch auf einem Flugzeug, das beim Beheben noch gar nicht auf
dem Gerät war.

## P22 — Der Fortschritt fehlte, weil das Signal zu früh kam

**Gemeldet:** beim Herunterladen eines Flugzeugs wurde nicht angezeigt,
dass etwas läuft.

**Ursache, im eigenen Code.** `catalogBusy` fragt die Prozesse nach ihrem
Zustand. Die Reihenfolge war:

```cpp
_hangarStatus = tr("Downloading …");
emit catalogChanged();     // hier ausgeloest
_acDl.start(...);          // Prozess startet erst danach
```

Zum Zeitpunkt des Signals lief noch nichts, `catalogBusy` war also
`false` — und danach kam bis zum Ende des Downloads kein weiteres Signal.
Die Anzeige blieb aus, obwohl alles funktionierte. Dasselbe beim
Katalogholen.

**Behoben:** Signal nach `start()`, in beiden Fällen, mit dem Grund als
Kommentar daneben.

**Und gleich richtig gemacht.** Statt nur eines Drehrads jetzt Prozent
und Rate — Flugzeuge sind zig Megabyte groß, der Cub allein 66 MB, und
ein Drehrad ohne Zahl sieht aus wie ein Hänger. Dafür `aria2c` statt
`curl`, weil es einmal pro Sekunde eine Zusammenfassung ausgibt.

**Format geprüft, nicht angenommen:**

```
[#2b8a45 21MiB/65MiB(32%) CN:2 DL:1.9MiB ETA:22s]
```

**Und dabei einen zweiten Fehler gefunden.** Die Probe nahm den
**ersten** Treffer im Ausgabestück — bei mehreren Zeilen auf einmal wäre
das der älteste, der Balken liefe hinterher. Jetzt wird der letzte
genommen: gegen dasselbe Protokoll geprüft liefert „erster" 1 %, „letzter"
32 %.

Der Balken erscheint nur, solange es eine echte Prozentzahl gibt — beim
Katalogholen und beim Auspacken gibt es keine, und ein bei null
stehender Balken wäre eine schlechtere Antwort als gar keiner.

## P23 — „Bei 0 % verschwunden" war ein Erfolg, kein Fehlschlag

**Gemeldet:** Fenster mit Fortschrittsbalken bei 0 %, dann weg — für die
DA20.

**Nachgesehen statt vermutet.** Im Flugzeugverzeichnis lag die **DA40**,
angelegt um 15:12. Der Download hatte also funktioniert. Die volle Kette
danach von Hand nachgefahren, genau wie die App sie ausführt:

```
aria2 exit=0    23325182 Bytes
unzip exit=0    -> Katana/
```

**Erklärung.** Die DA40 ist 22 MB und die Leitung gab 4,2 MiB/s her — der
Download war in fünf Sekunden fertig. aria2 gibt einmal pro Sekunde eine
Zusammenfassung aus, die erste noch bei 0 %; danach war alles vorbei und
das Fenster verschwand. Was aussah wie ein Abbruch, war das Gegenteil.

**Was das ausschließt.** Einen Fehler im Download- oder Auspackweg. Was
es **nicht** ausschließt: dass die Anzeige taugt. Sie tut es nicht.

**Behoben — an der Rückmeldung, nicht am Mechanismus:**

* nach dem Ende bleibt eine Meldung stehen („Katana installed" bzw. der
  Fehlertext), sechs Sekunden lang und antippbar;
* die Laufzeile nennt jetzt auch die Megabyte (`19MiB/22MiB`), damit ein
  zu schneller Download überhaupt Bewegung zeigt.

**Lehre.** Eine Anzeige, die nur den Normalfall abbildet, ist bei einem
schnellen Erfolg von einem Fehlschlag nicht zu unterscheiden — und der
Nutzer meldet dann zu Recht einen Fehler, den es nicht gibt. Der Bericht
war richtig, die Diagnose daraus wäre falsch gewesen.

Die DA20 (Katana, `katana`/`Katana.zip`) ist beim Nachfahren mit
installiert worden und liegt jetzt neben DA40 und J3Cub.

---

## P24 — Cockpitglas undurchsichtig: unser Fehler, aber nicht der, den ich vermutet hatte

**Frage:** Liegt es am Flugzeug oder an uns?

**Antwort: an uns**, und das ist belegt. Mit `FGFS_GLES_NO_FALLBACK=1`
**verschwindet die Haube vollständig** — man sieht Bahn, Wolken und
Gelände. Gezeichnet wird sie also von unserem eingebauten
Rückfallprogramm, von dem das Flugzeug nichts weiß. Ein Modellfehler
könnte sich so nicht verhalten.

Die Katana bringt alles mit, was sie soll:
`MATERIAL "transparent" … trans 0.85`, Textur ohne Alphakanal, und der
AC3D-Lader setzt dafür `BlendFunc`, `GL_BLEND ON` und `TRANSPARENT_BIN`.

### Drei Hypothesen, alle widerlegt

**1. Das Rückfallprogramm ignoriert das Materialalpha.** Es rechnet
`osg_Color × Textur`; das Material kommt darin nicht vor. Klang
zwingend. Patch geschrieben (`ffp_gles31.py`), gebaut, ausgeliefert —
**Bild unverändert.**

**2. Dann kommt das Alpha eben nicht an.** Sonde: Alpha im Shader fest
auf 0.15 verdrahtet, gebaut, geprüft dass die Sonde wirklich im
ausgelieferten Binary steht (zweimal) und der Lauf diese Bibliothek
benutzt. **Ebenfalls unverändert undurchsichtig.** Damit ist der
Alphawert nicht die Ursache.

**3. Unsere Lean-Optimierung wirft den Blendzustand weg.**
`FGFS_GLES_FAT=1` schaltet sie ab. **Unverändert.**

### Methodenwechsel: engere Isolierung

Statt einer vierten Hypothese der minimale Testfall — `katana.ac` mit
reinem OSG, ohne FlightGear, ohne SimGear. Läuft in Sekunden statt
Minuten. Gemessene Pixel:

| | |
|---|---|
| Hintergrund | rgb(38, 38, 51) |
| Rumpf | rgb(213, 213, 213) |
| **Haube** | **rgb(52, 57, 70)** |

Weder Rumpfweiß noch reiner Hintergrund: **die Haube blendet.** Im
isolierten Fall funktioniert die Durchsichtigkeit also einwandfrei.

### Mein Patch war überflüssig und ist zurückgenommen

A/B im Testfall, mit und ohne `ffp_gles31`: **exakt dieselben Pixel.**
Die Haube war auch vorher schon durchsichtig. Meine Prämisse war
falsch — das Materialalpha erreicht den Shader ohnehin, offenbar über
`osg_Color`. Der Patch hätte es ein zweites Mal multipliziert, sobald
ein Material anliegt, also zu *durchsichtigem* Glas geführt. Er ist
entfernt, die Bibliothek zurückgebaut, die Rückfall-Shader stehen
wieder im Original.

### Was daraus folgt

Nicht das Flugzeug, nicht OSG selbst, nicht das Rückfallprogramm, nicht
die Lean-Optimierung. Undurchsichtig wird es **nur unter FlightGear** —
der Unterschied liegt also im FlightGear/SimGear-Pfad. Nächste
Verdächtige: SimGears Effekt- und Zustandsbearbeitung am Flugzeugmodell,
und die Reihenfolge der Render-Bins unter dem Compositor.

**Vorausgesetzte Annahme, die noch zu prüfen ist.** Dass die weiße
Fläche im FlightGear-Bild wirklich die Haube ist und nicht etwas
anderes Großflächiges davor. Dafür spricht, dass sie mit dem Rückfall
verschwindet; dagegen, dass sie exakt rgb(255,255,255) ist, während der
Rumpf im Testfall nur 213 erreicht. Das gehört als Erstes geklärt —
zum Beispiel mit einer Außenansicht.

## P25 — Das Glas: eingekreist bis auf einen Schritt

Fortsetzung von P24. Vier weitere Vermutungen widerlegt, dann per Sonde
identifiziert.

**Von außen ist alles in Ordnung.** Über Telnet auf „Chase View"
umgeschaltet (die Eigenschaft beim Start wird überschrieben, das
funktioniert nur zur Laufzeit): Flugzeug unauffällig, Haube normal,
Himmel blau. **Das Weiß gibt es nur in der Cockpitansicht.**

**Widerlegt, der Reihe nach:**

* *Die Haube von innen* — alle transparenten Flächen im Modell sind
  einseitig (`SURF 0x10`/`0x00`, Bit 0x20 nicht gesetzt), würden von
  innen also weggeschnitten;
* *das Innenraummodell* — enthält gar kein transparentes Material;
* *dessen Textur fehlt* — isoliert gerendert kommt `interior.ac` mit
  7661 Farben und dunklen Tönen heraus, ist also texturiert.

**Methodenwechsel: die Fläche soll sich selbst melden.** Beiden
Rückfallvarianten je eine Signalfarbe gegeben — `plain` magenta,
`textured` grün — und vorher am Binary geprüft, dass beide wirklich drin
stehen. Ergebnis: die Fläche wird **grün**, 62,4 % des Bildes. Also die
**texturierte** Variante; eine Textur liegt an.

**Dann die Koordinate ausgelesen** (`fract(fgfs_tc)` statt der Farbe):

```
waagrecht: u 0.80 -> 0.87     senkrecht: u 0.82 -> 0.80
           v 0.11 -> 0.16                v 0.12 -> 0.15
```

Sie **variieren** — kein konstantes Attribut, kein Koordinatenfehler.
Die Fläche tastet einen kleinen Bereich der Textur ab.

**Und der Texel dort, direkt aus der PNG gelesen** (eigener Minimal-
Decoder, weil kein Bildwerkzeug auf dem Telefon liegt):

```
u=0.80 v=0.11 -> rgb(233, 233, 233)
u=0.87 v=0.16 -> rgb(233, 233, 233)
```

Ein hellgrauer Glasfleck — genau richtig für Glas, dessen
Durchsichtigkeit aus dem Material kommt.

### Damit steht die Kette

Geometrie richtig · Koordinaten richtig · Textur richtig ·
**Durchsichtigkeit fehlt**. Und aus P24: mit fest verdrahtetem Alpha
0,15 in *beiden* Rückfallvarianten blieb es undurchsichtig — also ist
**das Blending zur Zeichenzeit aus**.

### Der eine offene Schritt

Warum ist es aus? Der AC3D-Lader setzt `BlendFunc`, `GL_BLEND ON` und
`TRANSPARENT_BIN` (ac3d.cpp:253–259), und SimGear leitet daraus
`blend/active` ab — aber **nur, wenn der Zustand eine `BlendFunc`
trägt** (`Effect.cxx:1465–1475`; ohne BlendFunc setzt es ausdrücklich
`false`). Die Rückfalltechnik 13 in `model-default.eff` übernimmt diesen
Parameter.

Zu prüfen ist also, ob die `BlendFunc` SimGears Modellverarbeitung
überlebt. Genau dort liegt der nächste Schnitt.

**Alle Sonden sind entfernt**, die Bibliothek steht wieder im
Auslieferungszustand (nachgeprüft: beide Rückfall-Shader im Original,
keine Signalfarben mehr im Binary).

## P26 — Eine gemessene Zahl, und ein Schaden, den ich selbst angerichtet habe

### Die Messung

Sonde direkt vor dem Binden des Rückfallprogramms, die **GL selbst** nach
dem Blendzustand fragt:

```
textured=1   GL_BLEND=0   src=0x302   dst=0x303
```

`src`/`dst` sind exakt `GL_SRC_ALPHA` / `GL_ONE_MINUS_SRC_ALPHA` — die
Blendfunktion aus dem AC3D-Lader **kommt bei GL an**. Der Schalter
`GL_BLEND` ist trotzdem **aus**: Attribute werden angewandt, der Modus
nicht.

**Was das noch nicht belegt.** Die Sonde protokolliert die ersten 24
Rückfall-Bindungen eines Laufs, und das können Himmelskuppel oder Panel
sein. Dass *die Haube* mit GL_BLEND=0 gezeichnet wird, ist damit
wahrscheinlich, aber nicht gezeigt. Der Versuch, die Sonde um den
Texturnamen zu erweitern, hat den Quellbaum beschädigt (siehe unten) und
wurde nicht zu Ende geführt.

**Ausgeschlossen wurde unterwegs:**

* die Modus-Filterliste `fgfsDeadMode` aus Runde 4 — `GL_BLEND` (0x0BE2)
  steht nicht darin;
* der GLES2-`switch` in `applyMode` — `GL_BLEND` fällt dort in den
  `default`-Zweig, also auf `glEnable`;
* `FGFS_GLES_FAT=1` — das schaltet nur die Fehlerprüfung um, nicht die
  Modusanwendung; mein früherer Test damit war **kein** gültiger Test der
  Filterliste, und das ist hier richtigzustellen;
* SimGear ohne BlendFunc — die Sonde in `MakeEffectVisitor` zeigt
  **32 Geodes mit `blendfunc=yes` und `modeBLEND=1`**, die Information
  ist also vorhanden, wenn der Effekt gebaut wird.

**Eine eigene Fehlmessung dabei:** dieselbe Sonde meldete
`blend/active=absent` für alle Geodes. Das war falsch — die Parameter
liegen unter `effectRoot->parameters->blend`, ich habe direkt unter
`ssRoot` nachgesehen.

### Der Schaden, und die Wiederherstellung

Beim Erweitern der Sonde habe ich mit einem Python-Schnitt zu viel aus
`State.cpp` entfernt. Der Versuch, das durch Zurücksetzen auf die
Originalquelle und erneutes Anwenden von `ffp_gles*.py` zu heilen, hat
es **verschlimmert**: die Patchkette ist nicht darauf ausgelegt, aus dem
Original heraus einzeln neu zu laufen — jeder erwartet die exakte
Ausgabe der vorherigen. Danach fehlten in `State.cpp` unter anderem der
Shaderkonverter, `sampler1D` (Runde 19, ohne die Felder und Wälder
schwarz werden) und die Fixed-Function-Uniformen.

**Wiederhergestellt** aus der veröffentlichten Quelle im Repo
(`osg/State.cpp`, Stand bis Runde 26) plus `ffp_gles27` und `29`.
Danach neu gebaut und **gegen die ausgelieferte Fassung geprüft**:

| | Hintergrund | Haube | Rumpf |
|---|---|---|---|
| aus dem RPM | (38,38,51) | (52,57,70) | (213,213,213) |
| neu gebaut | (38,38,51) | (52,57,70) | (213,213,213) |

Identisch. Die Laufzeit auf dem Telefon war schon vorher aus dem RPM
zurückgesetzt (`libosg` und `fgfs`, beide ohne Sondenreste).

**Warum es überhaupt eng wurde.** Die Repo-Kopie war vom 4. September
und damit zwei Runden alt. Deshalb ist jetzt `collect-sources.sh`
gelaufen: `osg/State.cpp` (2497 Zeilen, alle Merkmale), `Geometry.cpp`,
`Program.cpp`, `VertexArrayState.cpp` und neu `osg/ac3d.cpp` sind im
Repo auf dem aktuellen Stand. Die veröffentlichte Quelle passt damit
wieder zu den Binärdateien — und ist beim nächsten Mal eine belastbare
Rücksetzmarke.

**Lehre.** Ein Schnitt per Textersetzung in fremdem C++ braucht einen
eindeutigen Endanker, nicht „bis zur nächsten schließenden Klammer".
Und vor solchen Eingriffen gehört der Ausgangszustand gesichert — die
Patchkette ist eine Vorwärtsrichtung, keine Rücksetzmöglichkeit.

## P27 — Die Sonde greift, kann die Haube aber nicht benennen

**Sonde** (reine Einfügung nach eindeutigem Anker, Sicherung
`State.cpp.beforeprobe` vorher): bei jeder Rückfall-Bindung Texturname
und `glGetBooleanv(GL_BLEND)`. 1541 Zeilen:

```
1047  tex=[]             textured=1  blend=0
 247  tex=[]             textured=1  blend=1
 164  tex=[katana-4.png] textured=1  blend=0
  82  tex=[wxecho.rgb]   textured=1  blend=1
   1  tex=[tooltip.png]  textured=1  blend=1
```

**Was das belegt.** Blending funktioniert beim Rückfall grundsätzlich —
`wxecho.rgb` und 247 unbenannte Bindungen laufen mit `blend=1`. Es ist
also kein pauschaler Ausfall des Modus, sondern trifft bestimmte
Drawables.

**Zwei Fehlschlüsse, rechtzeitig erkannt.**

* `katana-4.png` (164 × blend=0) sah aus wie die Livery der Haube. Ist
  es nicht: die Livery-Dateien nennen nur `texture.png` und
  `arraial.p.png`; `katana-4.png` steht ausschließlich in
  `katana-set.xml`:
      55:        <path>Previews/katana-4.png</path>
  Ein Vorschaubild (`Previews/`), nicht die 3D-Haube. Falsche Fährte.
* `texture.png` — die tatsächliche Haubentextur — erscheint **0 Mal**.
  Nicht weil die Haube den Rückfall nicht nutzt (P24: ohne Rückfall
  verschwindet sie), sondern weil 1294 Bindungen `tex=[]` melden: das
  Bild wird nach dem Hochladen freigegeben, `getImage(0)` liefert null.
  **Meine Sonde kann die Haube am Dateinamen prinzipiell nicht
  erkennen.** Sie steckt unter den 1294 unbenannten — in welcher der
  beiden Gruppen (blend=0 oder 1), ist damit offen.

**Vorausgesetzte Annahme, die gekippt ist.** Dass der Bilddateiname zur
Zeichenzeit noch verfügbar ist. Für Flugzeugtexturen ist er es nicht.

**Nächster Schnitt, jetzt präzise.** Die Bindung nicht am Bildnamen,
sondern am **GL-Texturobjekt** (`getTextureObject(contextID)->id()`)
kennzeichnen, und beim Laden des Modells einmal protokollieren, welche
Objekt-ID die Geode mit dem transparenten Material bekommt. Dann ist die
Haube in der Sonde eindeutig, und ihr Blendzustand direkt ablesbar.
Beides ist eine reine Einfügung; die Sicherung liegt bereit.

**Warum es hier hält.** Das Telefon hat das Heimnetz verloren —
gespeichert ist `innonet-636D`, sichtbar sind vier andere, Verbindungs-
versuch: `No carrier`. Route über Mobilfunk. Der Bauhost ist damit
unerreichbar, bis das Telefon wieder in Reichweite ist. Alles Lokale ist
erledigt: `libosg` aus dem RPM zurückgesetzt (0 Sondenreste), Gerät im
Auslieferungszustand.

## P28 — Bewiesen: die Haube wird mit ausgeschaltetem GL_BLEND gezeichnet

Zwei reine Einfügungen, beide vorher gesichert, beide im Binary
nachgewiesen:

* **Sonde A** (`Texture2D::apply`, erster Upload, solange das Bild noch
  existiert): `TEXID id=<GL-Objekt> file=<Datei>`;
* **Sonde B** (`applyFallbackProgramIfNeeded`): `GLASSPROBE texid=<GL-Objekt>
  blend=<glGetBooleanv(GL_BLEND)>`.

Verknüpft über die Objekt-ID — nicht über den Dateinamen, der ist zur
Zeichenzeit weg (P27). 165 TEXID-, 3408 GLASSPROBE-Zeilen:

```
texture.png   id=111   blend=0: 92   blend=1: 0
interior.png  id=113   blend=0:  1   blend=1: 0

smoke.png                 id=198/202  blend=1: 88/89   <- Partikel blenden
wxecho.rgb                id=57       blend=1: 175     <- Wetterradar blendet
loww-terminals-east.png   id=213      blend=1: 1       <- Szenerie-.ac blendet
```

**Schluss.** `texture.png` tragen Rumpf *und* Haube. Die Haube wird über
den Rückfall gezeichnet (P24: ohne ihn verschwindet sie), also ist sie
unter diesen 92 Bindungen — und keine einzige davon hat `GL_BLEND` an.
**Die Haube wird ohne Blending gezeichnet.** Damit ist der weiße Fleck
erklärt: Texel (233,233,233) mit Alpha aus dem Material, aber ohne
Blendmodus → undurchsichtig hellgrau, unter Beleuchtung weiß.

**Was das ausschließt.** Dass der Modus unter GLES pauschal nicht gesetzt
werden kann — Partikel, Wetterradar und Szenerie-Modelle blenden. Und
dass es am `.ac`-Ladeweg als solchem liegt: `loww-terminals-east.png`
ist ein Szenerie-`.ac` über denselben SimGear-Effektpfad und blendet.
Der Unterschied liegt also zwischen **Flugzeugmodell** und
**Szenerieobjekt** — gleicher Lader, gleicher Effekt-Mechanismus,
verschiedenes Ergebnis.

**Vorausgesetzte Annahme.** Dass Objekt 111 die Haube einschließt und
nicht nur den Rumpf. Gestützt durch P24 (Haube hängt am Rückfall) und
dadurch, dass es keine zweite `texture.png`-ID mit Bindungen gibt; nicht
direkt gemessen, weil Rumpf und Haube dasselbe GL-Objekt teilen. Eine
Sonde pro *Drawable* statt pro Textur würde das trennen.

**Nächster Schnitt.** Warum bekommt ein Szenerie-`.ac` seinen Blendmodus
und das Flugzeug-`.ac` nicht? Kandidaten: ein eigener Effekt aus
`katana.xml`, oder eine Behandlung des Flugzeugmodells (Optimizer,
Livery-Ersetzung), die den Modus vom Geode abstreift.

## P29 — Zwei weitere Verdächtige entlastet, einer bleibt

**Cache-Verstellung: widerlegt.** Sonde C liest an derselben Stelle, was
`State` glaubt und was GL sagt. Für `texture.png` (Objekt 111):
**`gl=0 state=0`, 74 von 74.** Beide sagen OFF — der Modus wurde nie auf
ON gesetzt, nichts hat ihn hinter `State`s Rücken ausgeschaltet. (Global
gibt es 156 × `gl=1 state=0`, also *existiert* ein Vorbeiregeln an
`State` — SimGears Canvas/ShivaVG ruft `glEnable/glDisable(GL_BLEND)`
direkt — aber es trifft die Haube nicht.)

**Eine Überinterpretation von mir, richtiggestellt.** Die in P26
gemessenen `src=0x302 dst=0x303` hatte ich als Beleg gelesen, dass die
BlendFunc der Haube bei GL ankommt. OSG setzt Attribute nur bei
*Änderung* neu — der Wert war mit hoher Wahrscheinlichkeit ein
Überbleibsel eines vorherigen Drawables (Partikel). Er beweist nichts
über die Haube.

**Material-Animation: widerlegt.** Die transparenten Flächen liegen in
den `.ac`-Objekten `vitres` (148/148), `HDRvitres` (148/148),
`propdisc`, `vitrelampe`, `propblur`. Die einzige `material`-Animation
in `katana.xml` zielt auf Rumpf, Flügel, Ruder und `tourvitres` — den
*Rahmen* — nicht auf `vitres`. Sie baut den Effekt der Haube nicht um.

**Was damit feststeht.** Der Effekt des `vitres`-Geodes enthält keinen
eingeschalteten Blendmodus. Der Weg dorthin ist bekannt und jede Stufe
gelesen: `setTranslucent` → BlendFunc am Geode → `makeParametersFromStateSet`
setzt `blend/active` nur bei gefundener BlendFunc → Technik `<blend>`
→ `parseBlendFunc` → `setAttributeAndModes`. Irgendwo dazwischen geht es
verloren. **Die eine ungemessene Größe ist `parameters/blend/active` für
genau diesen Geode** — meine Sonde in P26 las `ssRoot/blend` statt
`ssRoot/parameters/blend`. Mit dem richtigen Pfad ist das die
entscheidende Messung; sie braucht einen SimGear+FlightGear-Bau.

## P30 — SimGears Parameter sind richtig; der Verlust liegt dahinter

Sonde in `MakeEffectVisitor` mit dem **richtigen** Pfad
(`parameters/blend/...`), transparente Geodes über das Material-Alpha
erkannt (0,15 = `trans 0.85` der Katana):

```
 27  alpha=0.15  blendfunc=1  modeBLEND=1  p.active=true  p.mode=true  p.hint=transparent
366  alpha=1     blendfunc=0  modeBLEND=8  p.active=false p.mode=absent p.hint=default
```

**Was das ausschließt.** `makeParametersFromStateSet` als Verlierer: für
jeden transparenten Geode kommen `blend/active=true`, `blend/mode=true`
und `rendering-hint=transparent` heraus — genau das, was `BlendBuilder`
(strukturierter Zweig → `parseBlendFunc` → `setAttributeAndModes`) und
`HintBuilder` (`TRANSPARENT_BIN` → in OSG ebenfalls `GL_BLEND` ON)
brauchen. Bis hierher ist alles korrekt.

**Damit verbleiben zwei Stellen.** Entweder verliert der Effektbau
(`mergePropertyTrees` → `makeEffect` → Technik/Pass) den Modus, oder der
Pass hat ihn und unsere OSG-Portierung wendet ihn beim Zeichnen nicht
an — P29 zeigte `gl=0 state=0`, also *kein* `glEnable` und ein Cache,
der nie ON sah. Genau diese Signatur entstünde, wenn `GL_BLEND` in
`State` als ungültiger Modus geführt würde (`ModeStack.valid=false`):
`applyMode` täte dann nichts und ließe den Cache stehen.

## P31 — GEFUNDEN: eine eingeschobene Technik ohne Blendzustand

Sonde direkt am fertig gebauten Effekt, nur für transparente Geodes
(Alpha < 0,99), je Technik und Pass:

```
technique=0  modeBLEND=8 (INHERIT)  blendfunc=0  hint=0 (DEFAULT)      program=0   <- gewaehlt
technique=1  modeBLEND=1            blendfunc=1  hint=2 (TRANSPARENT)  program=1
technique=2  modeBLEND=1            blendfunc=1  hint=0                program=0/1
technique=3  modeBLEND=1            blendfunc=1  hint=2                program=1
technique=4  modeBLEND=1            blendfunc=1  hint=2                program=1
technique=5  modeBLEND=1            blendfunc=1  hint=2                program=0
technique=6  modeBLEND=1            blendfunc=1  hint=2                program=1
```

**Der Befund.** `model-default.eff` hat vier Techniken (n=5, 10, 11,
13); der fertige Effekt hat **sieben**. Technik 0 ist eingeschoben,
ohne Programm — deshalb bindet unser OSG-Rückfall (P24) — und **ohne
Blendmodus, ohne BlendFunc, ohne Transparenz-Bin**. Weil sie die erste
gültige ist (TECHPROBE: Index 0 VALID), gewinnt sie. Alle anderen
Techniken tragen den Blendzustand korrekt: die Parameter (P30) sind
angekommen, `parseBlendFunc` und `HintBuilder` haben gearbeitet — nur in
Technik 0 hat sie niemand angewandt.

**Was das erklärt — rückwärts durch die Kette.**
* P29 `gl=0 state=0`: `State` sah nie ON, weil der angewandte Pass den
  Modus gar nicht enthält (INHERIT). Kein Cache-Problem.
* P28 92/92 ohne Blending, P24 Haube verschwindet ohne Rückfall.
* P26 `src/dst` korrekt: Überbleibsel — Technik 0 setzt keine BlendFunc.
* Warum Szenerie-`.ac` blendet: entweder bekommt sie diese Technik nicht,
  oder ihre Transparenz kommt aus der Textur und einem anderen Bin-Weg.
  Zu prüfen, aber nicht mehr nötig für den Fix.

**Woher die Technik kommt.** Sieben statt vier, programmlos und vorn:
das ist die Handschrift unseres eigenen `sg_gles_technique.py`, das für
GLES eine shaderlose Technik vorschaltet, damit Modelle überhaupt
gezeichnet werden. Sie übernimmt Programmlosigkeit — aber keinen der
Zustände, die die Parameter liefern. **Der Fehler ist unserer**, wie in
P24 vermutet, nur an anderer Stelle als jede der Zwischenhypothesen.

**Fix-Richtung.** Die eingeschobene Technik muss dieselben
zustandsrelevanten Bausteine erhalten wie Technik 13 (`<blend>`,
`<rendering-hint>`, `<cull-face>`, `<material>`, Texturen) — oder gar
nicht eingeschoben werden, wenn Technik 13 (die *echte* programmlose
Rückfalltechnik mit korrektem Zustand) auf GLES als gültig gewählt
werden kann.

## P32 — Der Mechanismus vollständig: geerbtes GL_BLEND=OFF

Besitzer-Sonde: für jede Rückfallbindung der Haube (`texture.png`,
Objekt 111) der komplette State-Set-Stapel mit Modus und Besitzer.
63 von 65 identisch:

```
vp=1024x768 |
  [m0 P Camera]                          <- GL_BLEND OFF, Szenenwurzel
  [m8 -  Camera:near]                    <- INHERIT
  [m8 -]
  [m8 P  Group:viewerSceneRoot]
  [m0 -  Group:fakeRoot]                 <- GL_BLEND OFF, nochmals
  [m8 -  Switch:rendererScene]
  [m8 -  Group:material animation group] <- tiefste Ebene, INHERIT
```

(m0 = OFF, m8 = INHERIT, P = Programm am Set.)

**Der Beweis, geschlossen.** `renderer_compositor.cxx:474` setzt auf der
Szenenwurzel `GL_BLEND OFF` — das ist der normale Grundzustand. Alles
unterhalb bis zur Geometrie steht auf INHERIT (m8), erbt also OFF. Die
gewählte Technik 0 (P31: eingeschoben, programmlos, `modeBLEND=8`) setzt
den Modus **nicht** auf ON. Ergebnis: die Haube wird mit `GL_BLEND=OFF`
gezeichnet — genau die Messung aus P28.

Ein normaler transparenter Geode kehrt das um: seine Technik trägt
`modeBLEND=1` und überschreibt das geerbte OFF. Die Techniken 1–6 des
Effekts täten das auch (P31). Nur die für GLES vorgeschaltete, gewählte
Technik 0 tut es nicht — sie erbt still den Grundzustand OFF.

**Damit ist die Ursache abschließend lokalisiert:** die shaderlose
GLES-Rückfalltechnik übernimmt Programmlosigkeit, aber keinen der
Zustände, die Transparenz braucht (`blend`, `rendering-hint`). Der
Fehler ist unserer, in der GLES-Anpassung von SimGears Technikwahl.
Fix-Richtung unverändert wie P31; der genaue Ort der Einschiebung wird
als Nächstes im Quelltext bestimmt, dann der Fix gebaut und wie stets
gegengeprüft (Modelltest-Pixel Haube ≠ Hintergrund und ≠ Rumpf).

## P33 — Das falsche Effektfile gelesen; die Technikwahl selbst ist in Ordnung

Sonde `sg_tniqbuild_probe.py`: jede gebaute Technik mit Effekt-Adresse,
Index, Property-Index `n` und Schema; dazu Effekt-Adresse an PASSPROBE
und TECHPROBE, sodass Aufbau, Pass-Zustand und Cull-Wahl verknüpfbar
sind. Katana, 86 318 Cull-Zeilen.

**Befund 1.** Die Techniken heißen n=0, 4, 6, 7, 8, 9, 19 — nicht 5, 10,
11, 13. FlightGear lädt `fgdata/Compositor/Effects/model-default.eff`
(Compositor-Zweig, n=8 generic-Shader, n=9 fixed-function, n=19 ALS),
nicht `fgdata/Effects/model-default.eff`. Alles, was ich in P31 aus
`Effects/*.eff` gelesen habe, betraf Dateien, die gar nicht geladen
werden. Technik 0 (`als-shadow`) kommt aus `mergeSchemesFallbacks`
(`Compositor/Effects/schemes.xml` → `ALS/shadow-pass`), ist immer gültig,
wird aber nur für das Schema `als-shadow` gewählt — nie für den
Hauptdurchgang (wanted=[] in allen 85 934 Zeilen). **P31s "eingeschobene
Technik ohne Blend, die gewinnt" ist damit widerlegt**: gewählt wird
Index 1 = n=4 (Ubershader, Programm, Blend ON, Bin transparent) bzw. bei
den einfachen Effekten n=8.

**Befund 2.** Sechs der 27 transparenten Effekte tauchen an der Cull-Wahl
nie auf — ihre Geodes gehen nicht durch `chooseTechnique`.

**Voraussetzung der Sonde:** dass die Effekt-Adresse beim Laden dieselbe
ist wie zur Cull-Zeit (kein Klonen). Geprüft: 0 Adressen nur an der
Cull-Wahl.

## P34 — Was die GPU wirklich bekommt (OSG-Zeichensonde)

`probe_draw.py`: in `Geometry::drawImplementation`, für Geometrien mit
Gesamtfarbe Alpha < 0,99: gebundenes Programm (mit Name), GL_BLEND,
Blendfaktoren, aktueller Wert des Farbattributs, Elternkette.

```
Haube  vitres/intvitres:  prog=fgfs_fallback_textured  blend=0  curColor a=0.15
                          <EffectGeode <Group <pick render group <Group:vitres <SGRotAnimTransform
Lampenglas vitre:         prog=36 (Ubershader)         blend=1  curColor a=0.15
                          <EffectGeode <Group:vitre <shadow animation
```

Die Haube wird also **mit dem Rückfallprogramm und ohne Blending**
gezeichnet, das Lampenglas desselben Modells mit Ubershader und Blending.
Der Alpha-Wert kommt bei beiden korrekt an (0,15) — nicht der Wert fehlt,
sondern der Blend-Modus. Das bestätigt P28 für die Haube, aber P28s
Zuordnung "texture.png-Zeichnungen = Haube" war nur zufällig richtig.

**Anmerkung zur Methode:** Der in P32 und hier mitgeloggte
State-Set-Stapel zeigt in beiden Fällen keine Pass-Ebene, obwohl beim
Lampenglas das Pass-Programm eindeutig gebunden ist. `getStateSetStack()`
gibt also nicht den vollständigen angewandten Zustand wieder — P32s
Stapel-Interpretation ist damit als Beleg wertlos, das Ergebnis (Blend
geerbt OFF) bleibt durch die GL-Abfrage bestehen.

## P35 — Eine Sonde, die nichts sagte, und warum

`sg_cull_probe.py` in `EffectCullVisitor::apply(Geode&)`: 0 Zeilen in
drei Läufen (auch mit Namensfilter), obwohl TECHPROBE aus derselben
Funktion 400 000 Zeilen schrieb. Ursache: `SG_LOG(C,P,M)` legt intern
einen `std::ostringstream os` an; mein Stream hieß ebenfalls `os`, also
loggte das Makro seinen eigenen, leeren Stream — 2000 leere
`[ALRT]:opengl`-Zeilen im Log. Die Sonde feuerte also genau bis zu ihrer
Kappung, nur ohne Text. Lehre: in SG_LOG nie einen Stream namens `os`
übergeben; vor dem Vertrauen in "keine Zeile" das Log auf leere Zeilen
prüfen.

## P36 — GEFUNDEN: die Haube ist ein EffectGeode **ohne Effekt**

Sonde korrigiert (`pos` statt `os`), Katana, 2000 Zeilen:

```
vitres / intvitres:      eg=1 effect=0  ss=0 dss=0 nd=1 alpha=0.15   <- Haube
tourvitres/inttourvitres eg=1 effect=E  technique=1 alpha=1          <- Rahmen
vitre (Lampenglas):      eg=1 effect=E  technique=1 alpha=0.15
```

Die Haubengeodes sind EffectGeodes, tragen aber **keinen Effekt** und
auch keinen State-Set mehr (weder am Geode noch am Drawable). Damit geht
`EffectCullVisitor` in den `!effect`-Zweig — normaler `CullVisitor`, kein
Pass, kein Blend-Modus, kein Programm → Rückfallprogramm und
GL_BLEND=OFF von der Szenenwurzel geerbt (P32, P34). Die Technikwahl
ist unschuldig; sie findet gar nicht statt.

Beide Haubenobjekte haben im Modell ein eigenes `<effect>`:
`intvitres` → `Katana/Models/Effects/Glass/glassrain.eff` (erbt
`Effects/model-default`, Technik n=4 mit Cubemap-Texturen und
`glass-ALS`-Shadern, n=9 fixed-function), `HDRintvitres` → `glass.eff`
(erbt `model-combined-transparent`). Das Lampenglas hat keins und
funktioniert.

**Nächste Frage:** liefert `makeEffect` für glassrain null (Fehler
laufen über `reportFailure`, nicht SG_LOG, und der FG-Fehlerbericht
wird nur als GUI-Dialog gezeigt — im Log steht nichts), oder wird der
Effekt danach gelöscht? Sonde in `EffectGeode::setEffect(0)` und am
`makeEffect`-Ergebnis, mit Geode-Adresse zum Verknüpfen.

## P37 — URSACHE: der Glas-Effekt scheitert am Compositor-Shaderpfad

Sonden `sg_seteffect_probe.py` (MAKEEFFECT-Ergebnis je transparentem
Geode, SETEFFECT(0)) — und diesmal das **FG_HOME-Log** (`~/.fgfs/fgfs.log`)
statt der Konsole gelesen: die Konsole zeigt `WARN:general` nicht, das
Dateilog schon.

```
Error:not found from shader/effect::Couldn't locate shader:Compositor/Shaders/glass-ALS.vert
Error:misconfigured from shader/effect::Failed to build technique:couldn't find shader Compositor/Shaders/glass-ALS.vert
MAKEEFFECT geode=0x237b6670 alpha=0.15 effect=0 inherits=[../Effects/Glass/glassrain] parent=[intvitres]
MAKEEFFECT geode=0x235b7600 alpha=0.15 effect=0 inherits=[Effects/Glass/glassrain]    parent=[vitres]
```

**Die Kette, geschlossen:**
1. Die Katana gibt beiden Haubenobjekten den Effekt
   `Models/Effects/Glass/glassrain.eff`; dessen Technik n=4 verlangt
   `Shaders/glass-ALS.vert` (+ .frag, noise, filters-ALS).
2. SimGear mit Compositor-Unterstützung (`Effect.cxx:955`) schreibt jeden
   Shaderpfad `Shaders/…` zu `Compositor/Shaders/…` um — **ohne
   Rückfall** auf den klassischen Pfad. `fgdata/Compositor/Shaders/`
   enthält nur FGDatas eigene Shader; `glass-ALS.*` liegt nur in
   `fgdata/Shaders/`.
3. `ShaderProgramBuilder` wirft `BuilderException`; `makeEffect` fängt
   sie, meldet über `reportFailure` (→ GUI-Dialog, den es hier nie gibt)
   und liefert **null**.
4. `MakeEffectVisitor` hat den State-Set des Drawables bereits in
   Parameter verwandelt und entfernt; er hängt `setEffect(0)` an den
   neuen EffectGeode (P36: `eg=1 effect=0 ss=0 dss=0`).
5. `EffectCullVisitor` nimmt den `!effect`-Zweig: kein Pass, kein
   Blend-Modus, kein Transparent-Bin, kein Programm → OSG-Rückfall
   (`fgfs_fallback_textured`) mit `GL_BLEND=OFF` von der Szenenwurzel
   (P34). Alpha 0,15 kommt an, wird aber nie verrechnet.

**Antwort auf die Frage "Fehler des Flugzeugs oder unserer?":** Keins von
beiden im engeren Sinn und beides ein Stück: Das Flugzeug verwendet einen
Effekt, der auf den klassischen Shaderbaum zeigt (auf FlightGear 2020.3
ohne Compositor korrekt); unser Bau hat den Compositor an, und SimGears
Compositor-Zweig bricht bei einem fehlenden Shader den *ganzen* Effekt
ab — samt fixed-function-Technik n=9, die gar keinen Shader braucht. Mit
GLES hat es nichts zu tun: derselbe SimGear-Code täte auf jedem
Compositor-Bau dasselbe (nicht gemessen, aus dem Code gefolgert).

**Was frühere Befunde bedeuten:** P24 (Rückfallprogramm zeichnet die
Haube) und P28/P32/P34 (GL_BLEND OFF) waren richtig; P31 (eingeschobene
Technik) war eine Fehldeutung der falschen `.eff`-Datei (P33). Die ganze
Technikwahl war nie beteiligt — sie fand für die Haube nicht statt.

**Fix (`sg_shader_fallback.py`, SimGear Effect.cxx):**
1. Wird `Compositor/Shaders/x` nicht gefunden, wird `Shaders/x` gesucht
   (der klassische Ort, für den Flugzeugeffekte geschrieben sind).
2. Eine Technik, die nicht gebaut werden kann, wird mit Meldung fallen
   gelassen; die übrigen bleiben. Erst wenn keine übrig ist, scheitert der
   Effekt wie bisher. Für die Haube bleibt so mindestens n=9
   (fixed-function, mit Blend und Transparent-Bin) — der Fix hängt damit
   nicht davon ab, ob glass-ALS unter GLES kompiliert.

**Prüfung (geplant):** MAKEEFFECT effect≠0 für vitres/intvitres; die
OSG-Zeichensonde (P34) mit dem gefixten fgfs: Haube mit `blend=1`; dann
Sichtprüfung im Cockpit.

## P38 — Fix verifiziert: die Haube wird mit Effekt und Blending gezeichnet

`sg_shader_fallback.py` gebaut (SimGear + fgfs-gles3), Katana, gefixtes
fgfs mit der OSG-Zeichensonde (P34) und den SimGear-Sonden:

```
MAKEEFFECT parent=[intvitres] inherits=[../Effects/Glass/glassrain] effect=0x561874d0   (vorher 0)
MAKEEFFECT parent=[vitres]    inherits=[Effects/Glass/glassrain]    effect=0x56b7b100   (vorher 0)
DRAWPROBE  vitres/intvitres:  prog=30  blend=1  src=0x302 dst=0x303  curColor a=0.15    (vorher prog=9 fallback, blend=0)
dropping technique: 0 Zeilen
```

Der klassische Pfad liefert `Shaders/glass-ALS.*`; der Shader kompiliert
und linkt unter GLES sogar (Programm 30 statt Rückfall), Technik n=4 wird
gewählt, GL_BLEND ist an, Blendfunktion SRC_ALPHA/ONE_MINUS_SRC_ALPHA.
Keine Technik musste fallen gelassen werden — der zweite Teil des Fixes
(Technik überspringen) greift hier nicht, bleibt aber als Absicherung
für Effekte, deren Shader unter GLES nicht kompilieren.

**Voraussetzung dieser Messung:** dass `blend=1` + Alpha 0,15 im
Ubershader-Pfad tatsächlich in sichtbare Transparenz mündet — d. h. der
Shader schreibt `gl_FragColor.a` aus `gl_Color.a`/Textur. Für
glass-ALS.frag nicht nachgelesen; die Sichtprüfung im Cockpit steht aus.
Sollte die Haube weiterhin undurchsichtig sein, ist der nächste Verdacht
der Alpha-Ausgang des Shaders, nicht mehr der Zustand.

## P39 — A320-Displays: die Canvas-Pfade waren unter GLES Attrappen

Kein Messlauf nötig, der Bau selbst sagt es: `simgear/canvas/CMakeLists.txt`
der GLES-Bäume hat `add_subdirectory(ShivaVG/src)` auskommentiert und
bindet stattdessen `vgu_stubs.c` ein — jede `vg*`-Funktion ein No-op
("Der Canvas zeichnet damit nichts - betroffen sind Glascockpit-Displays").
ShivaVG (die OpenVG-Implementierung hinter `canvas.Path`) spricht OpenGL
1.x: `glBegin/glVertex`, `glVertexPointer`, Matrixstapel, 1D-Texturen,
`glTexGen` — 39 solche Aufrufstellen in shPipeline.c/shPaint.c/shContext.c,
unter GLES nicht einmal deklariert.

Folge: Canvas-**Text** (osgText, eigene Shader) und **Bilder** (OSG-Texturen)
erscheinen, alle **Linien und Flächen** (PFD-Skalen, ND-Symbole, ECAM-Rahmen)
fehlen. Beim A320 ist praktisch das ganze Display Pfad → "nicht gerendert".

**Fix-Ansatz (`sg_canvas_gles.py`):** ShivaVG unverändert wieder mitbauen,
darunter ein Shim (`shGLES.h/.c`), der genau die benutzte GL-1.1-Teilmenge
auf ES2 nachbildet: Matrixstapel, Immediate-Mode-Puffer (QUADS → Dreiecke,
QUAD_STRIP → Strip), Client-Arrays über `glVertexAttribPointer` auf dem
Standard-VAO (VAO 0 gebunden, damit OSGs VAOs unberührt bleiben),
1D-Texturen als N×1-2D-Texturen (Float-Daten → Bytes), TexGen-Ebenen und
Texturmatrix im eigenen Vertex-Shader, ein eigenes Programm. Stencil,
Blend, ColorMask, Scissor sind in ES vorhanden. `CanvasPath` übergibt vor
`vgDrawPath` OSGs Projektions- und Modelview-Matrix (ES hat keinen
Matrixzustand zu erben) und markiert danach bei OSG Programm, Attribute,
Modi und Vertex-Arrays als schmutzig. Der Canvas-FBO bekommt bei Bedarf
schon jetzt `PACKED_DEPTH_STENCIL` (ODGauge.cxx:353), was der Stencil-Fill
braucht.

**Voraussetzungen, die die Prüfung klären muss:** dass der eigene Shader
auf dem Mali kompiliert; dass `state->dirtyAll*()` reicht, damit OSG nach
dem Fremdzeichnen wieder korrekt zeichnet (sonst: Artefakte in der
Hauptszene nach dem ersten Canvas-Frame); dass die Canvas-Kamera wirklich
einen Stencil-Puffer hat (sonst bleibt der Fill leer, nur Striche kommen).

## P40 — Canvas-Shim, erster Lauf: Pfade zeichnen, aber als Bounding-Boxen

`sg_canvas_gles.py` gebaut, A320 mit Stromversorgung (Start-Skript der
App), Frame aus `/dev/shm/fgfs-frame` (`shmdump.py --flip`):

* vorher (Stubs): Displays an, nur Zahlen/Text, keine Linie, keine Fläche.
* nachher (Shim): Symbole erscheinen — aber als **gefüllte Rechtecke**:
  PFD-Skalen als gelbe/grüne Blöcke, im ND ein weißes Polygon in der
  Größe des Kompassbogens, ECAM-Rahmen als Kästen. Keine `shGLES`-Meldung
  im Log, der eigene Shader kompiliert also.

**Deutung:** ShivaVG zeichnet Füllung und Strich über den Stencil-Puffer
(Kontur → Stencil, dann ein Paint-Quad über die Bounding-Box mit
`glStencilFunc(GL_EQUAL,1,1)`). Ohne Stencil-Puffer besteht der Test
immer → jedes Paint-Quad malt seine ganze Bounding-Box. Genau das Bild.

**Warum kein Stencil:** `ODGauge::updateStencil` hängt
`PACKED_DEPTH_STENCIL_BUFFER` mit dem *unsized* `GL_DEPTH_STENCIL`
(0x84F9) an; OSGs `RenderBuffer::createObject` ruft
`glRenderbufferStorage` damit auf — unter GLES `INVALID_ENUM`, kein
Speicher, FBO unvollständig; `RenderStage` meldet das nur auf NOTICE
(nicht im Log) und fällt auf das Fenster-Framebuffer zurück (Rendern ins
Fenster, Kopie in die Textur) — das Fenster (pbuffer) hat keinen
Stencil. Das erklärt zugleich, warum die Displays überhaupt erscheinen.

**Voraussetzung dieser Deutung:** dass der Rückfall auf FRAME_BUFFER
stattfindet (aus dem Code gefolgert, nicht gemessen). Der Fix
(`ffp_gles32.py`: unsized → sized Formate, `GL_DEPTH24_STENCIL8`) ist
zugleich der Test — bleiben die Boxen, ist der Stencil nicht die (ganze)
Ursache.

## P41 — Canvas verifiziert: Stencil war es; die A320-Displays sind da

`ffp_gles32.py` (OSG `RenderBuffer::createObject`: unsized
`GL_DEPTH_STENCIL` → `GL_DEPTH24_STENCIL8` unter GLES) gebaut, A320
mit Start-Skript, Frame `a320-canvas2-2.png`: PFD mit blau/braunem
Horizont, Fahrt- und Höhenband, ND mit Kompassrose und Bögen, ECAM mit
Triebwerksbögen und Wheel-Seite, Standby-Instrumente — Linien und
Flächen, keine Bounding-Boxen mehr. Die Außenszene im selben Frame ist
unverändert sauber, d. h. `dirtyAll*()` nach dem Fremdzeichnen reicht
OSG, um seinen Zustand wiederherzustellen.

Damit steht die Kette für "Displays nicht gerendert":
1. ShivaVG durch Stubs ersetzt (P39) → gar keine Pfade.
2. Shim eingesetzt → Pfade, aber als Boxen (P40).
3. FBO ohne Stencil, weil der Renderbuffer unter GLES ein sized Format
   braucht (P40/P41) → mit Fix: korrekte Füllung und Striche.

Offen, nicht gemessen: Gradienten-Paints (1D-Textur, TexGen) — im A320
kommen sie offenbar nicht vor oder fallen nicht auf; Muster-Paints
(`vgDrawImage`) sind nicht implementiert (Rohrfunktionen, kein Absturz).

**Nachtrag (RPM-11):** dieselbe Prüfung mit den aus dem RPM installierten
Binärdateien (`a320-rpm11b-5.png`): PFD, ND, ECAM vollständig; das
`libosg` im RPM unterscheidet sich vom getesteten Bau in 169 von 4,7 M
Bytes (Relink, Build-ID), Verhalten identisch.

## P42 — Prüfung der Szenerie-Vorabprüfung: sieben echte Fehler, einer davon fatal

Drei unabhängige Prüfer (Werkzeug, Shell, App) über den Diff, jeder Fund
von zwei Skeptikern gegengeprüft. 16 bestätigte Befunde; die, die etwas
geändert haben:

1. **Fatal (App):** Die App startet gar nicht `fgfs-run`, sondern die
   FlightGear-Binärdatei direkt (`startSim()` baut Umgebung und Pfade
   selbst). Mein `--region` wäre als unbekannte Option an FlightGear
   gegangen — gegengeprüft auf dem Gerät: `Unknown command-line option:
   region` und sofortiger Abbruch. **Die ganze Funktion hätte den Start
   unbenutzbar gemacht.** Umgebaut: die App führt `fgfs-scenery` selbst
   als eigenen Prozess aus (Prüfung, dann bei Bedarf Abruf), mit
   Fortschritt aus aria2 und `stopSim()`, das ihn mitnimmt.
2. **404 zählt nicht als Fehler** (`walk`/`fetch_any`): Ein Lauf, in dem
   jeder Index 404 liefert, endete mit „nichts zu tun" und **vermerkte die
   Region als fertig**; jede spätere Prüfung sagte „vorhanden", obwohl
   nichts auf der Platte lag. Reproduziert mit lokalem HTTP-Server. Jetzt
   zählt jeder nicht gelesene Index als Fehler, `fetch_any` probiert bei
   404 erst die anderen Spiegel, und ein Teilbaum ohne einen einzigen
   gelesenen Index verhindert den Vermerk.
3. **Float-Schrittweite in `wanted_dirs`** verlor die östlichste
   Kachelspalte bei Längen knapp unter einer Zweierpotenz (z. B. −0,4543),
   die Region wurde trotzdem voll vermerkt. Jetzt ganzzahlige Kachelbereiche;
   nebenbei wickeln sich Längen an der Datumsgrenze korrekt um.
4. **`%.4f`-Rundung** des vermerkten Rechtecks ließ `--check` unmittelbar
   nach erfolgreichem Abruf scheitern (1 von 10 Stichproben). Jetzt wird
   jede Kante nach außen gerundet; Test: 0 von 20 Fehlschlägen.
5. **`--check` vertraute nur der Vermerkdatei**: Wer Kacheln löscht, um
   Platz zu schaffen, behielt eine bestandene Prüfung. Jetzt wird
   zusätzlich geprüft, ob die Terrain-Kachelverzeichnisse da sind.
6. **Verwaiste Downloads:** `stopSim()` beendete nur den Simulator;
   `fgfs-scenery` und sein `aria2c` liefen weiter. Jetzt reicht das
   Python-Skript SIGTERM/SIGINT an sein aria2c weiter, und die App
   beendet den Szenerie-Prozess zuerst.
7. **App-Kleinigkeiten:** „Zurücksetzen" bewegte den neuen Schalter nicht
   (Silica bricht die `checked`-Bindung beim ersten Tippen); gespeicherte
   Koordinaten ohne zugehöriges ICAO hätten für *jeden* Flughafen Wien
   geladen — Koordinaten sind jetzt an das ICAO gebunden, sonst wird nichts
   geladen; `Requires: fgfs-sailfish >= 2020.3.19-8`.

Widerlegt wurde einer („eine abstürzende Prüfung ist nicht von ‚fehlt' zu
unterscheiden" — genau so gewollt: im Zweifel laden).

**Lehre zur Methode:** Der fatale Befund (1) war keine Detailfrage,
sondern eine falsche Grundannahme von mir — ich hatte aus dem Vorhandensein
von `fgfs-run` geschlossen, die App benutze es. Die Prüfer haben es
schlicht nachgesehen. Bei jedem „X ruft Y auf" vor dem Bauen einmal
nachsehen, nicht schließen.

## P43 — „Start tut nichts": zweimal dieselbe Wahrnehmung, zwei Ursachen

1. **0.9.7:** Das App-Log (`~/.local/share/harbour-fgview/fgfs.log`,
   11:31) zeigt `Unknown command-line option: region` und den
   Hilfetext — FlightGear brach sofort ab. Genau P42/1; 0.9.8 war da
   noch nicht installiert (13:38).
2. **0.9.8 hätte es wiederholt, anders:** ohne Vermerk läuft die App in
   den Abruf, und der stand mit `Terrain,Objects,Airports,Models` 20
   Minuten im weltweiten **Airports**-Baum (4450 Indizes, Models noch
   nicht begonnen). Nur Terrain und Objects sind nach Kacheln gefiltert
   (`keep_dir`); die anderen beiden sind Weltbäume — meine Erweiterung
   der Teilbäume war der Fehler, `fgfs-run` hatte von Anfang an nur
   Terrain,Objects. Messung: Terrain,Objects für LOWW = 22 Indizes,
   771 Dateien aktuell, 45 Sekunden.

**Fix (-9 / 0.9.9):** Abruf nur Terrain,Objects; `--check` liefert **2**,
wenn Kacheln auf der Platte liegen, aber kein Vermerk existiert (Bestand
von vor den Vermerken) — die App startet dann sofort. Prüfung mit echtem
Bestand: exit 2 vor dem Abruf, exit 0 nach 45 s Abruf (Vermerk
`15.5330 47.1230 17.5330 49.1230 Objects,Terrain`).

Ohne Models fehlen weiterhin die OBJECT_SHARED-Modelle in den .stg-Dateien
(„Failed to load OBJECT_SHARED Models/…" im Log) — Gebäude/Objekte, nicht
Gelände. Ein gefilterter Models-Abruf (nur die in den .stg der Region
referenzierten Modelle) wäre der saubere Weg; offen.

## P44 — Nachladen im Flug: FlightGears TerraSync tut es, mit vorgegebenem Spiegel

Frage: kann Szenerie *während des Flugs* nachkommen, wenn man die
vorab geholte Region verlässt? FlightGear bringt TerraSync mit; der
GLES-Bau enthält es (154 Treffer, `/sim/terrasync/*` vorhanden). Sein
Server wird per DNS-NAPTR auf `terrasync.flightgear.org` gesucht — auf
Mobilfunk-Resolvern die übliche Fehlerquelle („no DNS entry found"). Mit
`--prop:/sim/terrasync/http-server=<Spiegel>` entfällt die Suche
(`stripPath` entfernt nur Schrägstriche am Ende; die URL darf den
`/ws2`-Pfad tragen, `_httpServer + "/Terrain/…"`).

**Test 1 (Graz):** untauglich — e015n47 lag schon in der LOWW-Box.
**Test 2 (Innsbruck, 5 min):** TerraSync lief, fasste 18 691 Dateien
an (`.dirhash` im weltweiten Airports-Baum — es holt Airports-Archiv und
Models beim Start, `syncAirportsModels()`), aber e011n47 war noch nicht da.
Zu früh abgebrochen.
**Test 3 (Innsbruck, lang):** bei t+60 s 52 Dateien in e011n47, dann
e011n46, e010n47, e010n46 jeweils Terrain+Objects („Successfully
synchronized"); Frame: Piste 26 in Innsbruck mit Bergen.

**In der App (0.9.10):** Schalter „Update scenery in flight" →
`--enable-terrasync` + `http-server`-Property; aus per Vorgabe (Netz im
Flug, einmalig Airports-Archiv und Models). Verträgt sich mit
`fgfs-scenery`: gleiche Verzeichnisse, gleiche `.dirindex`; TerraSync legt
zusätzlich `.dirhash` und `RecheckCache` an.
