/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
 * CSpider.js
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
 *                 Bob Clary <http://bclary.com/>
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

var gCSpiderOnLoadCallbackDelay = 100;
var gSecurityMessage = 'CSpider requires security privileges to operate.\nPlease see Help for more details.';
var gSecurityPrivileges = 'UniversalXPConnect UniversalBrowserRead UniversalBrowserWrite';


function CUrl(aDepth, aUrl, aReferer)
{
  dlog('CUrl(' + aDepth + ', ' + aUrl + ', ' + aReferer +')');
  this.mDepth = aDepth;
  this.mUrl   = aUrl;
  this.mReferer = aReferer;
}

function CSpider(/* String */ aUrl,
  /* String */ aDomain,
  /* Boolean */ aRestrictUrl,
  /* Number */ aDepth,
  /* CPageLoader */ aPageLoader,
  /* Seconds */ aOnLoadTimeoutInterval,
  /* Boolean */ aExtraPrivileges, // no longer used
  /* Boolean */ aRespectRobotRules,
  /* Boolean */ aFileUrls,
  /* String */ aUserAgent)
{
  //@JSD_LOG

  dlog('Constructing CSpider');

  if (aUrl.indexOf('http://') == -1 &&
      aUrl.indexOf('https://') == -1 &&
      aUrl.indexOf('file://') == -1 &&
      aUrl.indexOf('chrome://') == -1)
  {
    aUrl = 'http://' + aUrl;
  }

  this.mUrl = aUrl;

  if (aDomain)
  {
    this.mDomain = aDomain;
  }
  else
  {
    // remove extraneous leading parts of the url
    // to allow restricted urls to stay in the domain

    if (aUrl.indexOf('http://') != -1)
    {
      this.mDomain = aUrl.substr('http://'.length);
    }
    else
    {
      this.mDomain = aUrl.substr('https://'.length);
    }

    if (this.mDomain.indexOf('www.') != -1)
    {
      this.mDomain = this.mDomain.substr('www.'.length);
    }
  }

  this.mRestrictUrl = aRestrictUrl;
  this.mDepth  = aDepth;
  this.mPageLoader = aPageLoader;
  this.mOnLoadTimeoutInterval = (aOnLoadTimeoutInterval || 60) * 1000;
  this.mExtraPrivileges = aExtraPrivileges || false;
  this.mRespectRobotRules = aRespectRobotRules || false;
  this.mFileUrls = aFileUrls || false;
  this.mUserAgent = aUserAgent || 'Gecko/';
  this.init(aUrl);

}

CSpider.prototype.init = function CSpider_init(aUrl)
{
  //@JSD_LOG

  dlog('CSpider.init')

  this.mPagesVisited  = [];
  this.mPagesPending  = [ new CUrl(0, aUrl, null) ];
  this.mPageHash = {};
  this.mPageHash[aUrl] = true;
  this.mState = 'ready';
};

CSpider.prototype.run =
  function CSpider_run()
{
  //@JSD_LOG

  dlog('CSpider.run ' + this.mState);

  if (this.mState != 'ready')
  {
    dlog('CSpider.run called for invalid state ' + this.mState);
    return;
  }

  if (this.mDepth > -1)
  {
    this.init(this.mUrl);
    if (!this.mOnStart())
    {
      this.mState = 'ready';
      return;
    }
    this.mState = 'running';
    this.loadPage();
  }
};

CSpider.prototype.restart =
  function CSpider_restart()
{
  //@JSD_LOG

  dlog('CSpider.restart ' + this.mState);

  if (this.mState != 'paused' && this.mState != 'timeout')
  {
    dlog('CSpider.restart called for invalid state ' + this.mState);
    return;
  }

  if (!this.mOnRestart())
  {
    this.pause();
    return;
  }

  this.mState = 'running';
  this.loadPage();
};

CSpider.prototype.pause =
  function CSpider_pause()
{
  //@JSD_LOG

  dlog('CSpider.pause ' + this.mState);

  if (this.mPageLoader.ontimeout_ccallwrapper)
  {
    this.mState = 'pausing';
  }
  else
  {
    this.mState = 'paused';

    if (!this.mOnPause())
    {
      this.mState = 'running';
      this.loadPage();
    }
  }
};

