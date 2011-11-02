/* -*- Mode: JavaScript; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
 * User hook to investigate the use of 2 digit versions in Firefox 10.
 * Load initial page but do not spider it. Instead, load the contained
 * links and then for each link:
 *
 * 1. set ua to Firefox 9
 * 2. open link in new window
 * 3. record loaded resources
 * 4. take snapshot image of window using canvas
 * 5. close window
 * 6. set ua to Firefox 10
 * 7. open link in new window
 * 8. record loaded resources
 * 9. take snapshot image of window using canvas.
 * 10. compare loaded resources and snapshots to determine if
 *     page depends on Firefox 9 single digit version and
 *     output result to the log.
 *
 * see https://developer.mozilla.org/en/Mozilla_Embedding_FAQ/How_do_I...#How_do_I_change_the_user_agent_string.3F

 */

/*
 * ug_foo - global userhook variable
 */

var ug_canvas_height         = 1024;
var ug_canvas_width          = 1200;
var ug_load_delay            = 4*1000;
var ug_page_timeout          = 120;
var ug_user_agent_firefox_09 = 'Mozilla/5.0 (Windows NT 6.1; rv:9.0a2) Gecko/20100101 Firefox/9.0a2';
var ug_user_agent_firefox_10 = 'Mozilla/5.0 (Windows NT 6.1; rv:10.0a1) Gecko/20100101 Firefox/10.0a1';


var ug_xulns = 'http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul';

var ug_pbs = Components.classes["@mozilla.org/privatebrowsing;1"]
  .getService(Components.interfaces.nsIPrivateBrowsingService);

var ug_preferences = Components.classes['@mozilla.org/preferences;1'];
if (ug_preferences) {
  var ug_pref_service = ug_preferences.getService(Components.interfaces.nsIPrefService);
  var ug_pref_branch = ug_pref_service.getBranch('');
}

var ug_current_url;
var ug_current_user_agent;
var ug_xulbrowser;
var ug_page_loader;
var ug_loader_canvas;
var ug_loader_ctx;


var ug_link_index      = -1;
var ug_state_not_run   = 'not run';
var ug_state_timed_out = 'timed out';
var ug_state_loaded    = 'loaded';
var ug_data            = null;
var ug_responses       = [];
var ug_re_safebrowsing = /(safebrowsing-cache.google.com|safebrowsing.clients.google.com)/;
var ug_re_mozilla      = /mozilla\.(org|com)/i;
var ug_re_javascript   = /^javascript:/;

function userOnStart()
{
  dlog('userOnStart()');
  // turn off unsolicited popups during load.
  ug_pref_branch.setBoolPref('dom.disable_open_during_load', true);
  // turn on dump() function
  ug_pref_branch.setBoolPref('browser.dom.window.dump.enabled', true);
  // turn on private browsing
  ug_pbs.privateBrowsingEnabled = true;
}

function userOnBeforePage()
{
  dlog('userOnBeforePage()');
  registerDialogCloser();
}

function userOnPause()
{
  dlog('userOnPause()');
}

function userOnAfterPage()
{
  dlog('userOnAfterPage()');

  ug_xulbrowser = document.createElementNS(ug_xulns, 'xul:browser');
  ug_xulbrowser.setAttribute('type', 'content');
  ug_xulbrowser.style.position = 'absolute';
  ug_xulbrowser.style.top    = '0px';
  ug_xulbrowser.style.left   = '0px';
  ug_xulbrowser.style.height = ug_canvas_height + 'px';
  ug_xulbrowser.style.width  = ug_canvas_width + 'px';
  document.documentElement.appendChild(ug_xulbrowser);
  ug_xulbrowser.contentWindow.resizeTo(ug_canvas_width, ug_canvas_height);

  ug_loader_canvas = document.createElementNS('http://www.w3.org/1999/xhtml', 'canvas')
  ug_loader_canvas.height = ug_canvas_height;
  ug_loader_canvas.width  = ug_canvas_width;

  ug_loader_ctx = ug_loader_canvas.getContext('2d');

  cdump('Spider Comparator: var comparisons = [];');

  load_pages();
}

