// based upon http://developer.mozilla.org/en/docs/index.php?title=Chrome:_Command_Line
const nsISupportsString      = Components.interfaces.nsISupportsString;
const nsIAppShellService    = Components.interfaces.nsIAppShellService;
const nsISupports           = Components.interfaces.nsISupports;
const nsICategoryManager    = Components.interfaces.nsICategoryManager;
const nsIComponentRegistrar = Components.interfaces.nsIComponentRegistrar;
const nsICommandLine        = Components.interfaces.nsICommandLine;
const nsICommandLineHandler = Components.interfaces.nsICommandLineHandler;
const nsIFactory            = Components.interfaces.nsIFactory;
const nsIModule             = Components.interfaces.nsIModule;
const nsIWindowWatcher      = Components.interfaces.nsIWindowWatcher;

const CHROME_URI = "chrome://spider/content/";
const clh_contractID = "@mozilla.org/commandlinehandler/general-startup;1?type=spider";
const clh_CID = Components.ID("{38003cf3-3579-4985-b61f-e0ef78dc5bc5}");
const clh_category = "m-spider";

/**
 * Utility functions
 */

/**
 * Opens a chrome window.
 * @param aChromeURISpec a string specifying the URI of the window to open.
 * @param aArgument an argument to pass to the window (may be null)
 */
function openWindow(aChromeURISpec, aArgument)
{
  var ww = Components.classes["@mozilla.org/embedcomp/window-watcher;1"].
    getService(Components.interfaces.nsIWindowWatcher);
  ww.openWindow(null, aChromeURISpec, "_blank",
                "chrome,menubar,toolbar,status,resizable,dialog=no",
                aArgument);
}
 
/**
 * The XPCOM component that implements nsICommandLineHandler.
 * It also implements nsIFactory to serve as its own singleton factory.
 */
const SpiderHandler = {
  /* nsISupports */
  QueryInterface : function clh_QI(iid)
  {
    if (iid.equals(nsICommandLineHandler) ||
        iid.equals(nsIFactory) ||
        iid.equals(nsISupports))
      return this;

    throw Components.results.NS_ERROR_NO_INTERFACE;
  },

  /* nsICommandLineHandler */

  handle : function clh_handle(cmdLine)
  {

    // must invoke spider via -spider
    // arguments with values are optional 

    var errors     = '';
    var sArgument  = ''; // individual argument string value
    var oArguments = {}; // hash of argument string values
    var xArguments;      // xpcom nsISupportsString containing serialization
                         // of oArguments

    function getFlag(flag)
    {
      return cmdLine.handleFlag(flag, false);
    }

    function getArgument(flag)
    {
      try {
	var sArgument = cmdLine.handleFlagWithParam(flag, false);
      }
      catch (e) {
	errors += flag + " argument requires value: " + e + '\n';
      }
      return sArgument;
    }

    if (!getFlag("spider")) {
      return;
    }

    oArguments.url     = getArgument('url');
    oArguments.uri     = getArgument('uri');
    oArguments.domain  = getArgument('domain');
    oArguments.depth   = Number(getArgument('depth'));
    oArguments.timeout = Number(getArgument('timeout'));
    oArguments.wait    = Number(getArgument('wait'));
    oArguments.hook    = getArgument('hook');

    oArguments.start        = getFlag('start');
    oArguments.quit         = getFlag('quit');
    oArguments.robot        = getFlag('robot');
    oArguments.debug        = getFlag('debug');
    oArguments.jserrors     = getFlag('jserrors');
    oArguments.jswarnings   = getFlag('jswarnings');
    oArguments.chromeerrors = getFlag('chromeerrors');
    oArguments.xblerrors    = getFlag('xblerrors');
    oArguments.csserrors    = getFlag('csserrors');
    oArguments.httpresponses = getFlag('httpresponses');

    if (errors)
    {
      Components.utils.reportError(errors);
    }

    xArguments = Components.classes["@mozilla.org/supports-string;1"]
    .createInstance(nsISupportsString);
    xArguments.data = oArguments.toSource();

    openWindow(CHROME_URI, xArguments);
    cmdLine.preventDefault = true;

  },

  // CHANGEME: change the help info as appropriate, but
  // follow the guidelines in nsICommandLineHandler.idl
  // specifically, flag descriptions should start at
  // character 24, and lines should be wrapped at
  // 72 characters with embedded newlines,
  // and finally, the string should end with a newline
  helpInfo : 
  "  -spider              Start Spider (required)\n" +
  "  -url <url>           Spider site at <url>\n" +
  "  -uri <url>           Spider site at <uri>\n" +
  "  -domain <domain>     Restrict Spider to urls matching <domain>\n" +
  "  -depth <depth>       Spider to depth of <depth>\n" +
  "  -timeout <timeout>   Time out Spider if page takes more than <timeout>\n" +
  "                       seconds\n" +
  "  -wait <wait>         Pause Spider for <wait> seconds after each page\n" +
  "  -hook <hookscript>   Execute Spider <hookscript>\n" +
  "  -start               Automatically start Spider\n" +
  "  -quit                Automatically quit when finished\n" +
  "  -robot               Obey robots.txt\n" +
  "  -debug               Debug Spider\n" +
  "  -jserrors            Display JavaScript errors\n" +
  "  -jswarnings          Display JavaScript warnings\n" +
  "  -chromeerrors        Display chrome errors\n" +
  "  -xblerrors           Display XBL errors\n" +
  "  -csserrors           Display CSS errors\n" +
  "  -httpresponses       Display HTTP responses\n",

  /* nsIFactory */

  createInstance : function clh_CI(outer, iid)
  {
    if (outer != null)
      throw Components.results.NS_ERROR_NO_AGGREGATION;

    return this.QueryInterface(iid);
  },

  lockFactory : function clh_lock(lock)
  {
    /* no-op */
  }

};

/**
 * The XPCOM glue that implements nsIModule
 */
const SpiderHandlerModule = {
  /* nsISupports */
  QueryInterface : function mod_QI(iid)
  {
    if (iid.equals(nsIModule) ||
        iid.equals(nsISupports))
      return this;

    throw Components.results.NS_ERROR_NO_INTERFACE;
  },

  /* nsIModule */
  getClassObject : function mod_gch(compMgr, cid, iid)
  {
    if (cid.equals(clh_CID))
      return SpiderHandler.QueryInterface(iid);

    throw Components.results.NS_ERROR_NOT_REGISTERED;
  },

  registerSelf : function mod_regself(compMgr, fileSpec, location, type)
  {
    compMgr.QueryInterface(nsIComponentRegistrar);

    compMgr.registerFactoryLocation(clh_CID,
                                    "SpiderHandler",
                                    clh_contractID,
                                    fileSpec,
                                    location,
                                    type);

    var catMan = Components.classes["@mozilla.org/categorymanager;1"].
      getService(nsICategoryManager);
    catMan.addCategoryEntry("command-line-handler",
                            clh_category,
                            clh_contractID, true, true);
  },

  unregisterSelf : function mod_unreg(compMgr, location, type)
  {
    compMgr.QueryInterface(nsIComponentRegistrar);
    compMgr.unregisterFactoryLocation(clh_CID, location);

    var catMan = Components.classes["@mozilla.org/categorymanager;1"].
      getService(nsICategoryManager);
    catMan.deleteCategoryEntry("command-line-handler", clh_category);
  },

  canUnload : function (compMgr)
  {
    return true;
  }
};

/* The NSGetModule function is the magic entry point that XPCOM uses to find what XPCOM objects
 * this component provides
 */
function NSGetModule(comMgr, fileSpec)
{
  return SpiderHandlerModule;
}