CSpider.prototype.stop =
  function CSpider_stop()
{
  //@JSD_LOG

  dlog('CSpider.stop ' + this.mState);

  if (this.mPageLoader.ontimeout_ccallwrapper)
  {
    this.mState = 'stopping';
  }
  else
  {
    this.mState = 'stopped';

    if (!this.mOnStop() && this.mPagesPending.length > 0)
    {
      this.mState = 'running';
      this.loadPage();
    }
  }
};

CSpider.prototype.addPage =
  function CSpider_addPage(href)
{
  //@JSD_LOG
  if (!href)
  {
    return;
  }

  // only spider http protocols
  var lhref = href.toLowerCase();

  if (lhref.search(/^http(s)?:/) == -1)
  {
    if (lhref.search(/^file:/) == -1 || !this.mFileUrls)
    {
      // skip non http url if it is a non-file url or
      // if it is a file url and we have not allowed them.
      return;
    }
  }

  var hashIndex = href.indexOf('#');
  if (hashIndex != -1)
  {
    href = href.substr(0, hashIndex);
  }

  if (typeof(this.mPageHash[href]) != 'undefined' &&
      this.mPageHash[href])
  {
    return;
  }

  if (this.mCurrentUrl.mDepth + 1 > this.mDepth)
  {
    return;
  }

  if (this.mRestrictUrl && href.indexOf(this.mDomain) == -1)
  {
    return;
  }

  dlog('CSpider.addPage ' + href);
  this.mPageHash[href] = true;
  this.mPagesPending.push(
    new CUrl(this.mCurrentUrl.mDepth + 1, href, this.mCurrentUrl.mUrl ));
};