function userOnStop()
{
  dlog('userOnStop()');

  unregisterDialogCloser();
  reset_user_agent();
}

function reset_user_agent() {
  ug_pref_branch.clearUserPref('general.useragent.override');
  ug_pref_branch.clearUserPref('general.platform.override');
  ug_pref_branch.clearUserPref('general.appname.override');
  ug_pref_branch.clearUserPref('general.appversion.override');
}

function change_user_agent(ua)
{
  ug_pref_branch.setCharPref('general.useragent.override', ua);
}

function get_domain(url) {
  var re = /https?:\/\/([^\/]*)/;
  var captures = re.exec(url);
  if (captures && captures.length == 2) {
    return captures[1];
  }
  dlog('get_domain failed: url=' + url);
  return null;
}

function create_loader(onload_callback, ontimeout_callback) {
  dlog('create_loader');

  ug_responses = [];
  ug_xulbrowser.loadURI('about:blank', null);
  ug_page_loader = new CPageLoader(
    ug_xulbrowser,
    onload_callback,
    ontimeout_callback,
    ug_page_timeout,
    new CHTTPResponseObserver((function (response) {
      ug_responses.push(response);
    }))
  );

  dlog('create_loader: normal exit');
}

function update_msg(s) {
  msg(s + 
      ' ' + ug_current_url +
      ' (' + (ug_link_index + 1) +
      '/' + gSpider.mDocument.links.length + ')');
}

function load_pages() {
  dlog('load_pages()');

  if (ug_data) {
    var completed = true;   // true means all pages loaded
    var dump_images = true; // true means to remove image urls from dump to reduce output size.
    var differs = false;    // true means candidate for investigtion

    // For now only care about Firefox 9 vs. Firefox 10 image differences.
    differs = ug_data.comparison.images_differ;

    // delete unneeded data before dumping to the log...
    delete ug_data.comparison.image_data_diff;

    for each (var useragent in ['firefox_09', 'firefox_10']) {
      delete ug_data[useragent].image_data_diff;
      for each (var run in ['run1', 'run2']) {
        delete ug_data[useragent][run].responses;
        delete ug_data[useragent][run].image_data;
        delete ug_data[useragent][run].unique_responses;

        switch (ug_data[useragent][run].state) {
        case ug_state_not_run:
        case ug_state_timed_out:
          cdump('Spider: ' + ug_data.url + ' ' + useragent + ' ' + run + ' failed to complete ' + ug_data[useragent][run].state);
          completed = false;
          break;
        }
      }
    }

    if (!completed) {
      dump_images = false;
      cdump('Spider: ' + ug_data.url + ' did not complete loading each page.');
    }
    else if (!differs) {
      dump_images = false;
      cdump('Spider: ' + ug_data.url + ' is identical across reponses and useragents.');
    }
    else if (!ug_data.firefox_09.images_differ || !ug_data.firefox_10.images_differ) {
      cdump('Spider: ' + ug_data.url + ' Firefox 9 and/or Firefox 10\'s runs were not identical.');
    }

    for each (var useragent in ['firefox_09', 'firefox_10']) {
      for each (var run in ['run1', 'run2']) {
        if (!dump_images) { // don't dump image url if they are not different
          ug_data[useragent][run].image_url = '';
        }
        for each (var prop in ['state', 'image_url']) {
          cdump('Spider Comparator: url_data.' + useragent + '.' + run + '.' + prop + ' = ' + JSON.stringify(ug_data[useragent][run][prop]) + ';');
        }
      }
      for each (var prop in ['responses_differ', 'images_differ', 'image_diff_url']) {
        cdump('Spider Comparator: url_data.' + useragent + '.' + prop + '=' + JSON.stringify(ug_data[useragent][prop]) + ';');
      }
    }

    if (!dump_images) {
      ug_data.comparison.image_diff_url = '';
    }
    for each (var prop in ['responses_differ', 'firefox_09', 'firefox_10', 'images_differ', 'image_diff_url']) {
      cdump('Spider Comparator: url_data.comparison.' + prop + '=' + JSON.stringify(ug_data.comparison[prop]) + ';');
    }

  }

  if (++ug_link_index >= gSpider.mDocument.links.length) {
    dlog('load_pages: completed');
    gPageCompleted = true;
    return;
  }

  ug_current_url = gSpider.mDocument.links[ug_link_index].href;
  dlog('ug_current_url = ' + ug_current_url);

  if (ug_re_javascript.exec(ug_current_url)) {
    cdump('Spider: skipping javascript: link ' + ug_current_url);
    setTimeout(load_pages, 100);
    return;
  }

  var domain = get_domain(ug_current_url);
  if (!domain) {
    cdump('Spider: skipping null domain ' + ug_current_url);
    setTimeout(load_pages, 100);
    return;
  }

  if (ug_re_mozilla.exec(domain)) {
    cdump('Spider: skipping mozilla domain ' + ug_current_url);
    setTimeout(load_pages, 100);
    return;
  }

  // Force GC to see if this helps in memory growth.
  Components.utils.forceGC();

  ug_data = {
    url : ug_current_url,
    firefox_09 : {
      run1 : {
        state     : ug_state_not_run,
        responses : {},
        image_url : '',
        image_data : null,
        unique_responses : {},
      },
      run2 : {
        state     : ug_state_not_run,
        responses : {},
        image_url : '',
        image_data : null,
        unique_responses : {},
      },
      responses_differ : false,
      images_differ : false,
      image_data_diff : null,
      image_diff_url : '',
    },
    firefox_10 : {
      run1 : {
        state     : ug_state_not_run,
        responses : {},
        image_url : '',
        image_data : null,
        unique_responses : {},
      },
      run2 : {
        state     : ug_state_not_run,
        responses : {},
        image_url : '',
        image_data : null,
        unique_responses : {},
      },
      responses_differ : false,
      images_differ : false,
      image_data_diff : null,
      image_diff_url : '',
    },
    comparison : {
      responses_differ : false,
      images_differ    : false,
      firefox_09       : {unique_responses : {}},
      firefox_10       : {unique_responses : {}},
      image_data_diff : null,
      image_diff_url : '',
    }
  };

  cdump('Spider Comparator: url_data =' + JSON.stringify(ug_data) + ';');
  cdump('Spider Comparator: comparisons.push(url_data);');

  cdump('Spider: *****************************');
  cdump('Spider: load_pages: ug_current_url = ' + ug_current_url);
  setTimeout(load_page_firefox_09_1, 100);

}

