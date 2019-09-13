# Clize prints return values by default unless None is returned.
# We want this for help messages or if we don't save the output,

# check for and copy --output option (to decide if it's saved)
# (this is a bit kludgy - partial signature binding would be nicer,
# but clize doesn't support it easily)
import clize

from improver.cli.clize_routines import clizefy
from improver.cli.combine import combine_process


def preprocess_command(progname, command, *args):
    """Preprocess command before execution."""
    post_args = []
    outopt = '--output'
    for i, arg in enumerate(args, 1):
        if isinstance(arg, str) and arg.startswith(outopt):
            _, sep, output = arg.partition('=')
            if not sep:
                try:
                    output = args[i + 1]
                except IndexError:
                    output = ''
            post_args.extend([outopt, output])
            break
    return command, args, post_args


# alias to reuse in replacement later on
prep_cmd = preprocess_command


# helper function to execute the main CLI object
# (relaced later on to achieve subcommand chaining)
def process_command(progname, command, *args, verbose=False):
    """Common entry point for command execution."""
    result = CLI(progname, command, *args)
    if verbose:
        rtype = type(result)
        output = '%s.%s@%i' % (rtype.__module__, rtype.__name__, id(result))
        print(progname, command, *args, ' -> ', output)
    return result


# suppress output if saved already
def postprocess_command(progname, result, *post_args):
    """Postprocess result from command execution."""
    try:
        output = post_args[post_args.index('--output') + 1]
    except (ValueError, IndexError):
        return result  # we could reraise here to require output
    return


# IMPROVER main

@clizefy(with_output=False)
def main(progname: clize.parameters.pass_name,
         command: clize.Parameter.LAST_OPTION,
         *args,
         verbose: 'v' = False,
         command_preprocessor: clize.Parameter.IGNORE = None,
         command_processor: clize.Parameter.IGNORE = None,
         command_postprocessor: clize.Parameter.IGNORE = None):
    """IMPROVER post-processing toolbox

    Args:
        command (str):
            Command to execute
        args (tuple):
            Command arguments
        verbose (bool):
            Print executed commands

    See ``improver help [--usage] [command]`` for more information
    on available command(s).
    """
    command_preprocessor = command_preprocessor or preprocess_command
    command_processor = command_processor or process_command
    command_postprocessor = command_postprocessor or postprocess_command

    command, args, post_args = command_preprocessor(progname, command, *args)
    result = command_processor(progname, command, *args, verbose=verbose)
    return command_postprocessor(progname, result, *post_args)


# help command

@clizefy(
    with_output=False,
    help_names=(),  # no help --help
)
def improver_help(progname: clize.parameters.pass_name,
                  command=None, *, usage=False):
    """Show command help."""
    progname = progname.partition(' ')[0]
    args = [command, '--help', usage and '--usage']
    return process_command(progname, *filter(None, args))


# mapping of command names to CLI objects

cli_table = {
    'help': improver_help,
    'combine': combine_process,  # improver.cli.combine.process
    # 'nb_mask': nbmask_process,  # improver.cli.nbhood_iterate_with_mask.process
}

# main CLI object with subcommands

CLI = clize.Clize.get_cli(
    cli_table, description=main.cli.helper.description,
    footnotes="""See also improver --help for more information.""")

# NOTE: improver/cli/__main__.py could simply call `clize.run(main)`
# Then bin/improver can be almost as simple as: python -m improver.cli