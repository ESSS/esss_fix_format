# -*- coding: utf-8 -*-
import io
import os
import subprocess
import sys

import click


# This is a complete list of all modules in our stdlib which are not already known to isort
# This is a workaround for https://github.com/timothycrosley/isort/issues/464
all_stdlib_modules = ["Bastion", "CGIHTTPServer", "DocXMLRPCServer", "HTMLParser", "MimeWriter",
                      "SimpleHTTPServer", "UserDict", "UserList", "UserString", "aifc",
                      "antigravity", "ast",
                      "audiodev", "bdb", "binhex", "cgi", "chunk", "code", "codeop", "colorsys",
                      "cookielib", "copy_reg",
                      "dummy_thread", "dummy_threading", "formatter", "fpformat", "ftplib",
                      "genericpath",
                      "htmlentitydefs", "htmllib", "httplib", "ihooks", "imghdr", "imputil",
                      "keyword", "macpath", "macurl2path",
                      "mailcap", "markupbase", "md5", "mimetools", "mimetypes", "mimify",
                      "modulefinder", "multifile", "mutex",
                      "netrc", "new", "nntplib", "ntpath", "nturl2path", "numbers", "opcode",
                      "os2emxpath", "pickletools", "popen2", "poplib", "posixfile", "posixpath",
                      "pty",
                      "py_compile", "quopri", "repr", "rexec", "rfc822", "runpy", "sets", "sgmllib",
                      "sha", "sndhdr", "sre",
                      "sre_compile", "sre_constants", "sre_parse", "ssl", "stat", "statvfs",
                      "stringold",
                      "stringprep", "sunau", "sunaudio", "symbol", "symtable", "telnetlib", "this",
                      "toaiff", "token",
                      "tokenize", "tty", "types", "user", "uu", "wave", "xdrlib", "xmllib"]

ISORT_CONFIG = {
    'line_length': 100,
    'multi_line_output': 4,  # 4-vert-grid
    'use_parentheses': True,
    # This is a workaround for https://github.com/timothycrosley/isort/issues/464
    'known_standard_library': all_stdlib_modules,
}

EXTENSIONS = {'.py', '.cpp', '.c', '.h', '.hpp', '.hxx', '.cxx', '.java', '.js'}


@click.command()
@click.argument('files_or_directories', nargs=-1, type=click.Path(exists=True,
                                                                  dir_okay=True, writable=True))
@click.option('-k', '--check', default=False, is_flag=True,
              help='check if files are correctly formatted')
@click.option('--stdin', default=False, is_flag=True,
              help='read filenames from stdin (1 per line)')
@click.option('-c', '--commit', default=False, is_flag=True,
              help='use modified files from git')
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
        if extension not in EXTENSIONS:
            click.secho(click.format_filename(filename) + ': Unknown extension', fg='white')
            continue

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
                continue

        new_contents = original_contents

        eol = _peek_eol(first_line)
        ends_with_eol = new_contents.endswith(eol)

        if extension == '.py':
            sorter = isort.SortImports(file_contents=new_contents, **ISORT_CONFIG)
            # strangely, if the entire file is skipped by an "isort:skip_file"
            # instruction in the docstring, SortImports doesn't even contain an
            # "output" attribute
            if hasattr(sorter, 'output'):
                new_contents = sorter.output

        new_contents = fix_whitespace(new_contents.splitlines(True), eol, ends_with_eol)
        changed = new_contents != original_contents

        if not check and changed:
            with io.open(filename, 'w', encoding='UTF-8', newline='') as f:
                f.write(new_contents)

        if changed:
            changed_files.append(filename)
        status, color = _get_status_and_color(check, changed)
        click.secho(click.format_filename(filename) + ': ' + status, fg=color)

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
        result = [x.decode(sys.getfilesystemencoding()) for x in result]
        root = root.decode(sys.getfilesystemencoding())
    return sorted(os.path.join(root, x) for x in result)


if __name__ == "__main__":
    main()