// start firefox 9 1
function load_page_firefox_09_1() {
  dlog('load_page_firefox_09_1 url=' + ug_current_url);

  ug_current_user_agent = ug_user_agent_firefox_09;
  change_user_agent(ug_current_user_agent);

  var domain = get_domain(ug_current_url);
  if (domain) {
    ug_pbs.removeDataFromDomain(domain);
  }

  for each (var response in ug_responses) {
    var originalURI = response.originalURI;

    domain = get_domain(originalURI);
    if (domain) {
      ug_pbs.removeDataFromDomain(domain);
    }
  }

  create_loader(handle_initial_load_firefox_09_1, handle_timeout_firefox_09_1);
  update_msg('Firefox 9 1: loading');
  ug_page_loader.load(ug_current_url, null);
}

function handle_timeout_firefox_09_1() {
  dlog('handle_timeout_firefox_09_1');
  update_msg('Firefox 9 1: timed out');
  ug_data.firefox_09.run1.state = ug_state_timed_out;
  cdump('Spider: Firefox 9 1 TIMEOUT: ug_current_url=' + ug_current_url);
  setTimeout(load_pages, 100);
}

function handle_initial_load_firefox_09_1(evt) {
  cdump('handle_initial_load_firefox_09_1');
  update_msg('Firefox 9 1: loaded');
  setTimeout(handle_load_firefox_09_1, ug_load_delay, evt);
}

