/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
 * CCallWrapper.js
 */

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
 * The Original Code is Netscape code.
 *
 * The Initial Developer of the Original Code is
 * Netscape Corporation.
 * Portions created by the Initial Developer are Copyright (C) 2003
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s): Bob Clary <bclary@netscape.com>
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

function CCallWrapper(aObjectReference, 
                      aDelay,
                      aMethodName, 
                      aArgument0,
                      aArgument1,
                      aArgument2,
                      aArgument3,
                      aArgument4,
                      aArgument5,
                      aArgument6,
                      aArgument7,
                      aArgument8,
                      aArgument9
                     )
{
  this.mId = 'CCallWrapper_' + (CCallWrapper.mCounter++);
  this.mObjectReference = aObjectReference;
  this.mDelay     = aDelay;
  this.mTimerId = 0;
  this.mMethodName = aMethodName;
  this.mArgument0 = aArgument0;
  this.mArgument1 = aArgument1;
  this.mArgument2 = aArgument2;
  this.mArgument3 = aArgument3;
  this.mArgument4 = aArgument4;
  this.mArgument5 = aArgument5;
  this.mArgument6 = aArgument6;
  this.mArgument7 = aArgument7;
  this.mArgument8 = aArgument8;
  this.mArgument9 = aArgument9;
  CCallWrapper.mPendingCalls[this.mId] = this;
  dlog('Created CCallWrapper mMethodName=' + this.mMethodName + ', mTimerId=' + this.mTimerId + ', mId=' + this.mId);
}

CCallWrapper.prototype.execute = function CCallWrapper_execute()
{
  dlog('CCallWrapper.execute mMethodName=' + this.mMethodName + ' mTimerId=' + this.mTimerId + ', mId=' + this.mId);
  this.mObjectReference[this.mMethodName](this.mArgument0,
                                          this.mArgument1,
                                          this.mArgument2,
                                          this.mArgument3,
                                          this.mArgument4,
                                          this.mArgument5,
                                          this.mArgument6,
                                          this.mArgument7,
                                          this.mArgument8,
                                          this.mArgument9
                                         );
  delete CCallWrapper.mPendingCalls[this.mId];
  if (gDebug)
  {
    var dmsg = '[ ';
    var pmsg;
    for (pmsg in CCallWrapper.mPendingCalls)
    {
      dmsg += pmsg + ' ';
    }
    dmsg += ']';
    dlog('CCallWrapper.execute mPendingCalls=' + dmsg);
  }
};

CCallWrapper.prototype.cancel = function CCallWrapper_cancel()
{
  dlog('CCallWrapper.cancel mMethodName=' + this.mMethodName + ', mTimerId=' + this.mTimerId + ', mId=' + this.mId);
  clearTimeout(this.mTimerId);
  delete CCallWrapper.mPendingCalls[this.mId];
  if (gDebug)
  {
    var dmsg = '[ ';
    var pmsg;
    for (pmsg in CCallWrapper.mPendingCalls)
    {
      dmsg += pmsg + ' ';
    }
    dmsg += ']';
    dlog('CCallWrapper.cancel mPendingCalls=' + dmsg);
  }
};

CCallWrapper.asyncExecute = function CCallWrapper_asyncExecute(/* CCallWrapper */ callwrapper)
{
  CCallWrapper.mPendingCalls[callwrapper.mId].mTimerId =
  setTimeout(function (){CCallWrapper.mPendingCalls[callwrapper.mId].execute();},
             callwrapper.mDelay);
  dlog('CCallwrapper.asyncExecute mMethodName=' + callwrapper.mMethodName + ', mTimerId=' + callwrapper.mTimerId + ', mId=' + callwrapper.mId + ', mDelay=' + callwrapper.mDelay);
};

CCallWrapper.mCounter = 0;
CCallWrapper.mPendingCalls = {};
