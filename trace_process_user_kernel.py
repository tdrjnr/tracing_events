#!/usr/bin/env python

import re
import subprocess
import sys
import time

trace_dir = '/sys/kernel/debug/tracing'
syscall_event_dir = trace_dir + '/events/syscalls'
sched_switch_event_dir = trace_dir + '/events/sched/sched_switch'

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

def main(verbose, selected_pid, command):
  WriteFile(trace_dir + '/tracing_on', '0')
  # Change tracer to reset the trace data.
  WriteFile(trace_dir + '/current_tracer', 'blk')
  WriteFile(trace_dir + '/current_tracer', 'nop')
  WriteFile(trace_dir + '/set_event', '')
  WriteFile(syscall_event_dir + '/enable', "1")
  WriteFile(sched_switch_event_dir + '/enable', '1')
  WriteFile(trace_dir + '/tracing_on', '1')
  
  start_time = time.time()
  
  process = StartCommand(command)
  if selected_pid == -1:
    selected_pid = process.pid
  
  f = open(trace_dir + '/trace_pipe', 'r')
  should_exit = False
  should_exit_time = 0
  total_kernel_time = 0
  kernel_timestamp = 0
  in_kernel = False
  total_process_time = 0
  sched_in_timestamp = 0
  try:
    while True:
      if not should_exit:
        if process.poll() != None:
          should_exit = True
          should_exit_time = time.time()
      if should_exit and (time.time() - should_exit_time > 3):
        break
      s = f.readline()
      if re.search('sched_switch', s):
        m = re.search('(\d+\.\d+).*prev_pid=(\d+).*next_pid=(\d+)', s)
        if m:
          timestamp = float(m.group(1))
          prev_pid = int(m.group(2))
          next_pid = int(m.group(3))
          if next_pid == selected_pid:
            sched_in_timestamp = timestamp
            if in_kernel:
              kernel_timestamp = timestamp 
          elif prev_pid == selected_pid:
            print "timestamp - sched_in_timestamp = %lf" % (timestamp - sched_in_timestamp)
            total_process_time += int((timestamp - sched_in_timestamp) * 1e9)
            if in_kernel:
              total_kernel_time += int((timestamp - kernel_timestamp) * 1e9)
              kernel_timestamp = timestamp
          else:
            continue
      else:
        m = re.search('^\s+\S+-(\d+)', s)
        if m:
          pid = int(m.group(1))
          if selected_pid != pid:
            continue
        else:
          continue
        m = re.search('(\d+\.\d+)', s)
        if m:
          timestamp = float(m.group(1))
          is_enter = (False if re.search('->', s) else True)
          if is_enter:
            in_kernel = True
            kernel_timestamp = timestamp
          else:
            in_kernel = False
            total_kernel_time = int((timestamp - kernel_timestamp) * 1e9)
        
      if verbose:
        print s
  finally:
    f.close()
    WriteFile(trace_dir + '/tracing_on', '0')
    
  end_time = should_exit_time
  
  print 'total elapsed time is %lf s.' % (end_time - start_time)
  process_str = ("process %d" % selected_pid)
  print 'total process time of %s is %s ns.' % (
          process_str, HumanReadableNumber(total_process_time))
  print 'total time spent in kernel of %s is %s ns.' % (
          process_str, HumanReadableNumber(total_kernel_time))
  total_user_time = total_process_time - total_kernel_time
  print 'total time spent in user space of %s is %s ns.' % (
          process_str, HumanReadableNumber(total_user_time))

def usage():
  print "Usage: %s [options] [command args]" % sys.argv[0]
  print "Monitor runtime of a new command."
  print "\t-h  print this help information."
  print "\t-p <pid>  print runtime for selected pid instead of the command."
  print '\t-v  print verbose data'
  print '\n'

if __name__ == '__main__':
  verbose = False
  selected_pid = -1
  command = ['sleep', '1000000']
  i = 1
  while i < len(sys.argv):
    arg = sys.argv[i]
    if arg == '-h':
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
    print "selected_pid: %d" % selected_pid
    print "run command: ", command
  main(verbose, selected_pid, command)
  