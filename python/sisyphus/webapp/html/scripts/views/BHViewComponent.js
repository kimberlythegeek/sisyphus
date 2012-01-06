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
      bhview_name:'',
      bhview_index:0
   },

   initialize: function(selector, options){

      this.setOptions(options);
      
      this.parent(options);

      //This index is dynamically appended
      //to every id in a view clone.
      this.bhviewIndex = this.options.bhview_index;
      this.bhviewParentIndex = this.options.bhview_parent_index;
      this.parentWindowName = window.document.title;

      //Callback methods for button clicks
      this.buttonHandlers = { closetable:this.closeTable,
                              openwindow:this.openWindow,
                              refresh:this.refresh,
                              help:this.help,
                              signal_help:this.getDataHelp,
                              newwindow:this.moveToNewWindow,
                              increasesize:this.increaseSize,
                              decreasesize:this.decreaseSize };

      //Adapters to manage idiosynchratic view behavior
      this.dataAdapters = new DataAdapterCollection();

      this.model = new BHViewModel('#BHViewModel', {bhviewName:this.options.bhview_name,
                                                    dataAdapters:this.dataAdapters});

      this.visCollection = new VisualizationCollection('#VisualizationCollection', {});
      this.visName = 'table';

      this.view = new BHViewView('#BHViewView', { vis_read_name:'Table'});

      //The parent view index, it will be defined when this window
      //was spawned from another.
      if(( (window.opener != undefined) && (window.opener.document != undefined) ) && 
         (this.bhviewIndex == 0)){
         //get the parent bhview index embedded in the page
         this.bhviewParentIndex = this.view.getParentBHViewIndex();
         this.parentWindowName = window.opener.document.title;
      }

      //BHView events
      this.closeEvent = 'CLOSE_BHVIEW';
      this.addBHViewEvent = 'ADD_BHVIEW';
      this.processControlPanelEvent = 'PROCESS_CONTROL_PANEL';
      this.signalEvent = 'SIGNAL_BHVIEW';
      this.openCollectionEvent = 'OPEN_COLLECTION_BHVIEW';

      //Set up subscriptions
      this.subscriptionTargets = {};
      this.subscriptionTargets[this.processControlPanelEvent] = this.processControlPanel;
      this.subscriptionTargets[this.signalEvent] = this.signalHandler;

      //Boolean indicating if the server had to reset the
      //date range supplied by the user
      this.serverDateRangeUpdate = true;

      //Register subscribers
      BHPAGE.registerSubscribers(this.subscriptionTargets,
                                 this.view.allViewsContainerSel,
                                 this);

      //datatable.js object is stored in this attribute
      this.dataTable;

      //Look for signals embedded in the page to
      //initialize the control panel with
      this.signalData = this.getSignalDataFromPage();

      if(this.bhviewIndex == 0){

         //Disable the close button so the user cannot
         //have a viewless page
         this.view.disableClose(this.bhviewIndex);
         //Set up the update of the date range in the page every 60 minutes
         //and only run it if we are the first bhview.  The first bhview
         //cannot be deleted.
         this.updateDateRangeInterval = setInterval( _.bind(this.updateDateRange, this), 3600000 );

      }

      //We could be a child in a new window, register listener
      //for cross window communication
      this.notifyBHViewCollection();

      //Get a new HTML clone for the 
      //view and initialize it.
      this.getBHViewClone();

      //Display parent/child relationship
      this.view.displayParentChild(this.bhviewParentIndex, 
                                   this.bhviewIndex, 
                                   this.parentWindowName);

      var defaultLoad = this.model.getBHViewAttribute('default_load')
      if( (defaultLoad == 1) || 
          ((this.bhviewIndex == 0) && (this.signalData.signal != undefined)) ){
         //Select view and load the data
         this.view.displaySignalData('receive', this.signalData, this.bhviewIndex);
         this.selectBHView();
      }else{
         var bhviewReadName = this.model.getBHViewAttribute('read_name');

         this.view.displayBHViewName(this.bhviewIndex, bhviewReadName);
         this.setControlPanelEv();

         this.view.showNoDataMessage(this.bhviewIndex, 'sendsignal');
      }

   },
   notifyBHViewCollection: function(){

      if( (window.opener != undefined) && (window.opener.document != undefined) ){
         //If we have an opener we're a child on a new page
         window.opener.BHPAGE.BHViewCollection.loadNewChildWindow(window);
         //Register listener for signals from parent
         window.addEventListener('message', _.bind(this.processWindowSignal, this));
      }

   },
   processWindowSignal: function(event){

      var data = this.validateMessageData(event);
      if( (window.opener != undefined) && (window.opener.document != undefined) ){
         if(!_.isEmpty(data)){
            //Make sure the window/view sender are the appropriate parents
            if((data.window_sender == window.opener.document.title) && 
               (this.bhviewParentIndex == data.parent_bhview_index)){

               //Let listener know this is a window message
               data['window_message'] = true;
               $(this.view.allViewsContainerSel).trigger(this.signalEvent, data);

            }
         }
      }
   },
   validateMessageData: function(event){

      var safeData = {};
      var dataObject = JSON.parse(event.data);
      var targetOrigin = BHPAGE.getTargetOrigin();

      //Validate the origin is correct
      if(targetOrigin === event.origin){

         //Validate that we have the required fields, any window
         //could send a message
         if( (dataObject.data != undefined) &&
             (dataObject.window_sender != undefined) &&
             (dataObject.date_range != undefined) &&
             (dataObject.signal != undefined) ){

            //Yer all clear kid!
            safeData = dataObject;
         }
      }

      return safeData;
   },
   updateDateRange: function(){

      //Make ajax call to retrieve date range, update the values in the page
      if( this.model != undefined ){
         jQuery.ajax( this.model.dateRangeLocation, { accepts:'application/json',
                                                      dataType:'json',
                                                      cache:false,
                                                      type:'GET',
                                                      context:this.view,
                                                      success:this.view.updateDateRange });
      }
   },
   /****************
    *PUBLIC INTERFACE
    ****************/
   destroy: function(){

      //Delete the view from the DOM
      this.view.removeBHView(this.bhviewIndex);

      //Unbind local events
      var paginationSel = this.view.getTablePaginationSel(this.bhviewIndex);
      $(paginationSel).unbind();

      //Get rid of any events assigned with live
      if(this.dataTable != undefined){
         this.dataTable.die();
         //Call table destructor
         this.dataTable.fnDestroy();
      }

      //Unbind custom events
      BHPAGE.unbindSubscribers(this.subscriptionTargets,
                               this.view.allViewsContainerSel);

      //This should be done programmatically but not sure
      //if delete will work without explicit attribute reference.
      //Need to do some research...
      delete(this.subscriptionTargets);
      delete(this.bhviewIndex);
      delete(this.buttonHandlers);
      delete(this.model);
      delete(this.view);
      delete(this.visCollection);
      delete(this.dataAdapters);
      delete(this.closeEvent);
      delete(this.addBHViewEvent);
      delete(this.processControlPanelEvent);
      delete(this.signalEvent);
      delete(this.subscriptionTargets);
      delete(this.signalData);
      delete(this.dataTable);
   },
   selectBHView: function(item){

      var bhviewName = "";

      if(item != undefined){
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

      //Check if we have a collection
      var collection = this.model.getBHViewAttribute('collection')

      if( collection != undefined ){
         var data = { parent_bhview_index:this.bhviewIndex,
                      collection:collection,
                      display_type:BHPAGE.ConnectionsComponent.getDisplayType() };

         //Set the name to the 0 collection element
         bhviewName = collection[0].bhview;

         //Set data for the new collection view
         this.model.setBHViewHash(bhviewName);

         //Fire event to load the rest of the collection
         $(this.view.allViewsContainerSel).trigger(this.openCollectionEvent, data);

         return false;

      }

      var bhviewReadName = this.model.getBHViewAttribute('read_name');

      //Display new view's name
      this.view.displayBHViewName(this.bhviewIndex, bhviewReadName);

      this.view.showTableSpinner(this.bhviewIndex);

      //Set up control panel, this must be done
      //in the selectBHView method to account for
      //unique control panel/bhview relationships
      this.setControlPanelEv();

      //Display signal data
      this.view.displaySignalData('', this.signalData, this.bhviewIndex);

      var adapterName = this.model.getBHViewAttribute('data_adapter');
      var a = this.dataAdapters.getAdapter(adapterName);
      var params = "";
      if(this.signalData.signal != undefined){
         params += 'start_date=' + this.signalData.date_range.start_date + 
                   '&end_date=' + this.signalData.date_range.end_date + '&' +
                   this.signalData.signal + '=' + this.signalData.data;
      }else{
         params = a.getDefaultParams();
      }
      this.model.getBHViewData(bhviewName, 
                               this, 
                               this.initializeBHView, 
                               params,
                               this._fnError);
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

      var bhviewIndex = parseInt(data.bhview_index);

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

         //Display the signal data
         this.updateSignalDateRange();
         //this.signalData['date_range'] = dateRange;
         this.view.displaySignalData('', this.signalData, this.bhviewIndex);

         this.view.showTableSpinner(this.bhviewIndex);

         this.model.getBHViewData(this.model.getBHViewAttribute('name'),
                                  this, 
                                  this.initializeBHView,
                                  params,
                                  this._fnError);
      }
   },
   signalHandler: function(data){

      var processSignal = false;

      if(data.window_message === true){

         //message was sent from another window and has already been validated for receiving
         processSignal = true;

      }else if( (data.parent_bhview_index != this.bhviewIndex) && 
                (this.bhviewParentIndex == data.parent_bhview_index) ){

         //signal was sent from inside page, make sure it was not this view that sent it
         //and that the signal was sent from this view's parent
         processSignal = true;

      }

      if(this.model === undefined){
         //NOTE: this.model should never be undefined.  This is a hack to 
         //      handle when a bhview has been deleted by the user.  When
         //      a view is deleted the destroy method should remove all event 
         //      listeners.  However, the destroy method fails to remove signal
         //      listeners. Yucky... 
         processSignal = false;
      }

      if(processSignal){

         var signals = this.model.getBHViewAttribute('signals');

         if(data.window_message != true){
            //Get parent view index
            var parentIndex = BHPAGE.BHViewCollection.getBHViewParent(this.bhviewIndex);
            if( parentIndex != data.parent_bhview_index ){
               //signal sender is not the parent, ignore
               return;
            }
         }

         //Make sure the bhview can handle the signal
         if(signals[ data.signal ] != 1){
            return;
         }

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

      this.data = data;

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

         //Set the chart types
         this.setVisEv();

         //Load the table data
         this.dataTable = $(tableSel).dataTable( data );

         //Set up signal handling
         this.setDataTableSignals();

         //Update signal data to whatever the server set it to
         if((this.model.start_date != this.signalData.date_range.start_date) ||
            (this.model.end_date != this.signalData.date_range.end_date) ){

            this.serverDateRangeUpdate = true;

            this.signalData.date_range = { start_date:this.model.start_date, 
                                           end_date:this.model.end_date };
            this.view.displaySignalData('', this.signalData, this.bhviewIndex);
         }else{
            this.serverDateRangeUpdate = false;
         }

         this.tableCreated = true;

         var bhviewReadName = this.model.getBHViewAttribute('read_name');

         //Let everyone see the lovely view!
         this.view.showBHView(this.bhviewIndex, bhviewReadName);

         //The table is loaded and drawn first when it is hidden
         //this causes the column/row alignment to get off.  Redraw
         //the table after its display is set to visible to reset
         //alignment.
         this.dataTable.fnDraw();
         this.dataTable.fnAdjustColumnSizing();

         this.view.setHeight(tableSel, this.view.minScrollPanelSize);

         this.setVisualization();

      }else{
         this.view.showNoDataMessage(this.bhviewIndex);
      } 
   },
   getSignalDataFromPage: function(){

      var signals = this.model.getBHViewAttribute('signals');

      var adapterName = this.model.getBHViewAttribute('data_adapter');
      var a = this.dataAdapters.getAdapter(adapterName);
      var dateRange = a.getDateRangeParams('', this.signalData);

      var signalData = {date_range:dateRange};
      if(signals != undefined){

         for(var signal in signals){
            var signalDataSel = this.view.signalBaseSel + signal;
            var data = $( signalDataSel ).val();
            if(data != undefined){

               signalData['signal'] = signal;
               signalData['data'] = decodeURIComponent(data);

               //Remove signal to prevent all new bhviews from using
               //it as a default
               $( signalDataSel ).remove();
               return signalData;
            }
         }
      }
      return signalData;
   },
   updateSignalDateRange: function(){

      var controlPanelDropdownSel = this.view.getIdSelector(this.view.controlPanelDropdownSel, 
                                                            this.bhviewIndex);
      var adapterName = this.model.getBHViewAttribute('data_adapter');
      var a = this.dataAdapters.getAdapter(adapterName);
      var dateRange = a.getDateRangeParams(controlPanelDropdownSel, this.signalData);
      this.signalData['date_range'] = dateRange;

   },
   setDataTableSignals: function(){

      //if the table is scrolled make sure we close any open menus
      $(this.view.tableScrollClassSel).bind('scroll', _.bind(function(e){
         if(this.view != undefined){
            this.view.closeMenu();
         }
      }, this));

      //Catch click events on the datatable
      $(this.dataTable).live("click", _.bind( this._dataTableClickHandler, this));

   },
   _dataTableClickHandler: function(event){

      //close any open menus
      this.view.closeMenu();

      event.stopPropagation();

      //If user selected an anchor in the main cell content
      //selectedTrEl will be a tr element
      //var selectedTrEl = $(event.target).parent().parent().parent();
      var selectedTrEl = $(event.target).closest('tr');

      //Make sure a table row was retrieved
      if( $(selectedTrEl).is('tr') ){

         this.view.selectTableRow( selectedTrEl );

         var href = $(event.target).attr('href');
         if(href != undefined){

            href = href.replace(/\#/, '');

            var adapterName = this.model.getBHViewAttribute('data_adapter');
            var a = this.dataAdapters.getAdapter(adapterName);
            var targetData = BHPAGE.escapeForUrl($(event.target).text(), href);


            var controlPanelDropdownSel = this.view.getIdSelector(this.view.controlPanelDropdownSel, 
                                                                  this.bhviewIndex);
            var dateRange = a.getDateRangeParams(controlPanelDropdownSel, this.signalData);

            var signalData = { parent_bhview_index:this.bhviewIndex,
                               data:targetData,
                               date_range:dateRange,
                               signal:href };

            //Display the signalData
            this.view.displaySignalData('send', signalData, this.bhviewIndex);

            $(this.view.allViewsContainerSel).trigger(this.signalEvent, signalData);
         }
      }
   },
   /**************
    *BUTTON CLICK HANDLERS
    **************/
   closeTable: function(){
      this.view.closeMenu();
      //disable button if we are the main view
      if(this.bhviewIndex != 0){
         $(this.view.allViewsContainerSel).trigger( this.closeEvent, { bhview_index:this.bhviewIndex } ); 
      }
   },
   moveToNewWindow: function(){

      this.view.closeMenu();
      if(this.bhviewIndex != 0){

         //Get the dateRange
         var controlPanelDropdownSel = this.view.getIdSelector(this.view.controlPanelDropdownSel, 
                                                               this.bhviewIndex);
         var adapterName = this.model.getBHViewAttribute('data_adapter');
         var a = this.dataAdapters.getAdapter(adapterName);
         var params = a.processControlPanel(controlPanelDropdownSel, this.signalData);

         var bhviewName = this.model.getBHViewAttribute('name');

         //Build the data object for the event
         var data = { selected_bhview:bhviewName,
                      parent_bhview_index:this.bhviewParentIndex,
                      display_type:'page',
                      params:params };

         $(this.view.allViewsContainerSel).trigger(this.addBHViewEvent, data);
         $(this.view.allViewsContainerSel).trigger( this.closeEvent, { bhview_index:this.bhviewIndex } ); 
         
      }
   },
   openWindow: function(){

      this.view.closeMenu();
      var signals = this.model.getBHViewAttribute('signals');
      BHPAGE.ConnectionsComponent.setBHViewIndex(this.bhviewIndex);
      BHPAGE.ConnectionsComponent.open('open', signals);

   },
   refresh: function(){

      this.view.closeMenu();

      //Display the signal data
      this.view.displaySignalData('', this.signalData, this.bhviewIndex);

      data = { bhview_index:this.bhviewIndex }; 

      this.processControlPanel(data);

   },
   help: function(){

      this.view.closeMenu();
      var src = "/bughunter/views/help";
      var dialogHtml = this.view.getHelpModal(src);

      $(dialogHtml).dialog('open');
      return false;
   },
   getDataHelp: function(){

      this.view.closeMenu();
      var name = this.model.getBHViewAttribute('name')
      var src = "/bughunter/views/help#" + name;
      var dialogHtml = this.view.getHelpModal(src);
      $(dialogHtml).dialog('open');

      return false;
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
   setVisualization: function(item){

      var charts = this.model.getBHViewAttribute('charts');
      if(charts.length == 1){
         //No visualization other than table
         this.visName = "table";
         this.view.visReadName = "Table";
      }

      if(item){
         this.visName = $(item).attr('href').replace('#', '');
      }

      this._setVisReadName(charts);

      var bhviewReadName = this.model.getBHViewAttribute('read_name');
      this.view.displayBHViewName(this.bhviewIndex, bhviewReadName);

      var datatableWrapperSel = this.view.getIdSelector(this.view.tableSel, this.bhviewIndex) + 
                                this.view.wrapperSuffix;

      var visContainerSel = this.view.getIdSelector(this.view.visContainerSel, this.bhviewIndex);

      var spacerSel = this.view.getIdSelector(this.view.spacerSel, this.bhviewIndex);

      if(this.visName == 'table'){

         this.view.displayVisualization(datatableWrapperSel, visContainerSel, spacerSel, this.visName);

      }else{
         
         var detailSelectors = this.view.getVisDetailSelectors(this.bhviewIndex);

         this.view.displayVisualization(datatableWrapperSel, visContainerSel, spacerSel, this.visName);

         //Prepare a signalData structure for the visCollection to use if
         //a user selects a signal
         var controlPanelDropdownSel = this.view.getIdSelector(this.view.controlPanelDropdownSel, 
                                                               this.bhviewIndex);
         var adapterName = this.model.getBHViewAttribute('data_adapter');
         var a = this.dataAdapters.getAdapter(adapterName);
         var dateRange = a.getDateRangeParams(controlPanelDropdownSel, this.signalData);

         var signalData = { parent_bhview_index:this.bhviewIndex,
                            data:"",
                            date_range:dateRange,
                            signal:"" };

         var callback = _.bind( function(signalData){
                                    this.view.displaySignalData('send', signalData, this.bhviewIndex);
                                }, this);

         this.visCollection.display(this.visName, 
                                    this.dataTable.fnGetData(),
                                    detailSelectors,
                                    signalData,
                                    callback);
      }

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

         onOpen: _.bind(this._controlPanelOnOpen, this),

         onClose: _.bind( this._controlPanelOnClose, this),

         //This clickHandler prevents the form from closing when it's
         //clicked for data input.  
         clickHandler:_.bind( this._controlPanelClickHandler, this)
      });
   },
   _controlPanelOnOpen: function(event){

      //Make sure we don't have any extra keydown event bindings
      $(document).unbind('keydown');

      //Populate the control panel fields with
      //any signal data
      var controlPanelDropdownSel = this.view.getIdSelector(this.view.controlPanelDropdownSel, 
                                                            this.bhviewIndex);
      var serverResetDateRangeSel = this.view.getIdSelector(this.view.serverResetDateRangeSel,
                                                            this.bhviewIndex);
      var badDateFormatSel = this.view.getIdSelector(this.view.badDateFormatSel, this.bhviewIndex);

      var adapterName = this.model.getBHViewAttribute('data_adapter');
      var a = this.dataAdapters.getAdapter(adapterName);
      a.setControlPanelFields(controlPanelDropdownSel, this.signalData);
      a.checkDates(controlPanelDropdownSel, 
                   this.serverDateRangeUpdate,
                   this.model.start_date, 
                   this.model.end_date,
                   serverResetDateRangeSel,
                   badDateFormatSel);


      //Capture keydown and look for enter/return press
      $(document).keydown( _.bind( this._processControlPanelKeyPress, this ) );
   },
   _controlPanelOnClose: function(event){
      //Update the signal data when the menu is closed to make 
      //sure we get any modification to the date range
      var controlPanelDropdownSel = this.view.getIdSelector(this.view.controlPanelDropdownSel, 
                                                            this.bhviewIndex);
      var adapterName = this.model.getBHViewAttribute('data_adapter');
      var a = this.dataAdapters.getAdapter(adapterName);
      a.unbindPanel(controlPanelDropdownSel);

      var dateRange = a.getDateRangeParams(controlPanelDropdownSel, {});

      if(this.signalData){
         this.signalData['date_range'] = dateRange;
      }

      //This is really dangerous, it will clear all keydown events
      //assigned at the document level... which really should not be 
      //any.  When passing a function to unbind it fails probably because
      //_.bind() is used for context management... Ughhhh
      $(document).unbind('keydown');

   },
   _controlPanelClickHandler: function(event){

      var controlPanelBtId = this.view.getId(this.view.controlPanelBtSel, 
                                             this.bhviewIndex);

      var controlPanelClearBtId = this.view.getId(this.view.controlPanelClearBtSel, 
                                                  this.bhviewIndex);

      var controlPanelResetDatesBtId = this.view.getId(this.view.controlPanelResetDatesSel, 
                                                       this.bhviewIndex);

      var controlPanelDropdownSel = this.view.getIdSelector(this.view.controlPanelDropdownSel, 
                                                            this.bhviewIndex);

      var elId = $(event.target).attr('id');

      //This enables control panel's with checkboxes
      var adapterName = this.model.getBHViewAttribute('data_adapter');
      var a = this.dataAdapters.getAdapter(adapterName);
      a.processPanelClick(elId);

      if( elId == controlPanelBtId ){
         //close menu
         this.view.closeMenu();
         //fire event
         $(this.view.allViewsContainerSel).trigger( this.processControlPanelEvent, 
                                                  { bhview_index:this.bhviewIndex }); 
      }else if(elId == controlPanelResetDatesBtId){
         a.resetDates(controlPanelDropdownSel);
      }else if(elId == controlPanelClearBtId){
         a.clearPanel(controlPanelDropdownSel);
      }
      event.stopPropagation();
   },
   _processControlPanelKeyPress: function(event){
      //If the user presses enter/return simulate form submission
      if(event.keyCode == 13){
         //close menu
         this.view.closeMenu();
         //fire event
         $(this.view.allViewsContainerSel).trigger( this.processControlPanelEvent, 
                                                  { bhview_index:this.bhviewIndex }); 
      }
   },

   _fnError: function(data, textStatus, jqXHR){
      var messageText = 'Ohhh no, something has gone horribly wrong! ';
      messageText += ' HTTP status:' + data.status + ', ' + textStatus +
      ', ' + data.statusText;

      this.view.showNoDataMessage(this.bhviewIndex, 'error', messageText); 
   },
   _setVisReadName: function(charts){
      for(var i=0; i<charts.length; i++){
         if(charts[i].name == this.visName){
            this.view.visReadName = charts[i].read_name;
            break;
         }
      }
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

      //Scrolling params
      this.minScrollPanelSize = 200;
      this.defaultScrollPanelSize = 500;
      this.tableScrollClassSel = '.dataTables_scrollBody';

      //Main View Container
      this.allViewsContainerSel = '#bh_view_container';

      //Cloned Containers
      this.viewWrapperSel = '#bh_view_wrapper_c';
      this.singleViewContainerSel = '#bh_view_c';

      //table wrapper suffix
      this.wrapperSuffix = '_wrapper';

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

      this.scrollBodyClassSel = 'dataTables_scrollBody';

      //Close button selector
      this.closeButtonSel = '#bh_closetable_bt_c';
      this.newWindowButtonSel = '#bh_newwindow_bt_c';

      //Control panel ids
      this.controlPanelBtSel = '#bh_cp_load_view_c';
      this.controlPanelClearBtSel = '#bh_cp_clear_c';
      this.controlPanelDropdownSel = '#bh_cp_dropdown_c';
      this.controlPanelResetDatesSel = '#bh_reset_dates_c';

      //Signal display ids
      this.signalDataSentDisplaySel = '#bh_signal_data_sent_c';
      this.signalDataReceivedDisplaySel = '#bh_signal_data_received_c';
      this.signalDateRangeDisplaySel = '#bh_signal_date_range_c';
      this.signalHelpBtSel = '#bh_signal_help_bt_c';
      this.maxSignalDataLength = 50;

      //Date range selectors
      this.startDateSel = '#bh_start_date';
      this.endDateSel = '#bh_end_date';
      this.currentDateSel = '#bh_current_date';
      this.serverResetDateRangeSel = '#bh_server_date_range_reset_c';
      this.badDateFormatSel = '#bh_bad_date_format_c';

      //Parent/Child relationship display
      this.parentIndexDisplaySel = '#bh_parent_display_c';
      this.viewIndexDisplaySel = '#bh_view_display_c';
      this.parentBHViewIndexSel = '#bh_parent_bhview_index';

      //Visualization containers
      this.visContainerSel = '#bh_vis_container_c';
      this.graphContainerSel = '#bh_vis_graph_c';
      this.graphDetailsContainerSel = '#bh_vis_details_c';
      this.visLiCloneSel = '#bh_vis_li_clone';

      this.visDetailSelectors = { sig_detail:'#bh_signature_detail_c',
                                  message_detail:'#bh_message_detail_c',
                                  count_detail:'#bh_count_detail_c',
                                  platform_detail:'#bh_platform_detail_c',
                                  primary_label_detail:'#bh_primary_detail_label_c',
                                  secondary_label_detail:'#bh_secondary_detail_label_c' };

      this.visReadName = options.vis_read_name;

      //Spacer div between bhviews
      this.spacerSel = "#bh_spacer_c";
      this.tableSpacerHeight = 10;
      this.visSpacerHeight = 550;

      //Clone id selector, finds all elements with an id attribute ending in _c
      this.cloneIdSelector = '*[id$="_c"]';

      //The current selected row element in a table
      this.selectedTrEl;

      //Signal base id
      this.signalBaseSel = '#bh_post_';

      //Messages
      this.nodataMessage = 'No data available.';
      this.sendSignalMessage = 'Select a link in the parent view to send a signal.';
   },
   updateDateRange: function(data, textStatus, jqXHR){

      if(data.start_date != undefined){
         $(this.startDateSel).attr('value', data.start_date);
      }
      if(data.end_date != undefined){
         $(this.endDateSel).attr('value', data.end_date);
      }
      if(data.current_date != undefined){
         $(this.currentDateSel).attr('value', data.current_date);
      }
   },
   getTablePaginationSel: function(bhviewIndex){
      return this.tablePaginationSel.replace('BHVIEW_INDEX', bhviewIndex);
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

      var menuChildren = $(bhVisMenuSel).children();
      var liCloneEl = $(this.visLiCloneSel).get(0);

      for(var i=0; i<menuChildren.length; i++){
         var liEl = menuChildren[i]; 
         if( !$(liEl).attr('id') ){
            //Pre-existing li from another view type, delete it
            $(liEl).remove();
         }
      }

      if( _.isElement( liCloneEl ) ){

         for(var i=0; i < charts.length; i++){

            var c = charts[i];

            //clone the li
            var newLiEl = $(liCloneEl).clone();
            newLiEl.attr('id', '');

            //get anchor and set attributes and show the new li
            var anchor = $(newLiEl).find('a');
            $(anchor).attr('href', '#' + c.name);
            $(anchor).text(c.read_name);
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
    *BHVIEW MODIFICATION METHODS
    ************************/
   displayParentChild: function(parentIndex, bhviewIndex, parentWindowName){

      var parentIndexDisplaySel = this.getIdSelector(this.parentIndexDisplaySel, bhviewIndex);
      var viewIndexDisplaySel = this.getIdSelector(this.viewIndexDisplaySel, bhviewIndex);

      var parentText = parentWindowName;
      var viewText = parseInt(bhviewIndex) + 1; 

      if(parentIndex >= 0){
         parentText += ", View " + (parseInt(parentIndex) + 1);
      }

      $(parentIndexDisplaySel).text(parentText);
      $(viewIndexDisplaySel).text(viewText);

   },
   disableClose: function(bhviewIndex){
      var closeButtonSel = this.getIdSelector(this.closeButtonSel, bhviewIndex);
      $(closeButtonSel).addClass("ui-state-disabled");

      var newWindowButtonSel = this.getIdSelector(this.newWindowButtonSel, bhviewIndex);
      $(newWindowButtonSel).addClass("ui-state-disabled");
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
   setHeight: function(tableSel, targetHeight){
      var scrollBody = $(tableSel).parent();
      var h = parseInt( $(scrollBody).css('height') );
      if( h < targetHeight ){
         var newHeight = this.minScrollPanelSize + 'px';
         $(scrollBody).css('height', newHeight);
      }else{

      }
   },
   /*******************
    * GET METHODS
    *******************/
   getParentBHViewIndex: function(){
      return parseInt($(this.parentBHViewIndexSel).val());
   },
   getFilterSel: function(bhviewIndex){
      return '#bh_tview_c_' + bhviewIndex + '_filter';
   },
   getTableScrollContainer: function(bhviewIndex){
      var tableSel = this.getIdSelector(this.tableSel, bhviewIndex);
      return $(tableSel).parent(); 
   },
   getHelpModal: function(src){

      var helpIframe = '<div><iframe class="bh-help-frame ui-corner-all" src="' + src + '"></iframe></div>';
      var dialogHtml = $(helpIframe);

      $(dialogHtml).dialog({
         autoOpen: false,
         width: 600,
         height: 800,
         modal: true,
         title: "Bughunter Help"
       });

       return dialogHtml;
   },
   /*******************
    *TOGGLE METHODS
    *******************/
   displayVisualization: function(datatableWrapperSel, visContainerSel, spacerSel, visName){

      if(visName == 'table'){

         $(spacerSel).css('height', this.tableSpacerHeight);
         $(datatableWrapperSel).css('display', 'block');
         $(visContainerSel).css('display', 'none');

      }else {

         $(datatableWrapperSel).css('display', 'none');
         $(visContainerSel).css('display', 'block');
         $(spacerSel).css('height', this.visSpacerHeight);
      }
   },
   getVisDetailSelectors: function(bhviewIndex){

      var detailSelectors = {};
      var graphContainerSel = this.getIdSelector(this.graphContainerSel, bhviewIndex);
      var graphDetailsContainerSel = this.getIdSelector(this.graphDetailsContainerSel, bhviewIndex);

      for(var detailKey in this.visDetailSelectors){
         var detailSelector = this.getIdSelector(this.visDetailSelectors[detailKey], bhviewIndex);
         detailSelectors[detailKey] = detailSelector;
      }
      detailSelectors.detail_container = graphDetailsContainerSel;
      detailSelectors.graph_container = graphContainerSel;

      return detailSelectors;
   },
   displayBHViewName: function(bhviewIndex, bhviewReadName){
      var topbarTitleSel = this.getIdSelector(this.topBarTitleSel, bhviewIndex);
      $(topbarTitleSel).text(bhviewReadName + ' ' + this.visReadName);
   },
   displaySignalData: function(direction, signalData, bhviewIndex){

      var signalDateRangeDisplaySel = this.getIdSelector(this.signalDateRangeDisplaySel, bhviewIndex);

      //Show data range sent if we have one
      if(signalData.date_range){
         var dateRange = signalData.date_range.start_date + ' to ' + signalData.date_range.end_date;
         $(signalDateRangeDisplaySel).text(dateRange); 
      }
      //Show signal type and associated data
      if(signalData.data != undefined){
         var data = BHPAGE.unescapeForUrl(signalData.data);
         var displayData = data;
         if(signalData.data && signalData.signal){
            if(data.length >= this.maxSignalDataLength){
               displayData = data.substring(0, this.maxSignalDataLength - 3) + '...';
            }
         }
         if(direction == 'receive'){
            var signalDataReceivedDisplaySel = this.getIdSelector(this.signalDataReceivedDisplaySel, bhviewIndex);
            $(signalDataReceivedDisplaySel).text(displayData);
            $(signalDataReceivedDisplaySel).attr('title', data);
         }else if(direction == 'send'){
            var signalDataSentDisplaySel = this.getIdSelector(this.signalDataSentDisplaySel, bhviewIndex);
            $(signalDataSentDisplaySel).text(displayData);
            $(signalDataSentDisplaySel).attr('title', data);
         }
      }
   },
   showNoDataMessage: function(bhviewIndex, messageType, messageText){

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

      var message = this.nodataMessage;
      if(messageType == 'sendsignal'){
         message = this.sendSignalMessage;
      }else if(messageType == 'error'){
         message = messageText;
      }
      $(noDataSel).text(message);
      $(noDataSel).css('display', 'block');

   },
   closeMenu: function(){
      /*************
       *This method calls the kill() method of
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

      this.displayBHViewName(bhviewIndex, bhviewReadName);

      if(bhviewIndex == 0){
         //Disable the close button and move to new window button so the user cannot
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

      //Hide visualization
      var visContainerSel = this.getIdSelector(this.visContainerSel, bhviewIndex);
      $(visContainerSel).css('display', 'none');

      //Show spinner
      var spinnerSel = this.getIdSelector(this.spinnerSel, bhviewIndex);
      $(spinnerSel).css('display', 'block');
   },
   showTableSpinner: function(bhviewIndex){

      var noDataSel = this.getIdSelector(this.tableNoDataSel, 
                                         bhviewIndex);
      $(noDataSel).css('display', 'none');

      var tableSel = this.getIdSelector(this.tableSel, bhviewIndex) + this.wrapperSuffix;
      $(tableSel).css('display', 'none');

      //Hide visualization
      var visContainerSel = this.getIdSelector(this.visContainerSel, bhviewIndex);
      $(visContainerSel).css('display', 'none');
      
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

      var tableSel = this.getIdSelector(this.tableSel, bhviewIndex) + this.wrapperSuffix;
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
      this.dateRangeLocation = "/bughunter/views/get_date_range";

      //This is set from any incoming view data
      //to whatever the final range was.  If the
      //range provided by the UI is invalid the server 
      //will reset it.
      this.start_date = "";
      this.end_date = "";
   },
   /***************
    *GET METHODS
    ***************/
   getBHViewAttribute: function(attr){
      return this.bhviewHash[attr];
   },
   getBHViewData: function(bhviewName, context, fnSuccess, params, fnError){

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
                          error:fnError,
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

      //Set the date range
      this.start_date = dataObject.start_date;
      this.end_date = dataObject.end_date;

      //enable bhview hidden columns
      var hiddenColumns = this.getBHViewAttribute('hidden_columns');
      var aTargets = [];
      for(var col in hiddenColumns){
         aTargets.push(parseInt(hiddenColumns[col]));
      }

      //NOTE: datatableObject cannot be an attribute of the
      //      model instance because it is unique to different 
      //      views.
      var datatableObject = { bJQueryUI: true,
                              sPaginationType: "full_numbers",
                              bPaginate: true,
                              sScrollY:"500px",
                              bScrollCollapse:true,
                              sScrollX:"100%",

                              //Hide these columns in initial display
                              aoColumnDefs:[ 
                                 { bVisible: false, aTargets:aTargets }
                              ],

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
