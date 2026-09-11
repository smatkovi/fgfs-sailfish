#!/bin/bash
# host driver: build stages in order, merge each into the target as root
C=ba82fa4d3804
for f in sfos50-stack.sh sfos50-root-copy.sh; do
  docker cp ~/Downloads/$f $C:/home/mersdk/$f || { echo "DRIVER-FEHLER: $f nicht in den Container kopiert"; exit 1; }
done
# osg first: SimGear and FlightGear build against the target's /opt/osg-gles3
for s in ${STAGES:-osg plib simgear flightgear}; do
  docker exec $C bash -l /home/mersdk/sfos50-stack.sh $s | grep -q "STACK50-OK-$s" \
    || { docker exec $C tail -40 /home/mersdk/sfos50-$s.log; echo DRIVER-FEHLER-$s; exit 1; }
  docker exec -u root $C bash /home/mersdk/sfos50-root-copy.sh $s || { echo DRIVER-ROOTCOPY-FEHLER-$s; exit 1; }
  echo "stage $s ok $(date +%T)"
done
echo DRIVER-FERTIG
