var BHViewCollection = new Class({

   /***************************
    * BHViewCollection
    *
    *  Manages a collection of BHViews.  Uses a private model
    *  and view class for support.
    ***************************/
   Extends:Options,

   jQuery:'BHViewCollection',

   initialize: function(selector, options){

      this.setOptions(options);

      this.model = new BHViewCollectionModel('#BHViewCollectionModel', {});
      this.view = new BHViewCollectionView('#BHViewCollectionView', {});

      //Get the view marked as default in json structure
      this.defaultBHViewName = this.model.getDefaultBHView();

      this.subscriptionTargets = { CLOSE_BHVIEW:this.closeBHView,
                                   ADD_BHVIEW:this.addBHView,
                                   SIGNAL_BHVIEW:this.sendSignalToChildWindows,
                                   OPEN_COLLECTION_BHVIEW:this.openBHViewCollection };

      BHPAGE.registerSubscribers(this.subscriptionTargets, 
                                 this.view.allViewsContainerSel,
                                 this);

      //reset column widths when window resizes
      $(window).resize( _.bind( this.resizeWindow, this ) );
   },
   openBHViewCollection: function(data){

      var parentToIndexMap = {};

      for(var i=0; i < data.collection.length; i++){

         var bhviewChild = data.collection[i].bhview;
         var bhviewParent = data.collection[i].parent;

         var bhviewData = {  selected_bhview:bhviewChild,
                             display_type:'pane',
                             parent_bhview_index:parentToIndexMap[bhviewParent] };

         if( i === 0 ){
            //User has selected a collection from the Navigation
            //menu.  Change parent view to the first view in the 
            //collection
            if( data.parent_bhview_index != undefined ){

               parentToIndexMap[bhviewChild] = data.parent_bhview_index;

            } else {
               //Collection is set as the default item to display
               var newIndex = this.addBHView(bhviewData);
               parentToIndexMap[bhviewChild] = newIndex;

            }

         }else{
            var newIndex = this.addBHView(bhviewData);
            parentToIndexMap[bhviewChild] = newIndex;
         }
      }
   },
   resizeWindow: function(event){

      for(var i=0; i < this.model.bhviewCollection.length; i++){
         if( this.model.bhviewCollection[i].dataTable != undefined ){
            this.model.bhviewCollection[i].dataTable.fnAdjustColumnSizing();
         }
      }
   },
   getBHViewsBySignal: function(signal){
      return this.model.getBHViewsBySignal(signal);
   },
   getBHViewsBySignalHash: function(signals){
      return this.model.getBHViewsBySignalHash(signals);
   },
   getBHViewCount: function(){
      return this.model.getBHViewCount();
   },
   getAllBHViewNames: function(){
      return this.model.getAllBHViewNames();
   },
   getBHViewParent: function(childIndex){
      return this.model.bhviewRelationships[ childIndex ]['parent'];
   },
   addBHView: function(data){
      
      var bhviewName = data.selected_bhview;
      var bhviewHash = BHPAGE.navLookup[bhviewName];

      //View has no pane version and can only be launched
      //as a new page
      if(bhviewHash && (bhviewHash.page_target != undefined)){
         //Check for any page targets
         var url = bhviewHash.page_target.replace('HASH', '#');
         window.open(url);
         return false;
      }

      //Open new page for bhview
      if(data.display_type == 'page'){
         this.view.submitPostForm(this.model.newViewUrl, 
                                  data.params, 
                                  data.selected_bhview,
                                  data.parent_bhview_index);

      }else {
         //Open bhview in current page
         var defaultView = false;

         //First view created, mark as default so the bhview
         //can disable close button to prevent a state of 
         //no views displayed
         if(!this.model.hasBHView(data.selected_bhview)){
            bhviewName = this.defaultBHViewName;
            defaultView = true;

            bhviewHash = BHPAGE.navLookup[bhviewName];

            if(bhviewHash.collection != undefined){
               //Default view is a collection let openBHViewCollection handle it
               var data = { parent_bhview_index:undefined,
                            collection:bhviewHash.collection };

               this.openBHViewCollection(data);
               return false;
            }
         }

         var bhviewIndex = this.model.getBHViewIndex();

         var bhviewComponent = new BHViewComponent('#bhviewComponent', 
                                                 { bhview_name:bhviewName, 
                                                   bhview_parent_index:data.parent_bhview_index,
                                                   bhview_index:bhviewIndex }); 

         //Record parent/child relationships
         this.model.addParentChildRelationship(data.parent_bhview_index, bhviewIndex);

         if(defaultView){
            bhviewComponent.markAsDefault();
         }

         this.model.addBHView(bhviewComponent);

         return bhviewIndex;
      }
   },
   closeBHView: function(data){
      var bhview = this.model.getBHView(data.bhview_index);
      this.model.removeBHView(bhview);
      bhview.destroy();
   },
   loadNewChildWindow: function(childWindow){
      this.model.loadNewChildWindow(childWindow);
   },
   sendSignalToChildWindows: function(data){

      //Make sure the message was not sent from another window
      if(data.window_message === undefined){
         //Send message to child windows and include which
         //window sent the message
         data['window_sender'] = document.title;

         var targetOrigin = BHPAGE.getTargetOrigin();

         for(var i=0; i<this.model.childWindows.length; i++){
            this.model.childWindows[i].postMessage(JSON.stringify(data), targetOrigin);
         }
      }
   }
});
var BHViewCollectionView = new Class({

   Extends:View,

   jQuery:'BHViewCollectionView',

   initialize: function(selector, options){

      this.parent(options);

      this.urlBase = '/bughunter/views/';
      this.allViewsContainerSel = '#bh_view_container';
   },
   submitPostForm: function(newViewUrl, params, selectedView, parentBHviewIndex){

      /*****************
       * Note: Ran into some issues submitting the form
       * dynamically using jquery so using straight js here
       * instead.
       * ***************/

      //Create a form that will open a new page when submitted
      var form = document.createElement("form");
      form.setAttribute("method", "post");
      form.setAttribute("action", this.urlBase + '#' + selectedView);
      form.setAttribute("target", "_blank");

      var signals = BHPAGE.navLookup[selectedView]['signals'];

      var hiddenFields = this.loadSignalDataInPage(params, parentBHviewIndex, signals);
      for(var i=0; i < hiddenFields.length; i++){
         form.appendChild(hiddenFields[i]);
      }

      document.body.appendChild(form);

      var t = form.submit();

      //Finished with the form, remove from DOM
      $(form).remove();
   },
   loadSignalDataInPage: function(params, parentBHviewIndex, signals){

      var hiddenFields = [];

      if((signals != undefined) && (params != undefined)){
         for(var sig in signals){
            var match = params.split(sig + '=');

            //Make sure we have a match for a name/value pair
            if((match != null) && (match.length >= 2)){

               var signalHiddenField = document.createElement("input");

               //Load any signals in the params
               signalHiddenField.setAttribute('type', 'hidden');
               signalHiddenField.setAttribute('name', sig);
               signalHiddenField.setAttribute('value', encodeURIComponent(match[1]));
               hiddenFields.push(signalHiddenField);

               //Load the date range
               var dateMatch = match[0].replace(/&$/, '').split('&');
               if((dateMatch != null) && (dateMatch.length >= 2)){
                  for(var i=0; i < dateMatch.length; i++){
                     
                     var dateNameValue = dateMatch[i].split('=');
                     var signalHiddenField = document.createElement("input");
                     signalHiddenField.setAttribute('type', 'hidden');
                     signalHiddenField.setAttribute('name', dateNameValue[0]);
                     signalHiddenField.setAttribute('value', dateNameValue[1]);
                     hiddenFields.push(signalHiddenField);
                  }
               }
            }
         }
      }

      //Add the index of the parent view
      var parentHiddenField = document.createElement("input");
      parentHiddenField.setAttribute('type', 'hidden');
      parentHiddenField.setAttribute('name', 'parent_bhview_index');
      parentHiddenField.setAttribute('value', parentBHviewIndex);
      hiddenFields.push(parentHiddenField);

      return hiddenFields;
   }
});