function handle_load_firefox_09_1(evt) {
  dlog('handle_load_firefox_09_1 url = ' + ug_current_url);
  update_msg('Firefox 9 1: processing');

  ug_data.firefox_09.run1.state = ug_state_loaded;
  ug_data.firefox_09.run1.responses = {}

  for each (var response in ug_responses) {
    if (ug_re_safebrowsing.exec(response.originalURI))
      true;
    else if (ug_re_mozilla.exec(response.orignalURI))
      true;
    else if (response.contentType == 'application/ocsp-response')
      true;
    else
      ug_data.firefox_09.run1.responses[response.originalURI] = response;
  }
  dlog('handle_load_firefox_09_1: ug_current_url = ' + ug_current_url + ', ug_xulbrowser.currentURI = ' + ug_xulbrowser.currentURI + ', useragent = ' + ug_current_user_agent + ', responses = ' + ug_data.firefox_09.run1.responses.toSource());
  dlog('handle_load_firefox_01_1: window size = ' + ug_xulbrowser.contentWindow.innerWidth + ',' + ug_xulbrowser.contentWindow.innerHeight);

  ug_loader_ctx.drawWindow(ug_xulbrowser.contentWindow,
                           0, 0,
                           ug_xulbrowser.contentWindow.innerWidth, ug_xulbrowser.contentWindow.innerHeight,
                           "rgb(255,255,255)");
  ug_data.firefox_09.run1.image_url = ug_loader_canvas.toDataURL("image/png", "");
  ug_data.firefox_09.run1.image_data = ug_loader_ctx.getImageData(0, 0,
                                                                  ug_xulbrowser.contentWindow.innerWidth,
                                                                  ug_xulbrowser.contentWindow.innerHeight);

  setTimeout(load_page_firefox_09_2, 100);
}
// end firefox 9 - 1

// start firefox 9 2
function load_page_firefox_09_2() {
  dlog('load_page_firefox_09_2 url=' + ug_current_url);

  ug_current_user_agent = ug_user_agent_firefox_09;
  change_user_agent(ug_current_user_agent);

  var domain = get_domain(ug_current_url);
  if (domain) {
    ug_pbs.removeDataFromDomain(domain);
  }

  for each (var response in ug_responses) {
    var originalURI = response.originalURI;

    domain = get_domain(originalURI);
    if (domain) {
      ug_pbs.removeDataFromDomain(domain);
    }
  }

  create_loader(handle_initial_load_firefox_09_2, handle_timeout_firefox_09_2);
  update_msg('Firefox 9 2: loading');
  ug_page_loader.load(ug_current_url, null);
}

function handle_timeout_firefox_09_2() {
  dlog('handle_timeout_firefox_09_2');
  update_msg('Firefox 9 2: timed out');
  ug_data.firefox_09.run2.state = ug_state_timed_out;
  cdump('Spider: Firefox 9 2 TIMEOUT: ug_current_url=' + ug_current_url);
  setTimeout(load_pages, 100);
}

function handle_initial_load_firefox_09_2(evt) {
  cdump('handle_initial_load_firefox_09_2');
  update_msg('Firefox 9 2: loaded');
  setTimeout(handle_load_firefox_09_2, ug_load_delay, evt);
}

function handle_load_firefox_09_2() {
  dlog('handle_load_firefox_09_2 url = ' + ug_current_url);
  update_msg('Firefox 9 2: processing');

  ug_data.firefox_09.run2.state = ug_state_loaded;
  ug_data.firefox_09.run2.responses = {}

  for each (var response in ug_responses) {
    if (ug_re_safebrowsing.exec(response.originalURI))
      true;
    else if (ug_re_mozilla.exec(response.orignalURI))
      true;
    else if (response.contentType == 'application/ocsp-response')
      true;
    else
      ug_data.firefox_09.run2.responses[response.originalURI] = response;
  }
  dlog('handle_load_firefox_09_2: ug_current_url = ' + ug_current_url + ', ug_xulbrowser.currentURI = ' + ug_xulbrowser.currentURI + ', useragent = ' + ug_current_user_agent + ', responses = ' + ug_data.firefox_09.run2.responses.toSource());

  ug_loader_ctx.drawWindow(ug_xulbrowser.contentWindow,
                           0, 0,
                           ug_xulbrowser.contentWindow.innerWidth, ug_xulbrowser.contentWindow.innerHeight,
                           "rgb(255,255,255)");
  ug_data.firefox_09.run2.image_url = ug_loader_canvas.toDataURL("image/png", "");
  ug_data.firefox_09.run2.image_data = ug_loader_ctx.getImageData(0, 0,
                                                                  ug_xulbrowser.contentWindow.innerWidth,
                                                                  ug_xulbrowser.contentWindow.innerHeight);

  setTimeout(load_page_firefox_10_1, 100);
}
// end firefox 9 - 2

