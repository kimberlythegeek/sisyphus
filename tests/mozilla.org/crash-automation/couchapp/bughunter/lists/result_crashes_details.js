function(head, req) {
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code lib/bughunter.js
  // !code lib/result_details.js

  var key_options = {name:  'Crash', field: 'crashsignature'};

  provides("html", result_details_html);
}
