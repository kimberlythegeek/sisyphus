# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; -*-

import os
import sys
import re
import subprocess

K = 1024;
M = 1024 * K;
G = 1024 * M;

def scale_memory_to_bytes(memory, unit):

    if re.match('(kb|kbytes)', unit, re.IGNORECASE):
        memory *= K
    elif re.match('(mb|mbytes)', unit, re.IGNORECASE):
        memory *= M
    elif re.match('(gb|gbytes)', unit, re.IGNORECASE):
        memory *= G;
    else:
        raise Exception('Unknown memory unit ' + unit)

    return memory


def scale_bytes_to_unit(memory, unit):

    if re.match('(kb|kbytes)', unit, re.IGNORECASE):
        memory /= K
    elif re.match('(mb|mbytes)', unit, re.IGNORECASE):
        memory /= M
    elif re.match('(gb|gbytes)', unit, re.IGNORECASE):
        memory /= G;
    else:
        raise Exception('Unknown memory unit ' + unit)

    return memory


def determine_memory():
    raw_memory           = 0
    swap_memory          = 0
    ulimit_maxmemory     = 0
    ulimit_virtualmemory = 0

    if sys.platform == 'linux2' or sys.platform == 'cygwin':

        reMemTotal = re.compile(r'MemTotal:\s*([0-9]*) (..)')
        reSwapTotal = re.compile(r'SwapTotal:\s*([0-9]*) (..)')

        MEMINFO = open('/proc/meminfo', 'r')

        for line in MEMINFO:
            match = reMemTotal.match(line)

            if match:
                tmpmemory = float(match.group(1))
                unitmemory = match.group(2)
                raw_memory = scale_memory_to_bytes(tmpmemory, unitmemory)
            else:
                match = reSwapTotal.match(line)
                if match:
                    tmpmemory = float(match.group(1))
                    unitmemory = match.group(2)
                    swap_memory = scale_memory_to_bytes(tmpmemory, unitmemory)

        MEMINFO.close()

    elif sys.platform == 'darwin':

        reMemory = re.compile(r'^\s*Memory:\s*([0-9]*) ([a-zA-Z]+)')
        proc = subprocess.Popen(['system_profiler'],
                                preexec_fn=lambda : os.setpgid(0,0), # make the process its own process group
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        for line in proc.stdout:
            match = reMemory.match(line)
            if match:
                tmpmemory = float(match.group(1))
                unitmemory = match.group(2)
                raw_memory = scale_memory_to_bytes(tmpmemory, unitmemory)
    else:
        raise Exception('UnknownPlatform')


    reMaxMemory = re.compile(r'max memory size +\(([^,]+), \-m\) (.*)')
    reVirtualMemory = re.compile(r'virtual memory +\(([^,]+), \-v\) (.*)')

    proc = subprocess.Popen(['bash', '-c', 'ulimit -a'],
                            preexec_fn=lambda : os.setpgid(0,0), # make the process its own process group
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)

    for line in proc.stdout:

        match = reMaxMemory.match(line)
        if match:
            tmpmemory = match.group(2)
            unitmemory = match.group(1)

            if not tmpmemory:
                ulimit_maxmemory = 0
            elif tmpmemory == 'unlimited':
                ulimit_maxmemory = raw_memory
            else:
                tmpmemory = float(tmpmemory)
                ulimit_maxmemory = scale_memory_to_bytes(tmpmemory, unitmemory)
        else:
            match = reVirtualMemory.match(line)
            if match:
                tmpmemory = match.group(2)
                unitmemory = match.group(1)

                if not tmpmemory:
                    ulimit_virtualmemory = 0
                elif tmpmemory == 'unlimited':
                    ulimit_virtualmemory = swap_memory + raw_memory
                else:
                    tmpmemory = float(tmpmemory)
                    ulimit_virtualmemory = scale_memory_to_bytes(tmpmemory, unitmemory)


    unitmemory = scale_memory_to_bytes(1, unitmemory)

    return {"ram" : raw_memory,
            "swap": swap_memory,
            "max_memory" : ulimit_maxmemory,
            "max_virtual" : ulimit_virtualmemory,
            "unit" : unitmemory}

if __name__ == "__main__":
    memory = determine_memory()

    print ("raw_memory: %s, swap_memory: %s, ulimit_maxmemory: %s, ulimit virtualmemory: %s, ulimit units: %s" % 
           (memory['ram'], memory['swap'], memory['max_memory'], memory['max_virtual'], memory['unit']))
