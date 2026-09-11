#!/usr/bin/env python3
"""
Fence und PBO unter GLES2 abschalten.

GLES2 kennt weder Pixel-Buffer-Objects noch verhaelt sich
EGL_ANDROID_native_fence_sync wie unter Desktop-GL. Beides wird
deshalb nur noch im Desktop-Zweig benutzt; unter GLES2 bleibt der
Zero-Copy-Pfad ohne Synchronisation.

Ohne Fence kann der Presenter halb gezeichnete Frames sehen. Fuer
eine Leistungsmessung ist das ohne Belang.
"""

import sys

P = '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osgViewer/GraphicsWindowEGL.cpp'


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if 'GLES2: kein Fence' in s:
        print("bereits gepatcht")
        return 0

    old = '            if (_useFence) {\n                if (!_pCreateSync) {'
    new = ('''#ifdef OSG_GLES2_AVAILABLE
            /* GLES2: kein Fence - EGL_ANDROID_native_fence_sync
               verhaelt sich hier anders, und die Renderschleife
               bleibt sonst nach wenigen Frames stehen. */
            _useFence = false;
#endif
            if (_useFence) {
                if (!_pCreateSync) {''')

    if old not in s:
        print("FEHLER: Fence-Block nicht gefunden")
        return 1

    s = s.replace(old, new, 1)

    # PBO unter GLES2 gar nicht erst versuchen
    old2 = '            if (!loadPboEntryPoints()) {'
    new2 = ('''#ifdef OSG_GLES2_AVAILABLE
            if (true) {   /* GLES2 hat keine Pixel-Buffer-Objects */
#else
            if (!loadPboEntryPoints()) {
#endif''')
    if old2 in s:
        s = s.replace(old2, new2, 1)
        print("gepatcht: PBO unter GLES2 aus")

    open(P, 'w').write(s)
    print("gepatcht: Fence unter GLES2 aus")
    print("\nOSG-GLES neu bauen.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
