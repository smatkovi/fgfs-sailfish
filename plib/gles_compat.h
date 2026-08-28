/* gles_compat.h - Leeroperationen fuer Immediate-Mode-Aufrufe
 *
 * FlightGear und PLIB benutzen an einigen Stellen die
 * Fixed-Function-Pipeline, die es unter GLES2 nicht gibt. Statt den
 * Code auszuklammern - was Kontrollstrukturen zerreisst - werden die
 * Aufrufe zu Leeroperationen. Betroffen sind das 2D-Panel und die
 * PUI-Oberflaeche; beide werden auf dem Telefon nicht benutzt.
 */
#ifndef FG_GLES_COMPAT_H
#define FG_GLES_COMPAT_H
#ifdef SG_GLES2

#  define glBegin(a)               ((void)0)
#  define glEnd()                  ((void)0)
#  define glVertex2f(a,b)          ((void)0)
#  define glVertex3f(a,b,c)        ((void)0)
#  define glVertex3fv(a)           ((void)0)
#  define glTexCoord2f(a,b)        ((void)0)
#  define glColor3f(a,b,c)         ((void)0)
#  define glColor4f(a,b,c,d)       ((void)0)
#  define glColor4fv(a)            ((void)0)
#  define glNormal3f(a,b,c)        ((void)0)
#  define glNormal3fv(a)           ((void)0)
#  define glPushMatrix()           ((void)0)
#  define glPopMatrix()            ((void)0)
#  define glLoadIdentity()         ((void)0)
#  define glMatrixMode(a)          ((void)0)
#  define glTranslatef(a,b,c)      ((void)0)
#  define glRotatef(a,b,c,d)       ((void)0)
#  define glScalef(a,b,c)          ((void)0)
#  define glOrtho(a,b,c,d,e,f)     ((void)0)
#  define glTexEnvi(a,b,c)         ((void)0)
#  define glRasterPos2i(a,b)       ((void)0)
#  define glAlphaFunc(a,b)         ((void)0)
#  define glShadeModel(a)          ((void)0)

#  ifndef GL_QUADS
#    define GL_QUADS               0
#  endif
#  ifndef GL_POLYGON
#    define GL_POLYGON             0
#  endif
#  ifndef GL_MODELVIEW
#    define GL_MODELVIEW           0x1700
#  endif
#  ifndef GL_PROJECTION
#    define GL_PROJECTION          0x1701
#  endif
#  ifndef GL_TEXTURE_ENV
#    define GL_TEXTURE_ENV         0x2300
#  endif
#  ifndef GL_TEXTURE_ENV_MODE
#    define GL_TEXTURE_ENV_MODE    0x2200
#  endif
#  ifndef GL_MODULATE
#    define GL_MODULATE            0x2100
#  endif
#  ifndef GL_FLAT
#    define GL_FLAT                0x1D00
#  endif
#  ifndef GL_SMOOTH
#    define GL_SMOOTH              0x1D01
#  endif
#  ifndef GL_GREATER
#    define GL_GREATER             0x0204
#  endif

#  define glPushAttrib(a)          ((void)0)
#  define glPopAttrib()            ((void)0)
#  define glClipPlane(a,b)         ((void)0)
#  define glMultMatrixd(a)         ((void)0)
#  define glMultMatrixf(a)         ((void)0)
#  define glLoadMatrixd(a)         ((void)0)
#  define glLoadMatrixf(a)         ((void)0)

#  ifndef GL_ENABLE_BIT
#    define GL_ENABLE_BIT          0x00002000
#  endif
#  ifndef GL_COLOR_MATERIAL
#    define GL_COLOR_MATERIAL      0x0B57
#  endif
#  ifndef GL_CLIP_PLANE0
#    define GL_CLIP_PLANE0         0x3000
#    define GL_CLIP_PLANE1         0x3001
#    define GL_CLIP_PLANE2         0x3002
#    define GL_CLIP_PLANE3         0x3003
#    define GL_CLIP_PLANE4         0x3004
#    define GL_CLIP_PLANE5         0x3005
#  endif
#  ifndef GL_MODELVIEW_MATRIX
#    define GL_MODELVIEW_MATRIX    0x0BA6
#  endif
#  ifndef GL_PROJECTION_MATRIX
#    define GL_PROJECTION_MATRIX   0x0BA7
#  endif
#  ifndef GL_LINE_LOOP
#    define GL_LINE_LOOP           0x0002
#  endif
#  ifndef GL_TRIANGLE_FAN
#    define GL_TRIANGLE_FAN        0x0006
#  endif

#  define glVertex2fv(a)           ((void)0)
#  define glVertex2d(a,b)          ((void)0)
#  define glVertex2dv(a)           ((void)0)
#  define glVertex3d(a,b,c)        ((void)0)
#  define glTranslated(a,b,c)      ((void)0)
#  define glRotated(a,b,c,d)       ((void)0)
#  define glScaled(a,b,c)          ((void)0)
#  define glMaterialfv(a,b,c)      ((void)0)
#  define glMaterialf(a,b,c)       ((void)0)
#  define glLightfv(a,b,c)         ((void)0)
#  define glLineStipple(a,b)       ((void)0)
#  define glPolygonMode(a,b)       ((void)0)
#  define glTexCoord2fv(a)         ((void)0)
#  define glColor3fv(a)            ((void)0)
#  define glColor3ub(a,b,c)        ((void)0)
#  define glColor4ub(a,b,c,d)      ((void)0)
#  define glFogf(a,b)              ((void)0)
#  define glFogfv(a,b)             ((void)0)
#  define glFogi(a,b)              ((void)0)

