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

rm -f $outputstem-[0-9]*.js

echo "creating $outputstem.js"
echo 'var comparisons = [];' > $outputstem.js

grep -h 'Spider Comparator: ' $inputlog | sed 's|.*Spider Comparator: ||' | while read -r line; do
  if echo $line | grep -q '^var comparisons'; then
      continue
  fi
  #if [[ $line == url_data\ =* ]]; then
  echo $line >> $outputstem.js
done