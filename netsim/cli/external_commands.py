#
# Run external commands from netlab CLI
#
import typing
import os
import subprocess
from box import Box

from .. import common
from . import is_dry_run
from ..utils import strings

def print_step(n: int, txt: str, spacing: typing.Optional[bool] = False) -> None:
  if spacing:
    print()
  print("Step %d: %s" % (n,txt))
  print("=" * 60)

def stringify(cmd : typing.Union[str,list]) -> str:
  if isinstance(cmd,list):
    return " ".join(cmd)
  return str(cmd)

def run_command(
    cmd : typing.Union[str,list],
    check_result : bool = False,
    ignore_errors: bool = False,
    return_stdout: bool = False) -> typing.Union[bool,str]:

  if common.debug_active('cli'):
    print(f"Not running: {cmd}")
    return True

  if is_dry_run():
    print(f"DRY RUN: {cmd}")
    return True

  if common.VERBOSE:
    print(f".. executing: {cmd}")

  if isinstance(cmd,str):
    cmd = [ arg for arg in cmd.split(" ") if arg not in (""," ") ]

  try:
    result = subprocess.run(cmd,capture_output=check_result,check=True,text=True)
    if not check_result:
      return True
    if return_stdout:
      return result.stdout
    return result.stdout != ""
  except Exception as ex:
    if not common.QUIET and not ignore_errors:
      print( f"Error executing {stringify(cmd)}:\n  {ex}" )
    return False

def test_probe(p : str) -> bool:
  return bool(run_command(p,check_result=True))

def set_ansible_flags(cmd : list) -> list:
  if common.VERBOSE:
    cmd.append("-" + "v" * common.VERBOSE)

  if common.QUIET:
    os.environ["ANSIBLE_STDOUT_CALLBACK"] = "selective"

  return cmd

def run_probes(settings: Box, provider: str, step: int = 0) -> None:
  if step:
    print_step(step,"Checking virtualization provider installation",spacing = True)
  elif common.VERBOSE:
    print("Checking virtualization provider installation")
  for p in settings.providers[provider].probe:
    if not test_probe(p):
      common.fatal("%s failed, aborting" % p)
  if common.VERBOSE or step and not is_dry_run():
    print(".. all tests succeeded, moving on\n")

def start_lab(settings: Box, provider: str, step: int = 2, cli_command: str = "test", exec_command: typing.Optional[str] = None) -> None:
  if exec_command is None:
    exec_command = settings.providers[provider].start
  print_step(step,f"starting the lab -- {provider}: {exec_command}")
  if not run_command(exec_command):
    common.fatal(f"{exec_command} failed, aborting...",cli_command)

def deploy_configs(step : int = 3, command: str = "test", fast: typing.Optional[bool] = False) -> None:
  print_step(step,"deploying initial device configurations",spacing = True)
  cmd = ["netlab","initial"]
  if common.VERBOSE:
    cmd.append("-" + "v" * common.VERBOSE)

  if os.environ.get('NETLAB_FAST_CONFIG',None) or fast:
    cmd.append("--fast")

  if not run_command(set_ansible_flags(cmd)):
    common.fatal("netlab initial failed, aborting...",command)

def custom_configs(config : str, group: str, step : int = 4, command: str = "test") -> None:
  print_step(step,"deploying custom configuration template %s for group %s" % (config,group))
  cmd = ["netlab","config",config,"--limit",group]

  if not run_command(set_ansible_flags(cmd)):
    common.fatal("netlab config failed, aborting...",command)

def stop_lab(settings: Box, provider: str, step: int = 4, command: str = "test", exec_command: typing.Optional[str] = None) -> None:
  print_step(step,"stopping the lab",True)
  if exec_command is None:
    exec_command = settings.providers[provider].stop
  if not run_command(exec_command):
    common.fatal(f"{exec_command} failed, aborting...",command)
#
# Get a list of external tool commands to execute
#
def get_tool_command(tool: str, cmd: str, topology: Box) -> typing.Optional[list]:
  tdata = topology.defaults.tools[tool] + topology.tools[tool]
  topology[tool] = tdata                       # Enable 'tool.param' syntax in tool commands
  runtime = tdata.runtime or 'docker'
  if not runtime in tdata:
    print("... skipping {tool} tool, no {runtime} runtime configuration")
    return None
  if not tdata[runtime][cmd]:
    print("... skipping {tool} tool, no {runtime} {cmd} command")
    return None
  cmds = tdata[runtime][cmd]
  return cmds if isinstance(cmds,list) else [ cmds ]

#
# Execute external tool commands
#
def execute_tool_commands(cmds: list, topology: Box) -> None:
  for cmd in cmds:
    cmd = strings.eval_format(cmd,topology)
    run_command(cmd = [ 'bash', '-c', cmd ],check_result=True)
