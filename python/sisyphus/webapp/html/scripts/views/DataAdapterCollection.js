var DataAdapterCollection = new Class({
   /****************************
    * DataAdapterCollection holds an associative array
    * of BHViewAdapter classes.  These adapter classes enable
    * individual bhviews to deliver idiosyncratic behavior that
    * is unique to the data that they deliver.  Callers call
    * getAdapter('adapter_name') to retrieve a specific bhview adapter.
    * **************************/

   Extends:Options,

   jQuery:'BHViewAdapterCollection',

   initialize: function(selector, options){

      this.setOptions(options);

      //Holds a list of adapters.  The key should be found in
      //views.json in the data_adapter attribute.
      this.adapters = { 'named_fields':new BHViewAdapter(),
                        'new_crashes':new NewCrashesAdapter() };
   },

   getAdapter: function(adapter){

      if(this.adapters[adapter] === undefined){
         return this.adapters['named_fields'];
      }else{
         return this.adapters[adapter];
      }
   }
});
var BHViewAdapter = new Class({
   /**************************
    * The BHViewAdapter provides functionality for managing 
    * the generic bhview.  The public interface includes all
    * bhview functionality that might need to be specialized.
    * New types of bhviews can inherit from BHViewAdapter and
    * override the public interface where necessary.
    *
    *     Public Interface
    *     ----------------
    *     setControlPanelFields()
    *     processControlPanel()
    *     clearPanel()
    *     getDefaultParams()
    *     processData()
    **************************/
   Extends:Options,

   jQuery:'BHViewAdapter',

   initialize: function(selector, options){

      this.setOptions(options);

      this.mediaColumns = { crashreport:true,
                            log:true };
                           
      this.wrapColumns = { url:true,
                           steps:true };

      this.cpStartDateName = 'start_date';
      this.cpEndDateName = 'end_date';

      this.startDateSel = '#bh_start_date';
      this.endDateSel = '#bh_end_date';

      this.cellAnchorClassSel = '.bh-cell-contextanchor';
      this.cellMenuClassSel = '.bh-cell-contextmenu';

   },
   setControlPanelFields: function(controlPanelDropdownEl, data){
      /*********************
       * Sets the values of the input fields in the control panel.  These 
       * fields may need to be pre-loaded with default values or the data 
       * from a particular signal.
       *
       * Parameters:
       *   
       *    controlPanelDropdownEl - The control panel DOM element
       *
       *    data - signal data object
       *             data.signal - name of signal
       *             data.data - signal data
       * *******************/
      if(!_.isEmpty(data)){
         //this.clearPanel(controlPanelDropdownEl);
         var el = $(controlPanelDropdownEl).find('[name="' + data.signal + '"]');
         $(el).attr('value', this.unescapeForUrl(data.data));

         if(!_.isEmpty(data.date_range)){
            var startInput = $(controlPanelDropdownEl).find('[name="start_date"]');
            startInput.attr('value',  data.date_range.start_date );
            var endInput = $(controlPanelDropdownEl).find('[name="end_date"]');
            endInput.attr('value', data.date_range.end_date );
         }

      }else {
         var startInput = $(controlPanelDropdownEl).find('[name="start_date"]');
         startInput.attr('value',  $(this.startDateSel).val() );
         var endInput = $(controlPanelDropdownEl).find('[name="end_date"]');
         endInput.attr('value', $(this.endDateSel).val() );
      }
   },
   processControlPanel: function(controlPanelSel, data){
      /*************************
       * Translate the values of the control panel fields 
       * or signal data into a URL parameter string.
       *
       * Parameters:
       *    
       *    controlPanelSel - Control panel id selector
       *    data - signal data object
       *       data.signal - name of signal
       *       data.data - signal data
       **************************/
      var params = "";

      if(!_.isEmpty(data)){
         if(!_.isEmpty(data.date_range)){
            params = 'start_date=' + data.date_range.start_date + 
                     '&end_date=' + data.date_range.end_date + '&' + 
                     data.signal + '=' + data.data; 
         }else{
            params = data.signal + '=' + data.data; 
         }
      }else{

         var inputs = $(controlPanelSel).find('input');

         for(var i=0; i<inputs.length; i++){
            var type = $(inputs[i]).attr('type');
            if(type == 'text'){
               var name = $(inputs[i]).attr('name');
               var v = $(inputs[i]).val();
               if(!(v === "")){
                  params += name + '=' + this.escapeForUrl(v) + '&';
               }
            }
         }
         var textareas = $(controlPanelSel).find('textarea');
         for(var i=0; i<textareas.length; i++){
            var name = $(textareas[i]).attr('name');
            var v = $(textareas[i]).val();
            if(!(v === "")){
               params += name + '=' + this.escapeForUrl(v) + '&';
            }
         }
         params = params.replace(/\&$/, '');
      }

      return params;
   },
   getDateRangeParams: function(controlPanelDropdownEl){

      var start = "";
      var end = "";

      if($(controlPanelDropdownEl)[0] === undefined){
         //Menu has not been created take date range out of page
         start = $(this.startDateSel).val();
         end = $(this.endDateSel).val();
         console.log([start, end]);
      }else{
         //Menu has been created already
         var startInput = $(controlPanelDropdownEl).find('[name="start_date"]');
         start = startInput.val();
         var endInput = $(controlPanelDropdownEl).find('[name="end_date"]');
         end = endInput.val();
      }

      return { start_date:start, end_date:end };
   },
   clearPanel: function(controlPanelSel){
      /*******************
       * Clear all of the input fields in the control panel.
       *
       * Parameters:
       *    controlPanelSel - Control panel id selector
       ********************/
      var inputs = $(controlPanelSel).find('input');
      var textareas = $(controlPanelSel).find('textarea');
      for(var i=0; i<inputs.length; i++){
         $(inputs[i]).attr('value', '');
      }
      for(var i=0; i<textareas.length; i++){
         $(textareas[i]).attr('value', '');
      }
   },
   getDefaultParams: function(){
      /******************
       * Build the default URL parameter string.  In this case
       * use the date range embedded in the page.
       * ****************/
      var params = 'start_date=' + $(this.startDateSel).val() +
                   '&end_date=' + $(this.endDateSel).val();
      return params;
   },
   processData: function(dataObject, datatableObject, signals){
      /****************************
       * Carry out any data processing unique to the bhview.
       *
       * Parameters:
       *    dataObject - Deserialized json from server.
       *    datatableObject - datatable.js object
       *    signals - Associative array of signals that the bhview
       *              can receive/send
       * ***************************/

      if(dataObject.length >= 1 ){

         wrapFound = false;
         signalsFound = false;
         mediaFound = false;

         //Build column names and test for columns that need
         //special handling.  We want to avoid iterating through
         //dataObject if we can.
         _.each( _.keys(dataObject[0]), _.bind(function(d){
            if(this.wrapColumns[d]){
               wrapFound = true;
            } 

            if(signals != undefined){
               if(signals[d] == 1){
                  signalsFound = true;
               }
            }

            if(this.mediaColumns[d]){
               mediaFound = true;
            }

            datatableObject.aoColumns.push({ "mDataProp":d, "sTitle":d });

         }, this) );

         if(wrapFound || signalsFound || mediaFound){
            for(var i=0; i<dataObject.length; i++){
               if(wrapFound){
                  //URL encoded spaces, %2, breaks wrapping in HTML table rows.
                  //Tried using decodeURI() here but it fails, not sure why...
                  //Resorted to replaceing %2 explicitly.  Maybe a better place
                  //for this would be in the server side environment, so we don't 
                  //have to iterate over every row.  
                  for(var w in this.wrapColumns){
                     if(dataObject[i][w] != undefined){
                        var data = dataObject[i][w].replace(/\%2/g, ' ');
                        data = data.replace(/\n/g, ' ');
                        dataObject[i][w] = BHPAGE.escapeHtmlEntities(data);
                     }
                  }
               }

               if(signalsFound){
                  for(var s in signals){
                     var eclass = 'bh-signal-' + s;
                     if(dataObject[i][s] != undefined){
                        //This is a hack to exclude the 'no signature' string.
                        //If more cases like 'no signature' are found a different
                        //approach will be required.  Using equality in a conditional
                        //to optimize performance, it will fail if there's any variation
                        //in the string...
                        if(dataObject[i][s] != '(no signature)'){
                           var contextMenuHtml = $(this.cellAnchorClassSel).html();

                           dataObject[i][s] = '<div style="display:inline;"><a class="' + eclass + 
                                               '" href="#' + s + '">' + BHPAGE.escapeHtmlEntities(dataObject[i][s]) + 
                                               '</a>' + contextMenuHtml + '</div>';
                        }
                     }
                  }
               }

               if(mediaFound){
                  for(var m in this.mediaColumns){
                     if(dataObject[i][m] != undefined){
                        var mediaHref = "http://qp-bughunter/bughunter/media" + dataObject[i][m].replace(/^.*media/, '');
                        dataObject[i][m] = '<a target="_blank" href="' + mediaHref +
                                           '">' + mediaHref + 
                                           '</>';
                     }
                  }
               }
            }
         }
      }
   },
   escapeForUrl: function(s, signal){
      if(signal == 'url'){
         //Return space to %2
         s = s.replace(/ /g, '%2');
      }
      return encodeURIComponent( BHPAGE.unescapeHtmlEntities(s) );
   },
   unescapeForUrl: function(s, signal){
      if(signal == 'url'){
         s = s.replace(/\%2/g, ' ');
      }
      return decodeURIComponent( BHPAGE.unescapeHtmlEntities(s) );
   }
});
var NewCrashesAdapter = new Class({

   Extends:BHViewAdapter,

   jQuery:'NewCrashesAdapter',

   initialize: function(selector, options){
      this.setOptions(options);
      this.parent(options);
   },
   getDefaultParams: function(){
      /******************
       * Build the default URL parameter string.  In this case
       * the date range should just be today's date which is the end date.
       * ****************/
      var params = 'start_date=' + $(this.endDateSel).val();
      return params;
   },
   setControlPanelFields: function(controlPanelDropdownEl, data){
      if(!_.isEmpty(data)){
         //this.clearPanel(controlPanelDropdownEl);
         var el = $(controlPanelDropdownEl).find('[name="' + data.signal + '"]');
         $(el).attr('value', this.unescapeForUrl(data.data));

         if(!_.isEmpty(data.date_range)){
            var startInput = $(controlPanelDropdownEl).find('[name="start_date"]');
            startInput.attr('value',  data.date_range.start_date );
            var endInput = $(controlPanelDropdownEl).find('[name="end_date"]');
            endInput.attr('value', data.date_range.end_date );
         }

      }else {
         //Set start date only
         var startInput = $(controlPanelDropdownEl).find('[name="start_date"]');
         if(!startInput.val()){
            startInput.attr('value',  $(this.endDateSel).val() );
         }
      }
   }
});
