#!/usr/bin/env python

import re
import subprocess
import sys
import time

trace_dir = '/sys/kernel/debug/tracing'
event_dir = trace_dir + '/events/sched/sched_stat_runtime'


def WriteFile(file, str):
  f = open(file, 'w')
  f.write(str)
  f.close()
  
def ReadFile(file):
  f = open(file, 'r')
  s = f.read()
  f.close()
  return s

def StartCommand(command):
  process = subprocess.Popen(command)
  return process

def HumanReadableNumber(number):
  s = ''
  while number >= 1000:
    if s != '':
      s = ',' + s
    s = ('%03d' % (number % 1000)) + s
    number /= 1000
  if s != '':
    s = ',' + s
  s = ('%d' % number) + s
  return s

def main(verbose, all_processes, selected_pid, command):
  WriteFile(trace_dir + '/tracing_on', '0')
  WriteFile(trace_dir + '/current_tracer', 'nop')
  WriteFile(trace_dir + '/set_event', '')
  WriteFile(event_dir + '/enable', "1")
  WriteFile(trace_dir + '/tracing_on', '1')
  
  start_time = time.time()
  
  process = StartCommand(command)
  if selected_pid == -1:
    selected_pid = process.pid
  
  f = open(trace_dir + '/trace_pipe', 'r')
  should_exit = False
  should_exit_time = 0
  total_runtime = 0
  try:
    while True:
      if not should_exit:
        if process.poll() != None:
          should_exit = True
          should_exit_time = time.time()
      if should_exit and (time.time() - should_exit_time > 3):
        break
      s = f.readline()
      if not all_processes:
        m = re.search(' pid=(\d+)', s)
        if m:
          pid = int(m.group(1))
          if selected_pid != pid:
            continue
        else:
          continue
      m = re.search(' runtime=(\d+) \[ns\]', s)
      if m:
        runtime = int(m.group(1))
        total_runtime += runtime
      if verbose:
        print s
  finally:
    f.close()
    WriteFile(trace_dir + '/tracing_on', '0')
    
  if not all_processes:
    end_time = should_exit_time
  else:
    end_time = time.time()
  
  print 'total elapsed time is %lf s.' % (end_time - start_time)
  print 'total runtime of %s is %s ns.' % (
          ('all processes' if all_processes else ("process %d" % selected_pid)),
          HumanReadableNumber(total_runtime))

def usage():
  print "Usage: %s [options] [command args]" % sys.argv[0]
  print "Monitor runtime of a new command."
  print '\t-a  calculate the runtime of all processes.'
  print "\t-h  print this help information."
  print "\t-p <pid>  print runtime for selected pid instead of the command."
  print '\t-v  print verbose data'
  print '\n'

if __name__ == '__main__':
  verbose = False
  all_processes = False
  selected_pid = -1
  command = ['sleep', '1000000']
  i = 1
  while i < len(sys.argv):
    arg = sys.argv[i]
    if arg == '-a':
      all_processes = True
    elif arg == '-h':
      usage()
      exit(0)
    elif arg == '-p':
      if i + 1 == len(sys.argv):
        raise Exception('no argument for -p option')
      selected_pid = int(sys.argv[i + 1])
      i += 1
    elif arg == '-v':
      verbose = True
    elif arg[0] != '-':
      break
    else:
      raise Exception('invalid option %s' % arg)
    i += 1
  if i < len(sys.argv):
    command = sys.argv[i:]
  if verbose:
    print "all processes: %d" % all_processes
    print "selected_pid: %d" % selected_pid
    print "run command: ", command
  main(verbose, all_processes, selected_pid, command)
  