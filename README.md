The idea is to use the linux tracing system to enhance my control of the
system.

1. Use /sys/kernel/debug/tracing/events/task/task_rename to trace running
of new executables. I can use /proc/xxx/cmdline to print the cmdline. 