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

      //This is dynamically set to the 
      //DOM element that a user right clicks
      //on in any table associated with a view.
      this.contextMenuTarget = undefined;  
      //This is set dynamically when the context menu is open.
      //It holds the text contained in the cell that the user
      //right clicked on
      this.cellText = undefined;
      //The id/index of the bhview that owns the context menu.  
      //This attribute is set when the user opens the context menu.
      this.bhviewMenuOwnerId = undefined;
      //This is populated when a user selects a URL or group of URLs
      //using the context menu
      this.urls = [];

      //This is set by resubmitUrls and contains the bhviewIndex
      //of the data view that triggered the URL_RESUBMISSION event.
      //This is the only case where this attribute is defined
      this.bhviewIndex = undefined;
 
      //Get the view marked as default in json structure
      this.defaultBHViewName = this.model.getDefaultBHView();

      this.subscriptionTargets = { CLOSE_BHVIEW:this.closeBHView,
                                   ADD_BHVIEW:this.addBHView,
                                   SIGNAL_BHVIEW:this.sendSignalToChildWindows,
                                   OPEN_COLLECTION_BHVIEW:this.openBHViewCollection,
                                   URL_RESUBMISSION:this.resubmitUrls };

      BHPAGE.registerSubscribers(this.subscriptionTargets, 
                                 this.view.allViewsContainerSel,
                                 this);

      //reset column widths when window resizes
      $(window).resize( _.bind( this.resizeWindow, this ) );

      this._initializeResubmitModal();

      this._bindCellContextMenu();

   },
   resubmitUrls: function(data){

      this.urls = this.view.loadUrls(data.urls);

      var comments = data.signature;

      this.bhviewIndex = data.bhview_index;

      var bhview = this.model.getBHView(this.bhviewIndex);

      //Show the spinner and close the menu so the user doesn't
      //keep clicking the submit button
      bhview.showTableSpinner();
      bhview.closeMenu();

      this.urlResubmissionEventData = data;

      this.model.resubmitUrls(this, 
                              comments, 
                              this.urls, 
                              _.bind(bhview.fnError, bhview), 
                              _.bind(this._resubmitCallbackEvent, this));


   },
   openBHViewCollection: function(data){

      var parentToIndexMap = {};

      //force parent to be the first bhview
      data.parent_bhview_index = 0;

      var indexTargets = this.model.getAllBHViewIndexes();
      //Remove all bhviews
      for(var i=0; i<indexTargets.length; i++){
         this.closeBHView({ bhview_index:indexTargets[i] });
      }

      for(var i=0; i < data.collection.length; i++){

         var bhviewChild = data.collection[i].bhview;
         var bhviewParent = data.collection[i].parent;

         var bhviewData = {  selected_bhview:bhviewChild,
                             display_type:'pane',
                             parent_bhview_index:parentToIndexMap[bhviewParent] };
         if( i == 0 ){
            //Collection is set as the default item to display
            var newIndex = this.addBHView(bhviewData);
            parentToIndexMap[bhviewChild] = newIndex;
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
   getAllBHViewNames: function(){
      return this.model.getAllBHViewNames();
   },
   getBHViewParent: function(childIndex){
      return this.model.bhviewRelationships[ childIndex ]['parent'];
   },
   addBHView: function(data){
      
      var bhviewName = data.selected_bhview;

      if(!this.model.hasBHView(bhviewName)){
         bhviewName = this.model.getDefaultBHView();
      }

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

         if(bhviewHash.collection != undefined){
            //view is a collection let openBHViewCollection handle it
            var dataForCollection = { parent_bhview_index:undefined,
                                      collection:bhviewHash.collection,
                                      display_type:'pane' };
            this.openBHViewCollection(dataForCollection);
            return false;
         }

         var bhviewIndex = this.model.getNewBHViewIndex();

         var bhviewComponent = new BHViewComponent('#bhviewComponent', 
                                                 { bhview_name:bhviewName, 
                                                   bhview_parent_index:data.parent_bhview_index,
                                                   bhview_index:bhviewIndex }); 

         this.model.addParentChildRelationship(data.parent_bhview_index, bhviewIndex);

         this.model.addBHView(bhviewComponent, bhviewIndex);

         return bhviewIndex;
      }
   },
   closeBHView: function(data){
      var bhview = this.model.getBHView(data.bhview_index);
      if( bhview != undefined ){
         bhview.destroy();
         this.model.removeBHView(data.bhview_index);
      }
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
   },
   _bindCellContextMenu: function(){
      document.addEventListener('contextmenu', _.bind( this._setContextMenu, this ) );
      $('menuitem').bind('click', _.bind( this._cellMenuClickHandler, this ) );
   },
   _setContextMenu: function(event){

      this.contextMenuTarget = event.target;  

      this.cellText = $(this.contextMenuTarget).text();

      //Set the index of the owner bhview
      var id = $(this.contextMenuTarget).closest('table').attr('id');
      var idMatch = id.match(/(\d+)$/);
      if(idMatch){
         this.bhviewMenuOwnerId = parseInt(idMatch[1]);
      }

      var sel = document.getSelection();

      if(sel){
         if(sel.focusNode){
            //See if the selection matches the cell contents
            if(sel.focusNode.parentElement != this.contextMenuTarget){
               //Selection parentElement does not match the element 
               //that the context menu was opened on, clear the selection
               //to avoid confusion
               if (sel.removeAllRanges) {
                  sel.removeAllRanges();
               } else if (sel.empty) {
                  sel.empty();
               }
            }
         }
      }
   },
   _cellMenuClickHandler: function(event){

      var action = $(event.target).attr('name');

      switch(action){

         case 'select':

            this._selectTextFromContextMenu();
            break;

         case 'copy':

            this._copyTextFromContextMenu();
            break;

         case 'resubmit_url':

            this.urls = [ this.cellText ];
            this.urls = this.view.loadUrls(this.urls);
            $(this.view.resubmitUrlDialogSel).dialog( 'open' );
            break;

         case 'resubmit_all_urls':

            //Get the id so we can retrieve the bhview
            if(this.bhviewMenuOwnerId >= 0){
               var bhview = this.model.getBHView(this.bhviewMenuOwnerId);
               //Get all of the urls in the column
               this.urls = bhview.getColumnData('url', function(cell){
                  var a = $(cell).find('a'); 
                  return( $(a).text() );
               });
               //Load urls into modal
               this.urls = this.view.loadUrls(this.urls);
            }

            $(this.view.resubmitUrlDialogSel).dialog( 'open' );
            break;

         case 'openurl':

            this._openUrlFromContextMenu();
            break;

         default: 

            //Use the user mouse selection and default to the table cell contents if
            //there's no selection
            var text = document.getSelection().toString() || $(this.contextMenuTarget).text();
            var eLink = new ExternalLink('#ExternalLink', {});
            var url = eLink.getUrl(action, text);
            if(url != undefined){
               window.open(url);
            }
       }
   },
   _initializeResubmitModal: function(){

      var resubmitButtons = { "Cancel":function(){ $(this).dialog("close"); },
                              "Submit":_.bind( this._resubmitUrl, this ) };

      $(this.view.resubmitUrlDialogSel).dialog({ 
         autoOpen: false,
         width:500,
         height:600,
         buttons:resubmitButtons,
         modal:true
      });
      $(this.view.resubmitSuccessSel).dialog({
         autoOpen: false,
         width:350,
         height:450,
         buttons:{ "Close":function(){ $(this).dialog("close"); } },
         modal:true
      });
   },
   _resubmitUrl: function(){
      
      var comments = $(this.view.resubmitCommentsSel).val();
      var bhview = this.model.getBHView(this.bhviewMenuOwnerId);

      this.model.resubmitUrls(this, 
                              comments, 
                              this.urls, 
                              _.bind(bhview.fnError, bhview), 
                              _.bind(this._resubmitCallback, this));

      $(this.view.resubmitUrlDialogSel).dialog('close');

   },
   _resubmitCallback: function(data, textStatus, jqXHR){

      var messages = data['message'].split(/;|,/);
      $(this.view.resubmitSuccessMessageSel).empty();
      for(var i=0; i<messages.length; i++){
         var mHtml = $('<p>' + messages[i] + '</p>');
         $(this.view.resubmitSuccessMessageSel).append(mHtml);
      }
      $(this.view.resubmitSuccessSel).dialog('open');

   },
   _resubmitCallbackEvent: function(data, textStatus, jqXHR){

      //This method is used when a URL resubmission event is fired from
      //another component
      this._resubmitCallback(data, textStatus, jqXHR);

      this.urlResubmissionEventData.callback();

      var bhview = this.model.getBHView(this.bhviewIndex);
      bhview.closeMenu();
      bhview.refresh();

   },
   _selectTextFromContextMenu: function(){
      if(this.contextMenuTarget){
         this.view.selectText(this.contextMenuTarget);
      }
   },
   _copyTextFromContextMenu: function(el){
      var text = "";
      if(this.contextMenuTarget){
         text = BHPAGE.unescapeHtmlEntities( $(this.contextMenuTarget).text() );
      }
      try {
         netscape.security.PrivilegeManager.enablePrivilege('UniversalXPConnect');
         const gClipboardHelper = Components.classes["@mozilla.org/widget/clipboardhelper;1"].
         getService(Components.interfaces.nsIClipboardHelper);
         gClipboardHelper.copyString(text);
      } catch(e) {
         alert("Javascript does not have access to the clipboard in your browser.  You can allow access by entering 'about:config' in the location bar in the browser and setting 'signed.applets.codebase_principal_support=true' or installing the AllowClipboard addon.  NOTE: This will only work in firefox.");
         return false;
      }
   },
   _openUrlFromContextMenu: function(el){
      //Open the url in a new window
      var href = $(this.contextMenuTarget).text();
      window.open(href);
   }
});
var BHViewCollectionView = new Class({

   Extends:View,

   jQuery:'BHViewCollectionView',

   initialize: function(selector, options){

      this.parent(options);

      this.urlBase = '/bughunter/views/';
      this.allViewsContainerSel = '#bh_view_container';
      this.resubmitUrlDialogSel = '#bh_resubmit_urls';
      this.resubmitUrlTextareaSel = '#bh_urls_container';
      this.resubmitCommentsSel = '#bh_resubmit_comments';
      this.resubmitSuccessSel = '#bh_resubmission_summary';
      this.resubmitSuccessMessageSel = '#bh_resubmission_message';

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
   },
   loadUrls: function(urls){

      $(this.resubmitUrlTextareaSel).empty();
      var seen = {};
      var count = 1;
      var uniqueUrls = [];
      for(var i=0; i<urls.length; i++){

         var escapedUrl = BHPAGE.escapeForUrl( urls[i] );

         //Don't load duplicate urls
         if( seen[ escapedUrl ] != true){

            uniqueUrls.push( escapedUrl );
            var row = '<tr><td>' + count + '</td>' + '<td>' + urls[i] + '</td></tr>';
            $(this.resubmitUrlTextareaSel).append( $(row) );

            seen[ escapedUrl ] = true;

            count++;
         }
      }

      return uniqueUrls;
   }
});

