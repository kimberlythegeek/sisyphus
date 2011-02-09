// Licensed under the Apache License, Version 2.0 (the "License"); you may not
// use this file except in compliance with the License. You may obtain a copy of
// the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
// WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
// License for the specific language governing permissions and limitations under
// the License.

  <!-- bc: derived from couchdb futon application futon.js -->

(function($) {

  function Session() {

    // ready modeled after futon.js Navigation ready
    // this isn't really needed here, but is a model
    // for other ready handlers.
    this.loaded = false;
    this.eventHandlers = {
      load: []
    };

    this.ready = function (callback) {
      /*
       * If called without a callback function, ready will
       * set load to true then call any pending load handlers.
       * If called with a callback function, if load has not
       * been set to true, the callback function will be cached
       * otherwise all pending callback functions will be called
       * in the order they were registered.
       */
      if (callback) {
        if (this.loaded)
          callback.apply(this);

        this.eventHandlers["load"].push(callback);
      }
      else {
        this.loaded = true;
        var callbacks = this.eventHandlers["load"];
        for (var i = 0; i < callbacks.length; i++)
          callbacks[i].apply(this);
      }
    };

    function doLogin(name, password, callback) {
      $.couch.login({
        name : name,
        password : password,
        success : function() {
          callback();
          $.application.session.load();
        },
        error : function(code, error, reason) {
          callback({name : "Error logging in: "+reason});
          $.application.session.load();
        }
      });
    };

    function doSignup(name, password, callback, runLogin) {
      $.couch.signup({
        name : name
      }, password, {
        success : function() {
          if (runLogin)
            doLogin(name, password, callback);
          else {
            callback();
            $.application.session.load();
          }
        },
        error : function(status, error, reason) {
          if (error == "conflict")
            callback({name : "Name '"+name+"' is taken"});
          else {
            callback({name : "Signup error:  "+reason});
          }
          $.application.session.load();
        }
      });
    };

    function validateUsernameAndPassword(data, callback) {
      if (!data.name || data.name.length == 0) {
        callback({name: "Please enter a name."});
        return false;
      };
      if (!data.password || data.password.length == 0) {
        callback({password: "Please enter a password."});
        return false;
      };
      return true;
    };

    this.login = function login() {
      $.showDialog($.application.path + "dialog/login.html", {
        submit: function(data, callback) {
          if (!validateUsernameAndPassword(data, callback))
            return;
          doLogin(data.name, data.password, callback);
        }
      });
      return false;
    };

    this.logout = function logout() {
      $.couch.logout({
        success : function(resp) {
          $.application.session.load();
        }
      });
    };

    this.signup = function signup() {
      $.showDialog($.application.path + "dialog/signup.html", {
        submit: function(data, callback) {
          if (!validateUsernameAndPassword(data, callback))
            return;
          doSignup(data.name, data.password, callback, true);
        }
      });
      return false;
    };

    this.load = function () {

      // we must not check the userCtx until after the call to the
      // user database has completed. But we also need the $.application.storage
      // initialized. Call this method after application.js has loaded.
      // It may result in a page partially loading before the check can occur.
      // It would be better to delay the page from loading anything until we've
      // been able to check the session...

      var sessionthisref = this;

      $.couch.session(
        {
          success : function(r) {
            sessionthisref.userCtx = r.userCtx;
            return; // temporarily disable login checks.
            var destinationurl = $.application.storage.get("destinationurl");

            if (!destinationurl)
              destinationurl = window.location.href.replace(/#$/, '');

            if (sessionthisref.userCtx.name) {
              // we are is logged in. so we can delete the destinationurl cookie
              $.application.storage.del("destinationurl", $.application.path);
              // use indexOf to test if destinationurl is contained in the window
              // location to handle the case where the location has an extra hash #
              // at the end. Can't use regular expressions due to the special chars
              // potentially in the url.
              if (window.location.href.indexOf(destinationurl) == -1) {
                // we are not at our destination, therefore redirect to it.
                window.location.href = destinationurl;
              }
              else if (window.location.pathname.indexOf($.application.path + "login.html") != -1) {
                // we are still at the login page, so redirect to the index.
                window.location.href = $.application.path + 'index.html';
              }
            }
            else {
              if (window.location.pathname.indexOf($.application.path + "login.html") == -1) {
                // we are not logged in and are not at the login page, therefore
                // save our destination as a cookie that expires in 6 minutes
                // then redirect to the login page.
                $.application.storage.set("destinationurl", destinationurl, $.application.path, 0.10);
                window.location.href = $.application.path + "login.html";
              }
            }
          },
          error: function (status, error, reason) {
            return; // temporarily disable login checks.
            alert("Error getting sesssion info: status=" + status + ", error=" + error + ", reason=" + reason);
          }
        }
      );
    };
  };

  function Storage() {
    var storage = this;
    this.decls = {};

    this.declare = function(name, options) {
      this.decls[name] = $.extend({}, {
        scope: "window",
        defaultValue: null,
        prefix: ""
      }, options || {});
    };

    this.declareWithPrefix = function(prefix, decls) {
      for (var name in decls) {
        var options = decls[name];
        options.prefix = prefix;
        storage.declare(name, options);
      }
    };

    this.del = function(name) {
      lookup(name, function(decl) {
        handlers[decl.scope].del(decl.prefix + name);
      });
    };

    this.get = function(name, defaultValue) {
      return lookup(name, function(decl) {
        var value = handlers[decl.scope].get(decl.prefix + name);
        if (value !== undefined)
          return value;

        if (defaultValue !== undefined)
          return defaultValue;

        return decl.defaultValue;
      });
    };

    this.set = function(name, value, path, expires) {
      lookup(name, function(decl) {
        handlers[decl.scope].set(decl.prefix + name, value, path, expires);
      });
    };


    function lookup(name, callback) {
      var decl = storage.decls[name];
      if (decl === undefined)
        return decl;

      return callback(decl);
    }

    // add port to cookie names to be able to distinguish
    // cookies between ports.
    var cookiePrefix = location.port + "_";

    var handlers = {

      "cookie": {
        get: function(name) {
          var nameEq = cookiePrefix + name + "=";
          var parts = document.cookie.split(';');
          for (var i = 0; i < parts.length; i++) {
            var part = parts[i].replace(/^\s+/, "");
            if (part.indexOf(nameEq) == 0)
              return decodeURIComponent(part.substring(nameEq.length, part.length));
          }
          return undefined;
        },
        set: function(name, value, path, expires) {
          /*
           * path and expires are specific to "cookie" declarations
           * and are ignored otherwise. Set expires to the number of
           * hours before a cookie expires, otherwise they
           * are session cookies.
           */
          var date = null;
          path = path || "/"; // default path to be root
          if (expires) {
            date = new Date();
            date.setTime(date.getTime() + expires*24*60*60*1000);
          }
          var cookievalue = cookiePrefix + name + "=" + encodeURIComponent(value) +
            (path ? ("; path=" + path) : "") +
            (date ? ("; expires=" + date.toGMTString()) : "");
          document.cookie = cookievalue;
        },
        del: function(name) {
          var date = new Date();
          date.setTime(date.getTime() - 24*60*60*1000); // yesterday
          var value = cookiePrefix + name + "=" +
            "; expires=" + date.toGMTString();
          document.cookie = value;
        }
      },

      "window": {
        get: function(name) {
          return JSON.parse(window.name || "{}")[name];
        },
        set: function(name, value) {
          var obj = JSON.parse(window.name || "{}");
          obj[name] = value || null;
          window.name = JSON.stringify(obj);
        },
        del: function(name) {
          var obj = JSON.parse(window.name || "{}");
          delete obj[name];
          window.name = JSON.stringify(obj);
        }
      }
    };

    // automatically declare our destinationurl and
    // sidebar-visibility cookie storage

    this.declare("destinationurl", {scope: "cookie", defaultValue: ""})
    this.declare("sidebar-visibility", {scope: "cookie", defaultValue: "show"});

    // pre declare cookies with our prefix
    var parts = document.cookie.split(';');
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i].replace(/^\s+/, '');
      if (part.indexOf(cookiePrefix) == 0) {
        // cookie stored by us.
        var names = part.split('=');
        if (names.length > 0)
          this.declare(names[0], {scope: "cookie"});
      }
    }
  }

  var urlPrefixPieces = [];
  for (var i = 0; i < window.location.pathname.split('/').length - 2; i++)
    urlPrefixPieces.push('..');
  $.couch.urlPrefix = urlPrefixPieces.join('/');

  $.application = $.application || {};
  $.application.domain = window.location.hostname;
  $.application.path = window.location.pathname.split('/').slice(0,4).join('/') + '/';
  $.extend($.application, {
    session : new Session(),
    storage: new Storage()
  });

  $.application.toggleSidebar = function () {

    if ($.application.storage.get("sidebar-visibility") == "hidden") {
      $(document.body).removeClass("fullwidth");
      $("#sidebar-toggle").attr("title", "Hide Sidebar").switchClass('ui-icon-circle-plus', 'ui-icon-circle-minus', 0);
      $.application.storage.set("sidebar-visibility", "show");
    }
    else {
      $(document.body).addClass("fullwidth");
      $("#sidebar-toggle").attr("title", "Show Sidebar").switchClass('ui-icon-circle-minus', 'ui-icon-circle-plus', 0);
      $.application.storage.set("sidebar-visibility", "hidden");
    }
  };

  $.application.session.load();

  // support HTML5's input[placeholder]
  $.fn.addPlaceholder = function() {
    if (this[0] && "placeholder" in document.createElement("input"))
      return undefined; // found native placeholder support

    return this.live('focusin', function() {
      var input = $(this);
      if (input.val() === input.attr("placeholder"))
        input.removeClass("placeholder").val("");

    }).live("focusout", function() {
      var input = $(this);
      if (input.val() === "")
        input.val(input.attr("placeholder")).addClass("placeholder");

    }).trigger("focusout");
  };

  $.fn.enableTabInsertion = function(chars) {
    chars = chars || "\t";
    var width = chars.length;
    return this.keydown(function(evt) {
      if (evt.keyCode == 9) {
        var v = this.value;
        var start = this.selectionStart;
        var scrollTop = this.scrollTop;
        if (start !== undefined) {
          this.value = v.slice(0, start) + chars + v.slice(start);
          this.selectionStart = this.selectionEnd = start + width;
        }
        else {
          document.selection.createRange().text = chars;
          this.caretPos += width;
        }
        return false;
      }
      return undefined;
    });
  };

  $(document)
    .ajaxStart(function() { $(this.body).addClass("loading"); })
    .ajaxStop(function() { $(this.body).removeClass("loading"); });

  // why did futon wrap this in a jquery ready call?
  // we are already in one aren't we?

  $(function() {

    $("input[placeholder]").addPlaceholder();

    $.get($.application.path + "/sidebar.html",
          function(resp) {
            $(resp).insertBefore("#content")
              .find("#sidebar-toggle").click(
                function(e) {
                  $.application.toggleSidebar();
                  return false;
                }
              );
            if ($.application.storage.get("sidebar-visibility") == "hidden") {
              $(document.body).addClass("fullwidth");
              $("#sidebar-toggle").attr("title", "Show Sidebar").switchClass('ui-icon-circle-minus', 'ui-icon-circle-plus', 0);
            }
            else {
              $(document.body).removeClass("fullwidth");
              $("#sidebar-toggle").attr("title", "Hide Sidebar").switchClass('ui-icon-circle-plus', 'ui-icon-circle-minus', 0);
            }
          }
         );


  });
}
)(jQuery);
