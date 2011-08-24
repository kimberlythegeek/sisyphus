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
 * The Original Code is Bughunter.
 *
 * The Initial Developer of the Original Code is
 * Mozilla Corporation.
 * Portions created by the Initial Developer are Copyright (C) 2011
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s):
 *   Mark Cote <mcote@mozilla.com>
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

/**
 * Class for handling authentication.
 */
var BughunterAuth = BughunterUtils.Base.extend({
  username: '',
  authenticating: false,
  usernameStorageKey: 'bughunter-username',
  requestedView: '',
  callbacks: [],

  constructor: function () {
    var storedUsername = localStorage.getItem(this.usernameStorageKey);
    if (storedUsername) {
      this.username = storedUsername;
    }
  },

  setUsername: function(username) {
    this.username = username;
    localStorage.setItem(this.usernameStorageKey, username);
    if (username) {
      for (var i = 0; i < this.callbacks.length; i++) {
        this.callbacks[i](this.username);
      }
    }
  },

  logIn: function (username, password, success, failed, error) {
    if (this.authenticating) {
      return;
    }
    this.username = '';
    var data = {
      username: username,
      password: password
    };
    SyncTracker.ajax({
      url: 'bughunter/api/login/',
      type: 'POST',
      data: data,
      success: _.bind(function(response) {
        this.authenticating = false;
        if (response.username === undefined) {
          if (failed) {
            failed();
          }
        } else {
          this.setUsername(response.username);
          if (success) {
            success();
          }
          if (this.requestedView) {
            var reqView = this.requestedView;
            this.requestedView = '';
            document.location.hash = reqView;
          } else {
            document.location.hash = '';
          }
        }
      }, this),
      error: _.bind(function() {
        this.authenticating = false;
        if (error) {
          error();
        }
      }, this)
    });
  },

  logOut: function () {
    this.setUsername('');
    SyncTracker.ajax({
      url: 'bughunter/api/logout/',
      type: 'POST',
      complete: function() {
        document.location.hash = 'login';
      }
    });
  },

  // Called by ajax handler if a 403 error is detected.
  redirect: function() {
    this.requestedView = document.location.hash;
    document.location.hash = 'login';
  }

});


/**
 * Main app logic.
 */
var BughunterAppRouter = Backbone.Router.extend({
  // FIXME: We should have a generic parameter handler, e.g. for start/end
  // dates, using "splat" parts (or consider switching to sugarskull routing
  // if easier).
  routes: {
    'login': 'login',
    'logout': 'logout',
    'admin/workers': 'workers',
    'admin/workersummary': 'workersummary',
    'admin/logs': 'logs',
    'admin/logs/:start': 'logs',
    'admin/logs/:start/:end': 'logs',
    'admin/worker/:id': 'worker',
    'admin/worker/:id/:start': 'worker',
    'admin/worker/:id/:start/:end': 'worker',
    'crashes/date': 'crashes_by_date',
    'crashes/date/:start': 'crashes_by_date',
    'crashes/date/:start/:end': 'crashes_by_date',
    'crashes/date/:start/:end/:newonly': 'crashes_by_date',
    '': 'default'
  },

  defaultRoute: 'admin/workers',
  refreshIntervalId: -1,
  request: null,
  pageView: null,
  model: null,

  initialize: function (options) {
    // default config
    this.config = {
    };

    if (options) {
      // extend our default config with passed in object attributes
      _.extend(this.config, options.spec);
    }

    Backbone.history.start();
    window.auth.callbacks.push(_.bind(this.userLoggedIn, this));
    return this;
  },

  userLoggedIn: function() {
    if (this.pageView) {
      this.pageView.header.render();
    }
  },

  default: function() {
    document.location.hash = this.defaultRoute;
  },

  login: function() {
    this.loadPage(null, BughunterLoginView, {}, false);
  },

  logout: function() {
    window.auth.logOut();
    document.location.hash = '';
  },

  crashes_by_date: function(start, end, newonly) {
    var modelOpts = {
      start: start,
      end: end,
    };
    if (newonly == 'newonly') {
      modelOpts.newonly = true;
    }
    this.normalizeTimes(modelOpts);
    this.loadPage(BughunterCrashSummaryModel, BughunterCrashSummaryView,
                  modelOpts, false);
  },

  workers: function() {
    this.loadPage(BughunterWorkerListModel, BughunterWorkerListView);
  },

  workersummary: function() {
    this.loadPage(BughunterWorkerSummaryModel, BughunterWorkerSummaryView);
  },

  normalizeTimes: function(options) {
    if (options.start == '-') {
      options.start = null;
    }
    if (options.end == '-') {
      options.end = null;
    }
  },

  logs: function(start, end) {
    var modelOpts = {
      start: start,
      end: end
    };
    this.normalizeTimes(modelOpts);
    this.loadPage(BughunterLogsModel, BughunterLogsView, modelOpts, false);
  },

  worker: function(id, start, end) {
    var modelOpts = {
      id: id,
      start: start,
      end: end
    };
    this.normalizeTimes(modelOpts);
    this.loadPage(BughunterWorkerModel, BughunterWorkerView, modelOpts,
		  false);
  },

  loadPage: function(model, view, modelOptions, refresh) {
    if (!this.pageView) {
      this.pageView = new BughunterPageView();
      this.pageView.render();
    }

    if (!modelOptions) {
      modelOptions = {};
    }
    if (refresh === undefined) {
      refresh = true;
    }
    SyncTracker.abort();
    if (this.request) {
      this.request.abort();
    }
    if (model) {
      this.model = new model(modelOptions);
    } else {
      this.model = null;
    }
    this.pageView.loadPage(new view({ model: this.model, el: $('#content') }));
    // FIXME: Fetching/refreshing (and this.model) probably doesn't belong 
    // here... maybe move to an object owned by BughunterPageView? The latter
    // could then be the only object knowing about #content.
    this.stopRefreshing();
    if (this.model) {
      var fetchOpts = {};
      if (refresh) {
        fetchOpts.success = _.bind(function() { this.startRefreshing(); }, this);
      }
      this.model.fetch(fetchOpts);
    }
  },

  startRefreshing: function() {
    if (this.request) {
      return;
    }
    this.refreshIntervalId = setInterval(_.bind(function() {
      this.request = $.get(this.model.collection.url,
			   _.bind(function(data, textStatus) {
        for (var i = 0; i < data.length; i++) {
          if ('pk' in data[i]) {
            // django-serialized data
            var model = this.model.collection.get(data[i]['pk']);
            model.set(model.parse(data[i]));
          } else {
            // direct json representation
            this.model.collection.get(data[i]['id']).set(data[i]);
          }
        }
	this.request = null;
      }, this), 'json');
    }, this), 60000);
  },

  stopRefreshing: function() {
    if (this.refreshIntervalId != -1) {
      clearInterval(this.refreshIntervalId);
      this.refreshIntervalId = -1;
    }
  }

});

