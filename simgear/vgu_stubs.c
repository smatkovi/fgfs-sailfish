/* vgu_stubs.c - Ruempfe fuer ShivaVG unter GLES2
 *
 * ShivaVG (OpenVG) zeichnet im Immediate Mode und ist unter GLES2
 * nicht baubar. Uebernommen wurde nur shVgu.c (reine Mathematik).
 * Der Canvas ruft weitere Funktionen auf; diese Ruempfe halten den
 * Linker zufrieden. Der Canvas zeichnet damit nichts - betroffen
 * sind Glascockpit-Displays, nicht die klassischen Instrumente.
 */
#include "ShivaVG/include/vg/openvg.h"

VGErrorCode vgGetError(void) { return VG_NO_ERROR; }

void vgAppendPathData(VGPath p, VGint n, const VGubyte* s, const void* d)
{ (void)p; (void)n; (void)s; (void)d; }

VGfloat vgGetParameterf(VGHandle o, VGint t)
{ (void)o; (void)t; return 0.0f; }

void vgClearPath(VGPath p, VGbitfield c) { (void)p; (void)c; }

VGPath vgCreatePath(VGint fmt, VGPathDatatype dt, VGfloat sc, VGfloat bi,
                    VGint sc2, VGint cc, VGbitfield caps)
{ (void)fmt;(void)dt;(void)sc;(void)bi;(void)sc2;(void)cc;(void)caps; return 0; }

void vgDestroyPath(VGPath p) { (void)p; }

VGPaint vgCreatePaint(void) { return 0; }
void vgDestroyPaint(VGPaint p) { (void)p; }
void vgSetPaint(VGPaint p, VGbitfield m) { (void)p; (void)m; }

void vgDrawPath(VGPath p, VGbitfield m) { (void)p; (void)m; }

void vgPathBounds(VGPath p, VGfloat* x, VGfloat* y, VGfloat* w, VGfloat* h)
{ (void)p; if(x)*x=0; if(y)*y=0; if(w)*w=0; if(h)*h=0; }

void vgSetParameterfv(VGHandle o, VGint t, VGint n, const VGfloat* v)
{ (void)o; (void)t; (void)n; (void)v; }

void vgSetf(VGParamType t, VGfloat v) { (void)t; (void)v; }
void vgSetfv(VGParamType t, VGint n, const VGfloat* v)
{ (void)t; (void)n; (void)v; }
void vgSeti(VGParamType t, VGint v) { (void)t; (void)v; }

/* ShivaVG-eigene Erweiterungen */
VGboolean vgCreateContextSH(VGint w, VGint h) { (void)w; (void)h; return VG_TRUE; }
void vgDestroyContextSH(void) {}
void vgResizeSurfaceSH(VGint w, VGint h) { (void)w; (void)h; }
VGboolean vgHasContextSH(void) { return VG_FALSE; }
