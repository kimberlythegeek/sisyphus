var BHPAGE;

var BughunterPage = new Class( {

   Extends: Page,

   jQuery:'BughunterPage',

   initialize: function(selector, options){

      this.parent(options);
      this.allViewsContainerSel = '#bh_view_container';
      this.addBHViewEvent = 'ADD_BHVIEW';

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

   $(BHPAGE.allViewsContainerSel).trigger(BHPAGE.addBHViewEvent, { selectedView:bhviewName,
                                                                   displayType:'pane' } );

});
