var ConnectionsComponent = new Class({

   Extends: Component,

   jQuery:'ConnectionsComponent',

   initialize: function(selector, options){

      this.setOptions(options);

      this.parent(options);

      this.view = new ConnectionsView('#ConnectionsView',{});
      this.model = new ConnectionsModel('#ConnectionsModel',{});

   },
   open: function(tab, signalingType, signals){

      this.setAllViewsOptionMenu(this.view.viewListSel, signals);

      this.view.setSignalingType(signalingType);
      this.view.open(tab, signalingType);
   },
   setAllViewsOptionMenu: function(selectSel, signals){
      var bhviewNames = BHPAGE.BHViewCollection.getBHViewsBySignalHash(signals);
      //Set up all views option menu
      this.view.setAllViewsOptionMenu(selectSel, bhviewNames);
   },
   setBHViewIndex: function(index){
      this.view.bhviewIndex = index;
   }

});
var ConnectionsView = new Class({

   Extends:View,

   jQuery:'ConnectionsView',

   initialize: function(selector, options){

      this.setOptions(options);
      this.parent(options);

      //List of hashes containing:
      // name:bhviewName, read_name:readName
      this.bhviewNames = this.options.bhviewNames;

      this.displayType = 'pane';

      this.allViewsContainerSel = '#bh_view_container';

      //Main modal container selector
      this.connectionsModalClassSel = '.bh-connections-modal';

      //Tab Selectors 
      this.mannageConnectionsTabSel = '#bh_manage_connections_tab';
      this.openNewViewTabSel = '#bh_open_new_view_tab';

      //Select menu selectors
      this.viewListSel = '#bh_view_list';

      //Radio buttons
      this.radioButtonOpenClassSel = '.bh-page-newpane';
      this.radioButtonConnectionsClassSel = '.bh-connections';

      //Events
      this.addBHViewEvent = 'ADD_BHVIEW';
      this.signalTypeEv = 'SET_SIGNALING_TYPE_BHVIEW';

      //Index of the view that opened the dialog
      this.bhviewIndex;

      this.initializeModal();
   },

   initializeModal: function(){

      //Set up the tag selection events
      this.setTabSelections();
      //Set up the radio buttons on the open page tab
      this.setRadioButtons();

      $(this.connectionsModalClassSel).dialog({ 
         autoOpen: false,
         width:400,
         height:600,
         buttons:this.getDialogButtons(),
         modal:true
      });
   },
   getDialogButtons: function(){

      var buttons = {
            "File Bug": function(){
               alert('File a bug');
            },
            "Cancel": function(){
               $(this).dialog('close');
            },
            "Open":_.bind(function(event){

               //Get the bhview the user selected
               var selectedView = this.getBHViewSelection();
               //Close the dialog
               $(this.connectionsModalClassSel).dialog('close');
               //Trigger the add view event
               $(this.allViewsContainerSel).trigger(this.addBHViewEvent, { selected_bhview:selectedView, 
                                                                           parent_bhview_index:this.bhviewIndex,
                                                                           display_type:this.displayType });

            }, this)
         };

      return buttons;
   },
   getBHViewSelection: function(){
      return $(this.viewListSel).attr('value');
   },
   setRadioButtons: function(radioButtonSelectors){
      $(this.radioButtonOpenClassSel).bind( 'click', _.bind(function(event){
            var value = $( event.target ).attr('value');
            if(value.search(/page/) > -1){
               this.displayType = 'page';
            }else if(value.search(/newpane/) > -1){
               this.displayType = 'pane';
            }
      }, this));
      $(this.radioButtonConnectionsClassSel).bind( 'click', _.bind(function(event){
            var value = $( event.target ).attr('value');
            $(this.allViewsContainerSel).trigger(this.signalTypeEv, 
                                                 { type:value, bhview_index:this.bhviewIndex } );
      }, this));
   },
   setSignalingType: function(type){
      var radioBts = $(this.radioButtonConnectionsClassSel);
      for(var i = 0; i<radioBts.length; i++){
         var value = $(radioBts[i]).attr('value');
         if(value == type){
            $(radioBts[i]).attr('checked', 1);
         }
      }
   },
   setAllViewsOptionMenu: function(listSel, bhviewNames){

      //Clear out any existing options
      $(listSel).empty();

      bhviewNames.sort(this.sortOptionMenu);

      for(var i=0; i<bhviewNames.length; i++){
         var optionEl = $('<option></option>');
         $(optionEl).attr('value', bhviewNames[i].name);
         $(optionEl).text(bhviewNames[i].read_name);
         if( i == 0 ){
            $(optionEl).attr('selected', 1);
         }
         $(optionEl).css('display', 'block');
         $(listSel).append(optionEl);
      }
   },
   sortOptionMenu: function(a, b){
      if( a.read_name.search(/^Site/) && b.read_name.search(/^Unit/) ){
         return 1;   
      }else{
         return -1;
      }
   },
   setTabSelections: function(){
      $(this.connectionsModalClassSel).tabs({
         select: function(event, ui){
            this.tabSelection = $(this.openNewViewTabSel).attr('href');
         }
      });
   },
   open: function(tab){

      var tabSel;
      if(tab == 'open'){
         tabSel = this.openNewViewTabSel;
      }else if(tab == 'connections'){
         tabSel = this.mannageConnectionsTabSel;
      }

      $(this.connectionsModalClassSel).tabs("select", tabSel);

      $(this.connectionsModalClassSel).dialog('open');
   }
});
var ConnectionsModel = new Class({

   Extends:View,

   jQuery:'ConnectionsModel',

   initialize: function(options){

      this.setOptions(options);

      this.parent(options);

   }
});
