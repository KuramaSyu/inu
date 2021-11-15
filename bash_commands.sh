#!/bin/bash

main(){
    options = $1;
    echo options;
    for i in $(seq 1 ${#$options})
    do
        echo "Letter $i: ${word:i-1:1}"
    done
}

start(){
    cd inu/;
    python3 main.py;
}