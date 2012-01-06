var ConnectionsComponent = new Class({

   Extends: Component,

   jQuery:'ConnectionsComponent',

   initialize: function(selector, options){

      this.setOptions(options);

      this.parent(options);

      this.view = new ConnectionsView('#ConnectionsView',{});
      this.model = new ConnectionsModel('#ConnectionsModel',{});

   },
   open: function(tab, signals){
      this.setAllViewsOptionMenu(this.view.viewListSel, signals);
      this.view.open(tab);
   },
   getDisplayType: function(){
      return this.view.displayType;
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

      this.allViewsContainerSel = '#bh_view_container';

      //Main modal container selector
      this.connectionsModalClassSel = '.bh-connections-modal';

      //Tab Selectors 
      this.openNewViewTabSel = '#bh_open_new_view_tab';

      //Select menu selectors
      this.viewListSel = '#bh_view_list';

      //Radio buttons
      this.radioButtonOpenClassSel = '.bh-page-newpane';

      //Events
      this.addBHViewEvent = 'ADD_BHVIEW';

      //Index of the view that opened the dialog
      this.bhviewIndex;

      this.initializeModal();
   },

   initializeModal: function(){

      //Set up the tag selection events
      this.setTabSelections();

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

               var displayType = $('input[name=open]:checked').val();

               //Trigger the add view event
               $(this.allViewsContainerSel).trigger(this.addBHViewEvent, { selected_bhview:selectedView, 
                                                                           parent_bhview_index:this.bhviewIndex,
                                                                           display_type:displayType });

            }, this)
         };

      return buttons;
   },
   getBHViewSelection: function(){
      return $(this.viewListSel).attr('value');
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
