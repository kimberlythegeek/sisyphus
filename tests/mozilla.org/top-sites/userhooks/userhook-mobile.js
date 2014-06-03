/* -*- Mode: JavaScript; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
 * User hook to investigate the use Mobile user agents and the user
 * of the video tag on the wild wild web.
 * Load initial page but do not spider it. Instead, load the contained
 * links and then for each link:
 *
 * see https://developer.mozilla.org/en/Mozilla_Embedding_FAQ/How_do_I...#How_do_I_change_the_user_agent_string.3F
 */
/*
* Color Histogram http://en.wikipedia.org/wiki/Color_histogram
* Compute a vector of the Color Histogram for each image based on all channels in the image rgba
* and treat the color histogram difference as the vector difference between the two images.
*/
/*
A new metric for grey-scale image comparison
Dale L Wilson, Adrian J Baddeley, Robyn A. Owens
May 18, 1995

 Root Mean Square - RMS
 Signal to Noise Ratio - SNR


RMS(f,g) = Math.sqrt( (1/N) Math.pow(SUM( (f(x) - g(x)), 2)) )

Note: RMS(f, g) = RMS(g, f)

SNR(f, g) = Math.sqrt( (SUM(Math.pow(g(x),2)))/(SUM( Math.pow(f(x) - g(x), 2))))

Note: SNR(f,g) != SNR(g, f)

SNR(f, g)/SNR(g, f) = Math.sqrt( SUM( Math.pow(g(x), 2) ) / SUM( Math.pow(f(x), 2)) )

so given |f|, |g|, SNR(f, g) we can calculate SNR(g, f) where Math.pow(|f|, 2) === SUM( Math.pow(f(x), 2) )

Generalize this to color images instead of gray scale images by treating rgba as a 4d
vector at each point in the image and performing vector differences and dot products
to obtain the corresponding values.

*/
/*
  for each url
  for each user agent in the list

  open link in new window
  record loaded resources
  take snapshot image of window using canvas
  investigate video tag
  close window

  issue report for url:
  user_agent video report

  ua1 ua2 ua3 ua4
  ua1  -   -   -   -
  ua2  d   -   -   -
  ua3  d   d   -   -
  ua4  d   d   d   -

  distinct combinations 1/2*N(N-1)
*/

/*
 * ug_foo - global userhook variable
 */

var ug_load_delay            = 4*1000;
var ug_page_timeout          = 120;
var ug_user_agents = [
  'Mozilla/5.0 (Android 2.3.3; Linux armv71; rv:11.0a1; Nexus One Build/FRG83) Gecko/20111107 Mobile Firefox/11.0a1',
  'Mozilla/5.0 (Android 3.1; Linux armv71; rv:11.0a1; GT-P7510 Build/HMJ37) Gecko/20111107 Firefox/11.0a1',
  'Mozilla/5.0 (Android; Linux armv71; Mobile; rv:11.0a1) Gecko/20111107 Firefox/11.0a1',
  'Mozilla/5.0 (Android; Linux armv71; rv:11.0a1) Gecko/20111107 (like WebKit) Firefox/11.0a1',
  'Mozilla/5.0 (Android; Linux armv71; rv:11.0a1) Gecko/20111107 (like WebKit) Mobile Firefox/11.0a1',
  'Mozilla/5.0 (Android; Linux armv71; rv:11.0a1) Gecko/20111107 Firefox/11.0a1',
  'Mozilla/5.0 (Android; Linux armv71; rv:11.0a1) Gecko/20111107 Mobile Firefox/11.0a1',
  'Mozilla/5.0 (Android; Linux armv7l; rv:10.0a1) Gecko/20111103 Firefox/10.0a1 Fennec/10.0a1',
  'Mozilla/5.0 (Android; Linux armv7l; rv:8.0) Gecko/20111104 Firefox/8.0 Fennec/8.0',
  'Mozilla/5.0 (Linux; U; Android 2.3.3; en-us; DROIDX Build 4.5.1_57_DX5-3) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1',
  'Mozilla/5.0 (Linux; U; Android 3.1; en-us; GT-P7510 Build/HMJ37) AppleWebKit/534.13 (KHTML, like Gecko) Version/4.0 Safari/534.13',
  'Mozilla/5.0 (Linux; U; Android 4.0; es-es; Tuna Build/IFK77E) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30',
  'Mozilla/5.0 (Windows NT 6.1; rv:8.0) Gecko/20100101 Firefox/8.0',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/534.30 (KHTML, like Gecko) Chrome/11.0.696.34 Safari 534.24',
  'Mozilla/5.0 (iPad; U; CPU OS 4_3_1 like Mac OS X; en-us) AppleWebKit/533.17.9 (KHTML, like Gecko) Version/5.0.2 Mobile/8G4 Safari/6533.18.5',
  'Mozilla/5.0 (iPhone; CPU iPhone OS 5_0 like Mac OS X) AppleWebKit/534.46 (KHTML, like Gecko) Version/5.1 Mobile/9A334 Safari/7534.48.3',
  'Mozilla/5.0 (iPhone; U; CPU like Mac OS X; en) AppleWebKit/420+ (KHTML, like Gecko) Version/3.0 Mobile/1A537a Safari/419.3'
];

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

