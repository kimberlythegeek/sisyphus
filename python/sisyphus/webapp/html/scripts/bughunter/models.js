var BughunterModel = Backbone.Model.extend({
  parse: function(response) {
    if (_.isArray(response)) {
      response = response[0];
    }
    var hash = {
      'id': response.pk
    };
    for (var f in response.fields) {
      hash[f] = response.fields[f];
    }
    return hash;
  }
});

var BughunterCollection = Backbone.Collection.extend({
  parse: function(response) {
    var hashes = [];
    var hash;
    for (var i = 0; i < response.length; i++) {
      hash = {
        'id': response[i].pk
      };
      for (var f in response[i].fields) {
        hash[f] = response[i].fields[f];
      }
      hashes.push(hash);
    }
    return hashes;
  }
});

var Worker = BughunterModel.extend({
  'id': '',
  'worker_type': '',
  'os_name': '',
  'hostname': '',
  'cpu_name': '',
  'datetime': '',
  'os_version': '',
  'state': '',
  url: function() { 
    return 'bughunter/api/admin/workers/' + this.id + '/';
  },
});

var WorkerCollection = BughunterCollection.extend({
  model: Worker,
  url: 'bughunter/api/admin/workers/',
  comparator: function(worker) {
    return worker.get('id');
  }
});

var WorkerSummary = Backbone.Model.extend({
  'id': '',
  'builder_active': 0,
  'builder_total': 0,
  'unittest_active': 0,
  'unittest_total': 0,
  'unittest_jobs': 0,
  'crashtest_jobs': 0,
  'crashtest_total': 0,
  'crashtest_active': 0,
  builders: function() {
    return this.get('builder_active') + ' / ' + this.get('builder_total');
  },
  unitTesters: function() {
    return this.get('unittest_active') + ' / ' + this.get('unittest_total');
  },
  unitTesterTP: function() {
    return this.get('unittest_jobs') + ' / hr';
  },
  crashTesters: function() {
    return this.get('crashtest_active') + ' / ' + this.get('crashtest_total');
  },
  crashTesterTP: function() {
    return this.get('crashtest_jobs') + ' / hr';
  }
});

var WorkerLogMessage = BughunterModel.extend({
  'id': '',
  'datetime': '',
  'message': '',
  'machinename': '',
  'worker_id': '',
});

var LogCollectionBase = BughunterCollection.extend({
  initialize: function(models, options) {
    this.options = options;
    this.checkDates();
  },
  model: WorkerLogMessage,
  comparator: function(logMessage) {
    return logMessage.get('datetime');
  },
  url: function() {
    var u = this.urlBase;
    if (this.options.start) {
      u += this.options.start + '/';
    } else {
      u += '-/';
    }
    if (this.options.end) {
      u += this.options.end + '/';
    } else {
      u += '-/';
    }
    return u;
  },
  destroy: function(success, error) {
    // Since generally the user will be clearing a number of log messages
    // at the same time, we'll use just one call instead of deleting each
    // one individually.
    if (this.isEmpty()) {
      success();
      return;
    }
    // More messages may have been added to the db since they were last
    // fetched (e.g. if an end date in the future was given), so make sure
    // we only delete the exact range that we have here.  Microsecond
    // resolution should be fine.
    var start = this.options.start;
    var end = this.options.end;
    this.options.start = this.at(0).get('datetime');
    this.options.end = this.at(this.length-1).get('datetime');
    var params = {
      url:          this.url(),
      type:         'DELETE',
      contentType:  'application/json',
      data:         null,
      dataType:     'json',
      processData:  false,
      success:      success,
      error:        error,
    };
    $.ajax(params);
    // Restore original date range so we refresh properly.
    this.options.start = start;
    this.options.end = end;
  },
  checkDates: function() {
    var conv = new AnyTime.Converter({ format: '%Y-%m-%dT%T' });
    var changed = false;
    if (!this.options.start) {
      // The default start time is one hour before the end.
      // If the end isn't given, we'll use now, but we don't set the end
      // option because we want it to be blank in the UI, so that it is
      // always 'now' when the view is refreshed.
      var endDate = this.options.end;
      if (!endDate) {
        endDate = new Date();
      }
      var startDate = endDate;
      startDate.setHours(endDate.getHours() - 1);
      this.options.start = conv.format(startDate);
      changed = true;
    }
    return changed;
  }
});

/**
 * Logs from a given worker for a given date range
 */
var WorkerLogCollection = LogCollectionBase.extend({
  initialize: function(models, options) {
    LogCollectionBase.prototype.initialize.call(this, models, options);
    this.urlBase = 'bughunter/api/admin/workers/' + this.options.worker_id + '/log/';
  }
});

/**
 * Logs from all workers for a given date range.
 */
var LogCollection = LogCollectionBase.extend({
  initialize: function(models, options) {
    LogCollectionBase.prototype.initialize.call(this, models, options);
    this.urlBase = 'bughunter/api/admin/workers/log/';
  },
  parse: function(response) {
    var hashes = [];
    var hash;
    for (var i = 0; i < response.length; i++) {
      hash = {
        'id': response[i].pk
      };
      for (var f in response[i].fields) {
        if (f == 'worker') {
          hash['hostname'] = response[i].fields[f].fields['hostname'];
          hash['worker_id'] = response[i].fields[f]['pk'];
        } else {
          hash[f] = response[i].fields[f];
        }
      }
      hashes.push(hash);
    }
    return hashes;
  }

});

var WorkerSummaryCollection = Backbone.Collection.extend({
  model: WorkerSummary,
  url: 'bughunter/api/admin/workersummary/',
  comparator: function(model) {
    return model.get('id');
  }
});

var BughunterAdminAppModel = BughunterModel.extend({
  initialize: function() {
    this.collection = new WorkerCollection();
  },
  fetch: function(options) {
    this.collection.fetch(options);
  }
});

var BughunterWorkerSummaryModel = BughunterModel.extend({
  initialize: function() {
    this.collection = new WorkerSummaryCollection();
  },
  fetch: function(options) {
    this.collection.fetch(options);
  }
});

var BughunterWorkerModel = BughunterModel.extend({
  initialize: function(options) {
    this.collection = new WorkerLogCollection([], {
      worker_id: options.id,
      start: options.start,
      end: options.end,
    });
    this.model = new Worker({ id: options.id });
  },
  fetch: function(options) {
    this.model.fetch(options);
    // collection is fetched after, by view
  }
});

var BughunterLogsModel = BughunterModel.extend({
  initialize: function(options) {
    this.collection = new LogCollection([], {
      start: options.start,
      end: options.end,
    });
  },
  fetch: function(options) {
    this.collection.fetch(options);
  }
});
