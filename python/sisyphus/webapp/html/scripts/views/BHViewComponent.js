var BHViewComponent = new Class({

   /********************************
    * BHViewComponent
    *
    *    This component encapsulates all of the functionality
    * of a single BHView.  The BH prefix on attribute or functions
    * is to help distinguish between the pane constructed in the 
    * user interface that constitutes a single functional component
    * and the View of MVC which is also used by the component.
    *    The component acts as both a public interface to component
    * functionality and a controller of it's own private View and Model
    * class.
    ********************************/
   Extends: Component,

   jQuery:'BHViewComponent',

   options: {
      bhviewName:'',
      bhviewIndex:0
   },

   initialize: function(selector, options){

      this.setOptions(options);
      
      this.parent(options);

      //This index is dynamically appended
      //to every id in a view clone.
      this.bhviewIndex = this.options.bhviewIndex;

      //The defaultBHView is the first view initialized
      //when the page loads.
      this.defaultBHView = false;

      //Callback methods for button clicks
      this.buttonHandlers = { closetable:this.closeTable,
                              openwindow:this.openWindow,
                              refresh:this.refresh,
                              help:this.help,
                              signal_help:this.getSignalHelp,
                              increasesize:this.increaseSize,
                              decreasesize:this.decreaseSize };

      //Adapters to manage idiosynchratic view behavior
      this.dataAdapters = new DataAdapterCollection();

      this.model = new BHViewModel('#BHViewModel', {bhviewName:this.options.bhviewName,
                                                    dataAdapters:this.dataAdapters});
      this.view = new BHViewView('#BHViewView', {});


      //BHView events
      this.closeEvent = 'CLOSE_BHVIEW';
      this.addBHViewEvent = 'ADD_BHVIEW';
      this.processControlPanelEvent = 'PROCESS_CONTROL_PANEL';
      this.signalEvent = 'SIGNAL_BHVIEW';
      this.signalTypeEvent = 'SET_SIGNALING_TYPE_BHVIEW';

      //Set up subscriptions
      this.subscriptionTargets = {};
      this.subscriptionTargets[this.processControlPanelEvent] = this.processControlPanel;
      this.subscriptionTargets[this.signalEvent] = this.signalHandler;
      this.subscriptionTargets[this.signalTypeEvent] = this.setSignalingType;

      //Register subscribers
      BHPAGE.registerSubscribers(this.subscriptionTargets,
                                 this.view.allViewsContainerSel,
                                 this);

      //datatable.js object is stored in this attribute
      this.dataTable;

      //Look for signals embedded in the page to
      //initialize the control panel with
      this.signalData = this.getSignalData();

      //The signalingType indicates whether a view
      //can send or receive signals.
      if(this.bhviewIndex == 0){
         //First view is a sender by default
         this.signalingType = 'send';
         //Disable the close button so the user cannot
         //have a viewless page
         this.view.disableClose(this.bhviewIndex);
      }else{
         //All other views are receivers
         this.signalingType = 'receive';
      }

      //Get a new HTML clone for the 
      //view and initialize it.
      this.getBHViewClone();

      //Select view and load the data
      this.selectBHView();

   },
   /****************
    *PUBLIC INTERFACE
    ****************/
   destroy: function(){

      //Delete the view from the DOM
      this.view.removeBHView(this.bhviewIndex);

      //Get rid of any events assigned with live
      this.dataTable.die();

      //Unbind local events
      var paginationSel = this.view.getTablePaginationSel(this.bhviewIndex);
      $(paginationSel).unbind();

      //Call table destructor
      this.dataTable.fnDestroy();

      //Unbind custom events
      BHPAGE.unbindSubscribers(this.subscriptionTargets,
                               this.view.allViewsContainerSel);

      //This should be done programmatically but not sure
      //if delete will work without explicit attribute reference.
      //Need to do some research...
      delete(this.subscriptionTargets);
      delete(this.signalingType);
      delete(this.bhviewIndex);
      delete(this.defaultBHView);
      delete(this.buttonHandlers);
      delete(this.model);
      delete(this.view);
      delete(this.dataAdapters);
      delete(this.closeEvent);
      delete(this.addBHViewEvent);
      delete(this.processControlPanelEvent);
      delete(this.signalEvent);
      delete(this.signalTypeEvent);
      delete(this.subscriptionTargets);
      delete(this.signalData);
      delete(this.dataTable);
   },
   selectBHView: function(item){

      var bhviewName = "";

      if(item){
         //Called from callback
         bhviewName = item.href.replace(/^.*?\#/, '');
      }else{
         //Called directly, use the bhviewHash
         bhviewName = this.model.getBHViewAttribute('name');
      }

      //Check for any page targets
      var ptarget = this.model.getBHViewPageTarget(bhviewName);
      if(ptarget != undefined){
         //View uses a pages target not the web service
         //send user to page
         ptarget = ptarget.replace('HASH', '#');

         window.open(ptarget);

         return false;
      }

      //Set data for new view
      this.model.setBHViewHash(bhviewName);

      this.view.showTableSpinner(this.bhviewIndex);

      //Set up control panel, this must be done
      //in the selectBHView method to account for
      //unique control panel/bhview relationships
      this.setControlPanelEv();

      var adapterName = this.model.getBHViewAttribute('data_adapter');
      var a = this.dataAdapters.getAdapter(adapterName);
      var params = "";
      if(this.signalData.signal != undefined){
         params += this.signalData.signal + '=' + this.signalData.data;
      }else{
         params = a.getDefaultParams();
      }
      this.model.getBHViewData(bhviewName, 
                               this, 
                               this.initializeBHView, 
                               params);

   },
   markAsDefault: function(){
      this.defaultBHView = true;
   },

   /***************
    * CUSTOM EVENT HANDLERS
    *
    * Custom events are defined in the constructor and
    * can be triggered from any other component.  All 
    * custom events are triggered on the '#bh_view_container' 
    * div.  This gives subscribers a single place to register.
    ***************/
   processControlPanel: function(data){

      var bhviewIndex = parseInt(data.bhviewIndex);

      //Since this is an event listener on the main view container
      //we need to confirm that the click event matches this BHView's 
      //index.
      if((bhviewIndex == this.bhviewIndex) || (data.signal != undefined)){
         var controlPanelDropdownSel = this.view.getIdSelector(this.view.controlPanelDropdownSel, 
                                                             this.bhviewIndex);

         var adapterName = this.model.getBHViewAttribute('data_adapter');
         var a = this.dataAdapters.getAdapter(adapterName);

         var params = "";
         if(data.signal != undefined){
            params = a.processControlPanel(controlPanelDropdownSel, data);
         }else{
            params = a.processControlPanel(controlPanelDropdownSel);
         }
         this.view.showTableSpinner(this.bhviewIndex);

         this.model.getBHViewData(this.model.getBHViewAttribute('name'),
                                  this, 
                                  this.initializeBHView,
                                  params);
      }
   },
   signalHandler: function(data){

      //If this view can receive and it's not the sender
      if((this.signalingType == 'receive') && 
         (this.signalData.bhviewIndex != this.bhviewIndex)){

         var signals = this.model.getBHViewAttribute('signals');

         //Make sure the bhview can handle the signal
         if(signals[ data.signal ] != 1){
            return;
         }

         //This view can receive signals
         if(data.signal == 'text_filter'){
            
            //This causes some resize bugs, could be cool in
            //the future if i can fix... commenting out for now
            
            //filter in browser using search box
            //this.dataTable.fnFilter( data.data );
            
         }else{
            this.signalData = data;
            //Pre-fill any fields
            var controlPanelDropdownSel = this.view.getIdSelector(this.view.controlPanelDropdownSel, 
                                                                   this.bhviewIndex);

            //Display the signal data
            this.view.displaySignalData('receive', this.signalData, this.bhviewIndex);

            var adapterName = this.model.getBHViewAttribute('data_adapter');
            var a = this.dataAdapters.getAdapter(adapterName);
            a.setControlPanelFields(controlPanelDropdownSel, this.signalData);

            var controlPanelDropdownSel = this.view.getIdSelector(this.view.controlPanelDropdownSel, 
                                                                  this.bhviewIndex);

            this.processControlPanel(this.signalData);
         }
      }
   },

   setSignalingType: function(data){
      if(data.bhviewIndex == this.bhviewIndex){
         this.signalingType = data.type;
      }
   },

   /********************
    *BHVIEW LOCAL EVENT REGISTRATION
    *
    * Local events in this case are events that 
    * have a single listener that is the BHView itself.
    ********************/
   registerBHViewEvents: function(){

      //Set up component events
      this.setMenuEv();
      this.setVisEv();
      this.setButtonEv();

   },
   setMenuEv: function(){

      $.ajax(this.view.navMenuHtmlUrl, { 

         accepts:'text/html',
         dataType:'html',

         success: _.bind(function(data){

            var navMenuSel = this.view.getIdSelector(this.view.navMenuSel, this.bhviewIndex);

            $(navMenuSel).menu({ 
               content: data,
               flyOut: true,
               showSpeed: 150,
               callback:{ method:this.selectBHView, 
                          context:this }
            });
         }, this) //end bind
      });
   },
   setControlPanelEv: function(){

      var controlPanel = this.model.getBHViewAttribute('control_panel');
      var bhcontrolPanelUrl = this.view.controlPanelHtmlUrl + controlPanel;

      $.ajax(bhcontrolPanelUrl, { 
         accepts:'text/html',
         dataType:'html',
         success: _.bind( this._setControlPanelCb, this )
      });
   },
   setVisEv: function(){

      var bhviewName = this.model.getBHViewAttribute('name');

      //Get chart types for bhview
      var charts = this.model.getBHViewAttribute('charts');

      //Get anchor id and ul id for view clone
      var visualizationSel = this.view.getIdSelector(this.view.visualizationSel, this.bhviewIndex);
      var visMenuSel = this.view.getIdSelector(this.view.visMenuSel, this.bhviewIndex);

      //Set the chart types
      this.view.setBHViewChartTypes(charts, visMenuSel);
      $(visualizationSel).menu({
         content: $(visMenuSel).html(),
         showSpeed: 50,
         callback: { method:this.setVisualization, context:this }
      });
   },

   setButtonEv: function(){

      var topBarSel = this.view.getIdSelector(this.view.topBarSel, this.bhviewIndex);
      var sel = '[id$="bt_c_' + this.bhviewIndex + '"]';
      var topBarAnchors = $(topBarSel).find(sel);
      for(var i=0; i<topBarAnchors.length; i++){
         var a = topBarAnchors[i];
         $(a).bind('click', {}, _.bind( function(event){
            //Get the href of the anchor
            var buttonType = "";
            if(event.target.tagName == 'SPAN'){
               var p = $(event.target).parent();

               var signalHelpSel = this.view.getIdSelector(this.view.signalHelpBtSel, this.bhviewIndex);
               if($(event.target).attr('id')){ 
                  buttonType = 'signal_help';
               }else{
                  buttonType = $(p).attr('href').replace('#', '');
               }
            }else { 
               buttonType = $(event.target).attr('href').replace('#', '');
            }

            if( _.isFunction(this.buttonHandlers[ buttonType ]) ){
               _.bind(this.buttonHandlers[ buttonType ], this)(); 
            }else{
               console.log("Component Error: No button handler for " + buttonType);
            }
            event.stopPropagation();
         }, this));
      }
   },
   /************************
    *BHVIEW PREPARATION METHODS
    ************************/
   getBHViewClone: function(){

      //Clone a new view
      this.view.cloneBHView(this.bhviewIndex);

      //Show the spinner
      this.view.showSpinner(this.bhviewIndex);

      //Register view events
      this.registerBHViewEvents();
   },

   initializeBHView: function(data, textStatus, jqXHR){

      if(data.aoColumns.length > 0){

         //Load the data into the table
         var tableSel = this.view.getIdSelector(this.view.tableSel, this.bhviewIndex);

         if(this.tableCreated == true){
            //Remove any events that were assigned with live
            $(tableSel).die();
            //destroy the table
            this.dataTable.fnClearTable();
            this.dataTable.fnDestroy();
         }

         //Get a new clone of the table
         this.view.getNewTableClone(this.bhviewIndex, tableSel);

         //Load the table data
         this.dataTable = $(tableSel).dataTable( data );

         //Set up signal handling
         this.setDataTableSignals();

         this.tableCreated = true;

         var bhviewReadName = this.model.getBHViewAttribute('read_name');

         //Let everyone see the lovely view!
         this.view.showBHView(this.bhviewIndex, bhviewReadName);

         //The table is loaded and drawn first when it is hidden
         //this causes the column/row alignment to get off.  Redraw
         //the table after its display is set to visible to reset
         //alignment.
         this.dataTable.fnDraw();
      }else{
         this.view.showNoDataMessage(this.bhviewIndex);
      } 
   },
   getSignalData: function(){

      var signals = this.model.getBHViewAttribute('signals');
      var signalData = {};

      if(signals != undefined){

         for(var signal in signals){
            var signalDataSel = this.view.signalBaseSel + signal;
            var data = $( signalDataSel ).val();
            if(data != undefined){
               signalData = { signal:signal,
                              data:data };
               //Remove signal to prevent all new bhviews from using
               //it as a default
               $( signalDataSel ).remove();
               return signalData;
            }
         }
      }
      return signalData;
   },
   setDataTableSignals: function(){

       /********************
        * NOTE: Binding of the context menu must be done every time a new page of 
        *       the data table is loaded.  There is no pagination event model in
        *       datatables.js.  It's supposed to be released in vs 2 and is being
        *       actively developed now.  For the moment use hacky click listener.
        *********************/
      var paginationSel = this.view.getTablePaginationSel(this.bhviewIndex);
      $(paginationSel).bind('click', _.bind(function(e){
         this._bindCellContextMenu();
      }, this));

      /**********************
       * NOTE: This click handler was originally in the live() call below.
       *       According to the datatables.js docs that is the prefered method
       *       for catching click events inside the table.
       *
       *       However, when cell menu's were added and removed, the datatable
       *       ceased to trigger an event for the menu anchor click.  This problem
       *       was removed by directly binding to the anchor taggle click.
       ***********************/
      this._bindCellContextMenu();

      //if the table is scrolled make sure we close any open menus
      $(this.view.tableScrollClassSel).bind('scroll', _.bind(function(e){
         if(this.view != undefined){
            this.view.closeMenu();
         }
      }, this));

      //Catch click events on the datatable
      $(this.dataTable).live("click", _.bind(function(event){

         //close any open menus
         this.view.closeMenu();

         event.stopPropagation();

         //If user selected an anchor in the main cell content
         //selectedTrEl will be a tr element
         var selectedTrEl = $(event.target).parent().parent().parent();

         //Make sure a table row was retrieved
         if( $(selectedTrEl).is('tr') ){

            this.view.selectTableRow( selectedTrEl );

            var href = $(event.target).attr('href');
            if(href != undefined){

               href = href.replace(/\#/, '');

               var adapterName = this.model.getBHViewAttribute('data_adapter');
               var a = this.dataAdapters.getAdapter(adapterName);
               var targetData = a.escapeForUrl($(event.target).text(), href);


               var controlPanelDropdownSel = this.view.getIdSelector(this.view.controlPanelDropdownSel, 
                                                                     this.bhviewIndex);
               var dateRange = a.getDateRangeParams(controlPanelDropdownSel);
               var signalData = { bhviewIndex:this.bhviewIndex,
                                  data:targetData,
                                  date_range:dateRange,
                                  signal:href };

               if(this.signalingType == 'send'){

                  //Display the signalData
                  this.view.displaySignalData('send', signalData, this.bhviewIndex);

                  $(this.view.allViewsContainerSel).trigger(this.signalEvent, signalData);
               }
            }
         }
      }, this));

      /*****************************
       * This captures the text entry in the search box and sends 
       * it out as a signal, currently not using this feature but
       * it could come in handy later so leaving it commented out for
       * now.
       *
      var filterSel = this.view.getFilterSel(this.bhviewIndex);
      var filterInputEl = $(filterSel).find('input');
      $(filterInputEl).bind('keyup', _.bind(function(event){ 

         var data = { bhviewIndex:this.bhviewIndex,
                      data:$(event.target).val(),
                      signal:'text_filter' };

         if(this.signalingType == 'send'){
            $(this.view.allViewsContainerSel).trigger(this.signalEvent, data);
         }
      }, this));
         ***************************/
   },
   openCellContextMenu: function(menuAnchorEl){

      //Get the row element user clicked on
      var selectedTrEl = $(menuAnchorEl).parent().parent().parent();

      if( $(selectedTrEl).is('tr') ){

         //Remove pre-existing menus
         this.view.removeFgmenuByClass(this.view.cellMenuTargetClass, menuAnchorEl);

         var menuAnchorToggleEl = $(this.cellAnchorClassSel).children()[0];

         var cellChildElements = $(menuAnchorEl).parent().children();
         var signal = $(cellChildElements[0]).attr('href').replace(/\#/, '');

         //Get the BHViews that listen for the signal
         var signalBHViews = BHPAGE.BHViewCollection.getBHViewsBySignal(signal);
         this.view.loadCellMenuOptions(signalBHViews);

         if(signal == 'url'){
            //Display url warning panel
            $(this.view.cellUrlMenuPanelClassSel).removeClass('hidden');
         } else {
            //Hide the url warning panel
            $(this.view.cellUrlMenuPanelClassSel).addClass('hidden');
         }

         //Clone the cell menu
         var cellMenuClone = this.view.cloneCellMenu();

         $(menuAnchorEl).menu({ 
            content: $(cellMenuClone).html(),
            showSpeed: 150,
            classTarget:this.view.cellMenuTargetClass,
            width: this.view.cellContextPanelWidth,

            clickHandler:_.bind(function(event){

               if($(event.target).hasClass(this.view.cellOpenBHViewBtClass)){

                  var cellChildElements = $(menuAnchorEl).parent().children();
                  var cellText = $(cellChildElements[0]).text();
                  var bhview = this.view.getCellMenuBHViewSelection(event.target);
                  var data = { selectedView:bhview,
                               displayType:'page',
                               params:signal + '=' + cellText };

                  $(this.view.allViewsContainerSel).trigger(this.addBHViewEvent, data);

               }else if($(event.target).hasClass(this.view.cellOpenPageBtClass)){

                  //Open the url in a new window
                  var cellChildElements = $(menuAnchorEl).parent().children();
                  var href = $(cellChildElements[0]).text();
                  this.view.closeMenu();
                  window.open(href);
               }

            }, this) //end bind
         });

         //Access menu created through allUIMenus in fg.menu
         //to display.  THis is an fg.menu hack.  fg.menu
         //needs to be adapted to directly manage multiple 
         //menus in a better way.
         allUIMenus[ allUIMenus.length - 1 ].showMenu();
      }
   },
   /**************
    *BUTTON CLICK HANDLERS
    **************/
   closeTable: function(){
      this.view.closeMenu();
      //disable button if we are the main view
      if(this.bhviewIndex != 0){
         $(this.view.allViewsContainerSel).trigger( this.closeEvent, { bhviewIndex:this.bhviewIndex } ); 
      }
   },
   openWindow: function(){
      this.view.closeMenu();
      BHPAGE.ConnectionsComponent.setBHViewIndex(this.bhviewIndex);
      BHPAGE.ConnectionsComponent.open('open', this.signalingType);
   },
   refresh: function(){
      this.view.closeMenu();
      this.selectBHView();
   },
   help: function(){
      this.view.closeMenu();
      alert("I'm so confused.  Please help me by writing some help messaging. Thanks!");
   },
   getSignalHelp: function(){
      alert("Please tell me all about sending and receiving signals, i'm a bit confused. Thanks!");
   },
   increaseSize: function(){

      this.view.closeMenu();
      var newHeight = this.view.changeViewHeight(this.bhviewIndex, 'increase');
      this.dataTable.fnSettings().oScroll.sY = newHeight + 'px';
   },
   decreaseSize: function(){

      this.view.closeMenu();
      var newHeight = this.view.changeViewHeight(this.bhviewIndex, 'decrease');
      this.dataTable.fnSettings().oScroll.sY = newHeight + 'px';
   },
   setVisualization: function( item ){
      this.view.closeMenu();
   },
    
   /*************
    *MENU CALLBACK METHODS
    *************/
    _setControlPanelCb: function(data){

      var controlPanelSel = this.view.getIdSelector(this.view.controlPanelSel, this.bhviewIndex);
      var controlPanelId = this.view.getId(this.view.controlPanelSel, this.bhviewIndex);

      //Remove existing menu from DOM
      this.view.removeControlPanel(this.bhviewIndex);

      //Set up ids
      var htmlEl = this.view.initializeControlPanel(data, this.bhviewIndex);

      $(controlPanelSel).menu({ 
         content: htmlEl.html(),
         showSpeed: 150,
         width: this.view.controlPanelWidth,

         onOpen: _.bind(function(event){
            //Populate the control panel fields with
            //any signal data
            var controlPanelDropdownSel = this.view.getIdSelector(this.view.controlPanelDropdownSel, 
                                                                  this.bhviewIndex);
            var adapterName = this.model.getBHViewAttribute('data_adapter');
            var a = this.dataAdapters.getAdapter(adapterName);
            a.setControlPanelFields(controlPanelDropdownSel, this.signalData);

         }, this),

         //This clickHandler prevents the form from closing when it's
         //clicked for data input.  
         clickHandler:_.bind(function(event){

            var controlPanelBtSel = this.view.getId(this.view.controlPanelBtSel, this.bhviewIndex);
            var controlPanelClearBtSel = this.view.getId(this.view.controlPanelClearBtSel, this.bhviewIndex);
            var controlPanelDropdownSel = this.view.getIdSelector(this.view.controlPanelDropdownSel, 
                                                                  this.bhviewIndex);

            var elId = $(event.target).attr('id');

            if( elId == controlPanelBtSel ){
               //close menu
               this.view.closeMenu();
               //fire event
               $(this.view.allViewsContainerSel).trigger( this.processControlPanelEvent, 
                                                         { bhviewIndex:this.bhviewIndex }); 
            }else if(elId == controlPanelClearBtSel){
               //Get data adapter to clear fields
               var adapterName = this.model.getBHViewAttribute('data_adapter');
               var a = this.dataAdapters.getAdapter(adapterName);
               a.clearPanel(controlPanelDropdownSel);
            }

            return false;

         }, this) //end bind
      });
   },
   _bindCellContextMenu: function(){
      $(this.view.cellMenuTogglerClassSel).bind('click', _.bind(function(event){
         event.stopPropagation();

         if(this.view != undefined){
            //See if the user has selected the cell context menu
            var menuAnchorEl;
            if($(event.target).attr('href') == this.view.cellMenuHref){
               menuAnchorEl = $(event.target);
            }else if($(event.target).parent().attr('href') == this.view.cellMenuHref){
               menuAnchorEl = $(event.target).parent();
            }
            if(menuAnchorEl != undefined){
               this.openCellContextMenu(menuAnchorEl);
            }
         }
      }, this));
   }
});
var BHViewView = new Class({

   /**************************
    * BHView manages all direct DOM manipulation
    * for the component.
    *************************/

   Extends:View,

   jQuery:'BHViewView',

   initialize: function(selctor, options){

      this.setOptions(options);

      this.parent(options);

      //HTML for navigation menu, control panel, and help
      this.navMenuHtmlUrl = '/nav/nav_menu.html';
      this.controlPanelHtmlUrl = '/control_panel/';
      this.helpHtmlUrl = '/help/';

      this.controlPanelWidth = 475;
      this.cellContextPanelWidth = 300;

      //Scrolling params
      this.minScrollPanelSize = 250;
      this.defaultScrollPanelSize = 500;
      this.tableScrollClassSel = '.dataTables_scrollBody';

      //Main View Container
      this.allViewsContainerSel = '#bh_view_container';

      //Cloned Containers
      this.viewWrapperSel = '#bh_view_wrapper_c';
      this.singleViewContainerSel = '#bh_view_c';

      //Spinners
      this.spinnerSel = '#bh_spinner_c';
      this.tableSpinnerSel = '#bh_table_spinner_c';
      this.tableNoDataSel = '#bh_table_nodata_c';

      //Data table
      this.tableSel = '#bh_tview_c';
      //Data table pagination container
      this.tablePaginationSel = '#bh_tview_c_BHVIEW_INDEX_paginate';

      //Top bar selectors
      this.topBarSel = '#bh_topbar_c';
      this.navMenuSel = '#bh_nav_menu_c';
      this.controlPanelSel = '#bh_control_panel_c';
      this.visualizationSel = '#bh_visualization_c';
      this.visMenuSel = '#bh_vis_menu_c';
      this.topBarTitleSel = '#bh_view_title_c';

      //Close button selector
      this.closeButtonSel = '#bh_closetable_bt_c';

      //Control panel ids
      this.controlPanelBtSel = '#bh_cp_load_view_c';
      this.controlPanelClearBtSel = '#bh_cp_clear_c';
      this.controlPanelDropdownSel = '#bh_cp_dropdown_c';

      //Cell context menu class selectors
      this.cellAnchorClassSel = '.bh-cell-contextanchor';
      this.cellMenuClassSel = '.bh-cell-contextmenu';
      this.cellMenuHref = '#cellmenu';
      this.cellOpenBHViewBtClass = 'bh-open-bhpage-link';
      this.cellOpenPageBtClass = 'bh-open-page-link';
      this.cellBHViewOptionsClassSel = '.bh-signal-views';
      this.cellUrlMenuPanelClassSel = '.bh-url-cell-menu-panel';
      this.cellMenuTogglerClassSel = '.bh-cell-menu-toggle';
      this.cellMenuTargetClass = 'bh-menu-target';

      //Signal display ids
      this.signalDirectionDisplaySel = '#bh_signal_direction_c';
      this.signalDataDisplaySel = '#bh_signal_data_c';
      this.signalDateRangeDisplaySel = '#bh_signal_date_range_c';
      this.signalHelpBtSel = '#bh_signal_help_bt_c';
      this.maxSignalDataLength = 60;

      //Clone id selector, finds all elements with an id attribute ending in _c
      this.cloneIdSelector = '*[id$="_c"]';

      //The current selected row element in a table
      this.selectedTrEl;

      //Signal base id
      this.signalBaseSel = '#bh_post_';

   },
   getTablePaginationSel: function(bhviewIndex){
      return this.tablePaginationSel.replace('BHVIEW_INDEX', bhviewIndex);
   },
   loadCellMenuOptions: function(signalBHViews){

      //Remove any options from the select menu
      var childOptions = $(this.cellBHViewOptionsClassSel).children();
      for(var i=0; i<childOptions.length; i++){
         $(childOptions[i]).remove();
      }

      //Populate the select menu embedded in the
      //cell context menu with the array of bhviews
      //provided
      for(var i=0; i<signalBHViews.length; i++){
         var optionEl = $('<option></option>');
         $(optionEl).attr('value', signalBHViews[i].name);
         $(optionEl).text(signalBHViews[i].read_name);
         if( i == 0 ){
            $(optionEl).attr('selected', 1);
         }
         $(optionEl).css('display', 'block');
         $(this.cellBHViewOptionsClassSel).append(optionEl);
      }
   },
   /****************************
    *BHVIEW PREPARATION METHODS
    ****************************/
   cloneBHView: function(bhviewIndex){
      
      //Clone single view container and append to the main container
      var viewWrapperEl = $(this.viewWrapperSel).clone();

      //Set up new bhviewIndex based id
      var viewWrapperId = this.getId(this.viewWrapperSel, bhviewIndex);
      $(viewWrapperEl).attr('id', viewWrapperId);

      $(this.allViewsContainerSel).append(viewWrapperEl);

      //Set the ids on the new clone
      this.setCloneIds(viewWrapperEl, bhviewIndex);

   },
   setCloneIds: function(containerEl, bhviewIndex){

      //find all elements with an id attribute ending in _c
      var cloneIdElements = $(containerEl).find(this.cloneIdSelector);

      for(var i=0; i<cloneIdElements.length; i++){
         var id = $(cloneIdElements[i]).attr('id'); 
         //Append the index to the id to make id unique
         $(cloneIdElements[i]).attr('id', this.getId(id, bhviewIndex));
      }

      //Check the element itself
      var containerId = $(containerEl).attr('id');
      if(!(containerId === undefined)){
         if(containerId.search(/_c$/) > -1){
            $(containerEl).attr('id', this.getId(containerId, bhviewIndex));
         }
      }

      return containerEl;
   },
   getNewTableClone: function(bhviewIndex, tableSel){
      //hide the table
      $(tableSel).fadeOut();
      //remove from DOM 
      $(tableSel).remove();
      //get a new clone
      var tableEl = $(this.tableSel).clone();
      //reset id
      $(tableEl).attr('id', this.getId(this.tableSel, bhviewIndex));
      //Get the topbar div to append to
      var topBarSel = this.getIdSelector(this.topBarSel, bhviewIndex);
      //load the new clone
      $(topBarSel).append( tableEl );
   },
   initializeControlPanel: function(html, bhviewIndex){
      var cpSel = this.getIdSelector(this.controlPanelDropdownSel, bhviewIndex);
      var el = this.setCloneIds($(html), bhviewIndex);
      return el;
   },
   setBHViewChartTypes: function(charts, bhVisMenuSel){
      /***************
       * Takes an array of chart objects and adds them to
       * the visualization ul in the top bar of the bhview.
       *
       * Parameters:
       *    charts - chart object
       *    bhVisMenSel - The ul id selector
       ***************/
      var menuChildren = $(bhVisMenuSel).children();
      var liCloneEl = "";

      for(var i=0; i<menuChildren.length; i++){
         var liEl = menuChildren[i]; 
         if($(liEl).css('display')){
            //This is the clone target
            liCloneEl = liEl;
         }else{
            //Pre-existing li from another view type, delete it
            $(liEl).remove();
         }
      }

      if( _.isElement( liCloneEl ) ){

         for(var i=0; i < charts.length; i++){

            var c = charts[i];

            //clone the li
            var newLiEl = $(liCloneEl).clone();

            //get anchor and set attributes and show the new li
            var anchor = $(newLiEl).find('a');
            $(anchor).attr('href', '#' + c.name);
            $(anchor).text(c.name.capitalize());
            $(bhVisMenuSel).append(newLiEl);
            newLiEl.css('display', 'block');
         }

      }else{
         console.log("html error: the element:" + bhVisMenuSel + " needs a <li></li> to clone!");
      }
   },
   removeControlPanel: function(bhviewIndex){

      /*******************
       * Beware Holy Hackery Ahead!
       *
       * fg.menu maintains a global array with menu
       * objects containing each menu that it has positioned.
       * In order to completely remove a positioned menu the 
       * following steps need to be carried out:
       *    
       *    1.) Unbind all events from the control panel anchor
       *    2.) Remove the menu object from allUIMenus
       *    3.) Remove the menu and its parent positioning div
       *        from the DOM.
       *    4.) If the user has not opened the control panel
       *        and switches views the previous dropdown menu
       *        will not have the positioning div but will still
       *        need to be removed. Remove it from the DOM using 
       *        its element id.
       *
       * NOTE: Clearly we are using fg.menu in a way that it 
       *       was not intended to be used.  A better approach
       *       would be a clean destructor implementation for menu 
       *       objects that live entirely in fg.menu but this will 
       *       require some significant changes to fg.menu.
       ********************/
      var controlPanelSel = this.getIdSelector(this.controlPanelSel, 
                                               bhviewIndex);
      $(controlPanelSel).unbind();

      //Remove menu from global array of menus
      var controlPanelDropdownId = this.getId(this.controlPanelDropdownSel, 
                                              bhviewIndex);
      for(var i=0; i<allUIMenus.length; i++){
         if(allUIMenus[i].menuExists){
            if(allUIMenus[i].elementId == controlPanelDropdownId){
               //close the menu
               allUIMenus[i].kill();
               //remove it from allUIMenus
               allUIMenus = _.without( allUIMenus, allUIMenus[i] );
            }
         }
      }

      //Remove click event listeners
      $(controlPanelDropdownId).unbind('click');

      /**********************
       * fg.menu wraps a div with the class positionHelper around
       * the menu to help with absolute positioning.  If we just remove
       * the dropdown menu without removing the positionHelper all
       * hell breaks loose because the positionHelper divs accumulate.  
       * This bit of hackery removes the container around the dropdown.
       * Ugh... I feel dirty.
       **********************/
      var sel = '[id="' + controlPanelDropdownId + '"]';
      var pD = $('.positionHelper').find(sel);
      var positionHelper = pD.parent().parent();
      $(positionHelper).remove();

   },
   /************************
    * CELL CONTEXT MENU METHODS
    * **********************/
   getCellMenuBHViewSelection: function(el){
      return $( el ).parent().find('select').attr('value');
   },
   removeFgmenuByClass: function(className, menuAnchorEl){

      /***********
       * Removes an fg.menu using the same recipe described in removeControlPanel
       * but takes a clasname and the toggler anchor element as
       * arguments.
       * *********/
      for(var i=0; i<allUIMenus.length; i++){
         if(allUIMenus[i].menuExists){
            if(allUIMenus[i].classTarget == className){

               //close the menu
               allUIMenus[i].kill();
               allUIMenus[i].menuExists = false;
               //remove it from allUIMenus
               allUIMenus = _.without( allUIMenus, allUIMenus[i] );
            }
         }
      }
      $(menuAnchorEl).unbind('click');
      var classSel = '.' + className;
      $(classSel).unbind('click');
      var pD = $('.positionHelper').find(classSel);
      var positionHelper = pD.parent().parent();
      $(positionHelper).remove();
   },
   cloneCellMenu: function(){
      var cellMenuClone = $(this.cellMenuClassSel).clone();
      $(cellMenuClone.children()[0]).addClass(this.cellMenuTargetClass);
      return cellMenuClone;
   },
   /************************
    *BHVIEW MODIFICATION METHODS
    ************************/
   disableClose: function(bhviewIndex){
      var closeButtonSel = this.getIdSelector(this.closeButtonSel, bhviewIndex);
      $(closeButtonSel).addClass("ui-state-disabled");
   },
   selectTableRow: function( selectedTrEl ){

      //Remove class on existing selection
      if(this.selectedTrEl){
         $(this.selectedTrEl).removeClass('row_selected');
      }

      //Get the row
      this.selectedTrEl = selectedTrEl;

      var trClass = $(this.selectedTrEl).attr('class');

      //Give it the selected class
      $(this.selectedTrEl).addClass('row_selected');

   },
   removeBHView: function(bhviewIndex){
      var wrapperSel = this.getIdSelector(this.viewWrapperSel, bhviewIndex);
      $(wrapperSel).remove(); 
   },
   changeViewHeight: function(bhviewIndex, direction){

      var scrollContainerEl = this.getTableScrollContainer(bhviewIndex);
      var h = parseInt( $(scrollContainerEl).css('height') );

      if(direction == 'decrease'){

         h = h - this.minScrollPanelSize;
         //Set the minimum
         if(h < this.minScrollPanelSize){
            h = this.minScrollPanelSize;
         }

      }else {
         h = h + this.minScrollPanelSize;
      }

      var hPix = h + 'px';
      $(scrollContainerEl).css('height', hPix);

      return hPix;
   },
   /*******************
    * GET METHODS
    *******************/
   getFilterSel: function(bhviewIndex){
      return '#bh_tview_c_' + bhviewIndex + '_filter';
   },
   getTableScrollContainer: function(bhviewIndex){
      var tableSel = this.getIdSelector(this.tableSel, bhviewIndex);
      return $(tableSel).parent(); 
   },
   /*******************
    *TOGGLE METHODS
    *******************/
   displaySignalData: function(direction, signalData, bhviewIndex){

      var signalDirectionDisplaySel = this.getIdSelector(this.signalDirectionDisplaySel, bhviewIndex);
      var signalDataDisplaySel = this.getIdSelector(this.signalDataDisplaySel, bhviewIndex);
      var signalDateRangeDisplaySel = this.getIdSelector(this.signalDateRangeDisplaySel, bhviewIndex);

      //Show direction of signal
      if(direction == 'receive'){
         $(signalDirectionDisplaySel).text(' Received');
      }else if(direction == 'send'){
         $(signalDirectionDisplaySel).text(' Sent');
      }
      //Show data range sent if we have one
      if(signalData.date_range){
         var dateRange = 'date range:' + signalData.date_range.start_date + ' to ' + signalData.date_range.end_date;
         $(signalDateRangeDisplaySel).text(dateRange); 
      }
      //Show signal type and associated data
      if(signalData.data && signalData.signal){
         var data = BHPAGE.escapeHtmlEntities(decodeURIComponent(signalData.data));
         var displayData = data;
         if(data.length >= this.maxSignalDataLength){
            displayData = data.substring(0, this.maxSignalDataLength - 3) + '...';
         }
         var signalDisplayData = signalData.signal + ':' + displayData;
         $(signalDataDisplaySel).text(signalDisplayData);
         $(signalDataDisplaySel).attr('title', data);
      }
   },
   showNoDataMessage: function(bhviewIndex){

      //Hide main pane spinner
      this.hideSpinner(bhviewIndex);

      //Hide the table
      var tableSel = this.getIdSelector(this.tableSel, bhviewIndex);
      $(tableSel).addClass('hidden');

      //Hide the spinner
      var spinnerSel = this.getIdSelector(this.tableSpinnerSel, bhviewIndex);
      $(spinnerSel).css('display', 'none');
      
      //Show the single bhview container
      var singleViewSel = this.getIdSelector(this.singleViewContainerSel, bhviewIndex);
      $(singleViewSel).removeClass('hidden');

      //Show top bar container
      var topBarSel = this.getIdSelector(this.topBarSel, bhviewIndex);
      $(topBarSel).removeClass('hidden');

      //Show message
      var noDataSel = this.getIdSelector(this.tableNoDataSel, 
                                         bhviewIndex);
      $(noDataSel).css('display', 'block');

   },
   closeMenu: function(){
      /*************
       *This method calls a the kill() method of
       *an fg.menu object to close the menu explicitly.
       *************/
      for(var i=0; i<allUIMenus.length; i++){
         if(allUIMenus[i].menuExists){
            allUIMenus[i].kill();
         }
      }
   },
   showBHView: function(bhviewIndex, bhviewReadName){

      //Show the topbar and table, they still won't be visible
      //at this point because their container div is hidden but
      //they will be ready for the fadeIn()
      var topBarSel = this.getIdSelector(this.topBarSel, bhviewIndex);
      $(topBarSel).removeClass('hidden');
      var tableSel = this.getIdSelector(this.tableSel, bhviewIndex);
      $(tableSel).removeClass('hidden');

      var topbarTitleSel = this.getIdSelector(this.topBarTitleSel, bhviewIndex);
      $(topbarTitleSel).text(bhviewReadName);

      if(bhviewIndex == 0){
         //Disable the close button so the user cannot
         //have a viewless page
         this.disableClose(bhviewIndex);
      }

      //Hide the spinner
      this.hideSpinner(bhviewIndex);
      this.hideTableSpinner(bhviewIndex);

      //Hide the no data message
      var noDataSel = this.getIdSelector(this.tableNoDataSel, 
                                         bhviewIndex);
      $(noDataSel).css('display', 'none');

      //If the spinner has been shown the viewWrapper is likely visible
      //but lets make sure in case caller did not call showSpinner()
      var viewWrapperSel = this.getIdSelector(this.viewWrapperSel, bhviewIndex);
      $(viewWrapperSel).css('display', 'block');

      //Show the container
      var singleViewContainerSel = this.getIdSelector(this.singleViewContainerSel, bhviewIndex);
      $(singleViewContainerSel).fadeIn();

   },
   showSpinner: function(bhviewIndex){
      //Make sure the wrapper is visible
      var viewWrapperSel = this.getIdSelector(this.viewWrapperSel, bhviewIndex);
      $(viewWrapperSel).removeClass('hidden');

      //Show spinner
      var spinnerSel = this.getIdSelector(this.spinnerSel, bhviewIndex);
      $(spinnerSel).css('display', 'block');
   },
   showTableSpinner: function(bhviewIndex){

      var noDataSel = this.getIdSelector(this.tableNoDataSel, 
                                         bhviewIndex);
      $(noDataSel).css('display', 'none');

      var tableSel = this.getIdSelector(this.tableSel, bhviewIndex) + '_wrapper';
      $(tableSel).css('display', 'none');

      //Show spinner
      var spinnerSel = this.getIdSelector(this.tableSpinnerSel, bhviewIndex);
      $(spinnerSel).css('display', 'block');
   },
   hideSpinner: function(bhviewIndex){
      //Needs to be display:none; so the view container doesn't get
      //pushed down.
      var spinnerSel = this.getIdSelector(this.spinnerSel, bhviewIndex);
      $(spinnerSel).css('display', 'none');
   },
   hideTableSpinner: function(bhviewIndex){
      var spinnerSel = this.getIdSelector(this.tableSpinnerSel, bhviewIndex);
      $(spinnerSel).css('display', 'none');

      var tableSel = this.getIdSelector(this.tableSel, bhviewIndex) + '_wrapper';
      $(tableSel).css('display', 'block');
   }
});
var BHViewModel = new Class({

   /****************************
    * BHViewModel manages data structures and server 
    * side data retrieval.
    ****************************/
   Extends:View,

   jQuery:'BHViewModel',

   initialize: function(selector, options){

      this.setOptions(options);

      this.parent(options);

      //enable ajax POST with CDRF Token
      this.modelAjaxSend();

      this.dataAdapters = options.dataAdapters;

      //Options for this view from views.json
      this.bhviewHash = {};
      this.setBHViewHash(this.options.bhviewName);
      this.apiLocation = "/bughunter/api/views/";
   },
   /***************
    *GET METHODS
    ***************/
   getBHViewAttribute: function(attr){
      return this.bhviewHash[attr];
   },
   getBHViewData: function(bhviewName, context, fnSuccess, params){

      var url = this.apiLocation + bhviewName;

      //Check for default data
      var serviceUrl = this.getBHViewAttribute('service_url');
      var data;
      if(serviceUrl != undefined){
         url = serviceUrl;
      }else{
         if(params != undefined){
            data = params;
         }else if(_.isString(this.bhviewHash['default_params'])){
            data = this.bhviewHash['default_params'];
         }
      }

      jQuery.ajax( url, { accepts:'application/json',
                          dataType:'json',
                          cache:false,
                          processData:false,
                          type:'POST',
                          data:data,
                          context:context,
                          success:fnSuccess,
                          dataFilter:_.bind(this.datatableAdapter, this) });

   },
   getBHViewPageTarget: function(bhviewName){
      if (BHPAGE.navLookup[bhviewName]){
         return BHPAGE.navLookup[bhviewName]['page_target'];
      }
   },
   /*****************
    *SET METHODS
    *****************/
   setBHViewHash: function(bhviewName){
      if (BHPAGE.navLookup[bhviewName]){
         this.bhviewHash = BHPAGE.navLookup[bhviewName];
      }else{
         console.log('view.json error: The view name, ' + bhviewName + ' was not found!');
      }
   },
   datatableAdapter: function(data, type){
      /*************
       * Adapt webservice data to datatable structure
       *************/

      //When JSON.parse() is used here jQuery fails to pass the
      //data returned to the success function ref.  This is why
      //jQuery.parseJSON is being used instead.  Not sure why this
      //occurs.
      var dataObject = jQuery.parseJSON( data );

      //NOTE: datatableObject cannot be an attribute of the
      //      model instance because it is unique to different 
      //      views.
      var datatableObject = { bJQueryUI: true,
                              sPaginationType: "full_numbers",
                              bPaginate: true,
                              sScrollY:"500px",
                              bScrollCollapse:true,
                              sScrollX:"100%",

                              //Double, Double Toil and Trouble
                              //see http://www.datatables.net/usage/options sDom for an
                              //explanation of the follow line
                              sDom:'<"H"lfr>tC<"F"ip>',

                              bScrollAutoCss: false,
                              bRetrieve:true,
                              //Treat search string as regexes
                              oSearch:{ sSearch:"", bRegex:true },
                              xScrollInner:true,
                              iDisplayLength:100,
                              aLengthMenu:[[25, 50, 100, 500, 1000], [25, 50, 100, 500, 1000]],
                              aaData:dataObject.data,
                              aoColumns:[],
                              
                              oColVis:{
                                 buttonText: "&nbsp;",
                                 bRestore: true,
                                 sAlign: "left",
                                 sSize: "css"
                              }
                           };

      var signals = this.getBHViewAttribute('signals');
      //Get a data adapter to process the data.  This allows
      //individual bhviews to process the data according to 
      //their requirements
      var adapterName = this.getBHViewAttribute('data_adapter');
      var a = this.dataAdapters.getAdapter(adapterName);
      a.processData(dataObject, datatableObject, signals);

      //return datatableObject;
      return JSON.stringify(datatableObject);
   },
   modelAjaxSend: function(){
      /*********************
       * This method configures an ajaxSend call in jquery.  It was taken from
       * https://docs.djangoproject.com/en/1.3/ref/contrib/csrf/
       * This sets a custom X-CSRFToken header to the value of the CSRF token.
       * It's called before every request.
       * *******************/
      jQuery.ajaxSetup({
         beforeSend: function(xhr, settings) {
            function getCookie(name) {
               var cookieValue = null;
               if (document.cookie && document.cookie != '') {
                  var cookies = document.cookie.split(';');
                  for (var i = 0; i < cookies.length; i++) {
                     var cookie = jQuery.trim(cookies[i]);
                     // Does this cookie string begin with the name we want?
                     if (cookie.substring(0, name.length + 1) == (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                     }
                  }
               }
               return cookieValue;
            }
            if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
               // Only send the token to relative URLs i.e. locally.
               xhr.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
            }
         } 
      });
   }
});
