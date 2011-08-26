// FIXME: Many of these views use ids too much; we should prefer element/class
// selectors.

/**** Partial Views ****/

/**
 * View for displaying data in a table via the jQuery DataTables plug-in.
 * This is intended to only wrap one <table> element.
 */
DataTableCollectionView = Backbone.View.extend({

  init: function(tablename, columns, defaultSorting) {
    this.colNumDisplayOffset = 0;
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
    this.render = _.bind(this.render, this);
    this.reset = _.bind(this.reset, this);
    this.collection.bind('reset', this.reset);
    this.collection.bind('add', _.bind(this.add, this));
    if (this.getCellValue !== undefined && this.getColNum !== undefined) {
      this.collection.bind('change', _.bind(this.change, this));
    }
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
  },

  render: function() {
    this.datatable.fnDraw();
    this.datatable.bAutoWidth = false;  // prevents column widths from changing
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

  reset: function() {
    this.datatable.fnClearTable();
    this.collection.forEach(function(model) {
      this.add(model, false);
    }, this);
    this.render();
  },

  add: function(model, redraw) {
    if (redraw === undefined) {
      redraw = true;
    }
    var modelId = model.get('id');
    var added = this.datatable.fnAddData(this.getRow(model), redraw);
    this.modelRowMap[modelId] = added[0];
    this.updateRowHighlighting(model, added[0]);
  },

  change: function(model) {
    var modelId = model.get('id');
    var rowId = this.modelRowMap[modelId];
    var changes = model.changedAttributes();
    for (var name in changes) {
      var value = this.getCellValue(model, name);
      var colNum = this.getColNum(model, name);
      this.updateCell(value, rowId, colNum, colNum + this.colNumDisplayOffset);
    }
    this.updateRowHighlighting(model, rowId);
  },

  updateRowHighlighting: function(model, rowId) {
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
  }
});


/**
 * List of workers.
 */
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
      { sTitle: 'CPU', modelKey: 'cpu_name' }
    ], [[1, 'asc']]);
    this.columnMap = {};
    for (var i = 0; i < this.columns.length; i++) {
      this.columnMap[this.columns[i].modelKey] = i;
    }
    this.colNumDisplayOffset = -1;  // since id is hidden
  },

  getCellValue: function(model, name) {
    //changes[name]
    return model.get(name);
  },

  getColNum: function(model, name) {
    return this.columnMap[name];
  },

  getRow: function(model) {
    var modelId = model.get('id');
    var data = [];
    for (var i = 0; i < this.columns.length; i++) {
      if (i == 1) {
        data.push(model.get(this.columns[i].modelKey) + ' <span class="buttons"><a href="#admin/worker/' + modelId + '" class="fg-button ui-state-default fg-button-icon-solo ui-corner-all" title="Logs">log</a></span>');
      } else {
	data.push(model.get(this.columns[i].modelKey));
      }
    }
    return data;
  },

  // FIXME generic callback?
  updateRowHighlighting: function(model, rowId) {
    var row = $(this.datatable.fnGetNodes(rowId));
    var highlightedStates = ['disabled', 'dead', 'zombie'];
    row.removeClass(highlightedStates.join(' '));
    var state = model.get('state');
    if (highlightedStates.indexOf(state) != -1) {
      row.addClass(state);
    }
  }
});


/**
 * Summary of workers.
 */
WorkerSummaryCollectionView = DataTableCollectionView.extend({
  initialize: function() {
    this.init('workersummary', [
      {}, 
      {sClass: 'text_right'}, 
      {sClass: 'text_right'},
      {sClass: 'text_right'},
      {sClass: 'text_right'},
      {sClass: 'text_right'}
    ], [[0, 'asc']]);
  },

  getRow: function(model) {
    return [model.get('id'), model.builders(), model.crashTesters(),
            model.crashTesterTP(), model.unitTesters(), model.unitTesterTP()];
  },

  getCellValue: function(model, name) {
    var value = '';
    if (name.match(/^builder_/)) {
      value = model.builders();
    } else if (name == 'crashtest_jobs') {
      value = model.crashTesterTP();
    } else if (name.match(/^crashtest_/)) {
      value = model.crashTesters();
    } else if (name == 'unittest_jobs') {
      value = model.unitTesterTP();
    } else if (name.match(/^unittest_/)) {
      value = model.unitTesters();
    }
    return value;
  },

  getColNum: function(model, name) {
    var colNum = -1;
    if (name.match(/^builder_/)) {
      colNum = 1;
    } else if (name == 'crashtest_jobs') {
      colNum = 3;
    } else if (name.match(/^crashtest_/)) {
      colNum = 2;
    } else if (name == 'unittest_jobs') {
      colNum = 5;
    } else if (name.match(/^unittest_/)) {
      colNum = 4;
    }
    return colNum;
  },

});


/**
 * Crash summary.
 */
