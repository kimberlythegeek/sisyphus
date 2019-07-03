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

Examples
Loading urls from a file

```
$ ssh mozauto@tantalus1.pi-interop.mdc1.mozilla.com
mozauto@tantalus1 $ ct
mozauto@tantalus1 $ python crashloader.py --urls=/tmp/urls --username=your_ldap_username@mozilla.com
```

Loading urls from Crash Stats
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

<!-- ## Helpful Tips

* Run SQL queries against the webapp’s DB
* Stop a current job from running -->
