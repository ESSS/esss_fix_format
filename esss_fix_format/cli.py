# -*- coding: utf-8 -*-
import codecs
import io
import os
import re
import subprocess
import sys

import click
import pydevf

CPP_PATTERNS = {
    '*.cpp',
    '*.c',
    '*.h',
    '*.hpp',
    '*.hxx',
    '*.cxx',
}

PATTERNS = {
    '*.py',
    '*.java',
    '*.js',
    '*.pyx',
    '*.pxd',
    'CMakeLists.txt',
    '*.cmake',
}.union(CPP_PATTERNS)


def is_cpp(filename):
    """Return True if the filename is of a type that should be treated as C++ source."""
    from fnmatch import fnmatch
    return any(fnmatch(os.path.basename(filename), p) for p in CPP_PATTERNS)


def should_format(filename):
    """Return True if the filename is of a type that is supported by this tool."""
    from fnmatch import fnmatch
    filename_no_ext, ext = os.path.splitext(filename)
    ipynb_filename = filename_no_ext + '.ipynb'
    # ignore .py file that has a jupytext configured notebook with the same base name
    if ext == '.py' and os.path.isfile(ipynb_filename):
        with open(ipynb_filename) as f:
            return 'jupytext' not in f.read()
    return any(fnmatch(os.path.basename(filename), p) for p in PATTERNS)


# caches which directories have the `.clang-format` file, *in or above it*, to avoid hitting the
# disk too many times
__HAS_DOT_CLANG_FORMAT = dict()


def should_use_clang_format(filename):
    filename = os.path.abspath(filename)
    path_components = filename.split(os.sep)[:-1]
    paths_to_try = tuple(
        os.sep.join(path_components[:i] + ['.clang-format'])
        for i in range(1, len(path_components) + 1))

    # From file directory, going upwards, find the first directory already cached
    for i in range(len(paths_to_try) - 1, -1, -1):
        path = paths_to_try[i]
        has_it = __HAS_DOT_CLANG_FORMAT.get(path, None)
        if has_it is not None:
            break

    if has_it:
        return True

    # Go downwards again, looking in the disk and filling the cache if found
    found = False
    for path in paths_to_try[i + 1:]:
        if found:
            __HAS_DOT_CLANG_FORMAT[path] = True
            continue
        found = __HAS_DOT_CLANG_FORMAT[path] = os.path.isfile(path)

    return found


_created_processes = []


def _wait_current_processes():
    '''
    Note: before actually starting a new process, make sure the previous have been
    collected. This should not really be a problem in practice, but when running unit-
    tests on windows starting a new process while another is on shutdown can sometimes
    raise:

    [WinError 6] The handle is invalid error

    inside of subprocess.Popen when launching the new javaw executable (haven't been able
    to find the reason this happens).
    '''
    if _created_processes:
        import time
        for process in _created_processes:
            curr_time = time.time()
            while process.poll() is None:
                time.sleep(.05)
                if time.time() - curr_time > 3:
                    raise AssertionError(
                        "Unable to run because a previously created formatter "
                        "process has not been properly killed.")
        del _created_processes[:]


@click.command()
@click.argument('files_or_directories', nargs=-1, type=click.Path(exists=True,
                                                                  dir_okay=True, writable=True))
@click.option('-k', '--check', default=False, is_flag=True,
              help='Check if files are correctly formatted.')
@click.option('--stdin', default=False, is_flag=True,
              help='Read filenames from stdin (1 per line).')
@click.option('-c', '--commit', default=False, is_flag=True,
              help='Use modified files from git.')
@click.option('--git-hooks', default=False, is_flag=True,
              help='Add git pre-commit hooks to the repo in the current dir.')
def main(files_or_directories, check, stdin, commit, git_hooks):
    """Fixes and checks formatting according to ESSS standards."""

    if git_hooks:
        from esss_fix_format.hook_utils import install_pre_commit_hook
        install_pre_commit_hook()  # uses the current directory by default.
        return

    formatter = []

    def format_code(code_to_format):
        if not formatter:
            _wait_current_processes()

            # Start-up pydevf server on demand.
            process = pydevf.start_format_server()
            formatter.append(process)
            _created_processes.append(process)
        return pydevf.format_code_server(formatter[0], code_to_format)

    try:
        return _main(files_or_directories, check, stdin, commit, format_code)
    finally:
        if formatter:
            # Stop pydevf if needed.
            pydevf.stop_format_server(formatter[0])


