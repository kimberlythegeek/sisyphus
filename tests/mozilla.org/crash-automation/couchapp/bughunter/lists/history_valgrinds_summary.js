function(head, req) {
  // !code lib/bughunter.js
  // !code lib/history_summaries.js
 var key_options = {name:  'Valgrind', field: 'valgrindsignature'};

  provides("html", history_summary_html);
}
