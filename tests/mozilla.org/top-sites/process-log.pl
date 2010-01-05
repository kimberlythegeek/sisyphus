#!/usr/bin/perl -w

my $currentpage;
my $page;
my $currentassertion;
my $assertion;
my $currentexploitabletitle;
my $exploitabletitle;
my $currentexploitableclass;
my $exploitableclass;

while (<ARGV>)
{
    chomp;

    if ( ($page) = $_ =~ /Spider: Begin loading (.*)/)
    {
	$currentpage      = $page;
	$currentassertion = '';
	$currentexploitabletitle = '';
	$currentexploitableclass = '';
    }

    if ( ($exploitableclass) = $_ =~ /^Exploitability Classification: (.*)/)
    {
	$currentexploitableclass = $exploitableclass;
    }

    if ( ($exploitabletitle) = $_ =~ /^Recommended Bug Title: (.*)/)
    {
	$currentexploitabletitle = $exploitabletitle;
    }

    if ( ($assertion) = $_ =~ /(Assertion fail.*)/)
    {
	$currentassertion = $assertion;
    }

    if ( /EXIT STATUS:/ )
    {
	if ($currentexploitableclass)
	{
	    print "$currentexploitableclass: ";
	}

	if ($currentexploitabletitle)
	{
	    print "$currentexploitabletitle: ";
	}

	if ($currentassertion)
	{
	    print "$currentassertion: ";
	}

#	if ($currentpage)
#	{
#	    print "$currentpage: ";
#	}

	print "$_\n";

	$currentpage      = '';
	$currentassertion = '';
	$currentexploitableclass = '';
	$currentexploitabletitle = '';
    }
}
