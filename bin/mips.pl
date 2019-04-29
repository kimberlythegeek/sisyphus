#!/usr/bin/perl -w
# -*- Mode: Perl; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

# Calculate a relative speed measurement based on 
# iterating over a simple loop in perl. Print the
# result as millions of iterations per cpu second.

sub mips
{
    my $tries = 3;        # repeat count to get average
    my $m     = 1000000;  # scale to million iterations/second
    my $l     = 10000000; # number of iterations to time
    my $cpu   = 0;        # cpu time accumlator
    my $dummy = 0;        # dummy variable to prevent optimizations
    my $i;
    my $start;
    my $stop;
    my $a;

    for ($a = 0; $a < $tries; ++$a)
    {
        $start = (times)[0];
        for ($i = 0; $i < $l; ++$i)
        {
            $dummy += $i;
        }
        $stop = (times)[0];
        $cpu += $stop - $start;
    }
    $cpu /= $tries;

    print "" . int($l/($cpu*$m)) . "\n";

    return $dummy; # reuse dummy variable
}

mips;
