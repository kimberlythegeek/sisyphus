#!/usr/bin/perl -w
# -*- Mode: Perl; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

use Date::Parse;

if (@ARGV == 0)
{
    die "usage: dateparse.pl datestring";
}

my $datestring = $ARGV[0];
my $time = str2time($datestring);
print($time);

