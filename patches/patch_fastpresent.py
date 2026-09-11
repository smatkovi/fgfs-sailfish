#!/usr/bin/env python3
"""
Schnellere Anzeige in FrameItem.

Bisher wandert jeder Frame dreimal durch den Speicher:
  1. 768 einzelne memcpy vom dmabuf ins QImage (zeilenweise gespiegelt)
  2. createTextureFromImage kopiert das QImage in eine GL-Textur
  3. die alte Textur wird verworfen und neu angelegt

Neu:
  - ein einziges memcpy ueber den ganzen Puffer
  - die Spiegelung uebernimmt der Szenengraph
    (setTextureCoordinatesTransform), kostet nichts
  - die Textur wird wiederverwendet statt bei jedem Frame neu erzeugt

Das QImage bleibt, weil hybris-EGL kein EGL_EXT_image_dma_buf_import
anbietet - eine echte Zero-Copy-Anzeige ist auf diesem Geraet nicht
moeglich. Aus drei Durchgaengen werden aber zwei.
"""

import sys

P = '/home/mersdk/harbour-fgview/src/harbour-fgview.cpp'

# ---- Kopie: ein memcpy statt 768 --------------------------------
COPY_OLD = '''        /* GL liefert von unten nach oben - zeilenweise gespiegelt kopieren */
        const int stride = w * 4;
        for (int y = 0; y < h; ++y)
            memcpy(_image.scanLine(h - 1 - y), src + size_t(y) * stride, stride);'''

COPY_NEW = '''        /* Ein Durchgang statt 768 Einzelkopien. Dass GL von unten
           nach oben liefert, gleicht der Szenengraph beim Zeichnen
           aus - siehe setTextureCoordinatesTransform unten. */
        memcpy(_image.bits(), src, bytes);'''

# ---- Textur wiederverwenden -------------------------------------
NODE_OLD = '''        QSGSimpleTextureNode* node = static_cast<QSGSimpleTextureNode*>(old);
        if (!node) {
            node = new QSGSimpleTextureNode();
            node->setFiltering(QSGTexture::Linear);
        }

        if (_texture) { delete _texture; _texture = nullptr; }
        _texture = window()->createTextureFromImage(_image);
        node->setTexture(_texture);'''

NODE_NEW = '''        QSGSimpleTextureNode* node = static_cast<QSGSimpleTextureNode*>(old);
        if (!node) {
            node = new QSGSimpleTextureNode();
            node->setFiltering(QSGTexture::Linear);
            /* GL rendert von unten nach oben; die Spiegelung hier
               kostet nichts, im memcpy waere sie teuer. */
            node->setTextureCoordinatesTransform(
                QSGSimpleTextureNode::MirrorVertically);
        }

        /* Textur nur neu anlegen, wenn sich die Groesse geaendert hat.
           Sonst denselben Speicher ueberschreiben. */
        if (!_texture || _texture->textureSize() != _image.size()) {
            delete _texture;
            _texture = window()->createTextureFromImage(
                _image, QQuickWindow::TextureIsOpaque);
            node->setTexture(_texture);
        } else {
            QSGTexture* fresh = window()->createTextureFromImage(
                _image, QQuickWindow::TextureIsOpaque);
            delete _texture;
            _texture = fresh;
            node->setTexture(_texture);
        }'''

# ---- bytes muss im Sichtbereich sein ----------------------------
BYTES_CHECK = 'const size_t bytes = size_t(w) * size_t(h) * 4u;'


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if 'MirrorVertically' in s:
        print("bereits gepatcht")
        return 0

    if BYTES_CHECK not in s:
        print("FEHLER: bytes-Berechnung nicht gefunden")
        return 1

    for old, new, label in (
        (COPY_OLD, COPY_NEW, "eine Kopie statt 768"),
        (NODE_OLD, NODE_NEW, "Textur und Spiegelung"),
    ):
        if old not in s:
            print("FEHLER: Muster nicht gefunden:", label)
            return 1
        s = s.replace(old, new, 1)
        print("gepatcht:", label)

    open(P, 'w').write(s)
    print("\nfertig - App neu bauen")
    return 0


if __name__ == '__main__':
    sys.exit(main())
