from django.contrib import admin

from bughunter.models import Worker
admin.site.register(Worker)

from bughunter.models import Branch
admin.site.register(Branch)

from bughunter.models import Build
admin.site.register(Build)

from bughunter.models import Crash
admin.site.register(Crash)

from bughunter.models import Assertion
admin.site.register(Assertion)

from bughunter.models import Valgrind
admin.site.register(Valgrind)

from bughunter.models import UnitTestRun
admin.site.register(UnitTestRun)

from bughunter.models import UnitTestResult
admin.site.register(UnitTestResult)

from bughunter.models import UnitTestCrash
admin.site.register(UnitTestCrash)

from bughunter.models import UnitTestCrashDumpMetaData
admin.site.register(UnitTestCrashDumpMetaData)

from bughunter.models import UnitTestAssertion
admin.site.register(UnitTestAssertion)

from bughunter.models import UnitTestValgrind
admin.site.register(UnitTestValgrind)

from bughunter.models import SocorroRecord
admin.site.register(SocorroRecord)

from bughunter.models import SiteTestRun
admin.site.register(SiteTestRun)

from bughunter.models import SiteTestCrash
admin.site.register(SiteTestCrash)

from bughunter.models import SiteTestCrashDumpMetaData
admin.site.register(SiteTestCrashDumpMetaData)

from bughunter.models import SiteTestAssertion
admin.site.register(SiteTestAssertion)

from bughunter.models import SiteTestValgrind
admin.site.register(SiteTestValgrind)
