# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import glob
import json
import logging
import os
import platform
import random
import re
import signal
import sys
import tempfile
import time
import urlparse

import requests

import mozprofile

from marionette_driver.marionette import Marionette, Alert
from marionette_driver import errors

def get_remote_text(url):
    """Return the string containing the contents of a remote url if the
    request is successful, otherwise return None.

    :param url: url of content to be retrieved.

    """
    logger = logging.getLogger('sisyphus')

    try:
        parse_result = urlparse.urlparse(url)
        if not parse_result.netloc or parse_result.scheme.startswith('file'):
            local_file = open(parse_result.path)
            with local_file:
                return local_file.read()

        while True:
            r = requests.get(url, headers={'user-agent': 'sisyphus'})
            if r.ok:
                return r.text
            elif r.status_code != 503:
                logger.warning("Unable to open url %s : %s",
                               url, r.reason)
                return None
            # Server is too busy. Wait and try again.
            # See https://bugzilla.mozilla.org/show_bug.cgi?id=1146983#c10
            logger.warning("HTTP 503 Server Too Busy: url %s", url)
            time.sleep(60 + random.randrange(0, 30, 1))
    except Exception, e:
        logger.warning('%s: Unable to open %s', e, url)

    return None


def runner_options():
    parser = argparse.ArgumentParser(description='Sisyphus Firefox runner')
    parser.add_argument('--url',
                        help='URL to load into Firefox.')
    parser.add_argument('--restart',
                        action='store_true',
                        default=False,
                        help='Restart after setting preferences.')
    parser.add_argument('--wait',
                        default=0,
                        help="""Time in seconds to wait before closing browser.
                        Default: 0.""")
    parser.add_argument('--binary',
                        required=True,
                        help='Path to Firefox binary.')
    parser.add_argument('--profile',
                        help="""Path to profile. If not specified, a temporary
                        profile will be created""")
    parser.add_argument('--page-load-timeout',
                        type=int,
                        default=300,
                        help="""Time in seconds before Firefox process killed.
                        Default: 300.""")
    parser.add_argument('--script-timeout',
                        type=int,
                        default=10,
                        help="""Time in seconds before Script is terminated.
                        Default: 10.""")
    parser.add_argument('--gecko-log',
                        default='-',
                        help="""Path to gecko log file.
                        Default: "-" write to stdout.""")
    parser.add_argument('--symbols-path',
                        help='Path to directory containing Firefox symbols.')
    parser.add_argument('--stackwalk-binary',
                        default='/usr/local/bin/minidump_stackwalk',
                        help="""Path to mindump_stackwalk binary.
                        Default: /usr/local/bin/minidump_stackwalk.""")
    parser.add_argument('--chrome-script',
                        dest='chrome_scripts',
                        action='append',
                        default=[],
                        help="""Path to script to be loaded into the chrome
                        context. Repeat for additional files.
                        Be careful not to block the browser with modal requests.""")
    parser.add_argument('--content-script',
                        dest='content_scripts',
                        action='append',
                        default=[],
                        help="""Path to script to be loaded into the content
                        context. Repeat for additional files.""")
    parser.add_argument('--set-preference',
                        dest='set_preferences',
                        action='append',
                        default=[],
                        help="""Add preference of the form name=value.
                        Repeat for additional preferences.""")
    parser.add_argument('--preference-file',
                        dest='preference_files',
                        action='append',
                        default=[],
                        help="""Path to prefs.js file containing preferences.""")
    parser.add_argument('--preference-json',
                        dest='preference_jsons',
                        action='append',
                        default=[],
                        help="""Path to json file containing preferences
                        {'name':value...}. Repeat for additional files.""")
    parser.add_argument('--extension',
                        action='append',
                        default=[],
                        help="""Path to extension to install.
                        Repeat for additional extensions.""")
    parser.add_argument('--extensions-dir',
                        help='Path to directory containing extensions to install.')
    return parser.parse_args()


