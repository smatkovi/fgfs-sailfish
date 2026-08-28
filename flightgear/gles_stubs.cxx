/* gles_stubs.cxx
 *
 * 1. TLS-Polster fuer libhybris
 *
 * Der Mali-Treiber legt den aktuellen GL-Kontext in Bionics TLS-Slot 3
 * ab, also bei TP+24. Auf aarch64 beginnt der statische TLS-Block bei
 * TP+16, und das Hauptprogramm bekommt ihn vor allen Bibliotheken -
 * libtls-padding.so kann daran nichts aendern. FlightGears eigene
 * thread_local-Variablen landen damit genau auf den Bionic-Slots und
 * ueberschreiben den Kontextzeiger.
 *
 * Dieses Feld steht als erste TLS-Variable im ersten Objekt und haelt
 * die unteren Slots frei.
 */
__thread char hybris_bionic_tls_reserve[128]
    __attribute__((used, aligned(16)));

/* 2. Ruempfe fuer ShivaVG (unter GLES2 nicht baubar) */
