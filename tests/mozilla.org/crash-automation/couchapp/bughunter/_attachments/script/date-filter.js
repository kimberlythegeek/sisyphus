function stringifykeys(startkey, endkey) {
  var filterstringbuffer = [];

  if (startkey) {
    filterstringbuffer.push('From ' + startkey);
  }

  if (endkey) {
    filterstringbuffer.push('To ' + endkey);
  }

  return filterstringbuffer.join(' ');
}

$(document).ready(

  function() {

    var startkey = '';
    var endkey   = '';
    var querystrings = document.location.search.split('&');
    var querystring;
    var captures;

    for each(querystring in querystrings) {
      if ((captures = /startkey=([^&]+)/.exec(querystring))) {
        startkey = JSON.parse(decodeURIComponent(captures[1]));
      }
      if ((captures = /endkey=([^&]+)/.exec(querystring))) {
        endkey = JSON.parse(decodeURIComponent(captures[1]));
      }
    }


    $("#filter_text").text(stringifykeys(startkey, endkey));


    var url = $.application.path + 'dialog/date-filter.html';

    $("#modify_filter").click(
      function () {

        $(document.body).append("<div id='date_dialog'></div>");
        var $dialog  = $("#date_dialog");

        $dialog.load(url, function() {
          $(this).dialog({
            title: "Filter",
            height: 'auto',
            width: 'auto',
            modal:true,
            open: function () {
              var filter_form = $("#date_filter_form");

              $("#fromdate").datepicker({dateFormat: "yy-mm-dd"});
              $("#todate").datepicker({dateFormat: "yy-mm-dd"});

              $("#fromdate").datepicker("setDate", startkey + "");
              $("#todate").datepicker("setDate", endkey + "");
            },
            close: function () {
              ;
            },
            buttons: {
              "Apply Filter" : function () {

                filter = {};

                if ($("#fromdate").val()) {
                  if (key_type == String)
                    startkey = $("#fromdate").val();
                  else if (key_type == Array)
                    startkey = [$("#fromdate").val()];
                }

                if ($("#todate").val()) {
                  if (key_type == String)
                    endkey = $("#todate").val();
                  else if (key_type == Array)
                    endkey = [$("#todate").val()];
                }

                var search = document.location.search;

                if (startkey) {
                  var startkeyjson = JSON.stringify(startkey);
                  if (search.indexOf('startkey=') == -1)
                    search += '&startkey=' + startkeyjson;
                  else {
                    if (key_type == Array)
                      search = search.replace(/startkey=\[[^\]]*\]/, 'startkey=' + startkeyjson);
                    else
                      search = search.replace(/startkey="[^"]*"/, 'startkey=' + startkeyjson);
                  }
                }

                if (endkey) {
                  var endkeyjson = JSON.stringify(endkey);
                  if (search.indexOf('endkey=') == -1)
                    search += '&endkey=' + endkeyjson;
                  else {
                    if (key_type == Array)
                      search = search.replace(/endkey=\[[^\]]*\]/, 'endkey=' + endkeyjson);
                    else
                      search = search.replace(/endkey="[^"]*"/, 'endkey=' + endkeyjson);
                  }
                }

                document.location.search = search;

              },
              "Close": function() {
                $(this).dialog("close");
              }
            }
          });

        });

      });

  });
