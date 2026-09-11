#!/usr/bin/env python3
"""SimGear: let the BTG loader merge terrain geometry (FGFS_BTG_OPTIMIZE=1).

The terrain tiles go through NoOptimizePolicy, so nothing is ever merged; the
device draws about 740 drawables per frame, and at roughly 28 microseconds per
draw call that is most of the 21 ms draw phase.  OptimizeModelPolicy already
exists for models - this uses the same osgUtil::Optimizer on tiles, but only
with the passes that cannot move geometry:

  MERGE_GEOMETRY      combine drawables that share the same state
  SHARE_DUPLICATE_STATE  one state set instead of many identical ones
  INDEX_MESH          reuse vertices instead of repeating them

FLATTEN_STATIC_TRANSFORMS is deliberately left out: the tiles hang below
transforms that place them on the globe, and resolving those could move the
geometry.  Merging costs time while a tile loads, so it is behind a switch
until measured.

  python3 sg_btg_optimize.py [simgear-source-root]
"""
import os
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/simgear-2020.3.19'
p = os.path.join(ROOT, 'simgear/scene/tgdb/SGReaderWriterBTG.cxx')
s = open(p).read()

old = '''typedef ModelRegistryCallback<DefaultProcessPolicy, NoCachePolicy,
                              NoOptimizePolicy,
                              NoSubstitutePolicy, BuildGroupBVHPolicy>
BTGCallback;
'''
new = '''/* FlightGear GLES port, FGFS_BTG_OPTIMIZE=1: merge tile geometry on load.
   Without it every tile arrives as it was written, which is where most of
   the per-frame draw calls come from. */
struct BTGOptimizePolicy {
    BTGOptimizePolicy(const std::string&) {}
    osg::Node* optimize(osg::Node* node, const std::string&, const osgDB::Options*)
    {
        static const int on = (::getenv("FGFS_BTG_OPTIMIZE") != 0) ? 1 : 0;
        if (!on || !node) return node;
        osgUtil::Optimizer optimizer;
        optimizer.optimize(node,
                           osgUtil::Optimizer::MERGE_GEOMETRY |
                           osgUtil::Optimizer::SHARE_DUPLICATE_STATE |
                           osgUtil::Optimizer::INDEX_MESH);
        return node;
    }
};

typedef ModelRegistryCallback<DefaultProcessPolicy, NoCachePolicy,
                              BTGOptimizePolicy,
                              NoSubstitutePolicy, BuildGroupBVHPolicy>
BTGCallback;
'''
if new in s:
    print('  schon aktuell')
else:
    assert s.count(old) == 1, 'Anker fehlt oder mehrdeutig'
    s = s.replace(old, new)
    for inc, after in (('#include <osgUtil/Optimizer>\n', '#include <osgDB/Registry>\n'),
                       ('#include <cstdlib>\n', '#include <osgUtil/Optimizer>\n')):
        if inc not in s:
            assert s.count(after) == 1, 'Include-Anker fehlt: %r' % after
            s = s.replace(after, after + inc)
    open(p, 'w').write(s)
    print('geaendert simgear/scene/tgdb/SGReaderWriterBTG.cxx')
print('fertig')
