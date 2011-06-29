var BughunterAdminAppController = Backbone.Controller.extend({
  routes: {
    'admin/workers': 'workers',
    'admin/workersummary': 'workersummary',
    'admin/logs': 'logs',
    'admin/logs/:start': 'logs',
    'admin/logs/:start/:end': 'logs',
    'admin/worker/:id': 'worker',
    'admin/worker/:id/:start': 'worker',
    'admin/worker/:id/:start/:end': 'worker',
    '': 'default'
  },

  refreshIntervalId: -1,
  request: null,
  model: null,
  view: null,

  initialize: function (options) {
    // default config
    this.config = {
    };

    // extend our default config with passed in object attributes
    _.extend(this.config, options.spec);

    this.tmplRenderer = Tempo.prepare('wrapper');

    $('#menubar').buttonset();
    $("input:radio[name='menuradio']").change(_.bind(function(){
        document.location.hash = 'admin/' + $('input:radio[name=menuradio]:checked').val();
    }, this));

    Backbone.history.start();
    return this;
  },

  default: function() {
    this.workers();
  },

  workers: function() {
    $('#menuworkers').attr('checked', true);
    $('#menubar').buttonset('refresh');
    this.loadPage(BughunterAdminAppModel, BughunterAdminAppView);
  },

  workersummary: function() {
    $('#menuworkersummary').attr('checked', true);
    $('#menubar').buttonset('refresh');
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
    $('#menulogs').attr('checked', true);
    $('#menubar').buttonset('refresh');
    var modelOpts = {
      start: start,
      end: end
    };
    this.normalizeTimes(modelOpts);
    this.loadPage(BughunterLogsModel, BughunterLogsView, modelOpts, false);
  },

  worker: function(id, start, end) {
    // Can only get here through the workers view, so uncheck all menu
    // options.
    $('input:radio[name=menuradio]').attr('checked', false);
    $('#menubar').buttonset('refresh');
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
    $('#wrapper').hide();
    if (this.view) {
      this.view.destroy();
    }
    this.tmplRenderer.clear();
    this.model = new model(modelOptions);
    this.view = new view({ model: this.model, renderer: this.tmplRenderer });
    this.view.render();
    $('#wrapper').show();
    this.stopRefreshing();
    var fetchOpts = {};
    if (refresh) {
      fetchOpts.success = _.bind(function() { this.startRefreshing(); }, this);
    }
    this.model.fetch(fetchOpts);
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
  },

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

  var sync = function(method, model, success, error) {
    var type = methodMap[method];
    var modelJSON = (method === 'create' || method === 'update') ?
      JSON.stringify(model.toJSON()) : null;
    var params = {
      url:          getUrl(model),
      type:         type,
      contentType:  'application/json',
      data:         modelJSON,
      dataType:     'json',
      processData:  false,
      success:      function(data, textStatus, jqXHR) {
	serverTime = new Date(jqXHR.getResponseHeader('Sisyphus-Localtime'));
	success(data, textStatus, jqXHR);
      },
      error:        error,
      complete:     function(jqXHR) {
	xhrs.splice(xhrs.indexOf(jqXHR), 1);
      }
    };
    xhrs.push($.ajax(params));
  };

  var abort = function() {
    for (var i = 0; i < xhrs.length; i++) {
      xhrs[i].abort();
    };
  };

  return {
    sync: sync,
    abort: abort,
    xhrs: xhrs,
    serverTime: function() { return serverTime; }
  };
}();

Backbone.sync = SyncTracker.sync;
