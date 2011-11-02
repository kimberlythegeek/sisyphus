#!/bin/bash

usage() {
  echo "extract.sh inputlog outputstem"
  exit 2
}

if [[ ! -e $1 || -z "$2" ]]; then
  usage
fi

inputlog=$1
outputstem=$2

rm -f $outputstem-*.js

let comparison_counter=0
let comparison_per_page=1
let page_counter=0

echo "creating $outputstem-$page_counter.js"
echo 'var comparisons = [];' > $outputstem-$page_counter.js

grep '^Spider Comparator: ' $inputlog | sed 's|^Spider Comparator: ||' | while read -r line; do
  if echo $line | grep -q '^var comparisons'; then
      continue
  fi
  #if [[ $line == url_data\ =* ]]; then
  if echo $line | grep -q '^url_data *=' ; then
      let comparison_counter=comparison_counter+1
      if [[ $comparison_counter -gt $comparison_per_page ]]; then
          let comparison_counter=1
          let page_counter=page_counter+1
          echo "creating $outputstem-$page_counter.js"
          echo 'var comparisons = [];' >> $outputstem-$page_counter.js
      fi
  fi
  echo $line >> $outputstem-$page_counter.js
done