var ug_xulvbox;
var ug_xulbrowser;
var ug_page_loader;
var ug_canvas;
var ug_ctx;
/*
  var ug_canvas_height         = 1024;
  var ug_canvas_width          = 1200;
*/
// iphone 4 960-by-640
// Most sites assume landscape orientation?
var ug_canvas_width          = 960;
var ug_canvas_height         = 640;


var ug_link_index      = -1;
var ug_state_not_run   = 'not run';
var ug_state_timed_out = 'timed out';
var ug_state_loaded    = 'loaded';
var ug_ua_index        = -1;
var ug_data            = null;
var ug_responses       = [];
var ug_re_safebrowsing = /(safebrowsing-cache.google.com|safebrowsing.clients.google.com)/;
var ug_re_mozilla      = /mozilla\.(org|com|net)/i;
var ug_re_javascript   = /^javascript:/;

// allow sharing of identical image_urls
var ug_image_cache_id  = -1;
var ug_image_cache     = {};

function userOnStart()
{
  cdump('userOnStart()');
  // turn off unsolicited popups during load.
  ug_pref_branch.setBoolPref('dom.disable_open_during_load', true);
  // turn on dump() function
  ug_pref_branch.setBoolPref('browser.dom.window.dump.enabled', true);
  // turn on private browsing
  ug_pbs.privateBrowsingEnabled = true;
  // resize Spider to the screen size
  window.resizeTo(screen.availWidth, screen.availHeight);
  window.focus();
}

function userOnBeforePage()
{
  cdump('userOnBeforePage()');
  registerDialogCloser();
}

function userOnPause()
{
  cdump('userOnPause()');
}

function userOnAfterPage()
{
  cdump('userOnAfterPage()');

  ug_xulvbox = document.createElementNS(ug_xulns, 'xul:vbox');
  ug_xulvbox.setAttribute('flex', '1');
  ug_xulvbox.setAttribute('maxheight', ug_canvas_height);
  ug_xulvbox.setAttribute('maxwidth', ug_canvas_width);
  ug_xulvbox.setAttribute('minheight', ug_canvas_height);
  ug_xulvbox.setAttribute('minwidth', ug_canvas_width);
  ug_xulvbox.height = ug_canvas_height;
  ug_xulvbox.width = ug_canvas_width;
  ug_xulbrowser = document.createElementNS(ug_xulns, 'xul:browser');
  ug_xulbrowser.setAttribute('type', 'content');
  ug_xulbrowser.setAttribute('flex', '1');
  ug_xulbrowser.setAttribute('id', 'ug_xulbrowser');
  ug_xulvbox.appendChild(ug_xulbrowser);
  document.documentElement.appendChild(ug_xulvbox);

  ug_canvas        = document.createElementNS('http://www.w3.org/1999/xhtml', 'canvas')
  ug_ctx           = ug_canvas.getContext('2d');
  ug_canvas.height = ug_canvas_height;
  ug_canvas.width  = ug_canvas_width;

  cdump('Spider Comparator: var comparisons = [];');

  load_pages();
}

function userOnStop()
{
  cdump('userOnStop()');

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
  cdump('change_user_agent: ' + ua);
  ug_pref_branch.setCharPref('general.useragent.override', ua);
}

