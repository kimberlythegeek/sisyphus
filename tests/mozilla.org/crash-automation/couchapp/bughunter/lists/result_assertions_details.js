function(head, req) {
  // !code lib/bughunter.js
  // !code lib/result_details.js
  var key_options = {name:  'Assertion', field: 'assertion'};

  provides("html", result_details_html);
}