CrashSummaryCollectionView = DataTableCollectionView.extend({
  initialize: function() {
    this.init('crashesbydate', [
      { sTitle: 'Signature', sType: 'string' },
      { sTitle: 'Fatal Message' },
      { sTitle: 'Total&nbsp;Count', sType: 'numeric' },
      { sTitle: 'Counts Broken Down', bSortable: false }
    ], [[2, 'desc']]);
  },

  getRow: function(model) {
    var totalCount = 0;
    var breakDown = '';
    var branches = model.get('branches');
    var branchNames = [];
    for (branch in branches) {
      branchNames.push(branch);
    }
    branchNames.sort();
    for (var i = 0; i < branchNames.length; i++) {
      var branch = branchNames[i];
      var breakDowns = [];
      for (var platform in branches[branch]) {
        totalCount += branches[branch][platform];
        breakDowns.push(platform + ': ' + branches[branch][platform]);
      }
      breakDown += '<b>' + branch + '</b>: ' + breakDowns.join(' | ') + '</br>';
    }
    breakDown = breakDown.replace(' ', '&nbsp;', 'g');
    var fatal_message = model.get('fatal_message');
    if (!fatal_message) {
      fatal_message = '<i>none</i>';
    }
    var signature = model.get('signature');
    return [signature, fatal_message, totalCount, breakDown];
  }
});


/**
 * Header: auth info, menu bar, view title.
 */
HeaderView = Backbone.View.extend({
  render: function() {
    this.el.html(ich.toolbar({username: window.auth.username}));
    $('#menubar').buttonset();
    $("input:radio[name='menuradio']").change(function() {
      app.navigate('admin/' + $('input:radio[name=menuradio]:checked').val(), 
                   true);
    });
  },

  changeView: function(headerInfo) {
    var headerTitle = headerInfo.title ? headerInfo.title : '';
    this.el.find('.title').text(headerTitle);
    document.title = headerTitle + ' - bughunter';
    if (headerInfo.buttonId) {
      $('#' + headerInfo.buttonId).attr('checked', true);
    } else {
      // none checked
      $('input:radio[name=menuradio]').attr('checked', false);
    }
    $('#menubar').buttonset('refresh');
  }
});


/********* Body views *********/

BughunterWorkerListView = Backbone.View.extend({
  initialize: function() {
    this.collectionView = null;
    this.header = {
      buttonId: 'menuworkers',
      title: 'workers'
    };
  },

  render: function() {
    this.el.html(ich.standardtable());
    this.collectionView = new WorkerCollectionView({ el: $('#main table'),
      collection: this.model.collection });
    this.collectionView.createTable();
    this.collectionView.datatable.fnAddData([0, 'Loading...', '', '', '', '', '', '']);
  },

  destroy: function() {
    if (this.collectionView) {
      this.collectionView.destroy();
    }
  }
});


BughunterWorkerSummaryView = Backbone.View.extend({
  initialize: function() {
    this.collectionView = null;
    this.header = {
      buttonId: 'menuworkersummary',
      title: 'bughunter worker summary'
    };
  },

  render: function() {
    this.el.html(ich.workersummary());
    this.collectionView = new WorkerSummaryCollectionView({
      el: $('#main table'),
      collection: this.model.collection
    });
    this.collectionView.createTable();
    this.collectionView.datatable.fnAddData(['Loading...', '', '', '', '', '']);
  },

  destroy: function() {
    if (this.workerSummaryCollectionView) {
      this.workerSummaryCollectionView.destroy();
    }
  }
});


