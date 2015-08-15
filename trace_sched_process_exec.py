#!/usr/bin/env python

import re
import sys

trace_dir = '/sys/kernel/debug/tracing'
event_dir = trace_dir + '/events/sched/sched_process_exec'


def WriteFile(file, str):
  f = open(file, 'w')
  f.write(str)
  f.close()
  
def ReadFile(file):
  f = open(file, 'r')
  s = f.read()
  f.close()
  return s

def ReadCmdline(pid_str):
  file = '/proc/%s/cmdline' % pid_str
  s = None
  try:
    data = ReadFile(file)
    s = ''
    for i in range(len(data)):
      c = data[i]
      if c == '\0':
        c = ' '
      s += c
  except IOError:
    #print "can't read cmdline for pid %s" % pid_str
    pass
  return s

def main(verbose):
  WriteFile(trace_dir + '/tracing_on', '0')
  WriteFile(trace_dir + '/current_tracer', 'nop')
  WriteFile(trace_dir + '/set_event', '')
  WriteFile(event_dir + '/enable', "1")
  WriteFile(trace_dir + '/tracing_on', '1')
  f = open(trace_dir + '/trace_pipe', 'r')
  try:
    while True:
      s = f.readline()
      if verbose:
        print s
      m = re.search(' pid=(\d+)', s)
      if m:
        pid_str = m.group(1)
        cmdline = ReadCmdline(pid_str)
        if cmdline:
          print 'new task %s, cmdline %s' % (pid_str, cmdline)
  finally:
    f.close()
    WriteFile(trace_dir + '/tracing_on', '0')

if __name__ == '__main__':
  verbose = False
  for arg in sys.argv:
    if arg == '-v':
      verbose = True
  main(verbose)
  