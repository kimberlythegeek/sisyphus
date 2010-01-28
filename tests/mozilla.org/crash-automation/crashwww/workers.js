function showWorkers(view) {
  var workers = view.rows;
  var list = $("#workers-list");
  for(var i = 0; i < workers.length; i++) {
    var worker = workers[i].value;
    var state = getState(worker.state);
    var os = getOSName(worker.os_name, worker.os_version);

    var date = new Date(worker.datetime);
    var dateHTML = "<span class='expand' onclick='expandDate()'>" + formatDate(date) +  "</span>";
    dateHTML += "<div class='light-sub'>" + differenceString(date, new Date()) + " ago</div>";

    var stateHTML = "<span class='worker-" + state.state + "'>" + state.state + "</span>";
    if(state.build)
      stateHTML += " " + state.build;
    if(state.url) {
      var urlText = state.url
      if(urlText.length > 60)
        urlText = urlText.slice(0, 60) + "...";
        stateHTML += "<div><a href=" + state.url + " class='url light-sub' >" + urlText + "</a></div>";
    }
    list.append("<tr>"
                 + "<td>" + worker._id + "</td>"
                 + "<td>" + os + "</td>"
                 + "<td>" + stateHTML + "</td>"
                 + "<td>" + dateHTML + "</td></tr>");
  }
}


function getState(stateString) {
  var urlMatch = /^(.+?)\s+(.+)\s+(https?:\/\/[\w\.\-\/]*)/.exec(stateString);
  if(urlMatch)
     return {state: urlMatch[1],
             build: urlMatch[2],
             url : urlMatch[3] };
  return {state: stateString, url: ''};
}
