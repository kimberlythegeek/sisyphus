#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
        sisyphus_dir     = os.environ["SISYPHUS_DIR"]
        tempdir          = os.path.join(sisyphus_dir, 'python')
        if tempdir not in sys.path:
            sys.path.append(tempdir)

        tempdir          = os.path.join(tempdir, 'sisyphus')
        if tempdir not in sys.path:
            sys.path.append(tempdir)

        tempdir          = os.path.join(tempdir, 'webapp')
        if tempdir not in sys.path:
            sys.path.append(tempdir)

        import django
        django.setup()
        from django.core.management import execute_from_command_line

        execute_from_command_line(sys.argv)
    except Exception, e:
        sys.stderr.write('bughunter error manager.py: %s\n' % e)
        raise