// start firefox 10 1
function load_page_firefox_10_1() {
  dlog('load_page_firefox_10_1 url=' + ug_current_url);

  ug_current_user_agent = ug_user_agent_firefox_10;
  change_user_agent(ug_current_user_agent);

  var domain = get_domain(ug_current_url);
  if (domain) {
    ug_pbs.removeDataFromDomain(domain);
  }

  for each (var response in ug_responses) {
    var originalURI = response.originalURI;

    domain = get_domain(originalURI);
    if (domain) {
      ug_pbs.removeDataFromDomain(domain);
    }
  }

  create_loader(handle_initial_load_firefox_10_1, handle_timeout_firefox_10_1);
  update_msg('Firefox 10 1: loading');
  ug_page_loader.load(ug_current_url, null);

}

function handle_timeout_firefox_10_1() {
  dlog('handle_timeout_firefox_10_1');
  update_msg('Firefox 10 1: timed out');
  ug_data.firefox_10.run1.state = ug_state_timed_out;
  cdump('Spider: Firefox 10 1 TIMEOUT: ug_current_url=' + ug_current_url);
  setTimeout(load_pages, 100);
}

function handle_initial_load_firefox_10_1(evt) {
  cdump('handle_initial_load_firefox_10_1');
  update_msg('Firefox 10 1: loaded');
  setTimeout(handle_load_firefox_10_1, ug_load_delay, evt);
}

function handle_load_firefox_10_1() {
  dlog('handle_load_firefox_10_1 url = ' + ug_current_url);
  update_msg('Firefox 10 1: processing');

  ug_data.firefox_10.run1.state = ug_state_loaded;
  ug_data.firefox_10.run1.responses = {}

  for each (var response in ug_responses) {
    if (ug_re_safebrowsing.exec(response.originalURI))
      true;
    else if (ug_re_mozilla.exec(response.orignalURI))
      true;
    else if (response.contentType == 'application/ocsp-response')
      true;
    else
      ug_data.firefox_10.run1.responses[response.originalURI] = response;
  }
  dlog('handle_load_firefox_10_1: ug_current_url = ' + ug_current_url + ', ug_xulbrowser.currentURI = ' + ug_xulbrowser.currentURI + ', useragent = ' + ug_current_user_agent + ', responses = ' + ug_data.firefox_10.run1.responses.toSource());

  ug_loader_ctx.drawWindow(ug_xulbrowser.contentWindow,
                           0, 0,
                           ug_xulbrowser.contentWindow.innerWidth, ug_xulbrowser.contentWindow.innerHeight,
                           "rgb(255,255,255)");
  ug_data.firefox_10.run1.image_url = ug_loader_canvas.toDataURL("image/png", "");
  ug_data.firefox_10.run1.image_data = ug_loader_ctx.getImageData(0, 0,
                                                                  ug_xulbrowser.contentWindow.innerWidth,
                                                                  ug_xulbrowser.contentWindow.innerHeight);

  setTimeout(load_page_firefox_10_2, 100);
}
// end firefox 10 1

// start firefox 10 2
function load_page_firefox_10_2() {
  dlog('load_page_firefox_10_2 url=' + ug_current_url);

  ug_current_user_agent = ug_user_agent_firefox_10;
  change_user_agent(ug_current_user_agent);

  var domain = get_domain(ug_current_url);
  if (domain) {
    ug_pbs.removeDataFromDomain(domain);
  }

  for each (var response in ug_responses) {
    var originalURI = response.originalURI;

    domain = get_domain(originalURI);
    if (domain) {
      ug_pbs.removeDataFromDomain(domain);
    }
  }

  create_loader(handle_initial_load_firefox_10_2, handle_timeout_firefox_10_2);
  update_msg('Firefox 10 2: loading');
  ug_page_loader.load(ug_current_url, null);

}