function get_domain(url) {
  var re = /https?:\/\/([^\/]*)/;
  var captures = re.exec(url);
  if (captures && captures.length == 2) {
    return captures[1];
  }
  cdump('get_domain failed: url=' + url);
  return null;
}

function create_loader(onload_callback, ontimeout_callback) {
  cdump('create_loader');

  cdump('create_loader: before ug_xulbrowser.contentWindow.{width,height} = ' +
        ug_xulbrowser.contentWindow.innerWidth + '/' +
        ug_xulbrowser.contentWindow.innerHeight);

/*
  cdump('create_loader: resize ug_xulbrowser.contentWindow.{width,height} to ug_canvas {width,height} = ' +
        ug_canvas_width + '/' + ug_canvas_height);

  ug_xulbrowser.contentWindow.resizeTo(ug_canvas_width, ug_canvas_height);
  cdump('create_loader: after ug_xulbrowser.contentWindow.{width,height}=' +
        ug_xulbrowser.contentWindow.innerWidth + '/' +
        ug_xulbrowser.contentWindow.innerHeight);

*/
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

  cdump('create_loader: normal exit');
}

function update_msg(s) {
  msg(s +
      '\n' + ug_current_user_agent +
      '\n' + ug_current_url +
      '\n(' + (ug_link_index + 1) +
      '/' + gSpider.mDocument.links.length + ')');
}

function load_pages() {
  cdump('load_pages()');

  var user_agent;
  var iua;
  var ua1;
  var jua;
  var ua2;
  var prop;

  if (ug_data) {
    var completed = true;   // true means all pages loaded

    cdump('Spider Comparator: var image_cache = {};');
    for (var image_cache_id in ug_image_cache) {
      cdump('Spider Comparator: image_cache["' + image_cache_id + '"] = "' + ug_image_cache[image_cache_id] + '";');
    }

    for each (user_agent in ug_user_agents) {

      delete ug_data.user_agents[user_agent].image_data;

      switch (ug_data.user_agents[user_agent].state) {
      case ug_state_not_run:
      case ug_state_timed_out:
        cdump('Spider: ' + ug_data.url + ' ' + user_agent + ' failed to complete ' + ug_data.user_agents[user_agent].state);
        completed = false;
        break;
      }
    }

    if (!completed) {
      cdump('Spider: ' + ug_data.url + ' did not complete loading each page.');
    }

    for each (user_agent in ug_user_agents) {
      for (prop in ug_data.user_agents[user_agent]) {
        cdump('Spider Comparator: url_data.user_agents["' + user_agent + '"].' + prop + ' = ' + JSON.stringify(ug_data.user_agents[user_agent][prop]) + ';');
      }
    }

    for (iua = 0; iua < ug_user_agents.length; iua++) {
      ua1 = ug_user_agents[iua];
      for (jua = 0; jua < iua; jua++) {
        ua2 = ug_user_agents[jua];
        cdump('Spider Comparator: url_data.comparison["' + ua1 + '"]["' + ua2 + '"] = ' +
              JSON.stringify(ug_data.comparison[ua1][ua2]) + ';');
      }
    }

  }

  if (++ug_link_index >= gSpider.mDocument.links.length) {
    cdump('load_pages: completed');
    gPageCompleted = true;
    return;
  }

  ug_current_url = gSpider.mDocument.links[ug_link_index].href;
  cdump('ug_current_url = ' + ug_current_url);

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

  ug_image_cache_id  = -1;
  ug_image_cache     = {};

  ug_data = {
    url        : ug_current_url,
    user_agents : {},
    comparison : {},
  };

  for each (user_agent in ug_user_agents) {
    ug_data.user_agents[user_agent] = {
      state      : ug_state_not_run,
      responses  : {},
      image_cache_id  : null,
      width      : -1,
      height     : -1,
      histogram  : new Array(256),
      rgba_signal : 0
    };
    for (var ihistogram = 0; ihistogram < 256; ihistogram++) {
      ug_data.user_agents[user_agent].histogram[ihistogram] = 0;
    }
  }

  for (iua = 0; iua < ug_user_agents.length; iua++) {
    ua1 = ug_user_agents[iua];
    ug_data.comparison[ua1] = {};
    for (jua = 0; jua < iua; jua++) {
      ua2 = ug_user_agents[jua];
      ug_data.comparison[ua1][ua2] = {
        responses_differ : false,
        images_differ    : false,
        //image_diff_url   : '',
        percent_diff     : 0,
        histogram_distance : 0,
        rgba_noise : 0,
      }
    }
  }

  cdump('Spider Comparator: url_data =' + JSON.stringify(ug_data) + ';');
  cdump('Spider Comparator: comparisons.push(url_data);');

  cdump('Spider: *****************************');
  cdump('Spider: load_pages: ug_current_url = ' + ug_current_url);

  // Force GC to see if this helps in memory growth.
  Components.utils.forceGC();

  ug_ua_index = -1;

  setTimeout(load_page_user_agent, 100);

}

