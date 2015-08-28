#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

        from django.core.management import execute_from_command_line

        execute_from_command_line(sys.argv)
    except Exception, e:
        sys.stderr.write('bughunter error manager.py: %s\n' % e)
        raise
