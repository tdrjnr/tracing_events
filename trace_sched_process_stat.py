#!/usr/bin/env python

import re
import subprocess
import sys
import time

trace_dir = '/sys/kernel/debug/tracing'
runtime_event_dir = trace_dir + '/events/sched/sched_stat_runtime'
sleep_event_dir = trace_dir + '/events/sched/sched_stat_sleep'
wait_event_dir = trace_dir + '/events/sched/sched_stat_wait'
block_event_dir = trace_dir + '/events/sched/sched_stat_blocked'
iowait_event_dir = trace_dir + '/events/sched/sched_stat_iowait'
syscall_event_dir = trace_dir + '/events/syscalls/'
context_switch_event_dir = trace_dir + '/events/sched/sched_switch'


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

def main(verbose, all_processes, selected_pid, run_list, command):
  enable_block = False
  enable_runtime = False
  enable_sleep = False
  enable_wait = False
  enable_iowait = False
  enable_syscall = False
  enable_switch = False
  for item in run_list:
    if item == 'block':
      enable_block = True
    elif item == 'runtime':
      enable_runtime = True
    elif item == 'sleep':
      enable_sleep = True
    elif item == 'wait':
      enable_wait = True
    elif item == 'iowait':
      enable_iowait = True
    elif item == 'syscall':
      enable_syscall = True
    elif item == 'switch':
      enable_switch = True
    else:
      raise Exception('unknown run_item: %s' % item)
  
  WriteFile(trace_dir + '/tracing_on', '0')
  # Change tracer to reset the trace data.
  WriteFile(trace_dir + '/current_tracer', 'blk')
  WriteFile(trace_dir + '/current_tracer', 'nop')
  WriteFile(trace_dir + '/set_event', '')
  if enable_runtime:
    WriteFile(runtime_event_dir + '/enable', "1")
  if enable_sleep:
    WriteFile(sleep_event_dir + '/enable', '1')
  if enable_wait:
    WriteFile(wait_event_dir + '/enable', '1')
  if enable_block:
    WriteFile(block_event_dir + '/enable', '1')
  if enable_iowait:
    WriteFile(iowait_event_dir + '/enable', '1')
  if enable_syscall:
    WriteFile(syscall_event_dir + '/enable', '1')
  if enable_switch:
    WriteFile(context_switch_event_dir + '/enable', '1')
  WriteFile(trace_dir + '/tracing_on', '1')
  
  start_time = time.time()
  
  process = StartCommand(command)
  if selected_pid == -1:
    selected_pid = process.pid
  
  f = open(trace_dir + '/trace_pipe', 'r')
  should_exit = False
  should_exit_time = 0
  total_runtime = 0
  total_sleeptime = 0
  total_waittime = 0
  total_blocktime = 0
  total_iowait_time = 0
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
            total_process_time += int((timestamp - sched_in_timestamp) * 1e9)
            if in_kernel:
              total_kernel_time += int((timestamp - kernel_timestamp) * 1e9)
          else:
            continue
      else:      
        if not all_processes:
          if re.search(' sched_stat', s):
            # sched_stat_sleep can happen in other process's context.
            m = re.search(' pid=(\d+)', s)
          else:
            m = re.search('^\s+\S+-(\d+)', s)
          if m:
            pid = int(m.group(1))
            if selected_pid != pid:
              continue
          else:
            continue
        if re.search('sched_stat_runtime', s):
          m = re.search(' runtime=(\d+) \[ns\]', s)
          if m:
            runtime = int(m.group(1))
            total_runtime += runtime
        elif re.search('sched_stat_sleep', s):
          m = re.search(' delay=(\d+) \[ns\]', s)
          if m:
            sleeptime = int(m.group(1))
            total_sleeptime += sleeptime
        elif re.search('sched_stat_wait', s):
          m = re.search(' delay=(\d+) \[ns\]', s)
          if m:
            waittime = int(m.group(1))
            total_waittime += waittime
        elif re.search('sched_stat_blocked', s):
          m = re.search(' delay=(\d+) \[ns\]', s)
          if m:
            blocktime = int(m.group(1))
            total_blocktime += blocktime
        elif re.search('sched_stat_iowait', s):
          m = re.search(' delay=(\d+) \[ns\]', s)
          if m:
            iowait_time = int(m.group(1))
            total_iowait_time += iowait_time
        elif re.search(' sys_', s):
          m = re.search('(\d+\.\d+)', s)
          if m:
            timestamp = float(m.group(1))
            is_enter = (False if re.search('->', s) else True)
            if is_enter:
              in_kernel = True
              kernel_timestamp = timestamp
            else:
              in_kernel = False
              total_kernel_time += int((timestamp - kernel_timestamp) * 1e9)

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
  process_str = ('all processes' if all_processes else ("process %d" % selected_pid))
  if enable_runtime:
    print 'total runtime of %s is %s ns.' % (process_str, HumanReadableNumber(total_runtime))
  if enable_sleep:
    print 'total sleep time of %s is %s ns.' % (process_str, HumanReadableNumber(total_sleeptime))
  if enable_wait:
    print 'total wait time in runqueue of %s is %s ns.' % (process_str, 
                                                         HumanReadableNumber(total_waittime))
  if enable_block:
    print 'total block time of %s is %s ns.' % (process_str, HumanReadableNumber(total_blocktime))
  if enable_iowait:
    print 'total iowait time of %s is %s ns.' % (process_str, HumanReadableNumber(total_iowait_time))
  if enable_switch:
    print 'total process time of %s is %s ns.' % (process_str, HumanReadableNumber(total_process_time))
  if enable_syscall:
    print 'total kernel space time of %s is %s ns.' % (process_str, HumanReadableNumber(total_kernel_time))
  
  if enable_switch and enable_syscall:
    total_user_time = total_process_time - total_kernel_time
    print 'total user space time of %s is %s ns.' % (process_str, HumanReadableNumber(total_user_time))
  

def usage():
  print "Usage: %s [options] [command args]" % sys.argv[0]
  print "Monitor runtime of a new command."
  print '\t-a  calculate the runtime of all processes.'
  print "\t-h  print this help information."
  print "\t-p <pid>  print runtime for selected pid instead of the command."
  print '\t-r run_item1,run_item2,...'
  print '\t    Decide which items to calculate. Possibles items are:'
  print '\t      block  -- block time'
  print '\t      iowait  -- time waiting on io operations'
  print '\t      runtime -- time executing on a cpu'
  print '\t      sleep   -- time sleeping'
  print '\t      switch  -- time spent in the selected process'
  print '\t      wait    -- time waiting on the runqueue'
  print '\t      syscall -- time spent in kernel space'
  print '\t-v  print verbose data'
  print '\n'

if __name__ == '__main__':
  verbose = False
  all_processes = False
  selected_pid = -1
  command = ['sleep', '1000000']
  run_list = ['block', 'iowait', 'sleep', 'runtime', 'wait', 'syscall', 'switch']
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
    elif arg == '-r':
      if i + 1 == len(sys.argv):
        raise Exception('no argument for -r option')
      run_list = sys.argv[i + 1].split(',')
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
  
  if all_processes and ('switch' in run_list):
    raise Exception("`-r switch` can't be used together with `-a`")
  
  if not all_processes and not ('switch' in run_list) and ('syscall' in runlist):
    raise Exception("`-r syscall should be used together with `-a` or `-r switch`")
  
  if verbose:
    print "all processes: %d" % all_processes
    print "selected_pid: %d" % selected_pid
    print "run command: ", command
  main(verbose, all_processes, selected_pid, run_list, command)
  