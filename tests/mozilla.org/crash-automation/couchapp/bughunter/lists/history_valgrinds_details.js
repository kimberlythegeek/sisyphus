function(head, req) {
  // !code lib/bughunter.js
  // !code lib/history_details.js
  var key_options = {name:  'Valgrind', field: 'valgrindsignature'};

  provides("html", history_details_html);
}
