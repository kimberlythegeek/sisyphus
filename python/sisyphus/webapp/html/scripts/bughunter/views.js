DataTableCollectionView = Backbone.View.extend({
  init: function(tablename, columns, defaultSorting) {
    this.modelRowMap = [];
    this.tablename = tablename;
    this.columns = columns;
    this.tableConfig = {
      bAutoWidth: false,
      bFilter: false,
      bInfo: false,
      bJQueryUI: true,
      bPaginate: false,
      bSortClasses: false,
      fnDrawCallback: _.bind(function() {
        if (this.datatable) {
          localStorage.setItem(this.localStorageName('sorting'),
                               this.datatable.fnSettings().aaSorting);
        }
      }, this)
    };
    if (columns) {
      this.tableConfig.aoColumns = columns;
    }
    if (localStorage.getItem(this.localStorageName('sorting'))) {
      this.tableConfig.aaSorting =
        [
          localStorage.getItem(this.localStorageName('sorting'))
            .split(',')
            .map(function(x) {
              if (parseInt(x) == x) {
                return parseInt(x);
              }
              return x;
            })
        ];
    } else if (defaultSorting) {
      this.tableConfig.aaSorting = defaultSorting;
    }
    this.addRow = _.bind(this.addRow, this);
    this.changeRow = _.bind(this.changeRow, this);
    this.render = _.bind(this.render, this);
    this.refresh = _.bind(this.refresh, this);
    this.collection.bind('refresh', this.refresh);
    return this;
  },

  localStorageName: function(settingName) {
    return 'bughunter-' + this.tablename + '-' + settingName;
  },

  createTable: function() {
    this.datatable = this.el.dataTable(this.tableConfig);
  },

  destroy: function() {
    this.datatable.fnDestroy();
    this.el.remove();
  },

  render: function() {
    this.datatable.fnDraw();
    this.datatable.bAutoWidth = false;  // prevents column widths from changing
    var el = this.el;
    var datatable = this.datatable;
    // Highlight the first row on loading--this gives the user a hint that
    // the 'log' buttons appear on hover.
    var firstRow = $(this.el.find('tbody').find('tr')[0]);
    firstRow.find('.buttons').css({'visibility': 'visible'});
    firstRow.addClass('highlighted');
    // Remove the 'artificial' highlighting when the table is first moused-over.
    this.el.unbind('mouseover');
    this.el.mouseover(function() {
      firstRow.find('.buttons').css({'visibility': 'hidden'});
      firstRow.removeClass('highlighted');
      $(this).unbind('mouseover');
    });
    $(this.datatable.fnGetNodes()).hover(function() {
      $(this).find('.buttons').css({'visibility': 'visible'});
    }, function() {
      $(this).find('.buttons').css({'visibility': 'hidden'});
    });

    $('.fg-button').hover(
      function(){ 
	$(this).addClass("ui-state-hover"); 
      },
      function(){ 
	$(this).removeClass("ui-state-hover"); 
      }
    );
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
    this.init('workers', [
      { sTitle: 'id', sType: 'numeric', modelKey: 'id', bVisible: false },
      { sTitle: 'Hostname', modelKey: 'hostname' },
      { sTitle: 'Type', modelKey: 'worker_type' },
      { sTitle: 'State', modelKey: 'state' },
      { sTitle: 'Last&nbsp;Update&nbsp;(PT)', modelKey: 'datetime' },
      { sTitle: 'OS', modelKey: 'os_name', sWidth: '10em' },
      { sTitle: 'Version', modelKey: 'os_version' },
      { sTitle: 'CPU', modelKey: 'cpu_name' },
    ], [[1, 'asc']]);
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
    this.updateRowHighlighting(model, rowId);
  },

  addRow: function(model, redraw) {
    if (redraw === undefined) {
      redraw = true;
    }
    var modelId = model.get('id');
    var data = [];
    for (var i = 0; i < this.columns.length; i++) {
      if (i == 1) {
	//data.push(model.get(this.columns[i].modelKey) + ' <span class="buttons"><a href="#admin/worker/' + modelId + '" class="fg-button ui-state-default fg-button-icon-solo ui-corner-all" title="Logs"><span class="ui-icon ui-icon-script"></span></a></span>');
        data.push(model.get(this.columns[i].modelKey) + ' <span class="buttons"><a href="#admin/worker/' + modelId + '" class="fg-button ui-state-default fg-button-icon-solo ui-corner-all" title="Logs">log</a></span>');
      } else {
	data.push(model.get(this.columns[i].modelKey));
      }
    }
    var added = this.datatable.fnAddData(data, redraw);
    this.modelRowMap[modelId] = added[0];
    this.updateRowHighlighting(model, added[0]);
  },

  updateRowHighlighting: function(model, rowId) {
    var row = $(this.datatable.fnGetNodes(rowId));
    var highlightedStates = ['disabled', 'dead', 'zombie'];
    row.removeClass(highlightedStates.join(' '));
    var state = model.get('state');
    if (highlightedStates.indexOf(state) != -1) {
      row.addClass(state);
    }
  },

});

