function(head, req) {
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code lib/bughunter.js
  // !code lib/history_summaries.js

 var key_options = {name:  'Valgrind', field: 'valgrindsignature'};

  provides("html", history_summary_html);
}
