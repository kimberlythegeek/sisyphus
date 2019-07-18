# Tantalus

## Table of contents:

* [Getting involved](#getting-involved)
* [Infrastructure](#infrastructure)
* [Usage](#usage)
  * [Requirements](#Requirements)
  * [Basic Usage](#basic-usage)
* [Helpful Tips](#helpful-tips)

## Getting involved

We love working with contributors to improve and add features to our projects. At this time, Tantalus is in its formative stages. The project requires enhanced privileges to access internal environments that are not publicly accessible.

We genuinely appreciate your interest in this project and hope to one day open it up to the community. For now, this is a project that is being worked on internally at Mozilla.

## Infrastructure

This project is a fork of Bughunter, an internal tool designed to reproduce crashes from reports
in crash stats. Bughunter is also referred to as Sisyphus.

The infrastructure has one main virtual machine (VM), Tantalus, which is based on a Red Hat Fedora 64-bit image. Tantalus executes the tests on the virtual machines, also known as workers or worker VMs, and also hosts the web application. Each of the worker VMs is running Windows 10 64-bit.

The tests consist of loading URLs that are either pulled from [crash-stats.mozilla.com](https://crash-stats.mozilla.com/), commonly referred to as Socorro, or loaded from a specified file. If the browser crashes during startup or when opening a URL, the crash data, along with other information about the build, is stored in the database and is viewable at [http://tantalus1.pi-interop.mdc1.mozilla.com/bughunter/](tantalus1.pi-interop.mdc1.mozilla.com/bughunter).

There is one “master” worker, which will be referred to as the *builder*. This is the default build,  `win10i64-01.pi-interop.mdc1.mozilla.com`. It is responsible for locating and downloading the correct Firefox builds via the Taskcluster API, and uploading the builds to Tantalus. The rest of the workers obtain their builds from Tantalus.

Each worker is configured with a different 3rd party application, such as antivirus program, accessibility software, or firefox extension. The different configurations are maintained with VM snapshots.

![image](https://user-images.githubusercontent.com/18633586/60605561-fdb96c00-9d76-11e9-9c6c-20ac31216c3f.png)

## Usage

### Requirements

Base requirements:

* A Mozilla employee LDAP account
* Ensure you are in the  `VPN_Web_predict` group LDAP group
* A VPN that is configured to work with [Mozilla VPN](https://mana.mozilla.org/wiki/display/SD/VPN)
* A Remote Desktop Protocol client for Microsoft
* Credentials for the `mozauto` account on the Worker VMs


### Basic Usage

The builder is specified in a file called `crashworker.sh`. This file also specifies which
firefox builds to test against on each worker. This file is located in `/mozilla/bin`. It is
run on Windows using the `crashworker.bat` file.

The `crashworker.bat` file needs to be started on each VM that will be used for testing. Login to the workers using RDP (credentials can be acquired from kimberlythegeek or mbrandt), and run the `crashworker.bat` file located on the desktop.

Once the script has been started on each worker, ssh into Tantalus to start the `crashloader.py` script. The alias `ct` will change directories to the location of the script.

#### Examples
The following examples will create one test run for each URL used as an input,
**for each worker VM currently running `crashworker.bat`**. The first example,
is using a file containing a list of 200 urls. So, each worker will test **all 200** urls.

Currently there are **7 worker VMs** configured to run tests, each with a different
third-party application installed. The URLs and apps for the workers are as follows:

3rd Party App | URL
--- | ---
Default | [win10i64-01.pi-interop.mdc1.mozilla.com](win10i64-01.pi-interop.mdc1.mozilla.com)
Avast | [win10i64-02.pi-interop.mdc1.mozilla.com](win10i64-02.pi-interop.mdc1.mozilla.com)
AVG | [win10i64-03.pi-interop.mdc1.mozilla.com](win10i64-03.pi-interop.mdc1.mozilla.com)
Avira | [win10i64-04.pi-interop.mdc1.mozilla.com](win10i64-04.pi-interop.mdc1.mozilla.com)
Kaspersky | [win10i64-05.pi-interop.mdc1.mozilla.com](win10i64-05.pi-interop.mdc1.mozilla.com)
360 Total Security | [win10i64-06.pi-interop.mdc1.mozilla.com](win10i64-06.pi-interop.mdc1.mozilla.com)
NVDA | [win10i64-07.pi-interop.mdc1.mozilla.com](win10i64-07.pi-interop.mdc1.mozilla.com)

##### Loading urls from a file

```
$ ssh mozauto@tantalus1.pi-interop.mdc1.mozilla.com
mozauto@tantalus1 $ ct
mozauto@tantalus1 $ python crashloader.py --urls=/tmp/urls --username=your_ldap_username@mozilla.com
```

##### Loading urls from Crash Stats
```
$ python crashloader.py --start-date=2019-04-11T12:00:00 --stop-date=2019-04-22T18:00:00
```

For a complete list of options, use `python crashloader.py --help`

```
$ python crashworker.py --help
Usage: crashloader.py [options]


Options:
  -h, --help            show this help message and exit
  --userhook=USERHOOK   userhook to execute for each loaded page. Defaults to
                        test-crash-on-load.js.
  --page-timeout=PAGE_TIMEOUT
                        Time in seconds before a page load times out. Defaults
                        to 180 seconds
  --site-timeout=SITE_TIMEOUT
                        Time in seconds before a site load times out. Defaults
                        to 300 seconds
  --build               Perform own builds
  --no-upload           Do not upload completed builds
  --nodebug             default - no debug messages
  --debug               turn on debug messages
  --processor-type=PROCESSOR_TYPE
                        Override default processor type: intel32, intel64,
                        amd32, amd64
  --symbols-paths=SYMBOLS_PATHS
                        Space delimited list of paths to third party symbols.
                        Defaults to /mozilla/flash-symbols
  --do-not-reproduce-bogus-signatures
                        Do not attempt to reproduce crashes with signatures of
                        the form (frame)
  --buildspec=BUILDSPECS
                        Build specifiers: Restricts the builds tested by this
                        worker to one of opt, debug, opt-asan, debug-asan.
                        Defaults to all build types specified in the Branches
                        To restrict this worker to a subset of build
                        specifiers, list each desired specifier in separate
                        --buildspec options.
  --tinderbox           If --build is specified, this will cause the worker to
                        download the latest tinderbox builds instead of
                        performing custom builds. Defaults to False.
Usage: crashworker.py [options]
```

### Viewing results

* [View crash data](http://tantalus1.pi-interop.mdc1.mozilla.com/bughunter)
* [View Workers](http://tantalus1.pi-interop.mdc1.mozilla.com/#admin/workers)
* [Worker Summary](http://tantalus1.pi-interop.mdc1.mozilla.com/#admin/workersummary)

#### Configuring Additional Workers

Bughunter, or Sisyphus, from which Tantalus was forked, only had the capability to
target machines by *operating system*. This was problematic for our purposes, as we
are running the same operating systems, but with different third party applications installed
on each.

Tantalus creates an entry in SiteTestRun for each combination of:
- operating system
- firefox channel
- firefox build
- url

So, if you have multiple workers with the same operating system, Tantalus will load balance
by dividing the test runs among all the workers.

To improve efficiency, we needed to enable concurrent test runs on our workers--that is,
creating a SiteTestRun for each combination of:
- operating system
- firefox channel
- firefox build
- url
- *and* third party application

The quickest way to accomplish this is neither optimal nor recommended, but it is the
approach we are currently using: we have coupled the third party application with the
firefox build.

After provisioning a new worker (likely a clone of the default or -01 worker), and
installing the third party application of your choice, proceed as follows.

1. For each firefox build type you wish to test, create a new row in the Branch
table of the database. An example for the ESET antivirus program:

product | branch | major_version | buildtype
--- | --- | --- | ---
firefox | nightly | 6800 | opt-eset
firefox | nightly | 6800 | opt-asan-eset
firefox | beta | 6800 | opt-eset

2. Modify the `/mozilla/bin/crashworker.sh` file to include the new worker and buildspecs.
While not required, it is recommended to make this change on all workers for consistency.

```

...

while true; do
    case $(hostname) in
        win10i64-01)
            python    crashworker.py --page-timeout=$page_timeout --site-timeout=$site_timeout --do-not-reproduce-bogus-signatures --buildspec=opt --buildspec=opt-asan --tinderbox --build
            ;;

            ...

        win10i64-08)
            python    crashworker.py --page-timeout=$page_timeout --site-timeout=$site_timeout --do-not-reproduce-bogus-signatures --buildspec=opt-eset --buildspec=opt-asan-eset --tinderbox
            ;;
    esac
    echo waiting...
    sleep 300
done
```

#### Useful SQL Queries

Currently the data formatting and reporting is performed manually, and there are a
variety of SQL queries that make these tasks easier to complete.

##### Check for Test Completion

To check if there are any unprocessed urls:

```
SELECT * FROM SiteTestRun WHERE state != 'completed'
```

To abort any remaining tests:

```
UPDATE SiteTestRun SET state = 'completed' WHERE state != 'completed'
```

##### Fetch Crash Data For Tantalus Report
The columns in this query match up with the table structure used in our Tantalus
reports, currently displayed in a Google Docs spreadsheet.

```
SELECT d.signature as app, a.url, a.reason, a.crashtype, a.datetime, a.exploitability, b.branch, b.buildtype, a.crashreport, b.log, b.fatal_message, c.signature as crash_signature
	FROM SiteTestCrash a
		LEFT JOIN SiteTestRun b on a.testrun_id = b.id
		LEFT JOIN Crash c on a.crash_id = c.id
		LEFT JOIN SocorroRecord d on b.socorro_id = d.id
		ORDER BY a.datetime DESC;
```

##### List URLs Ordered by Crash Rate
This will fetch a list of all URLs associated with a crash, ordered from high to low,
by the number of crashes reported.
```
SELECT url, COUNT(url) AS count FROM SiteTestCrash GROUP BY url ORDER BY count DESC;
```

##### List Crash Signatures Ordered by Crash Rate
```
SELECT reason, COUNT(reason) AS count FROM SiteTestCrash GROUP BY reason ORDER BY count DESC;
```



<!-- ## Helpful Tips

* Run SQL queries against the webapp’s DB
* Stop a current job from running -->
