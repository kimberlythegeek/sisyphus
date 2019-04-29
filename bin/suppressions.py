# suppressions.py - collect valgrind suppression rules from stdin and
# write unique sorted list of suppression rules to stdout.
#
# Usage: cat file [file...] | python suppressions.py > valgrind.sup

import sys

inblock = False
inblock_start = False
curr_rule = ""
rules = {}

line = sys.stdin.readline()

while line:
    line = line.rstrip()

    if inblock_start:
        inblock_start = False
        if line.find('<insert_a_suppression_name_here>') == -1:
            inblock = False
            curr_rule = ''

    if line == "{":
        inblock = True
        inblock_start = True

    if inblock:
        curr_rule = curr_rule + line + "\n"

    if line == "}":
        if not curr_rule in rules:
            rules[curr_rule] = True

        inblock = False
        curr_rule = ""

    line = sys.stdin.readline()

rule_list = [curr_rule for curr_rule in rules]
rule_list.sort()

for curr_rule in rule_list:
    print curr_rule
