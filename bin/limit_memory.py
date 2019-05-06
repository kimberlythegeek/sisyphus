"""
limit_memory.py emits a string containing a ulimit command which limits the
maximum memory and virtual memory to 75% of the available amounts. This is
to be used to prevent the test process from starving the system of memory
or swap and causing the system to fail.
"""
import sys
import os
sisyphus_dir = os.environ["TEST_DIR"]
sisyphus_bin = os.path.join(sisyphus_dir, 'bin')
sys.path.append(sisyphus_bin)

import memory

# limit the test process to 75% of the total system memory

percent       = 0.75

if sys.platform == 'linux2':
    mem = memory.determine_memory()
    ram_limit     = int(percent * mem['ram'] / mem['unit'])
    virtual_limit = int(percent * mem['max_virtual'] / mem['unit'])
    print 'ulimit -m %s' % ram_limit
elif sys.platform == 'cygwin':
    print 'echo ulimit can not be used to limit memory or virtual memory usage on cygwin'
elif sys.platform == 'darwin':
    print 'echo ulimit or launchctl can not be used to limit memory or virtual memory usage on darwin'

