#!/bin/bash

echo "HG_NODE=$HG_NODE"

rm -f /home/bclary/mozilla/builds/hg.mozilla.org/sisyphus/results/*.log

/home/bclary/mozilla/builds/hg.mozilla.org/sisyphus/bin/builder.sh -p firefox -b inbound -T opt -B 'build'

rc=0
if egrep -q 'intel-gcm.*error: (missing|unknown)' /home/bclary/mozilla/builds/hg.mozilla.org/sisyphus/results/*.log; then
    rc=1
fi

echo "exit code $rc"
exit $rc


