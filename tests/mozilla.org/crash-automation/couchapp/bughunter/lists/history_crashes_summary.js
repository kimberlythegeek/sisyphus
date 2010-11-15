function(head, req) {
  // !code lib/bughunter.js
  // !code lib/history_summaries.js

 var key_options = {name:  'Crash', field: 'crashsignature'};

  provides("html", history_summary_html);
}