def run_firefox(args):
    logger = logging.getLogger('sisyphus')
    logger.setLevel(logging.DEBUG)
    streamhandler = logging.StreamHandler(stream=sys.stdout)
    streamformatter = logging.Formatter('%(asctime)s %(name)15s %(levelname)-8s %(message)s')
    streamhandler.setFormatter(streamformatter)
    logger.addHandler(streamhandler)

    # On Windows, make sure we point to the same temp directory as cygwin.
    if platform.system() == 'Windows':
        tempfile.tempdir = 'C:\\cygwin\\tmp'
    # Clean up tmpaddons
    tmpaddons = glob.glob(os.path.join(tempfile.gettempdir(), 'tmpaddon*'))
    for tmpaddon in tmpaddons:
        os.unlink(tmpaddon)

    # Work around Windows issues with shell metacharacters in url.
    if not args.url:
        if "URL" in os.environ:
            args.url = os.environ["URL"]
        else:
            logger.error("run_firefox: url is required")
            return

    # Load preferences of the form name=value from the
    # command line arguments.
    def eval_value(value):
        """Convert preference string value"""
        if value == 'true':
            value = True
        elif value == 'false':
            value = False
        else:
            try:
                value = eval(value)
            except NameError:
                # Leave string value alone.
                pass
        return value

    mozprofile_preferences = mozprofile.prefs.Preferences()

    preferences = {}
    set_preference_args = []
    for set_preference_arg in args.set_preferences:
        (name, value) = set_preference_arg.split('=', 1)
        set_preference_args.append((name, eval_value(value)))

    preferences.update(dict(set_preference_args))

    # Load preferences of from json files.
    for preference_json_arg in args.preference_jsons:
        preferences.update(dict(mozprofile_preferences.read_json(preference_json_arg)))

    # Load preferences from Firefox prefs.js/user.js files.
    for preference_file_arg in args.preference_files:
        preferences.update(dict(mozprofile_preferences.read_prefs(preference_file_arg)))

    logger.info("preferences: %s", json.dumps(preferences, indent=2, sort_keys=True))

    profile = mozprofile.profile.FirefoxProfile(profile=args.profile,
                                                preferences=preferences)
    client = Marionette(host='localhost',
                        port=2828,
                        bin=args.binary,
                        profile=profile,
                        gecko_log=args.gecko_log,
                        symbols_path=args.symbols_path)

    client.start_session()
    if args.restart:
        client.restart(clean=False, in_app=True)
    client.maximize_window()

    references = {'time_out_alarm_fired': False}

    if hasattr(signal, 'SIGALRM'):
        # Windows doesn't support SIGALRM. marionette
        # doesn't support cygwin paths...
        def timeout_handler(signum, frame):
            logger.warning("navigate: %s timed out" % args.url)
            references['time_out_alarm_fired'] = True
            client.quit()

        default_alarm_handler = signal.getsignal(signal.SIGALRM)

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(args.page_load_timeout + 2*args.script_timeout)

    try:
        client.timeout.page_load = args.page_load_timeout
        client.timeout.script = args.script_timeout
        # Register the dialog closer for the browser. If the download
        # dialog appears, it will be closed and the browser window
        # will be closed. This forces marionette to return from
        # navigate and works around Bug 1366035. This version does
        # not dismiss normal Alerts which can be handled by Marionette's Alert.
        dialog_closer_script = """
var gDialogCloser;
var gDialogCloserObserver;
var gDialogCloserSubjects = [];

registerDialogCloser = function () {
  gDialogCloser = Components.classes['@mozilla.org/embedcomp/window-watcher;1'].getService(Components.interfaces.nsIWindowWatcher);
  gDialogCloserObserver = {observe: dialogCloser_observe};
  gDialogCloser.registerNotification(gDialogCloserObserver);
}

unregisterDialogCloser = function () {
  if (!gDialogCloserObserver || !gDialogCloser)
  {
    return;
  }

  gDialogCloser.unregisterNotification(gDialogCloserObserver);
  gDialogCloserObserver = null;
  gDialogCloser = null;
}

dialogCloser_observe = function (subject, topic, data) {
  if (subject instanceof ChromeWindow && topic == 'domwindowopened' )
  {
    gDialogCloserSubjects.push(subject);
    subject.setTimeout(closeDialog, 5000)
  }
}

closeDialog = function () {
  var subject;
  while ( (subject = gDialogCloserSubjects.pop()) != null)
  {
      if (subject.document instanceof XULDocument) {
          var uri = subject.document.documentURI;
          //if (uri.startsWith('chrome://') && uri.endsWith('ialog.xul')) {
          //    subject.close();
          //} else
          if (uri == 'chrome://mozapps/content/downloads/unknownContentType.xul') {
              dump('Sisyphus Runner: Closing Window due to download dialog\\n');
              subject.close();
              window.close();
          }
      }
  }
}

registerDialogCloser();
"""
        client.set_context(client.CONTEXT_CHROME)
        client.execute_script(dialog_closer_script,
                              new_sandbox=False, script_timeout=client.timeout.script)
        client.set_context(client.CONTEXT_CONTENT)
        try:
            logger.info('New Page: %s' % args.url)
            client.navigate(args.url)
            client.maximize_window()
        except Exception, e:
            logger.warning('navigate: %s', e)

        # Do not call client.check_for_crash() as that will invoke
        # mozcrash which will delete the dump files. Handle the dumps
        # in the caller.
        client.set_context(client.CONTEXT_CONTENT)
        for content_script_url in args.content_scripts:
            content_script = get_remote_text(content_script_url)
            if content_script:
                try:
                    logger.info('<contentscript>\n%s\n</contentscript>', content_script)
                    result = client.execute_script(content_script, script_args=[], script_timeout=client.timeout.script)
                    logger.info('content script result: %s', result)
                except errors.ScriptTimeoutException, e:
                    logger.warning('content script: %s', e)
        for chrome_script_url in args.chrome_scripts:
            chrome_script = get_remote_text(chrome_script_url)
            if chrome_script:
                with client.using_context(client.CONTEXT_CHROME):
                    try:
                        logger.info('<chromescript>\n%s\n</chromescript>', chrome_script)
                        result = client.execute_script(chrome_script, sandbox='system', script_args=[client.timeout.script], script_timeout=client.timeout.script)
                        logger.info('chrome script result: %s\n', result)
                    except errors.ScriptTimeoutException, e:
                        logger.warning('chrome script: %s', e)
        time.sleep(float(args.wait))
        while True:
            try:
                logger.info('alert: %s', Alert(client).text)
                Alert(client).dismiss()
            except errors.NoAlertPresentException:
                break
        client.quit(in_app=True)
    except (errors.TimeoutException, errors.UnknownException, IOError), e:
        logger.warning("ABNORMAL: %s", e)
        try:
            client.quit(in_app=True)
            if client.session:
                os.kill(client.session['moz:processID'], 9)
        except errors.MarionetteException, e:
            if 'Please start a session' not in e.message:
                raise # If the error is not that the app had disconnected/terminated.
    except errors.MarionetteException, e:
        logger.exception('time_out_alarm_fired %s', references['time_out_alarm_fired'])
        if 'Please start a session' in e.message:
            pass # Typically terminated firefox with marionette calls pending.
    finally:
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)
            signal.signal(signal.SIGALRM, default_alarm_handler)

if __name__ == '__main__':
    logging.basicConfig()
    logger = logging.getLogger('sisyphus')
    args = runner_options()
    run_firefox(args)