var BHViewCollectionModel = new Class({

   Extends:Model,

   jQuery:'BHViewCollectionModel',

   initialize: function(selector, options){

      this.parent(options);

      this.newViewUrl = '/bughunter/views';
      this.urlResubmissionUrl = '/bughunter/api/resubmit/';

      //An object acting like an associative array that holds
      //all views
      this.bhviewCollection = {};

      //The length of bhviewCollection
      this.length = 0;

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
   resubmitUrls: function(context, comments, urls, fnError, fnSuccess){

      var data = JSON.stringify( { "comments":comments,
                                   "urls":urls } );

      jQuery.ajax( this.urlResubmissionUrl, { accepts:'application/json',
                                              dataType:'json',
                                              cache:false,
                                              processData:false,
                                              type:'POST',
                                              data:data,
                                              context:context,
                                              error:fnError,
                                              success:fnSuccess });
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
   getLength: function(){
      return this.length;
   },
   getBHView: function(bhviewIndex){
      if( this.bhviewCollection[ bhviewIndex ] != undefined ){
        return this.bhviewCollection[bhviewIndex]; 
      }
   },
   getAllBHViewIndexes: function(){
      var indexTargets = [];
      for(var bhviewIndex in this.bhviewCollection){
         indexTargets.push(bhviewIndex);
      }
      return indexTargets;
   },
   getNewBHViewIndex: function(){
      for(var i=0; i<this.length; i++){
         //Use any view indexes that have been removed
         if(this.bhviewCollection[i] === undefined){
            return i;
         }
      }
      return this.length;
   },
   getDefaultBHView: function(){
      for( var bhviewName in  BHPAGE.navLookup ){
         if (_.isNumber( BHPAGE.navLookup[bhviewName]['default'] )){
            return bhviewName;
         }
      }
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
   addBHView: function(bhview, bhviewIndex){
      this.bhviewCollection[ bhviewIndex ] = bhview;
      this.length++;
   },
   removeBHView: function(bhviewIndex){

      if( this.bhviewRelationships[bhviewIndex] != undefined ){
         var parentIndex = this.bhviewRelationships[bhviewIndex]['parent'];
         if( this.bhviewRelationships[parentIndex] != undefined ){
            //Remove this child from parent's children
            delete(this.bhviewRelationships[parentIndex]['children'][bhviewIndex]);
         }
         //Remove this bhview
         delete(this.bhviewRelationships[bhviewIndex]);
         delete(this.bhviewCollection[bhviewIndex]);

         this.length--;
      }
   },
   loadNewChildWindow: function(newWin){
      this.childWindows.push(newWin);
   }
});

var ExternalLink = new Class({

   jQuery:'ExternalLink',

   initialize: function(selector, options){

      this.bugzillaBase = 'https://bugzilla.mozilla.org/buglist.cgi?quicksearch=ALL classification:"Client Software" OR classification:"Components" AND ';
      this.crashstatsBase = "http://crash-stats.mozilla.com/search/?signature=~";

      this.bugzillaFieldMap = { sig: { value:'sig:REP' },
                                url: { value:'url:REP' },
                                summary: { value:'summary:REP' },
                                content: { value:'summary:REP OR comment:REP' } };
   },
   getUrl: function(action, text){

      var url = "";
      var actionComponents = action.split('_');
      if(actionComponents.length >= 3){

         //ExternalLink actions have the following format
         // 2 letter link destination (bz bugzilla, cs crash-stats)_link type(sig, fm, url)_search target
         //bz_sig_socorro
         
         //escape the text for url based searching 
         text = BHPAGE.escapeForUrl(text);

         if(actionComponents[0] == 'bz'){

            url = this.getBugzillaUrl(actionComponents[1], actionComponents[2], text);

         }else if(actionComponents[0] == 'cs'){

            url = this.getCrashstatsUrl(actionComponents[1], actionComponents[2], text);

         }
      }
      return url;
   },
   getBugzillaUrl: function(fieldType, searchType, text){
      
      var key = searchType;
      var rep = '"' + text + '"'; 

      if(this.bugzillaFieldMap[searchType] === undefined){
         searchType = 'content';
      }

      var url = this.bugzillaBase + this.bugzillaFieldMap[searchType].value.replace(/REP/g, rep);
      return url;
   },
   getCrashstatsUrl: function(fieldType, searchType, text){
      var url = this.crashstatsBase + text; 
      return url;
   }
});

