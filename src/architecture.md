# IPRec Architecture

The IPRec flow consists of 3 main tasks: fuzzing an ip, recording both
the fuzzed designs and the input designs, and analyzing the recorded
input design against the records of the fuzzed library.

## Fuzzer

The fuzzer takes the name of a given Xilinx IP and generates a
json dictionary containing the possible values of every property of
the IP.  This is then used to generate a random sampling of designs,
each containing a single instance of the given IP with a randomized
configuration.  Each design is synthesized and prepared for recording.
In order to eliminate vivado, this library of synthesized designs would
have to be replicated.

## Recording

The recording scripts generate a json file containing the connectivity
information as well as properties of each node in the graph. The
connectivity information includes both hierarchical connections as well
as primitive pins, and information about driver pins for each net.
The node properties include cell type, parent cell, associated bel
and bel properties.  There is also a flatten variant that ignores
hierarchical information.  This is used for the input design, rather
than the fuzzed library.  To remove vivado from the flow, the json files
would have to be provided.

## Analysis

The analysis step takes place in pure python with the igraph library,
and thus does not rely on vivado at all.
