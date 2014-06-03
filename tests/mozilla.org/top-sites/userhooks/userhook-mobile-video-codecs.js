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
  for each url
  for each user agent in the list

  open link in new window
  investigate video tag
  close window

  issue report for url:
  user_agent video report
*/

/*
 * ug_foo - global userhook variable
 */

var ug_load_delay            = 0*1000;
var ug_page_timeout          = 120;
var ug_user_agents = [
//  'Mozilla/5.0 (Android 2.3.3; Linux armv71; rv:11.0a1; Nexus One Build/FRG83) Gecko/20111107 Mobile Firefox/11.0a1',
  'Mozilla/5.0 (Android 3.1; Linux armv71; rv:11.0a1; GT-P7510 Build/HMJ37) Gecko/20111107 Firefox/11.0a1',
//  'Mozilla/5.0 (Android; Linux armv71; Mobile; rv:11.0a1) Gecko/20111107 Firefox/11.0a1',
//  'Mozilla/5.0 (Android; Linux armv71; rv:11.0a1) Gecko/20111107 (like WebKit) Firefox/11.0a1',
//  'Mozilla/5.0 (Android; Linux armv71; rv:11.0a1) Gecko/20111107 (like WebKit) Mobile Firefox/11.0a1',
//  'Mozilla/5.0 (Android; Linux armv71; rv:11.0a1) Gecko/20111107 Firefox/11.0a1',
  'Mozilla/5.0 (Android; Linux armv71; rv:11.0a1) Gecko/20111107 Mobile Firefox/11.0a1',
  'Mozilla/5.0 (Android; Linux armv7l; rv:10.0a1) Gecko/20111103 Firefox/10.0a1 Fennec/10.0a1',
//  'Mozilla/5.0 (Android; Linux armv7l; rv:8.0) Gecko/20111104 Firefox/8.0 Fennec/8.0',
//  'Mozilla/5.0 (Linux; U; Android 2.3.3; en-us; DROIDX Build 4.5.1_57_DX5-3) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1',
//  'Mozilla/5.0 (Linux; U; Android 3.1; en-us; GT-P7510 Build/HMJ37) AppleWebKit/534.13 (KHTML, like Gecko) Version/4.0 Safari/534.13',
//  'Mozilla/5.0 (Linux; U; Android 4.0; es-es; Tuna Build/IFK77E) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30',
  'Mozilla/5.0 (Windows NT 6.1; rv:8.0) Gecko/20100101 Firefox/8.0',
//  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/534.30 (KHTML, like Gecko) Chrome/11.0.696.34 Safari 534.24',
  'Mozilla/5.0 (iPad; U; CPU OS 4_3_1 like Mac OS X; en-us) AppleWebKit/533.17.9 (KHTML, like Gecko) Version/5.0.2 Mobile/8G4 Safari/6533.18.5',
  'Mozilla/5.0 (iPhone; CPU iPhone OS 5_0 like Mac OS X) AppleWebKit/534.46 (KHTML, like Gecko) Version/5.1 Mobile/9A334 Safari/7534.48.3',
//  'Mozilla/5.0 (iPhone; U; CPU like Mac OS X; en) AppleWebKit/420+ (KHTML, like Gecko) Version/3.0 Mobile/1A537a Safari/419.3'
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
var ug_page_loader = null;
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

function userOnStart()
{
  //cdump('userOnStart()');
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
  //cdump('userOnBeforePage()');
  registerDialogCloser();
}

function userOnPause()
{
  //cdump('userOnPause()');
}

function userOnAfterPage()
{
  //cdump('userOnAfterPage()');

  if (!document.getElementById('xulvbox')) {
    ug_xulvbox = document.createElementNS(ug_xulns, 'xul:vbox');
    ug_xulvbox.setAttribute('id', 'xulvbox');
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
    cdump('Spider Comparator: var comparisons = [];');
    cdump('Spider Comparator: var media_element_hash = {};');
  }
  load_pages();
}

function userOnStop()
{
  //cdump('userOnStop()');

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
  //cdump('change_user_agent: ' + ua);
  ug_pref_branch.setCharPref('general.useragent.override', ua);
}

function get_domain(url) {
  var re = /https?:\/\/([^\/]*)/;
  var captures = re.exec(url);
  if (captures && captures.length == 2) {
    return captures[1];
  }
  //cdump('get_domain failed: url=' + url);
  return null;
}

function create_loader(onload_callback, ontimeout_callback) {
  //cdump('create_loader');

  ug_responses = [];
  ug_xulbrowser.loadURI('about:blank', null);
  if (!ug_page_loader) {
    ug_page_loader = new CPageLoader(
      ug_xulbrowser,
      onload_callback,
      ontimeout_callback,
      ug_page_timeout,
      new CHTTPResponseObserver((function (response) {
        ug_responses.push(response);
      }))
    );
  }

  //cdump('create_loader: normal exit');
}

function update_msg(s) {
  msg(s +
      '\n' + ug_current_user_agent +
      ' (' + (ug_ua_index + '/' + ug_user_agents.length) + ')' +
      '\n' + ug_current_url);
}

function load_pages() {
  //cdump('load_pages()');

  var user_agent;
  var iua;
  var ua1;
  var jua;
  var ua2;
  var prop;

  ug_current_url = gSpider.mCurrentUrl.mUrl;
  cdump('ug_current_url = ' + ug_current_url);
  /*
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
  */
  ug_data = {
    url        : ug_current_url,
    user_agents : {},
  };

  for each (user_agent in ug_user_agents) {
    ug_data.user_agents[user_agent] = {
      state      : ug_state_not_run,
      media_element_ids : [], // media ids in media hash of top level media elements
    };
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

  if (ug_data) {
    var user_agent;
    var completed = true;   // true means all pages loaded

    for each (user_agent in ug_user_agents) {

      switch (ug_data.user_agents[user_agent].state) {
      case ug_state_not_run:
      case ug_state_timed_out:
        //cdump('Spider: ' + ug_data.url + ' ' + user_agent + ' failed to complete ' + ug_data.user_agents[user_agent].state);
        completed = false;
        break;
      }
    }

    if (!completed) {
      //cdump('Spider: ' + ug_data.url + ' did not complete loading each page.');
    }

    for each (user_agent in ug_user_agents) {
      for (prop in ug_data.user_agents[user_agent]) {
        cdump('load_pages: dumping ug_data.user_agents[' + user_agent + '].' + prop + ' = ' + ug_data.user_agents[user_agent][prop]);
        cdump('Spider Comparator: url_data.user_agents["' + user_agent + '"].' + prop + ' = ' + JSON.stringify(ug_data.user_agents[user_agent][prop]) + ';');
      }
    }

  }


    gPageCompleted = true;
    return;
  }

  // Force GC to see if this helps in memory growth.
  Components.utils.forceGC();

  ug_current_user_agent = ug_user_agents[ug_ua_index];

  //cdump('load_page_user_agent user_agent=' + ug_current_user_agent + ' url=' + ug_current_url);

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
  //cdump('handle_timeout_user_agent user_agent=' + ug_current_user_agent + ' url=' + ug_current_url);
  update_msg('timed out.');
  ug_data.user_agents[ug_current_user_agent].state = ug_state_timed_out;
  //cdump('Spider: ' + ug_current_user_agent + ' TIMEOUT: ug_current_url=' + ug_current_url);
  // We timed out with that user agent, skip to the next.
  setTimeout(load_page_user_agent, 100);
}

function handle_initial_load_user_agent(evt) {
  //cdump('handle_initial_load_user_agent user_agent=' + ug_current_user_agent + ' url=' + ug_current_url);
  update_msg('loaded.');

/*
  cdump('handle_initial_load_user_agent: ug_xulbrowser.contentWindow.{width,height}=' +
        ug_xulbrowser.contentWindow.innerWidth + '/' +
        ug_xulbrowser.contentWindow.innerHeight);
*/

  setTimeout(handle_load_user_agent, ug_load_delay, evt);
}

function handle_load_user_agent(evt) {
  //cdump('handle_load_firefox_user_agent user_agent=' + ug_current_user_agent + ' url=' + ug_current_url);
  update_msg('processing...');

  var contentDocument = ug_xulbrowser.contentWindow.document;

  ug_data.user_agents[ug_current_user_agent].state = ug_state_loaded;

  //cdump('handle_load_user_agent: user_agent = ' + ug_current_user_agent + ' ug_current_url = ' + ug_current_url);
  //cdump('handle_load_user_agent: window size = ' + ug_xulbrowser.contentWindow.innerWidth + ',' + ug_xulbrowser.contentWindow.innerHeight);

  collect_media(contentDocument.documentElement, null);

  setTimeout(load_page_user_agent, 100);
}


var ug_media_tags = ['object', 'embed', 'video', 'audio'];
var ug_media_hash = {object:1, embed:1, video:1, audio:1};

function is_media_element(element) {
  return element && element.nodeName.toLowerCase() in ug_media_hash;
}

var ug_media_element_hash = {};
var ug_media_element_id = -1;

function collect_media(start_element, start_element_id) {

  cdump('collect_media: start_element = ' + start_element + ' is a media element ' +  is_media_element(start_element));

  var start_element_is_media = is_media_element(start_element);
  var media_element;
  var media_ancestor;
  var media_tag;
  var children = []; // list of top level (non-fallback) media elements and their ids
  var media_element_data;
  var start_element_data = ug_media_element_hash[start_element_id];

  for each (media_tag in ug_media_tags) {
    var media_collection = start_element.getElementsByTagName(media_tag)

    for each (media_element in media_collection) {

      media_element_data = null;

      for (media_ancestor = media_element.parentNode;
           media_ancestor && media_ancestor != start_element;
           media_ancestor = media_ancestor.parentNode) {
        if (is_media_element(media_ancestor)) {
          // media_element is contained in a media element contained
          // in start_element, i.e. is a fall back for that element
          // but it is not a top level media element or a fallback for
          // the current start_element. We can stop looking.
          break;
        }
      }

      if (media_ancestor == start_element) {
        // media_element is a direct descendant of start_element and
        // is not contained in a media element contained within
        // start_element.
        media_element_data = ug_media_element_hash[++ug_media_element_id] = {
          url : ug_current_url,
          tag : media_element.nodeName.toLowerCase(),
          fallback_for : null,
          fallbacks : [],
        };
        media_element_data.media_types = getMediaTypes(media_element);
        if (start_element_is_media) {
          cdump('collect_media: start_element = ' + start_element + ', found fallback media_element = ' + media_element);
          media_element_data.fallback_for = start_element_id;
          start_element_data.fallbacks.push(ug_media_element_id);
          cdump('Spider Comparator: media_element_hash[' + start_element_id + '].fallbacks.push(' + ug_media_element_id + ')');
        }
        else {
          cdump('collect_media: start_element = ' + start_element + ', found media_element = ' + media_element);
        }
        ug_data.user_agents[ug_current_user_agent].media_element_ids.push(ug_media_element_id);
        children.push([media_element, ug_media_element_id]);
      }

      if (media_element_data) {
        cdump('Spider Comparator: media_element_hash[' + ug_media_element_id + '] = ' + media_element_data.toSource());
      }

    }
  }

  for each (var child in children) {
    collect_media(child[0], child[1]);
  }

  if (!start_element_is_media) {
    var frame_list;
    var frame;
    var iframe;

    // process documents included via iframes or frames
    frame_list = start_element.getElementsByTagName('iframe');
    for (iframe = 0; iframe < frame_list.length; iframe++) {
      frame = frame_list[iframe];
      cdump('collect_media: processing iframe ' + frame);
      if (frame.contentWindow.document.documentElement) {
        collect_media(frame.contentWindow.document.documentElement, null);
      }
      else {
        cdump('collect_media: processing iframe with null documentElement ' + frame.contentWindow.location);
      }
    }

    frame_list = start_element.getElementsByTagName('frame');
    for (iframe = 0; iframe < frame_list.length; iframe++) {
      frame = frame_list[iframe];
      cdump('collect_media: processing frame ' + frame);
      if (frame.contentWindow.document.documentElement) {
        collect_media(frame.contentWindow.document.documentElement, null);
      }
      else {
        cdump('collect_media: processing frame with null documentElement ' + frame.contentWindow.location);
      }
    }

  }
}

function parseMediaType(type) {
  var codecs = [];
  var type_captures = /([^;]*); codecs=(.*)/.exec(type);
  if (type_captures) {
    type = type_captures[1];
    var codec_string = type_captures[2];
    var codec_captures = /[\'\"]([^\'\"]*)[\'\"]/.exec(codec_string);
    if (codec_captures) {
      codecs = codec_captures[1].split(/[, ]+/);
    }
    else {
      codecs = [codec_string];
    }
  }
  return (type || codecs.length > 0) ? { type : type, codecs : codecs } : null;
}

function getMediaTypes(media_element) {
  var media_types = [];
  var media_element_type_hash = {};

  var tag = media_element.nodeName.toLowerCase();
  switch (tag) {
  case 'object':
  case 'embed':
    media_type = parseMediaType(media_element.type);
    if (media_type) {
      media_types.push(media_type);
    }
    break;
  case 'video':
  case 'audio':
    var source;
    var sources = media_element.getElementsByTagName('source');
    for (var j = 0; j < sources.length; j++) {
      if (!(source = sources[j]))
        continue;
      if (!(media_element.type in media_element_type_hash)) {
        media_element_type_hash[media_element.type] = 1;
        var media_type = parseMediaType(source.type);
        if (media_type && (media_type.type || media_type.codecs.length > 0)) {
          media_types.push(media_type);
        }
      }
    }
    break;
  }
  return media_types;
}

