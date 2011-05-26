"""
usage:

program_info.init(globals(), None)
....
if program_info.changed():
    # reload program

description:

program_info is used to determine if a program or one of its imported
modules has been modified since it started. This information can be
used by a program to determine if it should restart to pick up changed
code.

1. program_info only detects modules which have already been imported
   at global scope prior to the call to program_info.init.

2. program_info.init must be called at global scope after all imports
   using the following pattern: program_info.init(globals(), None)

"""

import os
import stat
import sys
import re

startdir       = os.getcwd()
programPath    = os.path.abspath(os.path.join(os.path.realpath(os.path.dirname(sys.argv[0])),
                                              os.path.basename(sys.argv[0])))
programModTime = os.stat(programPath)[stat.ST_MTIME]
data           = {"program" : {"file" : programPath, "modtime" : programModTime}}

def init(global_symbols):
    """
    init collects the paths and modification times of the modules
    imported at the global scope at the time it is called.

    usage: init() # called from global scope after all imports
    """

    reModule = re.compile(r"^<module '([^']+)' from '([^\']+)'>$")

    # create a copy of globals in case it changes while the interation is executing.
    symbols = dict(global_symbols)

    for p in symbols:
        s = str(symbols[p])

        match = reModule.match(s)
        if match:
            module_name = match.group(1)
            module_file  = match.group(2).replace('.pyc', '.py')
            data[module_name] = {"file" : module_file, "modtime" : os.stat(module_file)[stat.ST_MTIME]}

def changed():
    """
    changed() checks the modification times of the program file and globally imported
    modules and returns True if any have been modified.
    """

    for module_name in data:
        module = data[module_name]
        if not module:
            continue

        if os.stat(module["file"])[stat.ST_MTIME] != module["modtime"]:
            return True

    return False

if __name__ == "__main__":
    pass
