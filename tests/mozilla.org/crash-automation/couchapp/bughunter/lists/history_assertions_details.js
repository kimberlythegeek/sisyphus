function(head, req) {
  // !code vendor/couchapp/path.js
  // !code lib/bughunter.js
  // !code lib/history_details.js

  var key_options = {name:  'Assertion', field: 'assertion'};

  provides("html", history_details_html);
}