function handle_timeout_firefox_10_2() {
  dlog('handle_timeout_firefox_10_2');
  update_msg('Firefox 10 2: timed out');
  ug_data.firefox_10.run2.state = ug_state_timed_out;
  cdump('Spider: Firefox 10 2 TIMEOUT: ug_current_url=' + ug_current_url);
  setTimeout(load_pages, 100);
}

function handle_initial_load_firefox_10_2(evt) {
  cdump('handle_initial_load_firefox_10_2');
  update_msg('Firefox 10 2: loaded');
  setTimeout(handle_load_firefox_10_2, ug_load_delay, evt);
}

function handle_load_firefox_10_2() {
  dlog('handle_load_firefox_10_2 url = ' + ug_current_url)
  update_msg('Firefox 10 2: processing');

  ug_data.firefox_10.run2.state = ug_state_loaded;
  ug_data.firefox_10.run2.responses = {}

  for each (var response in ug_responses) {
    if (ug_re_safebrowsing.exec(response.originalURI))
      true;
    else if (ug_re_mozilla.exec(response.orignalURI))
      true;
    else if (response.contentType == 'application/ocsp-response')
      true;
    else
      ug_data.firefox_10.run2.responses[response.originalURI] = response;
  }
  dlog('handle_load_firefox_10_2: ug_current_url = ' + ug_current_url + ', ug_xulbrowser.currentURI = ' + ug_xulbrowser.currentURI + ', useragent = ' + ug_current_user_agent + ', responses = ' + ug_data.firefox_10.run2.responses.toSource());

  ug_loader_ctx.drawWindow(ug_xulbrowser.contentWindow,
                           0, 0,
                           ug_xulbrowser.contentWindow.innerWidth, ug_xulbrowser.contentWindow.innerHeight,
                           "rgb(255,255,255)");
  ug_data.firefox_10.run2.image_url = ug_loader_canvas.toDataURL("image/png", "");
  ug_data.firefox_10.run2.image_data = ug_loader_ctx.getImageData(0, 0,
                                                                  ug_xulbrowser.contentWindow.innerWidth,
                                                                  ug_xulbrowser.contentWindow.innerHeight);

  setTimeout(compare_useragents, 100);
}
// end firefox 10 2