var BHViewCollectionModel = new Class({

   Extends:Model,

   jQuery:'BHViewCollectionModel',

   initialize: function(selector, options){

      this.parent(options);

      this.newViewUrl = '/bughunter/views';

      //An associative array might be a better choice here.
      //Could embed the bhviewIndex in the keys.  Then we
      //can remove deleted array entries safely.
      this.bhviewCollection = [];

      /******
       * This data structure maintains the parent/child relationships
       * for all views a user has created
       * 
       *    { bhviewIndex: { parent:parent bhviewIndex,
       *                     children: { child bhviewIndex1 .. bhviewIndexn } }
       *
       * ****/
      this.bhviewRelationships = {};

      //List of children window objects on different tabs.
      //Used to manage cross tab communication.
      this.childWindows = [];

   },
   addParentChildRelationship: function(parentIndex, childIndex){

      //Has the parent already been entered?
      if(this.bhviewRelationships[parentIndex]){
         //Add the child index to children
         this.bhviewRelationships[parentIndex]['children'][childIndex] = 1;
         this.bhviewRelationships[childIndex] = { 'parent':parentIndex, 'children':{} };
      }else if( (parentIndex === undefined) && (childIndex == 0)){
         //First view
         this.bhviewRelationships[childIndex] = { 'parent':undefined, 'children':{} }; 
      }
   },
   getBHView: function(bhviewIndex){
      if( !_.isNull( this.bhviewCollection[ bhviewIndex ] ) ){
        return this.bhviewCollection[bhviewIndex]; 
      }else{
         console.log('bhviewCollection error: no view found at index ' + bhviewIndex);
      }
   },
   getBHViewCount: function(){
      var count = 0;
      for(var i=0; i<this.bhviewCollection.length; i++){
         if(!_.isUndefined(this.bhviewCollection[i].bhviewIndex)){
            count++;
         }
      }
      return count;
   },
   getBHViewIndex: function(){
      return this.bhviewCollection.length;
   },
   getDefaultBHView: function(){
      for( var bhviewName in  BHPAGE.navLookup ){
         if (_.isNumber( BHPAGE.navLookup[bhviewName]['default'] )){
            return bhviewName;
         }
      }
      console.log('Warning: no default bhViewHash found!');
   },
   getAllBHViewNames: function(){

      var mapReturn = _.map( _.keys( BHPAGE.navLookup ), function(key){ 
         return { name:key, read_name:BHPAGE.navLookup[key]['read_name'] };
      });

      return mapReturn;
   },
   getBHViewsBySignal: function(signal){
      var bhviews = [];
      for( var bhviewName in  BHPAGE.navLookup ){
         if (BHPAGE.navLookup[bhviewName]['send_only'] != undefined){
            //Some views can only send signals not receive them, exclude from list
            continue;
         }
         if (BHPAGE.navLookup[bhviewName]['signals'] != undefined){
            if (BHPAGE.navLookup[bhviewName]['signals'][signal] != undefined){
               bhviews.push(BHPAGE.navLookup[bhviewName]);
            }
         }
      }
      return bhviews;
   },
   getBHViewsBySignalHash: function(signals){
      var bhviews = [];
      for( var bhviewName in  BHPAGE.navLookup ){
         if (BHPAGE.navLookup[bhviewName]['send_only'] != undefined){
            //Some views can only send signals not receive them, exclude from list
            continue;
         }
         if (BHPAGE.navLookup[bhviewName]['signals'] != undefined){
            for(var signal in signals){
               if (BHPAGE.navLookup[bhviewName]['signals'][signal] != undefined){
                  bhviews.push(BHPAGE.navLookup[bhviewName]);
                  //We only need one match to include the signla
                  break;
               }
            }
         }
      }
      return bhviews;
   },
   hasBHView: function(bhviewName){
      if(!(BHPAGE.navLookup[bhviewName] === undefined)){
         return true;
      }else{
         return false;
      }
   },
   addBHView: function(bhview){
      this.bhviewCollection.push(bhview);
   },
   removeBHView: function(bhviewObject){

      var bhviewIndex = bhviewObject.bhviewIndex;

      //Clean up relationships
      var parentIndex = this.bhviewRelationships[bhviewIndex]['parent'];

      //Remove this child from parent's children
      delete(this.bhviewRelationships[parentIndex]['children'][bhviewIndex]);
      //Remove this bhview
      delete(this.bhviewRelationships[bhviewIndex]);

      this.bhviewCollection[bhviewObject] = delete(this.bhviewCollection[bhviewObject]);
   },
   loadNewChildWindow: function(newWin){
      this.childWindows.push(newWin);
   }
});
