
var comparison;

var user_agent;
var user_agents = [];
var user_agent_hash = {};
var classifier_hash = {};
var classifier_list = [];
var user_agent_data;

if (comparisons.length > 0) {
  for (user_agent in comparisons[0].user_agents) {
    if (user_agent in user_agent_hash) {
      continue;
    }
    user_agents.push(user_agent);
    user_agent_hash[user_agent] = {
      page_total: 0,       // total number of pages
      page_media_total: 0, // total number of pages with media tags
      media_total: 0,      // total number of top level media tags
      classifier_hash: {},      // hash of counts for each media tag grouping classification
    };
  }
}

document.writeln('<table border="1">');

for (var idata = 0; idata < comparisons.length; idata++) {
  // each item in comparisons corresponds to a single url
  var data =  comparisons[idata];

  for each (user_agent in user_agents) {

    user_agent_hash[user_agent].page_total += 1;

    var media_element_ids = data.user_agents[user_agent].media_element_ids;
    // collect the html presentation both for display purposes but also for use as a key
    // as the visual presentation does a good job of grouping the relevant data.
    classify_media_elements(media_element_ids);
  }
}

document.writeln('<table border="1">');
document.writeln('<thead>');
document.writeln('<tr>');
document.writeln('<th>Classifier</th>');
for each (user_agent in user_agents) {
  user_agent_data = user_agent_hash[user_agent];
  document.writeln('<th>');
  document.writeln(user_agent);
  document.writeln('<ul>');
  document.writeln('<li>#pages           : ' + user_agent_data.page_total + '</li>');
  document.writeln('<li>#pages with media: ' + user_agent_data.page_media_total + '</li>');
  document.writeln('<li>#media elements  : ' + user_agent_data.media_total + '</li>');
  document.writeln('</ul>');
  document.writeln('</th>');
}
document.writeln('</tr>');
document.writeln('</thead>');
document.writeln('<tbody>');


for (classifier in classifier_hash) {
  classifier_list.push(classifier);
}
classifier_list.sort()

for each (classifier in classifier_list) {
  document.writeln('<tr>');
  document.writeln('<td>' + classifier + '</td>')
  for each (user_agent in user_agents) {
    user_agent_data = user_agent_hash[user_agent];
    document.writeln('<td>');
    document.writeln(user_agent_data.classifier_hash[classifier]);
    document.writeln('</td>');
  }
  document.writeln('</tr>');
}
document.writeln('</tbody>');
document.writeln('</table>');

function classify_media_elements(media_elements_ids) {
  var html = '';
  html += '<table>';
  if (media_element_ids.length > 0) {

    user_agent_hash[user_agent].page_media_total += 1;
    user_agent_hash[user_agent].media_total += media_element_ids.length;

    for each (var media_element_id in data.user_agents[user_agent].media_element_ids) {
      var media_element = media_element_hash[media_element_id];
      try {
        html += classify_media_element(media_element);
      }
      catch(ex) {
        var html_fragment = '<tr><td style="background-color: red;">Missing media_element ' + media_element_id + '</td></tr>';
        html += html_fragment;
        var classifier = '<table>' + html_fragment + '</table>';
        if (!(classifier in classifier_hash)) {
          classifier_hash[classifier] = 1;
        }

        if (!(classifier in user_agent_hash[user_agent].classifier_hash)) {
          user_agent_hash[user_agent].classifier_hash[classifier] = 0;
        }

        user_agent_hash[user_agent].classifier_hash[classifier] += 1;

      }
    }
  }
  else {
    html += '<tr><td>No Media</td></tr>';

    var classifier = '<table><tr><td>No Media</td></tr></table>';
    if (!(classifier in classifier_hash)) {
      classifier_hash[classifier] = 1;
    }

    if (!(classifier in user_agent_hash[user_agent].classifier_hash)) {
      user_agent_hash[user_agent].classifier_hash[classifier] = 0;
    }

    user_agent_hash[user_agent].classifier_hash[classifier] += 1;
  }
  html += '</table>';
  return html;
}

function classify_media_element(media_element) {
  var html = '';
  html += '<tr>';
  html += '<td>';
  html += media_element.tag;
  html += '</td>';

  if (media_element.media_types.length > 0) {
    html += '<td>media types';
    html += '<table>';
    for each (var media_type in media_element.media_types) {
      html += '<tr><td>' + media_type.toSource() + '</td></tr>';
    }
    html += '</table>';
    html += '</td>';
  }
  else {
    html += '<td>No Media Types</td>';
  }

  if (media_element.fallbacks.length > 0) {
    html += '<td>fallbacks';
    html += '<table>';
    for each (var fallback_media_id in media_element.fallbacks) {
      var fallback_media_element = media_element_hash[fallback_media_id];
      html += output_fallback_media_element(fallback_media_element);
    }
    html += '</table>';
    html += '</td>';
  }
  else {
//    html += '<td>No Fallbacks</td>';
  }
  html += '</tr>';

  var classifier = '<table>' + html + '</table>';
  if (!(classifier in classifier_hash)) {
    classifier_hash[classifier] = 1;
  }

  if (!(classifier in user_agent_hash[user_agent].classifier_hash)) {
    user_agent_hash[user_agent].classifier_hash[classifier] = 0;
  }

  user_agent_hash[user_agent].classifier_hash[classifier] += 1;

  return html;
}


function output_fallback_media_element(fallback_media_element) {
  var html = '';
  html += '<tr>';
  html += '<td>';
  html += fallback_media_element.tag;
  html += '</td>';

  if (fallback_media_element.media_types.length > 0) {
    html += '<td>media types';
    html += '<table>';
    for each (var media_type in fallback_media_element.media_types) {
      html += '<tr><td>' + media_type.toSource() + '</td></tr>';
    }
    html += '</table>';
    html += '</td>';
  }
  else {
    html += '<td>No Media Types</td>';
  }

  if (fallback_media_element.fallbacks.length > 0) {
    html += '<td>fallbacks';
    html += '<table>';
    for each (var fallback_fallback_media_id in fallback_media_element.fallbacks) {
      var fallback_fallback_media_element = media_element_hash[fallback_fallback_media_id];
      html += output_fallback_media_element(fallback_fallback_media_element);
    }

    html += '</table>';
  }
  else {
    //html += '<td>No Fallbacks</td>';
  }
  html += '</tr>';
  return html;
}