WorkerSummaryCollectionView = DataTableCollectionView.extend({
  initialize: function() {
    this.init('workersummary', [{}, {sClass: 'text_right'}, {sClass: 'text_right'}, {sClass: 'text_right'}, {sClass: 'text_right'}, {sClass: 'text_right'}],
      [[0, 'asc']]);
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
    this.collectionView.createTable();
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
    this.collectionView.createTable();
    this.collectionView.datatable.fnAddData(['Loading...', '', '', '', '', '']);
  },

  destroy: function() {
    this.collectionView.destroy();
  }
});

BughunterLogsViewBase = Backbone.View.extend({
  destroy: function() {
    this.options.renderer.clear();
  },

  refreshLogs: function() {
    this.refresh();
    $('.loading').hide();
    $('table.logs').show();
    if (this.model.collection.isEmpty()) {
      $('.nologs').show();
    } else {
      $('.nologs').hide();
      $('#clearlog').show();
      $('#clearlog').click(_.bind(function() {
        $('.loading').show();
        $('table.logs').hide();
	this.model.collection.destroy(_.bind(function() {
	  this.model.collection.fetch();
	}, this));
      }, this));
    }

    // FIXME: Switch to something other than tempo so I don't have to do this.
    // See below for a complaint about inherited templates.
    var rows = $('table.logs tr');
    for (var i = 0; i < rows.length; i++) {
      if (i % 2 == 0) {
        $(rows[i]).addClass('even');
      } else {
        $(rows[i]).addClass('odd');
      }
    }

  },

  initLogCtrls: function() {
    if (this.model.collection.options.start &&
        this.model.collection.options.start != '-') {
      $('#logstart').val(this.model.collection.options.start);
    }
    if (this.model.collection.options.end) {
      $('#logend').val(this.model.collection.options.end);
    }
    var pickerOpts = {
      format: '%Y-%m-%dT%T'
    };
    function checkForm() {
      if ($('#logcontrols')[0].checkValidity()) {
        $('#refreshlog').removeClass('ui-state-disabled');
        $('#refreshlog').attr('disabled', false);
      } else {
        if (!$('#refreshlog').hasClass('ui-state-disabled')) {
          $('#refreshlog').addClass('ui-state-disabled');
        }
        $('#refreshlog').attr('disabled', true);
      }        
    }
    $('#logstart').keyup(checkForm);
    $('#logend').keyup(checkForm);
    checkForm();

    $('#logcontrols').submit(_.bind(function() {
      if (!$('#logcontrols')[0].checkValidity()) {
        return false;
      }
      var hash = this.hashBase;
      var start = $('#logstart').val();
      var end = $('#logend').val();
      if (!start) {
        start = '-';
      }
      hash += '/' + start;
      if (end) {
        hash += '/' + end;
      }
      document.location.hash = hash;
      return false;
    }, this));
  }
});

BughunterLogsView = BughunterLogsViewBase.extend({
  initialize: function() {
    this.model.collection.bind('refresh', _.bind(this.refreshLogs, this));
    this.hashBase = 'admin/logs';
  },

  refresh: function() {
    this.destroy();
    var start = this.model.collection.options.start;
    if (!start) {
      start = '-';
    }
    var end = this.model.collection.options.end;
    if (!end) {
      end = '-';
    }
    var logs = this.model.collection.toJSON();
    this.options.renderer.render([{
      page: 'logs',
      logs: logs,
    }]);
    this.initLogCtrls();
    // Blah, this is only necessary 'cause a child template can't
    // seem to read vars from a parent template in tempo.
    // FIXME: try other JS template libs.
    $('td.logmachine a').each(function() {
      $(this).attr('href', $(this).attr('href') + '/' + start + '/' + end);
    });
  }
});

BughunterWorkerView = BughunterLogsViewBase.extend({
  initialize: function() {
    // this should be a separate view -- not part of log summary page
    this.model.model.bind('change', _.bind(this.refreshDetails, this));
    // LogCollection or WorkerLogCollection
    this.model.collection.bind('refresh', _.bind(this.refreshLogs, this));
    this.hashBase = 'admin/worker/' + this.model.model.id;
  },

  refreshDetails: function() {
    /*
    if (this.model.collection.checkDates()) {
      var hash = 'admin/worker/' + this.model.model.id +
        '/' + this.tConv.format(new Date(this.model.collection.options.start)) +
        '/' + this.tConv.format(new Date(this.model.collection.options.end));
      Backbone.history.saveLocation(hash);
    }
    */
    this.refresh();
    
    // Details only loaded once; otherwise, we might want to change this
    // to not load logs each time.
    this.model.collection.fetch();
  },

  // There doesn't seem to be a way to do proper nested templates in tempo
  // (e.g. render a template and later render a subtemplate).  So we refresh
  // both times.  Not too bad since this data only loads once, at the moment,
  // but if it gets more complicated, consider using more than one renderer
  // (and thus move the renderer out of the controller and into the views).
  refresh: function() {
    this.destroy();
    this.options.renderer.render([{
      page: 'worker',
      hash: '#admin/worker/' + this.model.model.get('id'),
      worker: this.model.model.toJSON(),
      logs: this.model.collection.toJSON()
    }]);
    this.initLogCtrls();
  }
});