CSpider.prototype.loadPage =
  function CSpider_loadPage()
{
  //@JSD_LOG

  dlog('CSpider.loadPage ' + this.mState);

  if (this.mState != 'running')
  {
    dlog('CSpider.loadPage not running. ' + this.mState);
    return;
  }

  this.mState = 'loading';

  this.mCurrentUrl = this.mPagesPending.shift();

  var isGoodUrl = false;

  while (this.mCurrentUrl != null && !isGoodUrl)
  {
    var href = this.mCurrentUrl.mUrl;
    var lhref = href.toLowerCase();

    if (this.mCurrentUrl.mDepth > this.mDepth)
    {
      dlog('CSpider.loadPage ignoring ' + this.mCurrentUrl.mUrl +
           ' mCurrentUrl.mDepth > ' + this.mCurrentUrl.mDepth +
           ' CSpider.mDepth ' + this.mDepth);
      this.mCurrentUrl = this.mPagesPending.pop();
    }
    else if (
      lhref.search(/\.aac$/) != -1 ||
        lhref.search(/\.ads$/) != -1 ||
        lhref.search(/\.adp$/) != -1 ||
        lhref.search(/\.app$/) != -1 ||
        lhref.search(/\.asx$/) != -1 ||
        lhref.search(/\.bas$/) != -1 ||
        lhref.search(/\.bat$/) != -1 ||
        lhref.search(/\.bin$/) != -1 ||
        lhref.search(/\.chm$/) != -1 ||
        lhref.search(/\.cmd$/) != -1 ||
        lhref.search(/\.cpl$/) != -1 ||
        lhref.search(/\.crt$/) != -1 ||
        lhref.search(/\.csh$/) != -1 ||
        lhref.search(/\.dmg$/) != -1 ||
        lhref.search(/\.doc$/) != -1 ||
        lhref.search(/\.dtd$/) != -1 ||
        lhref.search(/\.exe$/) != -1 ||
        lhref.search(/\.fxp$/) != -1 ||
        lhref.search(/\.fdf$/) != -1 ||
        lhref.search(/\.hlp$/) != -1 ||
        lhref.search(/\.hta$/) != -1 ||
        lhref.search(/\.inf$/) != -1 ||
        lhref.search(/\.ins$/) != -1 ||
        lhref.search(/\.isp$/) != -1 ||
        lhref.search(/\.jar$/) != -1 ||
        lhref.search(/\.js$/)  != -1 ||
        lhref.search(/\.jse$/) != -1 ||
        lhref.search(/\.gz$/)  != -1 ||
        lhref.search(/\.ksh$/) != -1 ||
        lhref.search(/\.lnk$/) != -1 ||
        lhref.search(/\.mda$/) != -1 ||
        lhref.search(/\.mdb$/) != -1 ||
        lhref.search(/\.mde$/) != -1 ||
        lhref.search(/\.mdt$/) != -1 ||
        lhref.search(/\.mdw$/) != -1 ||
        lhref.search(/\.mdz$/) != -1 ||
        lhref.search(/\.mov$/) != -1 ||
        lhref.search(/\.mp3$/) != -1 ||
        lhref.search(/\.mp4$/) != -1 ||
        lhref.search(/\.msc$/) != -1 ||
        lhref.search(/\.msi$/) != -1 ||
        lhref.search(/\.msp$/) != -1 ||
        lhref.search(/\.mst$/) != -1 ||
        lhref.search(/\.ops$/) != -1 ||
        lhref.search(/\.pcd$/) != -1 ||
        lhref.search(/\.pdf$/) != -1 ||
        lhref.search(/\.pif$/) != -1 ||
        lhref.search(/\.ppt$/) != -1 ||
        lhref.search(/\.prf$/) != -1 ||
        lhref.search(/\.prg$/) != -1 ||
        lhref.search(/\.qtif$/) != -1 ||
        lhref.search(/\.reg$/) != -1 ||
        lhref.search(/\.rtf$/) != -1 ||
        lhref.search(/\.scf$/) != -1 ||
        lhref.search(/\.scr$/) != -1 ||
        lhref.search(/\.sct$/) != -1 ||
        lhref.search(/\.shb$/) != -1 ||
        lhref.search(/\.shs$/) != -1 ||
        lhref.search(/\.url$/) != -1 ||
        lhref.search(/\.vb$/)  != -1 ||
        lhref.search(/\.vbe$/) != -1 ||
        lhref.search(/\.vbs$/) != -1 ||
        lhref.search(/\.vml$/) != -1 ||
        lhref.search(/\.wsc$/) != -1 ||
        lhref.search(/\.wsf$/) != -1 ||
        lhref.search(/\.wsh$/) != -1 ||
        lhref.search(/\.tar$/) != -1 ||
        lhref.search(/\.tgz$/) != -1 ||
        lhref.search(/\.torrent$/) != -1 ||
        lhref.search(/\.wm$/) != -1 ||
        lhref.search(/\.wma$/) != -1 ||
        lhref.search(/\.wax$/) != -1 ||
        lhref.search(/\.wmv$/) != -1 ||
        lhref.search(/\.wvx$/) != -1 ||
        lhref.search(/\.xdp$/) != -1 ||
        lhref.search(/\.xfdf$/) != -1 ||
        lhref.search(/\.xls$/) != -1 ||
        lhref.search(/\.xpi$/) != -1 ||
        lhref.search(/\.zip$/) != -1
    )
    {
      dlog('CSpider.loadPage Bad Extension blocked ' + href);
      this.mCurrentUrl = this.mPagesPending.pop();
    }
    else if (this.mRespectRobotRules && isRobotBlocked(href, this.mUserAgent))
    {
      msg('CSpider.loadPage Robot Rules blocked ' + href);
      this.mCurrentUrl = this.mPagesPending.pop();
    }
    else
    {
      isGoodUrl = true;
    }
  }

  if (!this.mCurrentUrl)
  {
    dlog('CSpider.loadPage no more pages. Stop');
    this.stop();
    return;
  }

  // release reference to previous document
  this.mDocument = null;

  if (!this.mOnBeforePage())
  {
    this.pause();
    this.mPagesPending.push(this.mCurrentUrl);
    return;
  }

  dlog('CSpider.loadPage setting mPageLoader location=' +
       this.mCurrentUrl.mUrl);
  this.mPageLoader.load(this.mCurrentUrl.mUrl, this.mCurrentUrl.mReferer);

};

