DataTableCollectionView = Backbone.View.extend({
  init: function(columns, sorting) {
    this.modelRowMap = [];
    this.columns = columns;
    this.tableConfig = {
      bAutoWidth: false,
      bFilter: false,
      bInfo: false,
      bJQueryUI: true,
      bPaginate: false,
      bSortClasses: false
    };
    if (columns) {
      this.tableConfig.aoColumns = columns;
    }
    if (sorting) {
      this.aaSorting = sorting;
    }
    this.addRow = _.bind(this.addRow, this);
    this.changeRow = _.bind(this.changeRow, this);
    this.render = _.bind(this.render, this);
    this.refresh = _.bind(this.refresh, this);
    this.collection.bind('refresh', this.refresh);
    return this;
  },

  create_table: function() {
    this.datatable = this.el.dataTable(this.tableConfig);
  },

  destroy: function() {
    this.datatable.fnDestroy();
    this.el.remove();
  },

  render: function() {
    this.datatable.fnDraw();
    this.datatable.bAutoWidth = false;  // prevents column widths from changing
  },

  refresh: function() {
    this.datatable.fnClearTable();
    this.collection.forEach(function(model) {
      this.addRow(model, false);
    }, this);
    this.render();
  },

  updateCell: function(newValue, rowId, colNum, displayedColNum) {
    if (displayedColNum === undefined) {
      displayedColnum = colNum;
    }
    this.datatable.fnUpdate(newValue, rowId, colNum);
    var row = $(this.datatable.fnGetNodes(rowId));
    var cell = $(row.find('td')[displayedColNum]);
    var bgColor = row.css('background-color');
    cell.css({ 'background-color': '#ffcc66' });
    cell.animate({ backgroundColor: bgColor }, 2000,
      function() { $(this).css('background-color', ''); });
  },
});

WorkerCollectionView = DataTableCollectionView.extend({
  initialize: function() {
    this.init([
      { sTitle: 'id', sType: 'numeric', modelKey: 'id', bVisible: false },
      { sTitle: 'Hostname', modelKey: 'hostname' },
      { sTitle: 'Type', modelKey: 'worker_type' },
      { sTitle: 'State', modelKey: 'state' },
      { sTitle: 'Last&nbsp;Update', modelKey: 'datetime' },
      { sTitle: 'OS', modelKey: 'os_name', sWidth: '10em' },
      { sTitle: 'Version', modelKey: 'os_version' },
      { sTitle: 'CPU', modelKey: 'cpu_name' },
      //{ sTitle: 'Log' }
    ], [[1, 'desc']]);
    this.columnMap = {};
    for (var i = 0; i < this.columns.length; i++) {
      this.columnMap[this.columns[i].modelKey] = i;
    }
    this.collection.bind('add', this.addRow);
    this.collection.bind('change', this.changeRow);
  },

  changeRow: function(model) {
    var modelId = model.get('id');
    var rowId = this.modelRowMap[modelId];
    var changes = model.changedAttributes();
    for (var name in changes) {
      var colNum = this.columnMap[name];
      this.updateCell(changes[name], rowId, colNum, colNum-1); // -1 since id is hidden
    }
  },

  addRow: function(model, redraw) {
    if (redraw === undefined) {
      redraw = true;
    }
    var modelId = model.get('id');
    var data = [];
    for (var i = 0; i < this.columns.length; i++) {
      data.push(model.get(this.columns[i].modelKey));
    }
    var added = this.datatable.fnAddData(data, redraw);
    var state = model.get('state');
    if (state == 'disabled' || state == 'dead' || state == 'zombie') {
      var row = $(this.datatable.fnGetNodes(added[0]));
      if (!row.hasClass(state)) {
        row.addClass(state);
      }
    }
    this.modelRowMap[modelId] = added[0];
  },

});

WorkerSummaryCollectionView = DataTableCollectionView.extend({
  initialize: function() {
    this.init([{}, {sClass: 'text_right'}, {sClass: 'text_right'}, {sClass: 'text_right'}, {sClass: 'text_right'}, {sClass: 'text_right'}],
      [[0, 'desc']]);
    this.collection.bind('add', this.addRow);
    this.collection.bind('change', this.changeRow);
  },

  addRow: function(model, redraw) {
    if (redraw === undefined) {
      redraw = true;
    }
    var modelId = model.get('id');
    var data = [modelId, model.builders(), model.crashTesters(), model.crashTesterTP(), model.unitTesters(), model.unitTesterTP()];
    var added = this.datatable.fnAddData(data, redraw);
    this.modelRowMap[modelId] = added[0];
  },

  changeRow: function(model) {
    var modelId = model.get('id');
    var rowId = this.modelRowMap[modelId];
    var changes = model.changedAttributes();
    for (var name in changes) {
      if (name.match(/^builder_/)) {
        this.updateCell(model.builders(), rowId, 1, 1);
      } else if (name == 'crashtest_jobs') {
        this.updateCell(model.crashTesterTP(), rowId, 3, 3);
      } else if (name.match(/^crashtest_/)) {
        this.updateCell(model.crashTesters(), rowId, 2, 2);
      } else if (name == 'unittest_jobs') {
        this.updateCell(model.unitTesterTP(), rowId, 5, 5);
      } else if (name.match(/^unittest_/)) {
        this.updateCell(model.unitTesters(), rowId, 4, 4);
      }
    }
  },

});

BughunterAdminAppView = Backbone.View.extend({
  initialize: function() {
    this.options.renderer.render([{ page: 'workers' }]);
    this.collectionView = new WorkerCollectionView({ el: $('#main table'),
      collection: this.model.collection });
  },

  render: function() {
    this.collectionView.create_table();
    this.collectionView.datatable.fnAddData([0, 'Loading...', '', '', '', '', '', '']);
  },

  destroy: function() {
    this.collectionView.destroy();
  }
});

BughunterWorkerSummaryView = Backbone.View.extend({
  initialize: function() {
    this.options.renderer.render([{ page: 'workersummary' }]);
    this.collectionView = new WorkerSummaryCollectionView({ el: $('#main table'),
      collection: this.model.collection });
  },

  render: function() {
    this.collectionView.create_table();
    this.collectionView.datatable.fnAddData(['Loading...', '', '', '', '', '']);
  },

  destroy: function() {
    this.collectionView.destroy();
  }
});