def _process_file(filename, check, format_code):
    '''
    :returns: a tuple with (changed, errors, formatter):
        - `changed` is a boolean, True if the file was changed
        - `errors` is a list with 0 or more error messages
        - `formatter` is an optional string with the formatter used (None if it does not apply)
    '''
    import isort.settings

    # Initialize results variables
    changed = False
    errors = []
    formatter = None

    if not should_format(filename):
        click.secho(click.format_filename(filename) + ': Unknown file type', fg='white')
        return changed, errors, formatter

    if is_cpp(filename):
        with io.open(filename, 'rb') as f:
            content_bytes = f.read()
            content = content_bytes.decode('UTF-8')
            # Remove all ASCII-characters, by substituting all printable ASCII-characters
            # with NULL character. Here, ' ' is the first printable ASCII-character (code 32)
            # and '~' is the last printable ASCII-character (code 126).
            non_ascii = re.sub('[ -~]', '', content).strip()
            use_bom = len(non_ascii) > 0
            if use_bom and not content_bytes.startswith(codecs.BOM_UTF8):
                msg = (
                    ': ERROR Not a valid UTF-8 encoded file, since it contains'
                    ' non-ASCII characters. Ensure it has UTF-8 encoding with BOM.'
                )
                error_msg = click.format_filename(filename) + msg
                click.secho(error_msg, fg='red')
                errors.append(error_msg)
                return changed, errors, formatter

    if is_cpp(filename) and should_use_clang_format(filename):
        formatter = 'clang-format'
        if check:
            output = subprocess.check_output(
                'clang-format -output-replacements-xml "%s"' % filename, shell=True)
            changed = b'<replacement ' in output
        else:
            mtime = os.path.getmtime(filename)

            # checking if the terminal command is valid
            # might throw an exception if clang-format is not recognized
            try:
                subprocess.check_output('clang-format -i "%s"' % filename, shell=True)
            except subprocess.CalledProcessError as e:
                msg = ': ERROR (%s: %s): ' % (type(e).__name__, e)
                msg += 'Please check if "clang-format" is installed and accessible'
                error_msg = click.format_filename(filename) + msg
                click.secho(error_msg, fg='red')
                errors.append(error_msg)
                return changed, errors, formatter

            changed = os.path.getmtime(filename) != mtime

        return changed, errors, formatter

    with io.open(filename, 'r', encoding='UTF-8', newline='') as f:
        try:
            # There is an issue with isort (https://github.com/timothycrosley/isort/issues/350,
            # even though closed it is not fixed!) that changes EOL to \n when there is a import
            # reorder.
            #
            # So to be safe, it is necessary to peek first line to detect EOL BEFORE any
            # processing happens.
            first_line = f.readline()
            f.seek(0)
            original_contents = f.read()
        except UnicodeDecodeError as e:
            msg = ': ERROR (%s: %s)' % (type(e).__name__, e)
            error_msg = click.format_filename(filename) + msg
            click.secho(error_msg, fg='red')
            errors.append(error_msg)
            return changed, errors, formatter

    new_contents = original_contents

    eol = _peek_eol(first_line)
    ends_with_eol = new_contents.endswith(eol)
    extension = os.path.normcase(os.path.splitext(filename)[1])

    if extension == '.py':
        settings_path = os.path.abspath(os.path.dirname(filename))
        settings_loaded = isort.settings.from_path(settings_path)
        if settings_loaded['line_length'] < 80:
            # The default isort configuration has 79 chars, so, if the passed
            # does not have more than that, complain that .isort.cfg is not configured.
            msg = ': ERROR .isort.cfg not available in repository (or line_length config < 80).'
            error_msg = click.format_filename(filename) + msg
            click.secho(error_msg, fg='red')
            errors.append(error_msg)

        sorter = isort.SortImports(file_contents=new_contents, settings_path=settings_path)
        # On older versions if the entire file is skipped (eg.: by an "isort:skip_file")
        # instruction in the docstring, SortImports doesn't even contain an "output" attribute.
        # In some recent versions it is `None`.
        new_contents = getattr(sorter, 'output', None)
        if new_contents is None:
            new_contents = original_contents

        try:
            # Pass code formatter.
            new_contents = format_code(new_contents)
        except Exception as e:
            error_msg = 'Error formatting code: %s' % (e,)
            click.secho(error_msg, fg='red')
            errors.append(error_msg)

        if new_contents and (new_contents[0] == codecs.BOM_UTF8.decode('UTF-8')):
            msg = ': ERROR python file should not have a BOM.'
            error_msg = click.format_filename(filename) + msg
            click.secho(error_msg, fg='red')
            errors.append(error_msg)
            new_contents = new_contents[1:]

    elif is_cpp(filename):
        formatter = 'legacy formatter'

    new_contents = fix_whitespace(new_contents.splitlines(True), eol, ends_with_eol)
    changed = new_contents != original_contents

    if not check and changed:
        with io.open(filename, 'w', encoding='UTF-8', newline='') as f:
            f.write(new_contents)

    return changed, errors, formatter