BughunterDateControlsViewBase = Backbone.View.extend({
  initDateCtrls: function() {
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
      if ($('#datecontrolsform')[0].checkValidity()) {
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

    $('#datecontrolsform').submit(_.bind(function() {
      if (!$('#datecontrolsform')[0].checkValidity()) {
        return false;
      }
      var hash = this.hashBase;
      var start = $('#logstart').val();
      var end = $('#logend').val();
      if (!start) {
        start = '-';
      }
      if (!end) {
        end = '-';
      }
      hash += '/' + start + '/' + end;
      var extraParms = this.extraParms();
      for (var i = 0; i < extraParms.length; i++) {
        hash += '/' + extraParms[i];
      }
      // FIXME: this won't work if we switch to pushState
      if (document.location.hash == '#' + hash) {
        this.render();
        this.model.fetch();
      } else {
        app.navigate(hash, true);
      }
      return false;
    }, this));
  },

  extraParms: function() {
    return [];
  }
});


// FIXME: Inheritance here is a little weird; too much back-and-forth
// between base and derived classes.
BughunterLogsViewBase = BughunterDateControlsViewBase.extend({
  refreshLogs: function() {
    this.rowCount = 0;
    this.createTable();
    $('.loading').hide();
    if (this.model.collection.isEmpty()) {
      $('.nologs').show();
    } else {
      $('.nologs').hide();
      $('table.logs').show();
      $('#clearlog').show();
      $('#clearlog').click(_.bind(function() {
        $('.loading').show();
        $('table.logs').hide();
	this.model.collection.destroy(_.bind(function() {
	  this.model.collection.fetch();
	}, this));
      }, this));
    }
  },

  insertRow: function(rowData) {
    if (this.rowCount % 2 == 0) {
      rowData.rowclass = 'even';
    } else {
      rowData.rowclass = 'odd';
    }
    this.rowCount++;
    $("table.logs").append(this.rowTemplate(rowData));
  }
});


/* Combined worker-logs view */
BughunterLogsView = BughunterLogsViewBase.extend({
  initialize: function() {
    this.model.collection.bind('reset', _.bind(this.refreshLogs, this));
    this.hashBase = 'admin/logs';
    this.rowTemplate = ich.workercombinedlogentry;
    this.header = {
      buttonId: 'menulogs',
      title: 'combined worker logs'
    };
  },

  render: function() {
    this.el.html(ich.datecontrols());
    this.el.append(ich.workerlogs());
    this.el.find('.workerlogs').append(ich.combinedworkerlogstable());
    this.initDateCtrls();
  },

  createTable: function() {
    var start = this.model.collection.options.start;
    if (!start) {
      start = '-';
    }
    var end = this.model.collection.options.end;
    if (!end) {
      end = '-';
    }
    var logs = this.model.collection.toJSON();
    for (var i = 0; i < logs.length; i++) {
      logs[i].start = start;
      logs[i].end = end;
      this.insertRow(logs[i]);
    }
  }
});


BughunterWorkerView = BughunterLogsViewBase.extend({
  initialize: function() {
    this.model.model.bind('change', _.bind(this.refreshDetails, this));
    this.model.collection.bind('reset', _.bind(this.refreshLogs, this));
    this.hashBase = 'admin/worker/' + this.model.model.id;
    this.rowTemplate = ich.workerlogentry;
    this.header = {
      title: 'worker info'
    };
  },

  refreshDetails: function() {
    var workerConfig = { hash: '#admin/worker/' + this.model.model.get('id') };
    var worker = this.model.model.toJSON();
    for (var attr in worker) {
      workerConfig[attr] = worker[attr];
    }
    this.el.html(ich.workerdetails(workerConfig));
    this.el.append(ich.datecontrols());
    this.el.append(ich.workerlogs());
    this.el.find('.workerlogs').append(ich.workerlogstable());
    this.initDateCtrls();
    
    // Details only loaded once; otherwise, we might want to change this
    // to not load logs each time.
    this.model.collection.fetch();
  },

  render: function() {
    this.el.html(ich.loading());
  },

  // There doesn't seem to be a way to do proper nested templates in tempo
  // (e.g. render a template and later render a subtemplate).  So we refresh
  // both times.  Not too bad since this data only loads once, at the moment,
  // but if it gets more complicated, consider using more than one renderer
  // (and thus move the renderer out of the controller and into the views).
  createTable: function() {
    var logs = this.model.collection.toJSON();
    for (var i = 0; i < logs.length; i++) {
      this.insertRow(logs[i]);
    }
  }
});


BughunterCrashSummaryView = BughunterDateControlsViewBase.extend({
  initialize: function() {
    this.menuBarView = null;
    this.collectionView = null;
    this.hashBase = 'crashes/date';
    this.header = {
      title: 'crashes'
    };
  },

  render: function() {
    this.el.html(ich.datecontrols());
    this.el.find('.extracontrols').append(ich.newonlycontrols({ entitytype: 'crashes' }));
    this.el.append(ich.standardtable());
    this.initDateCtrls();
    if (this.model.collection.options.newonly) {
      $('#newonly').attr('checked', 'checked');
    }
    this.collectionView = new CrashSummaryCollectionView({ el: $('#main table'),
      collection: this.model.collection });
    this.collectionView.createTable();
    this.collectionView.datatable.fnAddData(['Loading...', '', '', '']);
  },

  destroy: function() {
    if (this.collectionView) {
      this.collectionView.destroy();
    }
  },

  extraParms: function() {
    if ($('#newonly').attr('checked')) {
      return ['newonly'];
    }
    return [];
  }
});


BughunterLoginView = Backbone.View.extend({
  render: function() {
    this.el.html(ich.login());
    $('#loginform').submit(_.bind(this.login_form_submitted, this));
    $('#username').focus();
  },

  postRender: function() {
    // This has to be done after the div is show()n.
    $('#username').focus();
  },

  login_form_submitted: function() {
    // FIXME: Needs a loading message of some kind.
    window.auth.logIn($('#username').val(), $('#password').val(), null,
      _.bind(function() {
        this.error('bad username/password');
      }, this), _.bind(function() {
        this.error('server error!');
      }, this));
    return false;
  },

  error: function(errmsg) {
    $('#loginmain .errormsgs').text(errmsg);
  }
});


/******** Main page view ********/

BughunterPageView = Backbone.View.extend({
  initialize: function() {
    this.header = new HeaderView({ el: $('#header') });
    this.body = null;
  },

  render: function() {
    this.header.render();
    if (this.body) {
      this.body.render();
    }
  },

  loadPage: function(body) {
    if (this.body) {
      this.body.el.hide();
      if (this.body.destroy) {
        this.body.destroy();
        this.body.el.html('');
      }
    }
    this.body = body;
    if (this.body.header) {
      this.header.changeView(this.body.header);
      this.header.el.show();
    } else {
      this.header.el.hide();
    }
    this.body.render();
    this.body.el.show();
    if (this.body.postRender) {
      this.body.postRender();
    }
  }
});