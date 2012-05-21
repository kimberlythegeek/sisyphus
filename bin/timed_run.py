#!/usr/bin/python -u
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

# Usage: timed_run timeout prefix command args
import os, signal, sys, time

#
# returns exit code as follows:
# 
exitOSError   = 66
exitSignal    = 77
exitTimeout   = 88
exitInterrupt = 99

pid = None
prefix = sys.argv[2]
elapsedtime = 0

if prefix == "-":
    prefix = ''
else:
    prefix = prefix + ':'

def getSignalName(num):
    for p in dir(signal):
        if p.startswith("SIG") and not p.startswith("SIG_"):
            if getattr(signal, p) == num:
                return p
    return "UNKNOWN"

def alarm_handler(signum, frame):
    global pid
    global prefix
    try:
	stoptime = time.time()
	elapsedtime = stoptime - starttime
        print "\n%s EXIT STATUS: TIMED OUT (%s seconds)\n" % (prefix, elapsedtime)
        flushkill(pid, signal.SIGKILL)
    except OSError, e:
        print "\ntimed_run.py: exception trying to kill process: %d (%s)\n" % (e.errno, e.strerror)
        pass
    flushexit(exitTimeout)

def forkexec(command, args):
    global prefix
    global elapsedtime
    #print command
    #print args
    try:
        pid = os.fork()
        if pid == 0:  # Child
            # increase the child's niceness so it doesn't starve the parent.
            os.nice(4)
            os.execvp(command, args)
            flushbuffers()
        else:  # Parent
            return pid
    except OSError, e:
        print "\n%s ERROR: %s %s failed: %d (%s) (%f seconds)\n" % (prefix, command, args, e.errno, e.strerror, elapsedtime)
        flushexit(exitOSError)

def flushbuffers():
        sys.stdout.flush()
        sys.stderr.flush()

def flushexit(rc):
        flushbuffers()
        sys.exit(rc)

def flushkill(pid, sig):
        flushbuffers()
        os.kill(pid, sig)

signal.signal(signal.SIGALRM, alarm_handler)
signal.alarm(int(sys.argv[1]))
starttime = time.time()
try:
	pid = forkexec(sys.argv[3], sys.argv[3:])
	status = os.waitpid(pid, 0)[1]
	signal.alarm(0) # Cancel the alarm
	stoptime = time.time()
	elapsedtime = stoptime - starttime
	# it appears that linux at least will on "occasion" return a status
	# when the process was terminated by a signal, so test signal first.
	if os.WIFSIGNALED(status):
            signum = os.WTERMSIG(status)
            if signum == 2:
                msg = 'INTERRUPT'
                rc = exitInterrupt
            else:
                msg = 'CRASHED'
                rc = exitSignal

            print "\n%s EXIT STATUS: %s signal %d %s (%f seconds)\n" % (prefix, msg, signum, getSignalName(signum), elapsedtime)
            flushexit(rc)

	elif os.WIFEXITED(status):
	    rc = os.WEXITSTATUS(status)
	    msg = ''
	    if rc == 0:
	        msg = 'NORMAL'
	    else:
	        msg = 'ABNORMAL ' + str(rc)
		rc = exitSignal

	    print "\n%s EXIT STATUS: %s (%f seconds)\n" % (prefix, msg, elapsedtime)
	    flushexit(rc)
	else:
	    print "\n%s EXIT STATUS: NONE (%f seconds)\n" % (prefix, elapsedtime)
	    flushexit(0)
except KeyboardInterrupt:
	flushkill(pid, 9)
	flushexit(exitInterrupt)

# check that the child process has terminated.
try:
    os.getpgid(pid)
    # process still exists. try to kill it and exit with OSError
    flushkill(pid, 9)
    flushexit(exitOSError)
except OSError:
    # process doesn't exist. all is well.
    1