CSpider.prototype.onLoadPageTimeout =
  function CSpider_onLoadPageTimeout()
{
  //@JSD_LOG

  dlog('CSpider.onLoadPageTimeout ' + this.mState);

  // call mOnPageTimeout prior to the mPageLoader.cancel
  // so that the timeout handler has access to the document
  // object.
  if (!this.mOnPageTimeout())
  {
    this.mState = 'running';
    this.loadPage();
    return;
  }

  this.mPageLoader.cancel();

  if (this.mState == 'pausing')
  {
    this.pause();
    return;
  }

  if (this.mState == 'stopping')
  {
    this.stop();
    return;
  }

  this.mState = 'timeout';
};

CSpider.prototype.onLoadPage =
  function CSpider_onLoadPage()
{
  //@JSD_LOG


  dlog('CSpider.onLoadPage ' + this.mState);

  if (this.mPageLoader.ontimeout_ccallwrapper)
  {
    this.mPageLoader.cancel();
  }

  this.mDocument = this.mPageLoader.getDocument();

  if (this.mState == 'stopping')
  {
    this.mOnAfterPage();
    this.stop();
    return;
  }

  if (this.mState == 'pausing')
  {
    this.pause();
    return;
  }

  if (this.mState != 'loading')
  {
    // XXX: bclary. this can occur in the XUL based version
    // since it appears the onload event fires multiple times
    // for a xul:iframe but not for an html:iframe.
    // go figure.
    // See https://bugzilla.mozilla.org/show_bug.cgi?id=196057
    // Fixed on trunk https://bugzilla.mozilla.org/show_bug.cgi?id=234455
    dlog('CSpider.onLoadPage called with state ' + this.mState +
         '. links not added to page stack');
    return;
  }

  var i;
  var links;

  try
  {
    links  = this.mDocument.links;
  }
  catch(ex)
  {
    msg(ex);
  }

  if (!links)
  {
    dlog('CSpider_onLoadPage: no document.links found in document');
  }
  else
  {
    var length = links.length;
    var href;

    if (length == 0)
    {
      dlog('CSpider_onLoadPage: document.links.length == 0');
    }

    for (i = 0; i < length; ++i)
    {
      href = links[i].href;
      if (href)
      {
        this.addPage(href);
      }
    }

    links = this.mDocument.getElementsByTagName('frame');
    length = links.length;

    for (i = 0; i < length; ++i)
    {
      href = links[i].src;
      if (href)
      {
        this.addPage(href);
      }
    }

    links = this.mDocument.getElementsByTagName('iframe');
    length = links.length;

    for (i = 0; i < length; ++i)
    {
      href = links[i].src;
      if (href)
      {
        this.addPage(href);
      }
    }
  }

  this.mState = 'loaded';

  this.mPagesVisited.push(this.mCurrentUrl.mUrl);

  if (!this.mOnAfterPage())
  {
    this.pause();
    return;
  }

  this.mState = 'running';
  this.loadPage();

};


CSpider.prototype.cancelLoadPage =
  function CSpider_cancelLoadPage()
{
  dlog('CSpider.cancelLoadPage ' + this.mState);

  this.mPageLoader.cancel();
  if (this.mCurrentUrl)
  {
    //    this.mPagesPending.push(this.mCurrentUrl);
    this.mCurrentUrl = null;
  }
  this.mDocument = null;
};

CSpider.prototype.mOnStart =
  function CSpider_mOnStart_Default()
{
  //@JSD_LOG
  // override this
  return true;
};

CSpider.prototype.mOnBeforePage =
  function CSpider_mOnBeforePage_Default()
{
  //@JSD_LOG
  // override this
  return true;
};

CSpider.prototype.mOnAfterPage =
  function CSpider_mOnAfterPage_Default()
{
  //@JSD_LOG
  // override this
  return true;
};

CSpider.prototype.mOnPageTimeout =
  function CSpider_mOnPageTimeout_Default()
{
  //@JSD_LOG
  // override this
  return true;
};

CSpider.prototype.mOnStop =
  function CSpider_mOnStop_Default()
{
  //@JSD_LOG
  // override this
  return true;
};

CSpider.prototype.mOnPause =
  function CSpider_mOnPause_Default()
{
  //@JSD_LOG
  // override this
  return true;
};

CSpider.prototype.mOnRestart =
  function CSpider_mOnRestart_Default()
{
  //@JSD_LOG
  // override this
  return true;
};
