#!/bin/sh -e
events='modify move create delete'
ignore='./library/|./checkpoints/|^./data/|/\.|\.log$'
event_opts=$(echo $events | sed -E 's/^| / -e /g')

inotifywait -qq --exclude "$ignore" $event_opts -r .
clear

python -m unittest
exec $0