function load_page_user_agent() {
  if (++ug_ua_index >= ug_user_agents.length) {
    setTimeout(compare_user_agents, 100);
    return;
  }

  // Force GC to see if this helps in memory growth.
  Components.utils.forceGC();

  ug_current_user_agent = ug_user_agents[ug_ua_index];

  cdump('load_page_user_agent user_agent=' + ug_current_user_agent + ' url=' + ug_current_url);

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

  create_loader(handle_initial_load_user_agent, handle_timeout_user_agent);
  update_msg('loading...');
  ug_page_loader.load(ug_current_url, null);
}

function handle_timeout_user_agent() {
  cdump('handle_timeout_user_agent user_agent=' + ug_current_user_agent + ' url=' + ug_current_url);
  update_msg('timed out.');
  ug_data.user_agents[ug_current_user_agent].state = ug_state_timed_out;
  cdump('Spider: ' + ug_current_user_agent + ' TIMEOUT: ug_current_url=' + ug_current_url);
  setTimeout(load_pages, 100);
}

function handle_initial_load_user_agent(evt) {
  cdump('handle_initial_load_user_agent user_agent=' + ug_current_user_agent + ' url=' + ug_current_url);
  update_msg('loaded.');

  cdump('handle_initial_load_user_agent: ug_xulbrowser.contentWindow.{width,height}=' +
        ug_xulbrowser.contentWindow.innerWidth + '/' +
        ug_xulbrowser.contentWindow.innerHeight);

  setTimeout(handle_load_user_agent, ug_load_delay, evt);
}

function handle_load_user_agent(evt) {
  cdump('handle_load_firefox_user_agent user_agent=' + ug_current_user_agent + ' url=' + ug_current_url);
  update_msg('processing...');

  ug_data.user_agents[ug_current_user_agent].state = ug_state_loaded;
  ug_data.user_agents[ug_current_user_agent].responses = {}

  for each (var response in ug_responses) {
    if (ug_re_safebrowsing.exec(response.originalURI))
      true;
    else if (ug_re_mozilla.exec(response.orignalURI))
      true;
    else if (response.contentType == 'application/ocsp-response')
      true;
    else
      ug_data.user_agents[ug_current_user_agent].responses[response.originalURI] = response;
  }

  cdump('handle_load_user_agent: user_agent = ' + ug_current_user_agent + ' ug_current_url = ' + ug_current_url);
  cdump('handle_load_user_agent: window size = ' + ug_xulbrowser.contentWindow.innerWidth + ',' + ug_xulbrowser.contentWindow.innerHeight);

  // record the actual size of the content
  ug_data.user_agents[ug_current_user_agent].width  = ug_xulbrowser.contentWindow.document.documentElement.offsetWidth;
  ug_data.user_agents[ug_current_user_agent].height = ug_xulbrowser.contentWindow.document.documentElement.offsetHeight;

  // clear the canvas context
  ug_ctx.clearRect(0, 0, ug_ctx.canvas.width, ug_ctx.canvas.height);

  // set canvas size to match the window size.
  ug_ctx.canvas.width  = ug_xulbrowser.contentWindow.innerWidth;
  ug_ctx.canvas.height = ug_xulbrowser.contentWindow.innerHeight;

  // capture the window contents at the current window size.
  cdump('handle_load_user_agent: before drawWindow canvas size: ' + ug_ctx.canvas.width + '/' + ug_ctx.canvas.height);
  ug_ctx.drawWindow(ug_xulbrowser.contentWindow,
                 0, 0,
                 ug_ctx.canvas.width,
                 ug_ctx.canvas.height,
                 "rgb(255,255,255)");
  cdump('handle_load_user_agent: after drawWindow canvas size: ' + ug_ctx.canvas.width + '/' + ug_ctx.canvas.height);

  ug_image_cache[++ug_image_cache_id] = ug_ctx.canvas.toDataURL("image/png", "");

  ug_data.user_agents[ug_current_user_agent].image_cache_id = ug_image_cache_id;
  ug_data.user_agents[ug_current_user_agent].image_data =
    ug_ctx.getImageData(0, 0, ug_ctx.canvas.width, ug_ctx.canvas.height);
  setTimeout(load_page_user_agent, 100);
}

