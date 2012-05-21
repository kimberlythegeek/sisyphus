#!/usr/bin/perl -w
# -*- Mode: Perl; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

use XML::Simple;

die "usage: get-extension-uuid.pl installrdfpath" if (! $ARGV[0]);
my $rdf = XMLin($ARGV[0], NSExpand => 1);
print $rdf->{"{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description"}->{"{http://www.mozilla.org/2004/em-rdf#}id"};
