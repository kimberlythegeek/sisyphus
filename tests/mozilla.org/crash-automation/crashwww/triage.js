var signatures;

function getTriageList() {
  getJSON("/crashtest/_design/signatures/_view/results_needing_triage", showTriage);
}

function showTriage(view) {
  signatures = view.rows.map(function(doc){return doc.value;});

  if(!signatures.length)
    $("#message").text("No results to triage");
  else
    $("#triage-list").show();

  var list = $("#triage-list");

  for(var i = 0; i < signatures.length; i++) {
    var sig = signatures[i];

    var date = formatDate(new Date(sig.datetime));
    var os = getOSName(sig.os_name, sig.os_version);
    var platform = sig.cpu_name;
    var ffVersion = getMajorVersion(sig.major_version);
    var geckoVersion = getGeckoBranch(ffVersion);

    var workerHTML = "<div>" + sig.worker_id + "</div><div>" + os+ "</div><div>Firefox " + ffVersion + "</div>";

    var bugsHTML = '';
   /*
    var bugs = sig.bug_list.split(/[\,\ \;]/);
     for(var j = 0; j < bugs.length; j++) {
       bugsHTML += "<a href=http://bugzilla.mozilla.org/show_bug.cgi?id=" + bugs[j] + ">bug " + bugs[j] + "</a>";
          }
    if(bugs.length == 0) */
    var onClick = "showFileBug(" + i + ",'" + os + "', '" + platform + "', '" + geckoVersion + "')";
    bugsHTML = '<div class="file-bug" onclick="' + onClick + '">File</div>';

    var urlText = sig.url;
    if(urlText.length > 60)
      urlText = urlText.slice(0, 60) + "...";

    list.append("<tr id='sig-" + i + "'>"
           + "<td><a href=" + getMXRUrl(sig.signature) + " class='url signature'>" + sig.signature + "</a></td>"
           + "<td><a href=/ui/" + sig.url + " class='url'>" + urlText + "</a></td>"
           + "<td id='bug-" + i + "'>" + bugsHTML + "</td>"
           + "<td id='related-" + i + "'><div class='fetching'>...</div></td>"
           + "<td>" + workerHTML + "</td>"
           + "<td>" + date + "</td></tr>");

    var url = bugzillaRESTUrl + '/bug?summary=' + encodeURIComponent(sig.signature) 
           + '%20crash&summary_type=contains_all_words';
    getJSON(url, function(index) {return function(resp) {showSimilarBugs(resp, index);}}(i), showCertError);
  }
}

function showSimilarBugs(resp, index) {
  var buglist = $('#related-' + index);
  buglist.empty();
  var bugs = resp.bugs;
  var bugsHTML = [];
  for(var i = 0; i < bugs.length; i++)
    bugsHTML.push("<a href=" + bugUrl(bugs[i].id) + ">" + bugs[i].id + "</a>");
  buglist.append(bugsHTML.join(", "));
}

function showCertError() {
  $("#message").text("Please add the <a href='https://www.mozilla.com/certs/mozilla-root.crt'>Mozilla Root Certificate</a> to allow Bugzilla requests");
}

