var Worker = Backbone.Model.extend({
  'id': '',
  'worker_type': '',
  'os_name': '',
  'hostname': '',
  'cpu_name': '',
  'datetime': '',
  'os_version': '',
  'state': ''
});

var WorkerCollection = Backbone.Collection.extend({
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

var WorkerSummaryCollection = Backbone.Collection.extend({
  model: WorkerSummary,
  url: 'bughunter/api/admin/workersummary/',
  comparator: function(model) {
    return model.get('id');
  }
});

var BughunterAdminAppModel = Backbone.Model.extend({
  initialize: function() {
    this.collection = new WorkerCollection();
  },
});

var BughunterWorkerSummaryModel = Backbone.Model.extend({
  initialize: function() {
    this.collection = new WorkerSummaryCollection();
  },
});
