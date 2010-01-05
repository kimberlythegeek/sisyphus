/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */
/* ***** BEGIN LICENSE BLOCK *****
 * Version: MPL 1.1/GPL 2.0/LGPL 2.1
 *
 * The contents of this file are subject to the Mozilla Public License Version
 * 1.1 (the "License"); you may not use this file except in compliance with
 * the License. You may obtain a copy of the License at
 * http://www.mozilla.org/MPL/
 *
 * Software distributed under the License is distributed on an "AS IS" basis,
 * WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
 * for the specific language governing rights and limitations under the
 * License.
 *
 * The Original Code is Mozilla Spider Code.
 *
 * The Initial Developer of the Original Code is
 * Mozilla Corporation.
 * Portions created by the Initial Developer are Copyright (C) 2006
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s): Bob Clary <http://bclary.com/>
 *
 * Alternatively, the contents of this file may be used under the terms of
 * either the GNU General Public License Version 2 or later (the "GPL"), or
 * the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
 * in which case the provisions of the GPL or the LGPL are applicable instead
 * of those above. If you wish to allow use of your version of this file only
 * under the terms of either the GPL or the LGPL, and not to allow others to
 * use your version of this file under the terms of the MPL, indicate your
 * decision by deleting the provisions above and replace them with the notice
 * and other provisions required by the GPL or the LGPL. If you do not delete
 * the provisions above, a recipient may use your version of this file under
 * the terms of any one of the MPL, the GPL or the LGPL.
 *
 * ***** END LICENSE BLOCK ***** */

var gDialogCloser;
var gDialogCloserObserver;

function registerDialogCloser()
{
  dlog('registerDialogCloser: start');
  if (!inChrome())
  {
    try
    {
      netscape.security.PrivilegeManager.
        enablePrivilege(gConsoleSecurityPrivileges);
    }
    catch(excp)
    {
      alert(gConsoleSecurityMessage);
      return;
    }
  }

  gDialogCloser = Components.
    classes['@mozilla.org/embedcomp/window-watcher;1'].
    getService(Components.interfaces.nsIWindowWatcher);

  gDialogCloserObserver = {observe: dialogCloser_observe};

  gDialogCloser.registerNotification(gDialogCloserObserver);

  dlog('registerDialogCloser: complete');
}

function unregisterDialogCloser()
{
  dlog('unregisterDialogCloser: start');

  if (!gDialogCloserObserver || !gDialogCloser)
  {
    return;
  }
  if (!inChrome())
  {
    try
    {
      netscape.security.PrivilegeManager.
        enablePrivilege(gConsoleSecurityPrivileges);
    }
    catch(excp)
    {
      alert(gConsoleSecurityMessage);
      return;
    }
  }

  gDialogCloser.unregisterNotification(gDialogCloserObserver);

  gDialogCloserObserver = null;
  gDialogCloser = null;

  dlog('unregisterDialogCloser: stop');
}

// use an array to handle the case where multiple dialogs
// appear at one time
var gDialogCloserSubjects = [];

function dialogCloser_observe(subject, topic, data)
{
  dlog('DialogCloser: ' +
       'subject: ' + subject + 
       ', topic=' + topic + 
       ', data=' + data + 
       ', subject.document.documentURI=' + subject.document.documentURI +
       ', subjects pending=' + gDialogCloserSubjects.length);
  if (subject instanceof ChromeWindow && topic == 'domwindowopened' )
  {
    gDialogCloserSubjects.push(subject);
    subject.setTimeout(closeDialog, 5000)
  }
  dlog('DialogCloser: subjects pending: ' + gDialogCloserSubjects.length);
}

function closeDialog()
{
  var subject;
  dlog('closeDialog: subjects pending: ' + gDialogCloserSubjects.length);

  while ( (subject = gDialogCloserSubjects.pop()) != null)
  {
    dlog('closeDialog: subject=' + subject);

    dlog('closeDialog: subject.document instanceof XULDocument: ' + (subject.document instanceof XULDocument));
    dlog('closeDialog: subject.document.documentURI: ' + subject.document.documentURI);

    if (subject.document instanceof XULDocument && 
        subject.document.documentURI == 'chrome://global/content/commonDialog.xul')
    {
      dlog('closeDialog: close');
      subject.close();
    }
    else
    {
      dlog('closeDialog: skip');
    }
  }
}
