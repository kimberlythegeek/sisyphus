const APP_NAME     = 'spider';
const APP_PACKAGE  = '/bclary.com/spider';
const APP_VERSION  = '0.0.5.1';
const APP_JAR_PATH = 'chrome/spider.jar';
const APP_JAR_FILE = 'spider.jar';
const APP_CONTENT  = 'content/spider/';
const APP_LOCALES  = ['locale/en-US/spider/'];
const APP_SKINS    = ['skin/classic/spider/', 'skin/modern/spider/'];

var i;
var chromeFolder;
var err = initInstall(APP_NAME, APP_PACKAGE, APP_VERSION);

logComment('initInstall err = ' + err);

if (!err)
{
  chromeFolder = getFolder('Chrome');
  setPackageFolder(chromeFolder);

  err = addFile(APP_PACKAGE, APP_VERSION, APP_JAR_PATH, chromeFolder, null);
  logComment('addFile: ' + APP_JAR_PATH + ', err = ' + err);
}

if (!err && APP_CONTENT)
{
  err = registerChrome(PACKAGE | DELAYED_CHROME, 
                       getFolder(chromeFolder, APP_JAR_FILE), APP_CONTENT);
  logComment('registerChrome content = ' + APP_CONTENT + ', err = ' + err);
}

if (!err && APP_LOCALES)
{
  for (i = 0; i < APP_LOCALES.length; i++)
  {
    err = registerChrome(LOCALE | DELAYED_CHROME, 
                         getFolder(chromeFolder, APP_JAR_FILE), APP_LOCALES[i]);
    logComment('registerChrome locale = ' + APP_LOCALES[i] + ', err = ' + err);
  }
}

if (!err && APP_SKINS)
{
  for (i = 0; i < APP_SKINS.length; i++)
  {
    err = registerChrome(SKIN | DELAYED_CHROME, 
                         getFolder(chromeFolder, APP_JAR_FILE), APP_SKINS[i]);
    logComment('registerChrome skin = ' + APP_SKINS[i] + ', err = ' + err);
  }
}

if (err)
{
  cancelInstall( err );
}
else
{
  performInstall();
}

