#!/usr/bin/env python3
"""FlightGear: AI flight plans that close with an EOF marker load again.

FGAIFlightPlan::parseProperties rejects a plan whose last waypoint is not
named END.  FGData's KSFO_depart_south_28L.xml - the only flight plan of
the aircraft_demo scenario - ends with END followed by the older EOF
marker, so the plan is refused ("Flightplan missing END node"), and the
scenario's 737 stays at 0/0 with no speed: loaded, counted in /ai/models,
never seen (BEFUNDE.md P46).  A waypoint named EOF is now skipped while
reading, which leaves END last.

Idempotent.  python3 fg_aiplan_eof.py [flightgear-source-root]"""
import os, sys
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/flightgear-2020.3.19'
p = os.path.join(ROOT, 'src/AIModel/AIFlightPlan.cxx')
s = open(p).read()
old = '''  for (int i = 0; i < node->nChildren(); i++) {
    FGAIWaypoint* wpt = new FGAIWaypoint;
    SGPropertyNode * wpt_node = node->getChild(i);
'''
new = '''  for (int i = 0; i < node->nChildren(); i++) {
    // the older end-of-file marker after END, as in KSFO_depart_south_28L
    if (std::string(node->getChild(i)->getStringValue("name", "")) == "EOF")
      continue;
    FGAIWaypoint* wpt = new FGAIWaypoint;
    SGPropertyNode * wpt_node = node->getChild(i);
'''
if new in s:
    print('fg_aiplan_eof: already applied')
else:
    assert s.count(old) == 1, 'anchor not found'
    open(p, 'w').write(s.replace(old, new))
    print('fg_aiplan_eof: applied')
