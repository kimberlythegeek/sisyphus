var HPAGE;

var HelpPage = new Class( {

   jQuery:'HelpPage',

   initialize: function(selector, options){

      this.waitMessageSel = '#bh_help_spinner';
      this.helpContentSel = '#bh_help_content';
   }

});

$(document).ready(function() {   

   HPAGE = new HelpPage();

   //Toggle off wait message and display help contents
   $(HPAGE.waitMessageSel).addClass('hidden');
   $(HPAGE.helpContentSel).removeClass('hidden');
   
});
