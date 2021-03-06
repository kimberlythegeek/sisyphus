#!/usr/bin/perl -w
# -*- Mode: Perl; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

my $K = 1024;
my $M = 1024 * $K;
my $G = 1024 * $M;

my $tmpmemory;
my $unitmemory;
my $raw_memory = 0;
my $swap_memory = 0;
my $ulimit_maxmemory = 0;
my $ulimit_virtualmemory = 0;
my $test_memory = 0;

# hack around lack of available environment entries in both
# cygwin perl and redhat perl.
# Note the bash -c set is required for ubuntu 9.04 otherwise the
# OSTYPE file will return no data. I don't know why.
open OSTYPE, "bash -c set | grep OSTYPE |" || die "Unable to open OSTYPE: $!";
while (<OSTYPE>)
{
    chomp;
    $ostype .= $_;
}
close OSTYPE;

die "Unable to determine OSTYPE" if (!$ostype);

if ($ostype =~ /linux/i || $ostype =~ /cygwin/i)
{
    open MEMINFO, "/proc/meminfo" or die "Unable to open /proc/meminfo";
    while (<MEMINFO>)
    {
        if ( ($tmpmemory, $unitmemory) = $_ =~ /MemTotal:\s*([0-9]*) (kB)/)
        {
            die "Unknown memory unit meminfo MemTotal $unitmemory" if $unitmemory ne "kB";

            $tmpmemory *= 1024;
            $raw_memory = int($tmpmemory / $G + .5);
        }
        elsif ( ($tmpmemory, $unitmemory) = $_ =~ /SwapTotal:\s*([0-9]*) (kB)/)
        {
            die "Unknown memory unit meminfo SwapTotal $unitmemory" if $unitmemory ne "kB";

            $tmpmemory *= 1024;
            $swap_memory = int($tmpmemory / $G + .5);
        }
    }
    close MEMINFO;
}
elsif ($ostype =~ /darwin/i)
{
    open SYSTEMPROFILER, "system_profiler|" or die "Unable to open system_profiler";
    while (<SYSTEMPROFILER>)
    {
        if (  ($tmpmemory, $unitmemory) = $_ =~ /^\s*Memory:\s*([0-9]*) ([a-zA-Z]+)/)
        {
            if ($unitmemory =~ /KB/)
            {
                $tmpmemory *= $K;
            }
            elsif ($unitmemory =~ /MB/)
            {
                $tmpmemory *= $M;
            }
            elsif ($unitmemory =~ /GB/)
            {
                $tmpmemory *= $G;
            }
            else
            {
                die "Unknown memory unit system_profiler $unitmemory";
            }
            $raw_memory = int($tmpmemory / $G + .5);
        }
    }
    close SYSTEMPROFILER;
}
else
{
    die "Unknown Operating System: $ostype";
}

open ULIMIT, 'bash -c "ulimit -a"|' or die "Unable to open ulimit -a";

while (<ULIMIT>)
{
    if (  ($unitmemory, $tmpmemory) = $_ =~ /max memory size + \(([a-zA-Z]*), \-m\) ([0-9]*)/)
    {
        if ($tmpmemory eq "")
        {
            $tmpmemory = 0;
        }

        if ($unitmemory =~ /kbytes/i)
        {
            $tmpmemory *= $K;
        }
        elsif ($unitmemory =~ /mbytes/i)
        {
            $tmpmemory *= $M;
        }
        elsif ($unitmemory =~ /gbytes/i)
        {
            $tmpmemory *= $G;
        }
        else
        {
            die "Unknown memory unit ulimit $unitmemory";
        }

        $ulimit_maxmemory = int($tmpmemory / $G + .5);
    }
    elsif (  ($unitmemory, $tmpmemory) = $_ =~ /virtual memory + \(([a-zA-Z]*), \-v\) ([0-9]*)/)
    {
        if ($tmpmemory eq "")
        {
            $tmpmemory = 0;
        }

        if ($unitmemory =~ /kbytes/i)
        {
            $tmpmemory *= $K;
        }
        elsif ($unitmemory =~ /mbytes/i)
        {
            $tmpmemory *= $M;
        }
        elsif ($unitmemory =~ /gbytes/i)
        {
            $tmpmemory *= $G;
        }
        else
        {
            die "Unknown virtual memory unit ulimit $unitmemory";
        }

        $ulimit_virtualmemory = int($tmpmemory / $G + .5);
    }
}
close ULIMIT;

$test_memory = $ulimit_virtualmemory > 0 ? $ulimit_virtualmemory : ($raw_memory + $swap_memory);

print "$test_memory";

