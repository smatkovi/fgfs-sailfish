#!/usr/bin/env python3
"""SimGear lowlevel.cxx: make the gz error path survive.

sg_location{thread_gzPath} builds a std::string from the path, but
setThreadLocalSimgearReadPath() is never called anywhere, so thread_gzPath is
always empty and the string construction throws
"basic_string: construction from null is not valid" - the reporting of a read
error kills the process before the error itself is ever seen.

Only pass a location when the path is set, and put the real cause (zlib code
and errno) into the message.

  python3 sg_lowlevel_fix.py [simgear-source-root]
"""
import re
import sys
import os

ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/simgear-2020.3.19'
p = os.path.join(ROOT, 'simgear/io/lowlevel.cxx')
s = open(p).read()

# 1) a helper that never throws, next to gzErrorMessage
anchor = 'static std::string gzErrorMessage(gzFile fd)\n'
assert s.count(anchor) == 1, 'gzErrorMessage not found'
s = s.replace(anchor,
'''/* FlightGear GLES port: thread_gzPath is never set (setThreadLocalSimgearReadPath
   has no callers), and sg_location built from an empty SGPath throws while
   reporting an error.  Report the location only when there is one. */
static sg_location gzLocation()
{
    return thread_gzPath.isNull() ? sg_location{} : sg_location{thread_gzPath};
}

''' + anchor)

# 2) include the zlib code and errno, so the actual cause is visible
old_msg = '''    if (errNum == Z_ERRNO) {
        return simgear::strutils::error_string(errno);
    } else if (gzMsg) {
        return {gzMsg};
    }
'''
assert s.count(old_msg) == 1, 'gzErrorMessage body not found'
s = s.replace(old_msg,
'''    if (errNum == Z_ERRNO) {
        return simgear::strutils::error_string(errno) + " (errno " + std::to_string(errno) + ")";
    } else if (gzMsg) {
        return std::string(gzMsg) + " (zlib code " + std::to_string(errNum) + ")";
    }
''')

# 3) every throw site uses the safe location
count = len(re.findall(r'sg_location\{thread_gzPath\}', s))
assert count > 0, 'no throw sites found'
s = s.replace('sg_location{thread_gzPath}', 'gzLocation()')
open(p, 'w').write(s)
print('geaendert %s (%d Wurfstellen)' % (p, count))
