var BughunterAdminAppController = Backbone.Controller.extend({
  routes: {
    'admin/:page': 'admin',
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

    this.tmplRenderer = Tempo.prepare('main');

    $('#menubar').buttonset();
    $("input:radio[name='menuradio']").change(_.bind(function(){
        document.location.hash = 'admin/' + $('input:radio[name=menuradio]:checked').val();
    }, this));

    Backbone.history.start();
    return this;
  },

  default: function() {
    this.admin('workers');
  },

  admin: function(page) {
    if (page == 'workers') {
      this.workers();
    } else if (page == 'workersummary') {
      this.workersummary();
    }
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

  loadPage: function(model, view) {
    if (this.request) {
      this.request.abort();
    }
    $('#wrapper').hide();
    if (this.view) {
      this.view.destroy();
    }
    this.model = new model();
    this.view = new view({ model: this.model, renderer: this.tmplRenderer });
    this.view.render();
    $('#wrapper').show();
    this.stopRefreshing();
    this.model.collection.fetch({
      success: _.bind(function() { this.startRefreshing(); }, this)
    });
  },

  startRefreshing: function() {
    if (this.request) {
      return;
    }
    this.refreshIntervalId = setInterval(_.bind(function() {
      this.request = $.get(this.model.collection.url,
			   _.bind(function(data, textStatus) {
        for (var i = 0; i < data.length; i++) {
          this.model.collection.get(data[i]['id']).set(data[i]);
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