function getMXRUrl(sig) {
  if(/@/.test(sig))
    return; // it's a binary
  var lastFunc = /(.+\|)?\s*(.+)/.exec(sig)[2];
  var funcName = /([^\(]+)(\(.*\))?/.exec(lastFunc)[1];
  return "http://mxr.mozilla.org/mozilla-central/search?string=" + funcName;
}

function showFileBug(index, os, platform, version) {
  if($('#bug-password').val() == '')
    showBugLogin();
  else
    hideBugLogin();

  var sig = signatures[index];
  $("#bug-summary").val(" Crash [@ " + sig.signature + "]");
  $("#bug-url").val(sig.url);
  $("#bug-version").val(version);
  $("#bug-os").val(os);
  $("#bug-platform").val(platform);
  $("#file-bug-dialog").dialog("open");
  $("#bug-submit").click(function() {submitBug(index);});
  $("#bug-" + index).addClass("filing-bug");

  $("#bug-submitting").hide();
  $("#bug-submit-error").hide();
  $("#bug-submit-box").show();
}

function hideBugLogin() {
  $("#bug-login").hide();
  $("#bug-form").show();
  $("#bug-logged-in-login").text($("#bug-email").val());
}

function showBugLogin() {
  $("#bug-login").show();
  $("#bug-form").hide();  
}

function getBugzillaConfig() {
  getJSON(bugzillaRESTUrl + "/configuration?flags=0", 
         function(resp){bugzillaConfig = resp;});
}

function fillBugzillaConfig() {
  var index = 0;

  // first sort alpha
  var prods = [];
  for(var product in bugzillaConfig.product)
    prods.push(product);
  prods.sort();

  $("#bug-product").empty();
  for(var i = 0; i < prods.length; i++)
     $("#bug-product").append("<option value='" + prods[i] + "'>" + prods[i] + "</option>");

  $("#bug-product").val("Core");
  fillComponents("Core");
  $("#bug-component").val("General");
  $("#bug-product").change(function(){ fillComponents($("#bug-product").val()); });

  $("#bug-os").empty();
  var oses = bugzillaConfig.field.op_sys.values;
  for(var i = 0; i < oses.length; i++)
    $("#bug-os").append("<option value='" + oses[i] + "'>" + oses[i] + "</option>");

  $("#bug-platform").empty();
  var platform = bugzillaConfig.field.platform.values;
  for(var i = 0; i < platform.length; i++)
    $("#bug-platform").append("<option value='" + platform[i] + "'>" + platform[i] + "</option>");
}

function fillComponents(prod) {
  var comps = [];
  for(var comp in bugzillaConfig.product[prod].component)
    comps.push(comp);
  comps.sort();

  $("#bug-component").empty();
  for(var i = 0; i < comps.length; i++)
    $("#bug-component").append("<option value='" + comps[i] + "'>" + comps[i] + "</option>");

  $("#bug-version").empty();
  var vers = bugzillaConfig.product[prod].version;
  for(var i = 0; i < vers.length; i++)
    $("#bug-version").append("<option value='" + vers[i] + "'>" + vers[i] + "</option>");
}

function submitBug(index) {
  var bug = JSON.stringify({ product: $("#bug-product").val(),
                         component: $("#bug-component").val(),
                         url: $("#bug-url").val(),
                         summary: $("#bug-summary").val(),
                         version: $("#bug-version").val(),
                         op_sys: $("#bug-os").val(),
                         platform: $("#bug-platform").val(),
                         description: $("#bug-description").val()});
  var url = bugzillaRESTUrl + "/bug?username=" + $("#bug-email").val() + "&password=" + $("#bug-password").val();
  postJSON(url, bug, function(resp) { bugSubmitted(index, resp);}, function(resp) {bugError();});

  $("#bug-submitting").show();
  $("#bug-submit-error").hide();
  $("#bug-submit-box").hide();
}

function bugSubmitted(index, resp) {
  if(resp.error)
    return bugError(resp);

  var id = resp.ref.match(/\d+$/);
  $("#bug-" + index).empty();
  $("#bug-" + index).append("<a href=" + bugUrl(id) + ">bug " + id + "</a>");
  $("#file-bug-dialog").dialog('close');
  
  var sig = signatures[index];
  sig.triage = "Bug " + id;
  var url = "/crashtest/" + sig._id; 
  /* post bug id to db document */
  putJSON(url, JSON.stringify(sig), function() {}, function() {});
}

function bugError(resp) {
  $("#bug-submitting").hide();
  $("#bug-submit-error").show();
  $("#bug-submit-box").show();

  if(resp.message)
    $("#submit-error").text(resp.message);
  else
    $("#submit-error").text("Connection Error " + resp.status);
}

