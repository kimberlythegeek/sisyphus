function(head, req) {
  // !code vendor/couchapp/path.js
  // !code lib/bughunter.js
  // !code lib/history_summaries.js

  var key_options = {name:  'Assertion', field: 'assertion'};

  provides("html", history_summary_html);
}
