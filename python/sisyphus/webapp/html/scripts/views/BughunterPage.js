var BHPAGE;

var BughunterPage = new Class( {

   Extends: Page,

   jQuery:'BughunterPage',

   initialize: function(selector, options){

      this.parent(options);
      this.allViewsContainerSel = '#bh_view_container';
      this.addBHViewEvent = 'ADD_BHVIEW';
      this.addBHViewEvent = 'ADD_BHVIEW';
      this.openCollectionEvent = 'OPEN_COLLECTION_BHVIEW';

      this.windowBaseName = "Bughunter ";
      this.pageCountName = 'bughunter_win_count';

      //Add new page
      this.addPageToLocalDB();
      var winName = this.getWindowName(this.windowBaseName);
      document.title = winName;

      //Make sure we adjust the page count variable in localStorage
      //when the window is closed
      window.onunload = _.bind(this.closeWindow, this);
   },
   getPageCount: function(){
      return parseInt(localStorage[this.pageCountName]);
   },
   getWindowName: function(baseName){
      return baseName + this.getPageCount();
   },
   getTargetOrigin: function(){
      var protocol = window.location.protocol;
      var hostname = window.location.host;
      return protocol + '//' + hostname;
   },
   addPageToLocalDB: function(){
      var pageCount = parseInt(localStorage[this.pageCountName] || 0);
      localStorage[this.pageCountName] = 1 + pageCount;
   },
   closeWindow: function(){
      var pCount = this.getPageCount();
      if(pCount > 1){
         localStorage[this.pageCountName] = pCount - 1;
      }else{
         //last page delete out of local storage
         delete(localStorage[this.pageCountName]);
      }
   },
   escapeForUrl: function(s, signal){
      return encodeURIComponent( BHPAGE.unescapeHtmlEntities(s) );
   },
   unescapeForUrl: function(s, signal){
      return decodeURIComponent( BHPAGE.unescapeHtmlEntities(s) );
   }

});

$(document).ready(function() {   

   BHPAGE = new BughunterPage();

   BHPAGE.navLookup = jQuery.parseJSON( $('#bh_nav_json' ).attr('value') );
   BHPAGE.BHViewCollection = new BHViewCollection('#BHViewCollection', {});

   var bhviewName = "";
   if( BHPAGE.urlObj.data.attr.fragment != undefined ){
      bhviewName = BHPAGE.urlObj.data.attr.fragment.replace('#', '');
   }

   BHPAGE.ConnectionsComponent = new ConnectionsComponent('#ConnectionsComponent', {});

   $(BHPAGE.allViewsContainerSel).trigger(BHPAGE.addBHViewEvent, { selected_bhview:bhviewName,
                                                                   display_type:'pane' } );

});
