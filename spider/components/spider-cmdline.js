// based upon http://developer.mozilla.org/en/docs/index.php?title=Chrome:_Command_Line
const nsISupportsString      = Components.interfaces.nsISupportsString;
const nsISupports           = Components.interfaces.nsISupports;
const nsICommandLineHandler = Components.interfaces.nsICommandLineHandler;
const nsIFactory            = Components.interfaces.nsIFactory;
const nsIWindowWatcher      = Components.interfaces.nsIWindowWatcher;

const CHROME_URI = "chrome://spider/content/";
const clh_contractID = "@mozilla.org/commandlinehandler/general-startup;2?type=spider";
const clh_CID = Components.ID("{38003cf3-3579-4985-b61f-e0ef78dc5bc5}");
const clh_category = "m-spider";

Components.utils.import("resource://gre/modules/XPCOMUtils.jsm");

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
 * See http://mxr.mozilla.org/mozilla-central/source/js/src/xpconnect/loader/XPCOMUtils.jsm
 */

function SpiderHandler() {}

SpiderHandler.prototype = {
  classDescription : "SpiderHandler",
  classID          : clh_CID,
  contractID       : clh_contractID,

  _xpcom_factory: {
    /*
     * singleton nsIFactory
     * see http://mxr.mozilla.org/mozilla-central/source/xpcom/components/nsIFactory.idl
     */
    createInstance : function clh_CI(outer, iid)
    {
      if (outer != null)
        throw Components.results.NS_ERROR_NO_AGGREGATION;

      // singleton because returns reference to an existing instance
      // instead of creating a new instance.
      return spiderhandler_singleton.QueryInterface(iid);
    },

    lockFactory : function clh_lock(lock)
    {
      /* no-op */
    }
  },

  // See http://mxr.mozilla.org/mozilla-central/source/xpcom/components/nsICategoryManager.idl
  _xpcom_categories : [
    { category : "command-line-handler",
      entry    : clh_category,  // optional - defaults to classDescription
      value    : clh_contractID // optional - defaults to contractID
    }
  ],

  QueryInterface : XPCOMUtils.generateQI(
    [
      nsICommandLineHandler,
      nsIFactory,
      nsISupports
    ]
  ),

  /* nsICommandLineHandler */

  handle : function clh_handle(cmdLine)
  {

    // must invoke spider via -spider
    // arguments with values are optional

    var errors     = '';
    var sArgument  = ''; // individual argument string value
    var oArguments = {}; // hash of argument string values
    var xArguments;      // xpcom nsISupportsString containing serialization of oArguments

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
    oArguments.invisible     = getFlag('invisible');

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
    "  -httpresponses       Display HTTP responses" +
    "  -invisible           Hide loaded page\n"
};

// create the singleton
spiderhandler_singleton = new SpiderHandler();

var components = [SpiderHandler];

/**
 * From https://developer.mozilla.org/en/XPCOM/XPCOM_changes_in_Gecko_1.9.3
 * XPCOMUtils.generateNSGetFactory was introduced in Mozilla 2 (Firefox 4).
 * XPCOMUtils.generateNSGetModule is for Mozilla 1.9.2 (Firefox 3.6).
 */
if (XPCOMUtils.generateNSGetFactory)
  var NSGetFactory = XPCOMUtils.generateNSGetFactory([SpiderHandler]);
else
  var NSGetModule = XPCOMUtils.generateNSGetModule([SpiderHandler]);