#  ifndef GL_AMBIENT_AND_DIFFUSE
#    define GL_AMBIENT_AND_DIFFUSE 0x1602
#  endif
#  ifndef GL_LINE_STIPPLE
#    define GL_LINE_STIPPLE        0x0B24
#  endif
#  ifndef GL_FRONT
#    define GL_FRONT               0x0404
#  endif
#  ifndef GL_FRONT_AND_BACK
#    define GL_FRONT_AND_BACK      0x0408
#  endif
#  ifndef GL_LINE
#    define GL_LINE                0x1B01
#  endif
#  ifndef GL_FILL
#    define GL_FILL                0x1B02
#  endif
#  ifndef GL_LIGHT0
#    define GL_LIGHT0              0x4000
#  endif
#  ifndef GL_AMBIENT
#    define GL_AMBIENT             0x1200
#  endif
#  ifndef GL_DIFFUSE
#    define GL_DIFFUSE             0x1201
#  endif
#  ifndef GL_SPECULAR
#    define GL_SPECULAR            0x1202
#  endif

#  ifndef GL_UNPACK_ROW_LENGTH
#    define GL_UNPACK_ROW_LENGTH   0x0CF2
#  endif
#  ifndef GL_UNPACK_SKIP_ROWS
#    define GL_UNPACK_SKIP_ROWS    0x0CF3
#  endif
#  ifndef GL_UNPACK_SKIP_PIXELS
#    define GL_UNPACK_SKIP_PIXELS  0x0CF4
#  endif
#  ifndef GL_UNPACK_SWAP_BYTES
#    define GL_UNPACK_SWAP_BYTES   0x0CF0
#  endif
#  ifndef GL_UNPACK_LSB_FIRST
#    define GL_UNPACK_LSB_FIRST    0x0CF1
#  endif
#  ifndef GL_PERSPECTIVE_CORRECTION_HINT
#    define GL_PERSPECTIVE_CORRECTION_HINT 0x0C50
#  endif
#  ifndef GL_POLYGON_SMOOTH_HINT
#    define GL_POLYGON_SMOOTH_HINT 0x0C53
#  endif
#  ifndef GL_LINE_SMOOTH_HINT
#    define GL_LINE_SMOOTH_HINT    0x0C52
#  endif
#  ifndef GL_POINT_SMOOTH_HINT
#    define GL_POINT_SMOOTH_HINT   0x0C51
#  endif
#  ifndef GL_FOG_HINT
#    define GL_FOG_HINT            0x0C54
#  endif
#  ifndef GL_NICEST
#    define GL_NICEST              0x1102
#  endif
#  ifndef GL_FASTEST
#    define GL_FASTEST             0x1101
#  endif

#  ifndef GL_LINE_SMOOTH
#    define GL_LINE_SMOOTH         0x0B20
#  endif
#  ifndef GL_POINT_SMOOTH
#    define GL_POINT_SMOOTH        0x0B10
#  endif
#  ifndef GL_LINE_STIPPLE_PATTERN
#    define GL_LINE_STIPPLE_PATTERN 0x0B25
#  endif
#  ifndef GL_POLYGON_SMOOTH
#    define GL_POLYGON_SMOOTH      0x0B41
#  endif
#  ifndef GL_LIGHTING
#    define GL_LIGHTING            0x0B50
#  endif

#  define glLoadMatrix(a)          ((void)0)

#  define glPushClientAttrib(a)    ((void)0)
#  define glPopClientAttrib()      ((void)0)
#  ifndef GL_ALL_ATTRIB_BITS
#    define GL_ALL_ATTRIB_BITS     0x000FFFFF
#  endif
#  ifndef GL_CLIENT_PIXEL_STORE_BIT
#    define GL_CLIENT_PIXEL_STORE_BIT 0x00000001
#  endif
#  ifndef GL_CLIENT_ALL_ATTRIB_BITS
#    define GL_CLIENT_ALL_ATTRIB_BITS 0xFFFFFFFF
#  endif

#  define glVertex2i(a,b)          ((void)0)
#  define glVertex3i(a,b,c)        ((void)0)
#  define glRecti(a,b,c,d)         ((void)0)
#  define glRectf(a,b,c,d)         ((void)0)
#  ifndef GL_FOG
#    define GL_FOG                 0x0B60
#  endif

#  ifndef GL_ALPHA_TEST
#    define GL_ALPHA_TEST 0x0BC0
#  endif

#  define glPointSize(a)            ((void)0)

#  define glBitmap(a,b,c,d,e,f,g)   ((void)0)
#  ifndef GL_CLAMP
#    define GL_CLAMP 0x812F
#  endif

#endif /* SG_GLES2 */
#endif /* FG_GLES_COMPAT_H */
