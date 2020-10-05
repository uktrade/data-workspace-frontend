#!/bin/bash

function run () {
   printf "%s\n" "$1"
   if $1; then
       printf "*** %s SUCCESSFUL ***\n" "$1"
   else
       printf "*** %s FAILED ***\n" "$1"
       exit 1
  fi
}
