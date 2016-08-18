# -*- coding: utf-8 -*-
import io
import os
import sys

import click
import subprocess

ISORT_CONFIG = {
    'line_length': 100,
    'multi_line_output': 4,  # 4-vert-grid
}

EXTENSIONS = {'.py', '.cpp', '.c', '.h', '.hpp', '.hxx', '.cxx', '.java', '.js'}


@click.command()
@click.argument('files_or_directories', nargs=-1, type=click.Path(exists=True,
                                                                  dir_okay=True, writable=True))
@click.option('--check', default=False, is_flag=True, help='check if files are correctly formatted')
@click.option('--stdin', default=False, is_flag=True, help='read filenames from stdin (1 per line)')
@click.option('-c', '--commit', default=False, is_flag=True, help='use modified files from git')
def main(files_or_directories, check, stdin, commit):
    """Fixes and checks formatting according to ESSS standards."""
    import isort
    if stdin:
        files = [x.strip() for x in click.get_text_stream('stdin').readlines()]
    elif commit:
        files = get_files_from_git()
    else:
        files = []
        for file_or_dir in files_or_directories:
            if os.path.isdir(file_or_dir):
                for root, dirs, names in os.walk(file_or_dir):
                    files.extend(os.path.join(root, n) for n in names
                                 if os.path.splitext(n)[1] in EXTENSIONS)
            else:
                files.append(file_or_dir)
    changed_files = []
    errors = []
    for filename in files:
        extension = os.path.splitext(filename)[1]
        if extension in EXTENSIONS:
            with io.open(filename, 'r', encoding='UTF-8', newline='') as f:
                try:
                    old_contents = f.read()
                except UnicodeDecodeError as e:
                    msg = ': ERROR (%s: %s)' % (type(e).__name__, e)
                    error_msg = click.format_filename(filename) + msg
                    click.secho(error_msg, fg='red')
                    errors.append(error_msg)
                    continue
            if extension == '.py':
                sorter = isort.SortImports(file_contents=old_contents, **ISORT_CONFIG)
                # strangely, if the entire file is skipped by an "isort:skip_file"
                # instruction in the docstring, SortImports doesn't even contain a
                # "output" attribute
                new_contents = sorter.output if hasattr(sorter, 'output') else old_contents
            else:
                new_contents = old_contents
            new_contents = fix_whitespace(new_contents)
            changed = new_contents != old_contents
        else:
            click.secho(click.format_filename(filename) + ': Unknown extension', fg='white')
            continue
        if not check and changed:
            with io.open(filename, 'w', encoding='UTF-8', newline='') as f:
                f.write(new_contents)

        if changed:
            changed_files.append(filename)
        status, color = _get_status_and_color(check, changed)
        click.secho(click.format_filename(filename) + ': ' + status, fg=color)

    def banner(caption):
        caption = ' %s ' % caption
        fill = (100 - len(caption))  // 2
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


def fix_whitespace(old_contents):
    """
    Fix whitespace issues in the given list of lines.

    :param unicode old_contents:
        List of lines to fix spaces and indentations.

    :return unicode:
        Returns the new contents.
    """
    lines, eol, ends_with_eol = _split_lines_and_original_eol(old_contents)
    lines = [i.expandtabs(4) for i in lines]
    result = eol.join(lines)
    if ends_with_eol:
        result += eol
    return result


def _split_lines_and_original_eol(contents):
    """
    Splits the given text, removing the original eol but returning the eol
    so it can be written again on disk using the original eol.

    :param unicode contents: full file text
    :return: a triple (lines, eol, ends_with_eol), where `lines` is a list of
        strings, `eol` the string to be used as newline and `ends_with_eol`
        a boolean which indicates if the last line ends with a new line or not.
    """
    lines = contents.splitlines(True)
    eol = u'\n'
    if lines:
        if lines[0].endswith(u'\r'):
            eol = u'\r'
        elif lines[0].endswith(u'\r\n'):
            eol = u'\r\n'
    ends_with_eol = contents.endswith(eol)
    lines = [i.rstrip() for i in lines]
    return lines, eol, ends_with_eol


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
    return sorted(os.path.join(root, x) for x in result)


if __name__ == "__main__":
    main()