function compare_useragents() {
  dlog('compare_useragents');

  update_msg('Comparing Firefox 9, Firefox 10');

  var useragent;
  var useragent_other;
  var run;
  var run_other;
  var url;

  // for each user agent and run, copy the responses to
  // unique_responses so that we can delete common urls and be left
  // with the unique responses for each run.
  for each (useragent in ['firefox_09', 'firefox_10']) {
    for each (run in ['run1', 'run2']) {
      for (url in ug_data[useragent][run].responses) {
        ug_data[useragent][run].unique_responses[url] = ug_data[useragent][run].responses[url];
      }
    }
  }

  // eliminate responses with common urls between the runs.
  for each (useragent in ['firefox_09', 'firefox_10']) {
    for each (run in ['run1', 'run2']) {
      switch (run) {
      case 'run1':
        run_other = 'run2';
        break;
      case 'run2':
        run_other = 'run1';
        break;
      }
      for (url in ug_data[useragent][run].responses) {
        if (url in ug_data[useragent][run_other].responses) {
          delete ug_data[useragent][run_other].unique_responses[url]
        }
        else {
          ug_data[useragent].responses_differ = true;
        }
      }
    }
  }

  var width = ug_xulbrowser.contentWindow.innerWidth;
  var height = ug_xulbrowser.contentWindow.innerHeight;
  var image_data_diff;
  var x;
  var y;
  var offset;
  var index;
  var component;
  var pixel_is_different;

  // for each useragent compare images between the runs.
  for each (useragent in ['firefox_09', 'firefox_10']) {

    dlog('compare_useragents: compare images ' + useragent);

    if (ug_data[useragent].run1.image_url != ug_data[useragent].run2.image_url) {

      dlog('compare_useragents: compare images' + useragent + ' generating diff');

      ug_data[useragent].images_differ = true;

      image_data_diff = ug_loader_ctx.createImageData(width, height);
      ug_data[useragent].image_data_diff = image_data_diff;

      dlog('compare_useragent: new image_data_diff: width=' + image_data_diff.width + ', height=' + image_data_diff.height);

      var run1_image_data_data = ug_data[useragent].run1.image_data.data;
      var run2_image_data_data = ug_data[useragent].run2.image_data.data;

      for (offset = 0; offset < height*width*4 ; offset += 4) {

        pixel_is_different = false;

        for (component = 0; component < 4; component++) {

          index = offset + component;

          if (run1_image_data_data[index] != run2_image_data_data[index]) {
            pixel_is_different = true;
            break;
          }
        }
        if (pixel_is_different) {
          for (component = 0; component < 4; component++) {

            index = offset + component;

            image_data_diff.data[index] = run2_image_data_data[index];
          }
        }
      }
      dlog('compare_useragent: updated image_data_diff: width=' + image_data_diff.width + ', height=' + image_data_diff.height);
      ug_loader_ctx.putImageData(image_data_diff, 0, 0);
      ug_data[useragent].image_diff_url = ug_loader_canvas.toDataURL("image/png", "");

    }
  }

  // Comparisons between the useragents only really matter if each
  // useragent's two runs were identical. For that reason, when
  // comparing the different useragents, we only compare their first
  // runs.

  // For each useragent and the first run, copy the responses to
  // unique_responses so that we can delete common urls and be left
  // with the unique responses for each useragent.
  for each (useragent in ['firefox_09', 'firefox_10']) {
    for (url in ug_data[useragent].run1.responses) {
      ug_data.comparison[useragent].unique_responses[url] = ug_data[useragent].run1.responses[url];
    }
  }

  // eliminate responses with common urls between the useragents.
  for each (useragent in ['firefox_09', 'firefox_10']) {
    switch (useragent) {
    case 'firefox_09':
      useragent_other = 'firefox_10';
      break;
    case 'firefox_10':
      useragent_other = 'firefox_09';
      break;
    }
    for (url in ug_data[useragent].run1.responses) {
      if (url in ug_data[useragent_other].run1.responses) {
        delete ug_data.comparison[useragent_other].unique_responses[url]
      }
      else {
        ug_data.comparison.responses_differ = true;
      }
    }
  }

  dlog('compare_useragents: compare images Firefox 9 to Firefox 10');


  // compare useragent's first run images by comparing their data urls.
  if (ug_data.firefox_09.run1.image_url != ug_data.firefox_10.run1.image_url) {

    dlog('compare_useragents: compare images Firefox 9 to Firefox 10 generating diff');

    ug_data.comparison.images_differ = true;

    image_data_diff = ug_loader_ctx.createImageData(width, height);
    ug_data.comparison.image_data_diff = image_data_diff;

    var firefox_09_image_data_data = ug_data.firefox_09.run1.image_data.data;
    var firefox_10_image_data_data = ug_data.firefox_10.run1.image_data.data;

    for (offset = 0; offset < height*width*4 ; offset += 4) {

      pixel_is_different = false;

      for (component = 0; component < 4; component++) {

        index = offset + component;

        if (firefox_09_image_data_data[index] != firefox_10_image_data_data[index]) {
          pixel_is_different = true;
          break;
        }
      }
      if (pixel_is_different) {
        for (component = 0; component < 4; component++) {

          index = offset + component;

          image_data_diff.data[index] = firefox_10_image_data_data[index];
        }
      }
    }

    ug_loader_ctx.putImageData(image_data_diff, 0, 0);
    ug_data.comparison.image_diff_url = ug_loader_canvas.toDataURL("image/png", "");

  }

  dlog('compare_useragents: exit');
  setTimeout(load_pages, 100);
}
