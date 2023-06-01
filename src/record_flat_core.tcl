set f [open [lindex $argv 1] w]
open_checkpoint [lindex $argv 0]
record_flat_core $f
close $f
