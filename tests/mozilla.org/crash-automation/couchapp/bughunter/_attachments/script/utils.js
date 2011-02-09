function findCSSRuleBySelector(selector) {
  var styleSheets = document.styleSheets;

  for (var i = 0; i < styleSheets.length; i++)
  {
    var styleSheet = styleSheets[i];
    for (var j = 0; j < styleSheet.cssRules.length; j++)
    {
      var cssRule = styleSheet.cssRules[j];
      if (cssRule.selectorText == selector)
        return cssRule;
    }
  }
  return null;
}