def _main(files_or_directories, check, stdin, commit, format_code):
    if stdin:
        files = [x.strip() for x in click.get_text_stream('stdin').readlines()]
    elif commit:
        files = get_files_from_git()
    else:
        files = []
        for file_or_dir in files_or_directories:
            if os.path.isdir(file_or_dir):
                for root, dirs, names in os.walk(file_or_dir):
                    files.extend(os.path.join(root, n) for n in names if should_format(n))
            else:
                files.append(file_or_dir)
    changed_files = []
    errors = []
    for filename in files:
        changed, new_errors, formatter = _process_file(filename, check, format_code)
        errors.extend(new_errors)
        if changed:
            changed_files.append(filename)
        status, color = _get_status_and_color(check, changed)
        msg = click.format_filename(filename) + ': ' + status
        if formatter is not None:
            msg += ' (' + formatter + ')'
        click.secho(msg, fg=color)

    def banner(caption):
        caption = ' %s ' % caption
        fill = (100 - len(caption)) // 2
        h = '=' * fill
        return h + caption + h

    if errors:
        click.secho('')
        click.secho(banner('ERRORS'), fg='red')
        for error_msg in errors:
            click.secho(error_msg, fg='red')
        sys.exit(1)
    if check and changed_files:
        click.secho('')
        click.secho(banner('failed checks'), fg='yellow')
        for filename in changed_files:
            click.secho(filename, fg='yellow')
        sys.exit(1)


def _get_status_and_color(check, changed):
    """
    Return a pair (status message, color) based if we are checking a file for correct
    formatting and if the file is supposed to be changed or not.
    """
    if check:
        if changed:
            return 'Failed', 'red'
        else:
            return 'OK', 'green'
    else:
        if changed:
            return 'Fixed', 'green'
        else:
            return 'Skipped', 'yellow'


def fix_whitespace(lines, eol, ends_with_eol):
    """
    Fix whitespace issues in the given list of lines.

    :param list[unicode] lines:
        List of lines to fix spaces and indentations.
    :param unicode eol:
        EOL of file.
    :param bool ends_with_eol:
        If file ends with EOL.

    :rtype: unicode
    :return:
        Returns the new contents.
    """
    lines = _strip(lines)
    lines = [i.expandtabs(4) for i in lines]
    result = eol.join(lines)
    if ends_with_eol:
        result += eol
    return result


def _strip(lines):
    """
    Splits the given text, removing the original eol but returning the eol
    so it can be written again on disk using the original eol.

    :param unicode contents: full file text
    :return: a triple (lines, eol, ends_with_eol), where `lines` is a list of
        strings, `eol` the string to be used as newline and `ends_with_eol`
        a boolean which indicates if the last line ends with a new line or not.
    """
    lines = [i.rstrip() for i in lines]
    return lines


def _peek_eol(line):
    """
    :param unicode line: A line in file.
    :rtype: unicode
    :return: EOL used by line.
    """
    eol = u'\n'
    if line:
        if line.endswith(u'\r'):
            eol = u'\r'
        elif line.endswith(u'\r\n'):
            eol = u'\r\n'
    return eol


def get_files_from_git():
    """Obtain from a list of modified files in the current repository."""

    def get_files(cmd):
        output = subprocess.check_output(cmd, shell=True)
        return output.splitlines()

    root = subprocess.check_output('git rev-parse --show-toplevel', shell=True).strip()
    result = set()
    result.update(get_files('git diff --name-only --diff-filter=ACM --staged'))
    result.update(get_files('git diff --name-only --diff-filter=ACM'))
    result.update(get_files('git ls-files -o --full-name --exclude-standard'))
    # check_output returns bytes in Python 3
    if sys.version_info[0] > 2:
        result = [os.fsdecode(x) for x in result]
        root = os.fsdecode(root)
    return sorted(os.path.join(root, x) for x in result)


if __name__ == "__main__":
    main()
