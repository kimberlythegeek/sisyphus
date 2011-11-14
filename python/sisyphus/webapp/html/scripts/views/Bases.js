var Page = new Class({

   Implements:Options,

   jQuery:'Page',

   initialize: function(selector, options){
      this.urlObj = jQuery.url(window.location);

      //Hardcoding here for speed, we need to encode/decode
      //lots of anchor values
      this.encodeHtmlEntities = [  [ new RegExp('&', 'g'), '&amp;' ],
                                   [ new RegExp('<', 'g'), '&lt;' ],
                                   [ new RegExp('>', 'g'), '&gt;' ],
                                   [ new RegExp('"', 'g'), '&quot;' ] ];

      this.decodeHtmlEntities = [  [ new RegExp('&amp;', 'g'), '&' ],
                                   [ new RegExp('&lt;', 'g'), '<' ],
                                   [ new RegExp('&gt;', 'g'), '>' ],
                                   [ new RegExp('&quot;', 'g'), '"' ] ];

   },
   registerSubscribers: function(subscriptionTargets, el, context){
      if(el === undefined){
         console.log( 'registerSubscribers error: el is undefined' );
      }
      for(var ev in subscriptionTargets){
         $( el ).bind(ev, {}, _.bind(function(event, data){
            if( _.isFunction( subscriptionTargets[ event.type ] ) ){
               data['event'] = event;
               _.bind( subscriptionTargets[ event.type ], context, data)();
            }else {
               console.log( 'registerSubscribers error: No function for ' + event.type );
            }
         }, context));
      }
   },
   unbindSubscribers: function(subscriptionTargets, el){
      for(var ev in subscriptionTargets){
         $(el).unbind( ev, subscriptionTargets[ev] );
      }
   },
   escapeHtmlEntities: function(str){
      for (var i=0; i<this.encodeHtmlEntities.length; i++){
         str = str.replace(this.encodeHtmlEntities[i][0], this.encodeHtmlEntities[i][1]);
      }
      return str;
   },
   unescapeHtmlEntities: function(str){
      if(str != undefined){
         for (var i=0; i<this.decodeHtmlEntities.length; i++){
            str = str.replace(this.decodeHtmlEntities[i][0], this.decodeHtmlEntities[i][1]);
         }
      }
      return str;
   }
});
var Component = new Class({

   Implements:Options,

   jQuery:'Component',

   initialize: function(selector, options){
   }
});
var Model = new Class({

   Implements:Options,

   jQuery:'Model',

   initialize: function(selector, options){
   }
});
var View = new Class({

   Implements:Options,

   jQuery:'View',

   initialize: function(selector, options){
   },
   getControlPanelValues: function(cpDropdownSel){

      var values = { r:[], p:[] };

      var selectMenus = $(cpDropdownSel).find('select');
      for(var i=0; i<selectMenus.length; i++){
         var v = $(selectMenus[i]).attr("value");
         this.loadSelectValue(v, values);
      }

      var inputs = $(cpDropdownSel).find('input', 'textarea');
      for(var i=0; i<inputs.length; i++){
         var type = $(inputs[i]).attr('type');
         if(type == 'text'){
            var ivalue = $(inputs[i]).val();
            var name = $(inputs[i]).attr('name');
            this.loadInputValue(name, ivalue, values);
         }
      }

      return values;
   },
   loadSelectValue: function(v, values){

      var fields = v.split('_');

      //field 0: will contain either r or p
      //field 1: is the index into a values array, this corresponds to the 
      //         order of arguments to be used in the webservice call
      //field 2: the value
      //
      //TODO: Need some good messaging here to let user know when a value
      //      formatted incorrectly
      var index = parseInt(fields[1]);
      values[ fields[0] ][ index ] = fields[2]; 
   },
   loadInputValue: function(name, ivalue, values){
      var fields = name.split('_');
      //field 0: will contain either r or p
      //field 1: is the index into a values array, this corresponds to the 
      //         order of arguments to be used in the webservice call
      var index = parseInt(fields[1]);
      values[ fields[0] ][ index ] = ivalue; 
   },
   getId: function(id, bhviewIndex){
      return id.replace(/\#/, '') + '_' + bhviewIndex;
   },
   getIdSelector: function(id, bhviewIndex){
      var newId = "";
      if(id.search(/^\#/) > -1){
         newId = id + '_' + bhviewIndex;
      }else{
         newId = '#' + id + '_' + bhviewIndex;
      }
      return newId;
   }

});
