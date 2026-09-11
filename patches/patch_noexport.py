#!/usr/bin/env python3
"""
Verhindert Zinks aussichtslose Exportversuche.

Der Mali-Treiber meldet ueber vkGetPhysicalDeviceExternalBufferProperties
exportable=0 - er kann Geraetespeicher nicht als dmabuf exportieren.
Zink prueft das nicht, sondern schliesst allein aus der Anwesenheit von
VK_KHR_external_memory_fd auf Exportfaehigkeit. Die Folge: bei jedem
Frame eine Reallokation der Ressource plus ein fehlschlagender
vkGetMemoryFdKHR, bis der Geraetespeicher erschoepft ist
("couldn't allocate memory: heap=0").

Der Patch fragt die Faehigkeit einmal beim Screen-Aufbau ab und
schaltet die Modifier-/dmabuf-Pfade ab, wenn der Treiber den Export
nicht anbietet.

Zusaetzlich fliegt die DMABUF-Probe aus GraphicsWindowEGL - sie hat
ihren Zweck erfuellt.
"""

import sys, re

ZS = '/home/mersdk/mesa-24.2.8/src/gallium/drivers/zink/zink_screen.c'
GW = '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osgViewer/GraphicsWindowEGL.cpp'

# --- Mesa: Exportfaehigkeit tatsaechlich abfragen -------------------
MESA_OLD = '''   if (screen->info.have_EXT_image_drm_format_modifier && screen->info.have_EXT_external_memory_dma_buf) {'''

MESA_NEW = '''   /* Nicht jeder Treiber, der external_memory_fd anbietet, kann auch
      exportieren. Der Mali-Blob etwa meldet exportable=0 - ohne diese
      Pruefung versucht Zink den Export bei jedem Frame erneut, mit
      einer Reallokation pro Versuch, bis der Speicher ausgeht. */
   bool can_export_dmabuf = false;
   if (screen->info.have_EXT_external_memory_dma_buf) {
      VkPhysicalDeviceExternalBufferInfo ebi = {0};
      ebi.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_BUFFER_INFO;
      ebi.usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT;
      ebi.handleType = VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT;

      VkExternalBufferProperties ebp = {0};
      ebp.sType = VK_STRUCTURE_TYPE_EXTERNAL_BUFFER_PROPERTIES;

      VKSCR(GetPhysicalDeviceExternalBufferProperties)(screen->pdev, &ebi, &ebp);
      can_export_dmabuf =
         (ebp.externalMemoryProperties.externalMemoryFeatures &
          VK_EXTERNAL_MEMORY_FEATURE_EXPORTABLE_BIT) != 0;

      if (!can_export_dmabuf) {
         mesa_logi("zink: driver cannot export dma-buf memory, "
                   "disabling modifier paths");
         screen->info.have_EXT_image_drm_format_modifier = false;
         screen->info.have_EXT_external_memory_dma_buf = false;
      }
   }

   if (screen->info.have_EXT_image_drm_format_modifier && screen->info.have_EXT_external_memory_dma_buf) {'''


def patch_mesa():
    s = open(ZS).read()
    if 'can_export_dmabuf' in s:
        print("Mesa: bereits gepatcht")
        return True
    if MESA_OLD not in s:
        print("Mesa: FEHLER, Muster nicht gefunden")
        return False
    s = s.replace(MESA_OLD, MESA_NEW, 1)
    open(ZS, 'w').write(s)
    print("Mesa: Exportfaehigkeit wird abgefragt")
    return True


def patch_gw():
    s = open(GW).read()
    if 'DMABUF-Probe' not in s:
        print("OSG: Probe bereits entfernt")
        return True
    start = s.find('        /* ---- Probe: dmabuf-Export der Farbtextur')
    end = s.find('/* ---- Ende Probe ---------------------------------------- */')
    if start < 0 or end < 0:
        print("OSG: FEHLER, Probe-Block nicht gefunden")
        return False
    end += len('/* ---- Ende Probe ---------------------------------------- */\n')
    s = s[:start] + s[end:]
    open(GW, 'w').write(s)
    print("OSG: DMABUF-Probe entfernt")
    return True


def main():
    ok = patch_mesa()
    ok = patch_gw() and ok
    print()
    print("Danach: Mesa neu bauen, OSG neu bauen, Laufzeitpaket packen.")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
