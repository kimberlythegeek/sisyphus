var VisualizationCollection = new Class({

   Extends:Options,

   jQuery:'VisualizationCollection',

   initialize: function(selector, options){

      this.setOptions(options);

      //Holds a list of adapters.  The key should be found in
      //views.json in the data_adapter attribute.
      this.visualizations = { 'platform_tree':new PlatformTree() };

   },

   display: function(visName, data, selectors, signalData, callback){

      if(this.visualizations[visName] === undefined){
      }else{

         this.visualizations[visName].setSelectors(selectors);
         this.visualizations[visName].setSignalData(signalData);
         this.visualizations[visName].setCallback(callback);
         
         this.visualizations[visName].display(data);
      }
   }
});
var Visualization = new Class({

   Extends:Options,

   jQuery:'Visualization',

   initialize: function(options){

      this.setOptions(options);

      //Selectors for specific bhview this Visualization 
      //is operating on
      this.selectors = {};
      //Signal identification data for bhview
      this.signalData = {};
      //bhview callback to be called when signal is sent
      this.callback = undefined;

      //Node to select when first opening
      this.defaultNode;

      this.allViewsContainerSel = '#bh_view_container';

      this.signalEvent = 'SIGNAL_BHVIEW';

      this.sourceColorMap = { nightly:'#CBA3F8',
                              aurora:'#A2CDF7',
                              beta:'#FFE9A0' };

      this.bitsColorMap = { "32/32":"#B3A0CC", 
                            "64/32":"#9CB4C8", 
                            "32/64":"#F0E2B7", 
                            "64/64":"#A5A5CE" };

      this.platformColorMap = { "Linux 2.6.35":'#356CA1',
                                "Linux 2.6.41":'#113E69',
                                "Linux 2.6.40":'#062544',
                                "Linux 2.6.38":'#618BB4',
                                "Mac OS X 10.5":'#A2CDF7',
                                "Mac OS X 10.6":'#CBE4FB',
                                "Win NT 6.0":'#BBDDD0',
                                "Win NT 5.1":'#86BAA7',
                                "Win NT 6.1":'#33A17A' };

   },
   setSelectors: function(selectors){
      this.selectors = selectors;
   },
   setSignalData: function(signalData){
      this.signalData = signalData;
   },
   setCallback: function(callback){
      this.callback = callback;
   },
   clearContainers: function(selectors){

      $(selectors.graph_container).empty();
      $(selectors.sig_detail).empty();
      $(selectors.message_detail).empty();
      $(selectors.count_detail).empty();
      $(selectors.platform_detail).empty();
   }

});
var PlatformTree = new Class({

   Extends:Visualization,

   jQuery:'BHViewAdapter',

   initialize: function(options){

      this.setOptions(options);
      this.parent(options);

      //total count of primary key
      this.totalPrimaryCount = 0;
     
   },

   display: function(data){

      this.clearContainers(this.selectors);

      var graphSel = this.selectors.graph_container;
      var detailSel = this.selectors.detail_container;

      var tree = this.adaptData(data);
      var labels = this._getDetailLabels();
      this._setDetailLabels(labels);

      this.sbGraph = new $jit.Sunburst({

         injectInto:graphSel.replace('#', ''),
         levelDistance: 72,
         width: 750,
         height: 740,

         Node: {
            overridable: true,
            type: 'gradient-multipie'
         },

         Label: {
            type: 'Native'
         },

         NodeStyles: {

            enable: true,
            type: 'Native',
            stylesClick: {
               'color': '#dd3333'  
            },  
            stylesHover: {  
               'color': '#dd3333'  
            }  
         },  
         Tips: {
            
            enable: true,
            onShow: function(tip, node){

               var html = "<div class=\"tip-title ui-state-highlight ui-widget ui-corner-all\">";
               var data = node.data;  
               html += "<div><b>" + data.type + ":</b> " + data.description + "</div>";  
               html += "<div><b>Count:</b> " + data.size + "</div>";  
               html += "</div>";
               tip.innerHTML = html;  
            }
         },

         Events: {

            enable:true,
            onClick: _.bind(this.selectNode, this)
         }

      });

      this.sbGraph.loadJSON(tree);
      this.sbGraph.refresh();

      var node = this.sbGraph.graph.getNode(this.defaultNode.id);
      this.selectNode(node);

   },

   selectNode:function(node){

      if(!node) return;

      this.sbGraph.rotate(node, 'animate', {  
         duration: 1000,  
         transition: $jit.Trans.Quart.easeInOut  
      });

      $(this.selectors.sig_detail).html(node.data.row[ this.primaryKey ]);
      $(this.selectors.message_detail).html(node.data.row[ this.secondaryKey ]);
            
      var sigCount = parseInt(node.data.row['Total Count']);
      var percentDistribution = Math.round( (sigCount/this.totalPrimaryCount)*100 );
      var totalCount = sigCount + ', ' + percentDistribution + '%';
      $(this.selectors.count_detail).html(totalCount);

      $(this.selectors.platform_detail).html(node.data.row['Platform']);

      if(node.data.type == 'Signature'){

         this.signalData.data = BHPAGE.escapeForUrl( node.data.row['signal_data'] );
         this.signalData.signal = node.data.row['signal_type'];
         this.callback(this.signalData);
         $(this.allViewsContainerSel).trigger(this.signalEvent, this.signalData); 

      }else {

         //Send text signal
         //this.signalData.data = BHPAGE.escapeForUrl( node.data.row['signal_data'] );
         //this.signalData.signal = 'bhtext';
         //this.signalData.data = node.data.description;
         //this.callback(this.signalData);
         //$(this.allViewsContainerSel).trigger(this.signalEvent, this.signalData); 

      }
   },

   adaptData:function(data){

      var tree = {
         "children":[ ],
         "data": {
            "$type":"none"
         },
         "id": "PlatformTree",
         "name": "PlatformTree"
      };
      var sigNodes = [];

      this.primaryKey = 'signature';
      this.secondaryKey = 'fatal_message';

      if(data[0].assertion != undefined){
         //adapt to assertion data
         this.primaryKey = 'assertion';
         this.secondaryKey = 'location';
      }else if(data[0].message != undefined){
         //adapt to valgrind data
         this.secondaryKey = 'message';
      }

      this.totalPrimaryCount = 0;

      this.dataLength = data.length;

      data.sort(this._sortData);

      for(var i=0; i<data.length; i++){

         var sig = data[i][this.primaryKey].match(/<a.*?\>(.*?)\<\/a\>/);
         if(!sig){
            continue;
         }

         var sigText = sig[1];
         var sliceSize = parseInt(data[i]['Total Count']);
         this.totalPrimaryCount += sliceSize;
         var sources = data[i]['Platform'].split('<br />');

         data[i]['signal_data'] = sigText;
         data[i]['signal_type'] = this.primaryKey;

         var node = this._preparePrimaryNode(i, sigText, sliceSize, data);

         for(var j=0; j<sources.length; j++){

            if(!sources[j]){
               continue;
            }
            var s = sources[j].replace(/&nbsp;/g, ' ').replace(/\s+/g, ' '); 
            var sNameMatch = s.match(/^\<b\>(\S+)\<\/b\>:(.*)$/);

            if(sNameMatch){

               var sName = sNameMatch[1];
               var sourceLine = sNameMatch[2];
               var platforms = sourceLine.split(/\<\/b\>/);
               var totalCount = 0;
               var sNode = this._prepareSecondaryNode(sName, i, j, data);

               if(j == 0){
                  this.defaultNode = sNode;
               }

               for(var k=0; k<platforms.length; k++){

                  if(!platforms[k].match(/\S/)){
                     continue;
                  }
                  
                  var countMatch = platforms[k].match(/^(.*?)(\d+\/\d+).*?(\d+)$/);

                  var platformLine = platforms[k].replace(/\<b\>\d+/, '').
                                                  replace(/Windows/, 'Win').
                                                  replace(/\d+\/\d+/, '').
                                                  replace(/x86/, '').
                                                  replace(/^\s+|\s+$/g, '');
                  if(countMatch){
                     var platformName = countMatch[1];
                        
                     var platformCount = parseInt( countMatch[3] );

                     totalCount += platformCount;

                     var osNode = this._prepareOsNode(i, j, k, platformLine, platformCount, data);

                     var bits = countMatch[2];

                     var bitNode = this._prepareBitNode(i, j, k, bits, platformCount, data);

                     osNode.children.push(bitNode);

                     sNode.children.push(osNode);
                  }
               }
               sNode.data.size = totalCount;
               sNode.data["$angularWidth"] = totalCount;
               node.children.push(sNode);
            }
         }

         tree.children.push(node);
      }

      return tree;
   },
   _getNode: function(type){

      var id = "PlatformTree/signature/";

      if(type == "signature"){
         id = "PlatformTree/signature/";
      }else if(type == 'source'){
         id = "PlatformTree/signature/source/";
      }else if(type == 'platform'){
         id = "PlatformTree/signature/source/platform/";
      }else if(type == 'bits'){
         id = "PlatformTree/signature/source/platform/bits/";
      }
      var node = { 
               "children":[],
               "data": {
                  "$color": "#AEA9F8",
                  "description":"",
                  "fatal_message":"",
                  "$angularWidth":"",
                  "size":""
               },
               "id": id,
               "name": ""
       };

       return node;
   },
   _preparePrimaryNode: function(i, sigText, sliceSize, data){

      var node = this._getNode('signature');

      node.id += i + Math.random()*10;
      node.name = sigText.substring(0, 10);
      node.data.row = data[i];
      node.data.description = sigText;
      node.data.size = sliceSize;
      node.data.type = 'Signature';
      node.data["$angularWidth"] = sliceSize;

      return node;
   },
   _prepareSecondaryNode: function(sName, i, j, data){

      var sNode = this._getNode('source');

      sNode.id += i + j + Math.random()*10;
      sNode.name = sName;
      sNode.data.row = data[i];

      var color = this.sourceColorMap[sNode.name];
      if(color){
         sNode.data['$color'] = color;
      }

      sNode.data.description = sName;
      sNode.data.type = 'Source';

      return sNode;
   },
   _prepareOsNode: function(i, j, k, platformLine, platformCount, data){

      var osNode = this._getNode('platform');

      osNode.id += i + j + k + Math.random()*10;
      osNode.name = platformLine.substring(0, 15);
      osNode.data.row = data[i];
      osNode.data.description = platformLine;
      osNode.data.size = platformCount;
      osNode.data.type = 'OS';

      var color = this.platformColorMap[platformLine];
      if(color){
         osNode.data['$color'] = color;
      }

      osNode.data['$angularWidth'] = platformCount;

      return osNode;
   },
   _prepareBitNode: function(i, j, k, bits, platformCount, data){

      var bitNode = this._getNode('bits');

      bitNode.id += i + j + k + Math.random()*10;
      bitNode.name = bits;
      bitNode.data.row = data[i];
      bitNode.data.description = bits;
      bitNode.data.size = platformCount;
      bitNode.data.type = 'Architecture';

      var bitColor = this.bitsColorMap[bits];
      if(bitColor){
         bitNode.data['$color'] = bitColor;
      }

      bitNode.data["$angularWidth"] = platformCount;

      return bitNode;
   },
   _sortData: function(a, b){

      var aCount = parseInt(a['Total Count']);
      var bCount = parseInt(b['Total Count']);

      return aCount-bCount; 
   },
   _getDetailLabels: function(){
      
      var labels = { primary:'Signature',
                     secondary:'Fatal Message' };

      if(this.primaryKey == 'assertion'){
         labels.primary = 'Assertion';
         labels.secondary = 'Location';
      }else if(this.secondaryKey == 'message'){
         labels.primary = 'Signature';
         labels.secondary = 'Message';
      }

      return labels;
   },
   _setDetailLabels: function(labels){

      $(this.selectors.primary_label_detail).text(labels.primary);
      $(this.selectors.secondary_label_detail).text(labels.secondary);

   }
});