function compare_user_agents() {
  cdump('compare_user_agents');

  update_msg('Comparing Images...');

  var user_agent;
/*
  var image_data_diff;
*/
  var x;
  var y;
  var offset;
  var index;
  var component;
  var pixel_is_different;
  var iua;
  var jua;
  var ua1;
  var ua2;
  var ua1_image_data;
  var ua2_image_data;
  var ua1_image_data_data;
  var ua2_image_data_data;

  var rgba_magnitude = Math.pow(256, 4);

  for (iua = 0; iua < ug_user_agents.length; iua++) {
    ua1 = ug_user_agents[iua];
    ua1_image_data_data = ug_data.user_agents[ua1].image_data.data;
    var histogram = ug_data.user_agents[ua1].histogram;

    var rgba_signal = 0;
    for (offset = 0; offset < ug_canvas_height*ug_canvas_width*4 ; offset += 4) {
      // compute color histograms for each user agent with 64
      // binning. That will result in 4 bins for each of red, blue, green,
      // alpha and a histogram of 256 bins.

      var red   = parseInt(ua1_image_data_data[offset]/64);
      var green = parseInt(ua1_image_data_data[offset + 1]/64);
      var blue  = parseInt(ua1_image_data_data[offset + 2]/64);
      var alpha = parseInt(ua1_image_data_data[offset + 3]/64);
      var ihistogram = parseInt((red + '') + (green + '') + (blue + '') + (alpha + ''), 4);
      histogram[ihistogram] += 1;

      // compute the "rgba_signal" as the sum of the magnitude of
      // the unit color vector at each point in the image. If all color
      // vectors are of length 1, the total rgba_signal for the image
      // is the number of pixels.

      rgba_signal += red*red + green*green + blue*blue + alpha*alpha;
    }
    ug_data.user_agents[ua1].rgba_signal = Math.sqrt(rgba_signal) / rgba_magnitude;
  }
  ua1_image_data_data = null; // try to reclaim memory

  // count pixels and different pixels.
  for (iua = 0; iua < ug_user_agents.length; iua++) {
    ua1 = ug_user_agents[iua];
    var ua1_histogram = ug_data.user_agents[ua1].histogram;

    for (jua = 0; jua < iua; jua++) {
      ua2 = ug_user_agents[jua];

      var ua2_histogram = ug_data.user_agents[ua2].histogram;
      var histogram_distance = 0;

      for (ihistogram = 0; ihistogram < 256; ihistogram++) {
        histogram_distance += Math.pow(ua1_histogram[ihistogram] - ua2_histogram[ihistogram], 2)
      }
      ug_data.comparison[ua1][ua2].histogram_distance = parseInt(100*Math.sqrt(histogram_distance)/(ug_canvas_width*ug_canvas_height));

      cdump('compare_user_agents: histogram_distance ' + ua1 + ' to ' + ua2 + ' ' + ug_data.comparison[ua1][ua2].histogram_distance);

      var total_pixels = 0;
      var total_different_pixels = 0;
      var rgba_noise = 0;

      cdump('compare_user_agents: compare images ' + ua1 + ' to ' + ua2 + ' generating diff');

      ua1_image_data = ug_data.user_agents[ua1].image_data;
      ua2_image_data = ug_data.user_agents[ua2].image_data;
      if (ua1_image_data.height != ua2_image_data.height) {
        cdump('ua1/ua2 height mismatch: ' + ua1_image_data.height + '/' + ua2_image_data.height);
      }
      if (ua1_image_data.width != ua2_image_data.width) {
        cdump('ua1/ua2 width mismatch: ' + ua1_image_data.width + '/' + ua2_image_data.width);
      }
      if (ua1_image_data.height != ua2_image_data.height) {
        cdump('ua1/ua2 height mismatch: ' + ua1_image_data.height + '/' + ua2_image_data.height);
      }

      ua1_image_data_data  = ug_data.user_agents[ua1].image_data.data;
      ua2_image_data_data  = ug_data.user_agents[ua2].image_data.data;

      cdump('Image Data: ' + ua1 + ' width=' + ug_data.user_agents[ua1].image_data.width + ', height=' +ug_data.user_agents[ua1].image_data.height);
      cdump('Image Data: ' + ua2 + ' width=' + ug_data.user_agents[ua2].image_data.width + ', height=' +ug_data.user_agents[ua2].image_data.height);

      for (offset = 0; offset < ug_canvas_height*ug_canvas_width*4 ; offset += 4) {

        ++total_pixels;
        pixel_is_different = false;

        for (component = 0; component < 4; component++) {

          index = offset + component;

          if (ua1_image_data_data[index] != ua2_image_data_data[index]) {
            pixel_is_different = true;
          }

          rgba_noise += Math.pow(ua1_image_data_data[index] - ua2_image_data_data[index], 2);
        }

        if (pixel_is_different) {
          ++total_different_pixels;
        }

      }

      ug_data.comparison[ua1][ua2].images_differ = false;
      if (total_different_pixels > 0) {
        ug_data.comparison[ua1][ua2].images_differ = true;
      }

      ug_data.comparison[ua1][ua2].percent_diff = parseInt(100*total_different_pixels/total_pixels);
      ug_data.comparison[ua1][ua2].rgba_noise   = Math.sqrt(rgba_noise) / rgba_magnitude;

      cdump('images different: ' + ug_data.comparison[ua1][ua2].images_differ + ', total pixels = ' + total_pixels + ', total different pixels = ' + total_different_pixels + ', percentage total = ' + 100*total_different_pixels/total_pixels);

      if (ug_data.user_agents[ua1].image_cache_id != ug_data.user_agents[ua2].image_cache_id &&
          ug_image_cache[ug_data.user_agents[ua1].image_cache_id] == ug_image_cache[ug_data.user_agents[ua2].image_cache_id]) {
        // The image cache ids are not the same but the image urls are identical. We only need one copy of the image url
        cdump('image urls are identical. share the image url for ua1 = ' + ua1 + ', image_cache_id = ' + ug_data.user_agents[ua1].image_cache_id + '; ua2 = ' + ua2 + ', image_cache_id = ' + ug_data.user_agents[ua2].image_cache_id);
        var ua2_image_cache_id = ug_data.user_agents[ua2].image_cache_id;
        delete ug_image_cache[ug_data.user_agents[ua2].image_cache_id];
        for (var ua3 in ug_data.user_agents) {
          if (ua2_image_cache_id == ug_data.user_agents[ua3].image_cache_id) {
            cdump('updating image_cache_id ua3 = ' + ua3 + ', image_cache_id from ' + ug_data.user_agents[ua3].image_cache_id + ' to ' + ua2_image_cache_id);
            ug_data.user_agents[ua3].image_cache_id = ug_data.user_agents[ua1].image_cache_id;
          }
        }
      }


      if ((ug_image_cache[ug_data.user_agents[ua1].image_cache_id] != ug_image_cache[ug_data.user_agents[ua2].image_cache_id]) !=
          ug_data.comparison[ua1][ua2].images_differ) {
        cdump('images difference and image urls do not agree');
        cdump('ua1 image_url: ' + ug_data.user_agents[ua1].image_cache_id);
        cdump('ua2 image_url: ' + ug_data.user_agents[ua2].image_cache_id);
      }
    }
  }

  cdump('compare_user_agents: exit');
  setTimeout(load_pages, 100);
}

function loadCanvas(image_url) {

  cdump('loadCanvas ' + ug_current_user_agent + ' ' + ug_current_url);

  var context = ug_canvas.getContext("2d");

  // load image from data url
  var image = new Image();
  image.onload = function() {
    cdump('loadCanvas image.onload ' + ug_current_user_agent + ' ' + ug_current_url);

    context.drawImage(this, 0, 0);
    ug_data.user_agents[ug_current_user_agent].image_data = context.getImageData(0, 0,
                                                                     ug_canvas_width, ug_canvas_height);
    setTimeout(load_page_user_agent, 100);
  };

  image.src = image_url;
}

