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
                                   ADD_BHVIEW:this.addBHView };

      BHPAGE.registerSubscribers(this.subscriptionTargets, 
                                 this.view.allViewsContainerSel,
                                 this);
   },
   getBHViewsBySignal: function(signal){
      return this.model.getBHViewsBySignal(signal);
   },
   getBHViewCount: function(){
      return this.model.getBHViewCount();
   },
   addBHView: function(data){
      
      var bhviewName = data.selectedView;
      var bhviewHash = BHPAGE.navLookup[bhviewName];

      //View has no pane version and can only be launched
      //as a new page
      if(bhviewHash && (bhviewHash.page_target != undefined)){
         //Check for any page targets
         var url = bhviewHash.page_target.replace('HASH', '#');
         window.open(url);
         return false;
      }

      if(data.displayType == 'page'){
         if(data.params){
            this.view.submitPostForm(this.model.newViewUrl, data.params, data.selectedView);
         }else{
            var url = this.model.newViewUrl + '#' + data.selectedView;
            window.open(url);
         }
      }else {
         var defaultView = false;

         if(!this.model.hasBHView(data.selectedView)){
            bhviewName = this.defaultBHViewName;
            defaultView = true;
         }

         var bhviewIndex = this.model.getBHViewIndex();

         var bhviewComponent = new BHViewComponent('#bhviewComponent', 
                                                 { bhviewName:bhviewName, 
                                                   bhviewIndex:bhviewIndex }); 
         if(defaultView){
            bhviewComponent.markAsDefault();
         }

         this.model.addBHView(bhviewComponent);
      }
   },
   closeBHView: function(data){
      var bhview = this.model.getBHView(data.bhviewIndex);
      this.model.removeBHView(bhview);
      bhview.destroy();
   },
   getAllBHViewNames: function(){
      return this.model.getAllBHViewNames();
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
   submitPostForm: function(newViewUrl, params, selectedView){

      var regex = /^(.*?)=(.*)$/;
      var match = regex.exec( params );

      //Make sure we have a match for a name/value pair
      if(!(match.length >= 3)){
         return;
      }

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

      //Set the name and value in an input field
      var hiddenField = document.createElement("input");
      hiddenField.setAttribute('type', 'hidden');
      hiddenField.setAttribute('name', match[1]);
      hiddenField.setAttribute('value', match[2]);
      form.appendChild(hiddenField);
      document.body.appendChild(form);
      form.submit();

      //Finished with the form, remove from DOM
      $(form).remove();
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
            //Some fews can only send signals not receive them, exclude from list
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
   removeBHView: function(bhviewIndex){
      this.bhviewCollection[bhviewIndex] = delete(this.bhviewCollection[bhviewIndex]);
   }
});
