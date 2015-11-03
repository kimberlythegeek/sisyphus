/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
 * top-sites user hook function
 * investigate top 100,000 alexa site flash usage.
 */

var gURL;
var gBodyRect;
var gUrls = {};

function userOnStart() {
  dlog('userOnStart()');
  gURL = gForm.url.value;
}

function userOnBeforePage() {
  dlog('userOnBeforePage()');

  registerDialogCloser();

  window.moveTo(0, 0);
  window.resizeTo(screen.availWidth, screen.availHeight);
  gBodyRect = null;
}

function userOnPause() {
  dlog('userOnPause()');
}

function userOnAfterPage() {
  dlog('userOnAfterPage()');

  var win;
  try {
    dlog('userOnAfterPage: getting defaultView');
    win = gSpider.mDocument.defaultView;
    if (win.wrappedJSObject) {
      dlog('userOnAfterPage: getting wrapped window object');
      win = win.wrappedJSObject;
    }
    dlog('userOnAfterPage: win=' + win);
    var winurl = win.document.location.href;
    dlog('userOnAfterPage: winurl=' + winurl);

    dlog('userOnAfterPage: getting document');
    var doc = win.document;
    if (doc.wrappedJSObject) {
      dlog('userOnAfterPage: getting wrapped document object');
      doc = doc.wrappedJSObject;
    }

    if (gBodyRect == null) {
      gBodyRect = get_rect(doc.body, win);
    }
    analyse_page(win, 0, null);

  }
  catch(ex) {
    cdump('JavaScript Error: userOnAfterPage:' + ex.toSource());
  }

  setTimeout(completePage, 0);
}

userOnPageTimeout = userOnAfterPage;

function completePage() {
  dlog('completePage()');

  gPageCompleted = true;
  unregisterDialogCloser();
}

function userOnStop() {
  dlog('userOnStop()');
}

/*
 * We start with the top level window which has a bounding
 * DOMRect top_rect relative to the browser's viewport.
 *
 * An iframe has a bounding DOMRect relative to the window
 * in which it is contained. An element in the iframe's
 * window has a bounding DOMRect relative to the iframe's
 * viewport.
 *
 * We want to create a DOMRect for the element contained in
 * the iframe that is relative to the top level viewport.
 *
 */
function get_rect(element, win) {
  // x, y, width, height, top, right, bottom, left

  dlog('get_rect: ' + element + ' ' + win);
  var rect = element.getBoundingClientRect();
  rect.x    += win.scrollX;
  rect.y    += win.scrollY;
  rect.left += win.scrollX;
  rect.top  += win.scrollY;
  return rect;
}

function adjust_rect_parent(parent_rect, child_rect) {
  // parent_rect is the DOMRect of the iframe in the parent
  // window.
  // child_rect is the DOMRect of the element in the iframe
  // window.
  // Return the adjusted child_rect so that it's x,y properties
  // are relative to the parent window.

  var rect;

  dlog('adjust_rect_parent:' + parent_rect + ' ' + child_rect);

  if (parent_rect)
    rect = new DOMRect(parent_rect.x + child_rect.x,
                       parent_rect.y + child_rect.y,
                       child_rect.width,
                       child_rect.height);
  else
    rect = new DOMRect(child_rect.x,
                       child_rect.y,
                       child_rect.width,
                       child_rect.height);

  return rect;
}

function rect_dict(rect) {
  dlog('rect_dict: ' + rect);

  if (!rect)
    return null;

  return {
  'x': rect.x,
      'y': rect.y,
      'left': rect.left,
      'top': rect.top,
      'right': rect.right,
      'bottom': rect.bottom,
      'width': rect.width,
      'height': rect.height,
      };
}


