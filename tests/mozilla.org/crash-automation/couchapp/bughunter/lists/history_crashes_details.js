function(head, req) {
  // !code lib/bughunter.js
  // !code lib/history_details.js
  var key_options = {name:  'Crash', field: 'crashsignature'};

  provides("html", history_details_html);
}