/**
 * Variety of sync that keeps track of the current XHRs and provides a way to
 * abort them. Also keeps track of server local time for use elsewhere.
 * FIXME: There is some duplicated code here.  This should better inherit
 * from the default sync.
 */
var SyncTracker = function() {
  var serverTime = null;
  var nextId = 0;
  var xhrs = [];

  var methodMap = {
    'create': 'POST',
    'update': 'PUT',
    'delete': 'DELETE',
    'read'  : 'GET'
  };

  var getUrl = function(object) {
    if (!(object && object.url)) throw new Error("A 'url' property or function must be specified");
    return _.isFunction(object.url) ? object.url() : object.url;
  };

  var ajax = function(params) {
    if (params.data && !_.isString(params.data)) {
      params.data = JSON.stringify(params.data);
    }
    var success = params.success;
    params.success = function(data, textStatus, jqXHR) {
      // FIXME: We haven't completely decided how we are handling the fact
      // that the timestamps in the db are in local time (e.g. Pacific Time).
      serverTime = new Date(jqXHR.getResponseHeader('Sisyphus-Localtime'));
      if (success) {
        success(data, textStatus, jqXHR);
      }
    };
    var complete = params.complete;
    params.complete = function(jqXHR, textStatus) {
      xhrs.splice(xhrs.indexOf(jqXHR), 1);
      if (complete) {
        complete(jqXHR, textStatus);
      }
    };
    xhrs.push($.ajax(params));
  };

  var sync = function(method, model, options) {
    var type = methodMap[method];
    var params = _.extend({
      type: type,
      dataType: 'json',
      statusCode: {
        403: function() {
          window.auth.redirect();
        }
      }
    }, options);

    if (!params.url) {
      params.url = getUrl(model) || urlError();
    }

    if (!params.data && model && (method == 'create' || method == 'update')) {
      params.contentType = 'application/json';
      params.data = JSON.stringify(model.toJSON());
    }

    if (Backbone.emulateJSON) {
      params.contentType = 'application/x-www-form-urlencoded';
      params.data        = params.data ? {model : params.data} : {};
    }

    if (Backbone.emulateHTTP) {
      if (type === 'PUT' || type === 'DELETE') {
        if (Backbone.emulateJSON) params.data._method = type;
        params.type = 'POST';
        params.beforeSend = function(xhr) {
          xhr.setRequestHeader('X-HTTP-Method-Override', type);
        };
      }
    }

    if (params.type !== 'GET' && ! Backbone.emulateJSON) {
      params.processData = false;
    }
    
    ajax(params);
  };

  var abort = function() {
    for (var i = 0; i < xhrs.length; i++) {
      xhrs[i].abort();
    };
  };

  return {
    ajax: ajax,
    sync: sync,
    abort: abort,
    xhrs: xhrs,
    serverTime: function() { return serverTime; }
  };
}();

Backbone.sync = SyncTracker.sync;