function ObjectData(element, win, level, iframe_rect) {
  dlog('ObjectData: ' + element + ' ' + win + ' ' + level + ' ' + iframe_rect);
  this.element   = element;
  this.win       = win;
  this.body_rect = gBodyRect;
  this.level     = level;
  this.classid   = element.getAttribute('classid');
  this.codebase  = element.getAttribute('codebase');
  this.src       = element.getAttribute('data');
  if (!this.src) {
    var params = element.querySelectorAll('param[name=movie]');
    if (params) {
      this.src = params[0].getAttribute('value');
    }
  }
  if (this.src) {
    if (/https?:\/\//.exec(this.src))
      ;
    else if (this.src.indexOf('//') == 0)
      this.src = win.document.location.protocol + this.src;
    else if (this.src.indexOf('/') == 0)
      this.src = win.document.location.protocol + '//' +
        win.document.location.host + this.src;
    else
      this.src = win.document.location.protocol + '//' +
        win.document.location.host + '/' + this.src;
  }
  this.type      = element.getAttribute('type');
  this.height    = element.getAttribute('height');
  this.width     = element.getAttribute('width');
  this.outerHTML = element.outerHTML;
  this.parentOuterHTML = element.parentElement.outerHTML;
  if (level == 0) {
    this.iframeHTML = '';
  }
  else {
    this.iframeHTML = win.document.body.outerHTML;
  }
  this.userAgent = navigator.userAgent;
  this.rect      = get_rect(element, win);
  this.adjusted_rect = adjust_rect_parent(iframe_rect, this.rect);
  this.is_flash  = (this.type == 'application/x-shockwave-flash' || (this.data && this.data.indexOf('.swf') != -1));

  if (this.classid)
    this.is_activex = true;
  else
    this.is_activex = false;
}

ObjectData.prototype.dict = function() {
  dlog('ObjectData.dict()');
  return {
  site: gURL,
      tagName: this.element.tagName,
      level: this.level,
      url: this.win.location.href,
      body_rect: rect_dict(this.body_rect),
      //rect: rect_dict(this.rect),
      adjusted_rect: rect_dict(this.adjusted_rect),
      height: this.height,
      width: this.width,
      src: this.src,
      outerHTML: this.outerHTML,
      parentOuterHTML: this.parentOuterHTML,
      iframeHTML: this.iframeHTML,
      userAgent: this.userAgent
      };
}

  function EmbedData(element, win, level, iframe_rect) {
    dlog('EmbedData: ' + element + ' ' + win + ' ' + level + ' ' + iframe_rect);
    this.element   = element;
    this.win       = win;
    this.body_rect = gBodyRect;
    this.level     = level;
    this.src       = element.getAttribute('src');
    if (this.src) {
      if (/https?:\/\//.exec(this.src))
        ;
      else if (this.src.indexOf('//') == 0)
        this.src = win.document.location.protocol + this.src;
      else if (this.src.indexOf('/') == 0)
        this.src = win.document.location.protocol + '//' +
          win.document.location.host + this.src;
      else
        this.src = win.document.location.protocol + '//' +
          win.document.location.host + '/' + this.src;
    }
    this.type      = element.getAttribute('type');
    this.height    = element.getAttribute('height');
    this.width     = element.getAttribute('width');
    this.outerHTML = element.outerHTML;
    this.parentOuterHTML = element.parentElement.outerHTML;
    if (level == 0) {
      this.iframeHTML = '';
    }
    else {
      this.iframeHTML = win.document.body.outerHTML;
    }
    this.userAgent = navigator.userAgent;
    this.is_flash  = (this.type == 'application/x-shockwave-flash' || (this.src && this.src.indexOf('.swf') != -1));
    this.rect      = get_rect(element, win);
    this.adjusted_rect = adjust_rect_parent(iframe_rect, this.rect);
  }

EmbedData.prototype.dict = function() {
  dlog('EmbedData.dict()');
  return {
  site: gURL,
      tagName: this.element.tagName,
      level: this.level,
      url: this.win.location.href,
      body_rect: rect_dict(this.body_rect),
      //rect : rect_dict(this.rect),
      adjusted_rect: rect_dict(this.adjusted_rect),
      height: this.height,
      width: this.width,
      src: this.src,
      outerHTML: this.outerHTML,
      parentOuterHTML: this.parentOuterHTML,
      iframeHTML: this.iframeHTML,
      userAgent: this.userAgent
      };
}

  function analyse_page(win, level, iframe_rect) {
    var max_level = 5;
    var i;
    var element;
    var elementlist;
    var embed;
    var object;

    dlog('analyse_page: href ' + win.document.location.href + ' level ' + level + ' iframe_rect ' + iframe_rect);

    // limit the depth of iframe inspection to 10
    // and do not visit the same url twice.
    if (level > max_level || gUrls[win.document.location.href]) {
      return;
    }

    /* If iframe_rect is not null, it is bounding client rect for the
     * iframe parent window of this window. We use iframe_rect to adjust
     * the object and embed element bounding rects so they are relative
     * to the top most window.
     */

    elementlist = win.document.getElementsByTagName('object');

    for (i = 0; i < elementlist.length; i++) {
      element   = elementlist[i];
      object = new ObjectData(element, win, level, iframe_rect);
      if (!object.is_activex && object.is_flash) {
        cdump(JSON.stringify(object.dict()));
      }
    }

    elementlist = win.document.getElementsByTagName('embed');
    for (i = 0; i < elementlist.length; i++) {
      element = elementlist[i];
      embed = new EmbedData(element, win, level, iframe_rect);

      if (embed.is_flash) {
        ignore = false;
        // Check if this is contained in a non-activex object.
        for (parent = element.parentElement; parent && parent.tagName != 'OBJECT'; parent = parent.parentElement)
          true;

        if (parent) {
          object = new ObjectData(parent, win, level, iframe_rect);

          //if (!object.is_activex && parent.src == embed.src) {
          if (!object.is_activex) {
            // Ignore an embed that is contained in an non-activex
            // object and which has the same flash file.
            ignore = true;
          }
        }
        if (!ignore) {
          cdump(JSON.stringify(embed.dict()));
        }
      }
    }

    // record this url, so we don't visit it again.
    gUrls[win.document.location.href] = 1;

    elementlist = win.document.getElementsByTagName('iframe');
    for (i = 0; i < elementlist.length; i++) {
      element = elementlist[i];
      child_iframe_rect = element.getBoundingClientRect();
      adjusted_child_iframe_rect = adjust_rect_parent(iframe_rect, child_iframe_rect);
      analyse_page(element.contentWindow, level+1, adjusted_child_iframe_rect);
    }
  }
