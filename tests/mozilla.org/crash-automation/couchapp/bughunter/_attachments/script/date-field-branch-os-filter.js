function stringifyfilter(filter, key_options) {
  var filterstringbuffer = [];

  if (filter) {

    /*
     * date type before: include if document's first date is prior
     * to the filter's start date
     *
     * date type after: include if document's first or last date is after
     * to the filter's start date.
     *
     * date type not before: include if document's first date is not prior
     * to the filter's start date.
     *
     * date type not after: include if document's last date is not after
     * to the filter's start date.
     *
     * Note: start_date <= end_date.
     * Note: not all combinations of start_date_type and end_date_type make
     *       sense.
     *
     *       start_date_type: before,   end_date_type: notbefore  => null set
     *       start_date_type: notafter, end_date_type: after      => null set
     *       start_date_type: notafter, end_date_type: not before => null set
     */

    if (filter.start_date_type == 'before')
      filterstringbuffer.push('Start Before ' + filter.start_date);
    else if (filter.start_date_type == 'after')
      filterstringbuffer.push('Start After ' + filter.start_date);
    else if (filter.start_date_type == 'notbefore')
      filterstringbuffer.push('Start Not before ' + filter.start_date);
    else if (filter.start_date_type == 'notafter')
      filterstringbuffer.push('Start Not after ' + filter.start_date);

    if (filter.end_date_type == 'before')
      filterstringbuffer.push('End Before ' + filter.end_date);
    else if (filter.end_date_type == 'after')
      filterstringbuffer.push('End After ' + filter.end_date);
    else if (filter.end_date_type == 'notbefore')
      filterstringbuffer.push('End Not before ' + filter.end_date);
    else if (filter.end_date_type == 'notafter')
      filterstringbuffer.push('End Not after ' + filter.end_date);

    if (filter.field)
      filterstringbuffer.push((key_options.name + ' matching ' + filter.field));

    if (filter.branches)
      filterstringbuffer.push('branches matching ' + filter.branches);

    if (filter.os)
      filterstringbuffer.push('OS matching ' + filter.os);

  }
  return filterstringbuffer.join(', ');
}

$(document).ready(

  function() {

    var filter = {};
    var querystrings = document.location.search.split('&');
    var querystring;
    var captures;

    for each(querystring in querystrings) {
      if ((captures = /filter=([^&]+)/.exec(querystring)))
        filter = JSON.parse(decodeURIComponent(captures[1]));
    }

    $("#filter_text").text(stringifyfilter(filter, key_options));

    var url = $.application.path + 'dialog/date-field-branch-os-filter.html';

    $("#modify_filter").click(
      function () {

        $(document.body).append("<div id='date_field_branch_os_dialog'></div>");
        var $dialog  = $("#date_field_branch_os_dialog");

        $dialog.load(url, function() {
          $(this).dialog({
            title: "Filter",
            height: 'auto',
            width: 'auto',
            modal:true,
            open: function () {
              var filter_form = $("#date_field_branch_os_filter_form");

              $("#start_date").datepicker({dateFormat: "yy-mm-dd"});

              if (filter.start_date_type == 'before')
                $("#start_date_type").val(["before"]);
              else if (filter.start_date_type == 'after')
                $("#start_date_type").val(["after"]);
              if (filter.start_date_type == 'notbefore')
                $("#start_date_type").val(["notbefore"]);
              else if (filter.start_date_type == 'notafter')
                $("#start_date_type").val(["notafter"]);

              $("#start_date").val(filter.start_date);

              $("#end_date").datepicker({dateFormat: "yy-mm-dd"});

              if (filter.end_date_type == 'before')
                $("#end_date_type").val(["before"]);
              else if (filter.end_date_type == 'after')
                $("#end_date_type").val(["after"]);
              else if (filter.end_date_type == 'notbefore')
                $("#end_date_type").val(["notbefore"]);
              else if (filter.end_date_type == 'notafter')
                $("#end_date_type").val(["notafter"]);

              $("#end_date").val(filter.end_date);

              $("#fieldvaluelabel").text(key_options.name);

              if (filter.field)
                $("#fieldvalue").val(filter.field);

              if (filter.branches) {
                var selectbranchesvalues = [];
                $("#selectbranches").find('option').each(
                  function (i) {
                    if (RegExp(filter.branches, 'i').test($(this).text()))
                      selectbranchesvalues.push($(this).text());
                  }
                );
                $("#selectbranches").val(selectbranchesvalues);
              }

              if (filter.os) {
                var selectosvalues = [];
                $("#selectos").find('option').each(
                  function (i) {
                    if (RegExp(filter.os, 'i').test($(this).text()))
                      selectosvalues.push($(this).text());
                  }
                );
                $("#selectos").val(selectosvalues);
              }

              $("#start_date_type").change(
                function () {
                  if ($(this).val() == "none")
                    $("#start_date").val('');
                });

              $("#end_date_type").change(
                function () {
                  if ($(this).val() == "none")
                    $("#end_date").val('');
                });

            },
            close: function () {
              ;
            },
            buttons: {
              "Apply Filter" : function () {

                filter = {};


                if ($("#start_date_type").val() != "none") {
                  filter.start_date_type = $("#start_date_type").val();
                  filter.start_date = $("#start_date").val();
                }

                if ($("#end_date_type").val() != "none") {
                  filter.end_date_type = $("#end_date_type").val();
                  filter.end_date = $("#end_date").val();
                }

                if ($("#fieldvalue").val())
                  filter.field = $("#fieldvalue").val();

                var selectbranches = $("#selectbranches").val();

                if (selectbranches && selectbranches.length)
                  filter.branches = selectbranches.join('|');

                var selectos = $("#selectos").val();

                if (selectos && selectos.length)
                  filter.os = selectos.join('|');

                var search = document.location.search;
                var filterjson = JSON.stringify(filter);

                if (search.indexOf('filter=') > -1)
                  search = search.replace(/filter={[^}]*}/, 'filter=' + filterjson);
                else
                  search += '&filter=' + filterjson;

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
