function(head, req) {
  // !code lib/bughunter.js
  // !code lib/result_details.js
  var key_options = {name:  'Valgrind', field: 'valgrindsignature'};

  provides("html", result_details_html);
}
