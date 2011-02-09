function(head, req) {
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code lib/bughunter.js
  // !code lib/result_details.js

  var key_options = {name:  'Valgrind', field: 'valgrindsignature'};

  provides("html", result_details_html);
}
