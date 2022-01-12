#!/usr/bin/env python
import codecs
import io
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import mock
import pytest
from click.testing import CliRunner

from esss_fix_format import cli


@pytest.fixture
def sort_cfg_to_tmpdir(tmpdir):
    import shutil

    shutil.copyfile(
        os.path.join(os.path.dirname(__file__), "..", ".isort.cfg"), str(tmpdir.join(".isort.cfg"))
    )


@pytest.fixture
def dot_clang_format_to_tmpdir(tmpdir):
    import shutil

    shutil.copyfile(
        os.path.join(os.path.dirname(__file__), "..", ".clang-format"),
        str(tmpdir.join(".clang-format")),
    )


@pytest.fixture
def input_file(tmpdir, sort_cfg_to_tmpdir):
    # imports out-of-order included in example so isort detects as necessary to change
    source = textwrap.dedent(
        """\
            import sys
            import os

            alpha
            bravo\\s\\t\\s
            charlie
            \\tdelta
            echo
            foxtrot
            golf #Comment
            hotel
        """.replace(
            "\\s", " "
        ).replace(
            "\\t", "\t"
        )
    )
    filename = tmpdir.join("test.py")
    filename.write(source)

    return filename


def test_command_line_interface(input_file):
    check_invalid_file(input_file)
    fix_invalid_file(input_file)

    check_valid_file(input_file)
    fix_valid_file(input_file)


@pytest.mark.parametrize("eol", ["\n", "\r\n", "\r"], ids=["lf", "crlf", "cr"])
def test_input_eol_preserved(input_file, eol):
    contents = input_file.read("r")
    contents = contents.replace("\n", eol)
    input_file.write(contents.encode("ascii"), "wb")
    check_invalid_file(input_file)
    fix_invalid_file(input_file)

    for line in io.open(str(input_file), newline="").readlines():
        assert line.endswith(eol)


def test_directory_command_line(input_file, tmpdir):
    another_file = tmpdir.join("subdir", "test2.py").ensure(file=1)
    input_file.copy(another_file)

    output = run([str(tmpdir), "--verbose"], expected_exit=0)
    output.fnmatch_lines(
        [
            str(another_file) + ": Fixed",
            str(input_file) + ": Fixed",
            "fix-format: 2 files changed, 0 files left unchanged.",
        ]
    )


@pytest.mark.xfail(reason="this is locking up during main(), but works on the cmdline", run=False)
def test_stdin_input(input_file):
    runner = CliRunner()
    result = runner.invoke(cli.main, args=["--stdin"], input=str(input_file) + "\n")
    assert result.exit_code == 0
    assert str(input_file) in result.output


def test_fix_whitespace(input_file):
    obtained = cli.fix_whitespace(input_file.readlines(), eol="\n", ends_with_eol=True)
    expected = textwrap.dedent(
        """\
            import sys
            import os

            alpha
            bravo
            charlie
            \\s\\s\\s\\sdelta
            echo
            foxtrot
            golf #Comment
            hotel
        """.replace(
            "\\s", " "
        )
    )
    assert obtained == expected


def test_imports(tmpdir, sort_cfg_to_tmpdir):
    source = textwrap.dedent(
        """\
        import pytest
        import sys

        import io
        # my class
        class Test:
            pass
    """
    )
    filename = tmpdir.join("test.py")
    filename.write(source, "w")

    check_invalid_file(str(filename))
    fix_invalid_file(str(filename))

    expected = textwrap.dedent(
        """\
        import io
        import sys

        import pytest


        # my class
        class Test:
            pass
    """
    )
    assert filename.read("r") == expected


@pytest.mark.parametrize("verbose", [True, False])
def test_verbosity(tmp_path, input_file, verbose):
    # already in tmp_path: a py file incorrectly formatted and .isort.cfg
    # prepare extra files: a CPP file and a py file already properly formatted
    isort_fn = tmp_path / ".isort.cfg"
    assert isort_fn.is_file()

    input_cpp = "namespace boost {}  "
    cpp_fn = tmp_path / "foo.cpp"
    cpp_fn.write_text(input_cpp)

    py_ok = tmp_path / "aa.py"  # to appear as first file and simplify handling the expected lines
    py_ok.write_text("import os\n")

    # run once with --check and test output
    args = ["--check", str(tmp_path)]
    if verbose:
        args.append("--verbose")
    output = run(args, expected_exit=1)
    expected_lines = []
    if verbose:
        expected_lines = [
            str(isort_fn) + ": Unknown file type",
            str(py_ok) + ": OK",
        ]
    expected_lines.extend(
        [
            str(cpp_fn) + ": Failed (legacy formatter)",
            str(input_file) + ": Failed",
            "fix-format: 2 files would be changed, 1 files would be left unchanged.",
        ]
    )
    output.fnmatch_lines(expected_lines)

    # run once fixing files and test output
    args = [str(tmp_path)]
    if verbose:
        args.append("--verbose")
    output = run(args, expected_exit=0)
    expected_lines = []
    if verbose:
        expected_lines = [
            str(isort_fn) + ": Unknown file type",
            str(py_ok) + ": Skipped",
        ]
    expected_lines += [
        str(cpp_fn) + ": Fixed (legacy formatter)",
        str(input_file) + ": Fixed",
        "fix-format: 2 files changed, 1 files left unchanged.",
    ]
    output.fnmatch_lines(expected_lines)

    # run again with everything already fixed
    args = [str(tmp_path)]
    if verbose:
        args.append("--verbose")
    output = run(args, expected_exit=0)
    expected_lines = []
    if verbose:
        expected_lines = [
            str(isort_fn) + ": Unknown file type",
            str(py_ok) + ": Skipped",
            str(cpp_fn) + ": Skipped (legacy formatter)",
            str(input_file) + ": Skipped",
        ]
    expected_lines += [
        "fix-format: 3 files left unchanged.",
    ]
    output.fnmatch_lines(expected_lines)


def test_filename_without_wildcard(tmpdir, sort_cfg_to_tmpdir):
    filename = tmpdir.join("CMakeLists.txt")
    filename.write("\t#\n")
    output = run([str(filename), "--verbose"], expected_exit=0)
    output.fnmatch_lines(str(filename) + ": Fixed")


@pytest.mark.parametrize("param", ["-c", "--commit"])
def test_fix_commit(input_file, mocker, param, tmpdir):
    def check_output(cmd, *args, **kwargs):
        if "--show-toplevel" in cmd:
            result = str(tmpdir) + "\n"
        else:
            result = input_file.basename + "\n"
        if sys.version_info[0] > 2:
            result = os.fsencode(result)
        return result

    m = mocker.patch.object(subprocess, "check_output", side_effect=check_output)
    output = run([param, "--verbose"], expected_exit=0)
    output.fnmatch_lines(str(input_file) + ": Fixed")
    assert m.call_args_list == [
        mock.call("git rev-parse --show-toplevel", shell=True),
        mock.call("git diff --name-only --diff-filter=ACM --staged", shell=True),
        mock.call("git diff --name-only --diff-filter=ACM", shell=True),
        mock.call("git ls-files -o --full-name --exclude-standard", shell=True),
    ]


def test_input_invalid_codec(tmpdir, sort_cfg_to_tmpdir):
    """Display error summary when we fail to open a file"""
    filename = tmpdir.join("test.py")
    filename.write("hello world".encode("UTF-16"), "wb")
    output = run([str(filename)], expected_exit=1)
    output.fnmatch_lines(str(filename) + ": ERROR (Unicode*")
    output.fnmatch_lines("*== ERRORS ==*")
    output.fnmatch_lines(str(filename) + ": ERROR (Unicode*")


def test_empty_file(tmpdir, sort_cfg_to_tmpdir):
    """Ensure files with a single empty line do not raise an error"""
    filename = tmpdir.join("test.py")
    filename.write("\r\n", "w")
    run([str(filename)], expected_exit=0)


@pytest.mark.parametrize(
    "notebook_content, expected_exit",
    [
        ('"jupytext": {"formats": "ipynb,py"} ”', 0),
        ("Not a j-u-p-y-t-e-x-t configured notebook", 1),
        (None, 1),
    ],
)
@pytest.mark.parametrize("formatter", ["pydev", "black"])
def test_ignore_jupytext(tmpdir, sort_cfg_to_tmpdir, notebook_content, expected_exit, formatter):
    if formatter == "black":
        tmpdir.join("pyproject.toml").write_text("[tool.black]", "UTF-8")

    if notebook_content is not None:
        filename_ipynb = tmpdir.join("test.ipynb")
        filename_ipynb.write_text(notebook_content, "UTF-8")

    filename_py = tmpdir.join("test.py")
    py_content = textwrap.dedent(
        """\
        # -*- coding: utf-8 -*-
        # ---
        # jupyter:
        #   jupytext:
        #     formats: ipynb,py:light
        #     text_representation:
        #       extension: .py
        #       format_name: light
        #       format_version: '1.3'
        #       jupytext_version: 0.8.6
        #   kernelspec:
        #     display_name: Python 3
        #     language: python
        #     name: python3
        # ---
        # ”
        import    matplotlib.pyplot   as plt
    """
    )
    filename_py.write_text(py_content, "UTF-8")

    output = run([str(filename_py), "--check"], expected_exit=expected_exit)
    if formatter == "black":
        if expected_exit == 0:
            assert output.str() == "fix-format: 0 files would be left unchanged."
        else:
            output.fnmatch_lines(
                [
                    "*test.py: Failed",
                ]
            )
    else:
        assert formatter == "pydev"
        if expected_exit == 0:
            assert output.str() == "fix-format: 0 files would be left unchanged."
        else:
            output.fnmatch_lines(
                [
                    "*test.py: Failed",
                ]
            )


@pytest.mark.parametrize("check", [True, False])
def test_python_with_bom(tmpdir, sort_cfg_to_tmpdir, check):
    filename = tmpdir.join("test.py")
    original_contents = codecs.BOM_UTF8 + b"import io\r\n"
    filename.write(original_contents, "wb")

    args = [str(filename)]
    if check:
        args = ["--check"] + args

    run(args, expected_exit=1)

    current_contents = filename.read("rb")
    if check:
        assert current_contents == original_contents
    else:
        assert current_contents == original_contents[len(codecs.BOM_UTF8) :]


@pytest.mark.parametrize(
    "source",
    [
        "",
        '"""\nisort:skip_file\n"""\nimport sys\nimport os\n',
        "# isort:skip_file\nimport sys\nimport os\n",
    ],
    ids=[
        "empty file",
        "module-level isort:skip_file docstring",
        "module-level isort:skip_file comment",
    ],
)
def test_skip_entire_file(tmpdir, sort_cfg_to_tmpdir, source):
    filename = tmpdir.join("test.py")
    filename.write(source)
    output = run([str(filename), "--verbose"], expected_exit=0)
    output.fnmatch_lines(str(filename) + ": Skipped")
    assert filename.read() == source


def test_isort_bug_with_comment_headers(tmpdir, sort_cfg_to_tmpdir):
    source = textwrap.dedent(
        """\
        '''
        See README.md for usage.
        '''
        import os

        #===============================
        # Ask
        #===============================
        import io


        def Ask(question, answers):
            pass
    """
    )
    filename = tmpdir.join("test.py")
    filename.write(source)
    check_invalid_file(filename)
    fix_invalid_file(filename)
    check_valid_file(filename)


def test_missing_builtins(tmpdir, sort_cfg_to_tmpdir):
    source = textwrap.dedent(
        """\
        import thirdparty
        import os
        import ftplib
        import numbers
    """
    )
    filename = tmpdir.join("test.py")
    filename.write(source)
    check_invalid_file(filename)
    fix_invalid_file(filename)
    check_valid_file(filename)
    obtained = filename.read()
    assert obtained == textwrap.dedent(
        """\
        import ftplib
        import numbers
        import os

        import thirdparty
    """
    )


def test_force_parentheses(tmpdir, sort_cfg_to_tmpdir):
    source = (
        "from shutil import copyfileobj, copyfile, copymode, copystat,\\\n"
        "    copymode, ignore_patterns, copytree, rmtree, move"
    )
    filename = tmpdir.join("test.py")
    filename.write(source)
    check_invalid_file(filename)
    fix_invalid_file(filename)
    check_valid_file(filename)
    obtained = filename.read()
    expected = (
        "from shutil import (\n"
        "    copyfile, copyfileobj, copymode, copystat, copytree, ignore_patterns, move, rmtree)"
    )
    assert obtained == expected


def test_no_isort_cfg(tmpdir):
    filename = tmpdir.join("test.py")
    filename.write("import os", "w")
    try:
        output = run([str(filename)], expected_exit=1)
    except Exception:
        for p in tmpdir.parts():
            isort_cfg_file = p.join(".isort.cfg")
            if isort_cfg_file.exists():
                msg = "Test does not expect that .isort.cfg is in one of the tmpdir parents ({})"
                raise AssertionError(msg.format(isort_cfg_file))
        raise
    output.fnmatch_lines(
        r"*ERROR .isort.cfg not available in repository (or line_length config < 80)."
    )


def test_isort_cfg_in_parent(tmpdir, monkeypatch):
    """
    This test checks that a configuration file is properly read from a parent directory.
    This need to be checked because isort it self can fail to do this when passed a relative path.
    """
    # more than 81 character on the same line.
    source = (
        "from shutil import copyfileobj, copyfile, copymode, copystat, copymode, ignore_patterns,"
        " move, rmtree"
    )
    filename = tmpdir.ensure("subfolder", "test.py")
    filename.write(source, "w")

    cfg_filename = tmpdir.ensure(".isort.cfg")
    cfg_filename.write("[settings]\nline_length=81\nmulti_line_output=1\n", "w")

    monkeypatch.chdir(os.path.dirname(str(filename)))
    output = run(["."], expected_exit=0)
    output.fnmatch_lines("*test.py: Fixed")
    obtained = filename.read()
    expected = "\n".join(
        [
            "from shutil import (copyfile,",
            "                    copyfileobj,",
            "                    copymode,",
            "                    copystat,",
            "                    ignore_patterns,",
            "                    move,",
            "                    rmtree)",
        ]
    )
    assert obtained == expected


def test_install_pre_commit_hook(tmpdir):
    tmpdir.mkdir(".git")

    from esss_fix_format import hook_utils

    hook_utils.install_pre_commit_hook(str(tmpdir))
    assert tmpdir.join(".git", "hooks", "_pre-commit-parts").exists()


def test_install_pre_commit_hook_command_line(tmpdir):
    tmpdir.mkdir(".git")
    original = os.curdir
    os.curdir = str(tmpdir)
    try:
        run(["--git-hooks"], 0)
    finally:
        os.curdir = original
    assert tmpdir.join(".git", "hooks", "_pre-commit-parts").exists()


def test_missing_bom_error_for_non_ascii_cpp(tmpdir):
    """
    Throws an error for not encoding with "UTF-8 with BOM" of non-ascii cpp file.
    """
    source = "int     ŢōŶ;   "
    filename = tmpdir.join("a.cpp")
    filename.write_text(source, encoding="UTF-8")
    output = run([str(filename)], expected_exit=1)
    output.fnmatch_lines(
        str(filename) + ": ERROR Not a valid UTF-8 encoded file, since it contains non-ASCII*"
    )
    output.fnmatch_lines("*== ERRORS ==*")
    output.fnmatch_lines(
        str(filename) + ": ERROR Not a valid UTF-8 encoded file, since it contains non-ASCII*"
    )


def test_bom_encoded_for_non_ascii_cpp(tmpdir, dot_clang_format_to_tmpdir):
    """
    Formats non-ascii cpp as usual, if it has 'UTF-8 encoding with BOM'
    """
    source = "int     ŢōŶ;   "
    filename = tmpdir.join("a.cpp")
    filename.write_text(source, encoding="UTF-8-SIG")
    check_invalid_file(filename, formatter="clang-format")
    fix_invalid_file(filename, formatter="clang-format")
    check_valid_file(filename, formatter="clang-format")
    obtained = filename.read_text("UTF-8-SIG")
    assert obtained == "int ŢōŶ;"


def test_use_legacy_formatter_when_there_is_no_dot_clang_format_for_valid(tmpdir):
    """
    Won't format C++ if there's no `.clang-format` file in the directory or any directory above.
    """
    source = "int   a;"
    filename = tmpdir.join("a.cpp")
    filename.write(source)
    check_valid_file(filename, formatter="legacy formatter")
    obtained = filename.read()
    assert obtained == source


def test_use_legacy_formatter_when_there_is_no_dot_clang_format_for_invalid(tmpdir):
    source = "int   a;  "
    filename = tmpdir.join("a.cpp")
    filename.write(source)
    check_invalid_file(filename, formatter="legacy formatter")
    fix_invalid_file(filename, formatter="legacy formatter")
    check_valid_file(filename, formatter="legacy formatter")
    obtained = filename.read()
    assert obtained == "int   a;"


def test_clang_format(tmpdir, dot_clang_format_to_tmpdir):
    source = "int   a;  "
    filename = tmpdir.join("a.cpp")
    filename.write(source)
    check_invalid_file(filename, formatter="clang-format")
    fix_invalid_file(filename, formatter="clang-format")
    check_valid_file(filename, formatter="clang-format")
    obtained = filename.read()
    assert obtained == "int a;"


def test_missing_clang_format(tmpdir, mocker, dot_clang_format_to_tmpdir):
    source = "int   a;  "
    filename = tmpdir.join("a.cpp")
    filename.write(source)

    # Check for invalid format:
    # File will not pass in the format check
    check_invalid_file(filename, formatter="clang-format")

    expected_command = 'clang-format -i "main.cpp"'
    expected_error_code = 1

    # The '*' is used to indicate that there may be a '.' in
    # the message depending on the python version
    expected_error_message = "Command '%s' returned non-zero exit status 1*" % expected_command
    message_extra_details = 'Please check if "clang-format" is installed and accessible'

    mocker.patch.object(
        subprocess,
        "check_output",
        side_effect=subprocess.CalledProcessError(expected_error_code, expected_command),
    )

    # Check if the command-line instruction returned an exception
    # of type CalledProcessError with the correct error message
    check_cli_error_output(
        filename, expected_error_message, message_extra_details, formatter="clang-format"
    )

    # test should skip file, so no changes are made
    obtained = filename.read()
    assert obtained == source


def run(args, expected_exit):
    from _pytest.pytester import LineMatcher

    runner = CliRunner()
    result = runner.invoke(cli.main, args)
    msg = "exit code %d != %d.\nOutput: %s" % (result.exit_code, expected_exit, result.output)
    assert result.exit_code == expected_exit, msg
    return LineMatcher(result.output.splitlines())


def fix_valid_file(input_file):
    output = run([str(input_file), "--verbose"], expected_exit=0)
    output.fnmatch_lines(str(input_file) + ": Skipped")


def _get_formatter_msg(formatter):
    return (" (%s)" % formatter) if formatter is not None else ""


def check_valid_file(input_file, formatter=None):
    output = run(["--check", "--verbose", str(input_file)], expected_exit=0)
    output.fnmatch_lines(str(input_file) + ": OK" + _get_formatter_msg(formatter))


def fix_invalid_file(input_file, formatter=None):
    output = run([str(input_file), "--verbose"], expected_exit=0)
    output.fnmatch_lines(str(input_file) + ": Fixed" + _get_formatter_msg(formatter))


def check_cli_error_output(input_file, expected_error_message, message_details, formatter=None):
    output = run([str(input_file), "--verbose"], expected_exit=1)
    msg = ": ERROR (CalledProcessError: %s): " % (expected_error_message)
    msg += message_details
    output.fnmatch_lines(str(input_file) + msg)


def check_invalid_file(input_file, formatter=None):
    output = run(["--check", "--verbose", str(input_file)], expected_exit=1)
    output.fnmatch_lines(str(input_file) + ": Failed" + _get_formatter_msg(formatter))


def test_find_pyproject_toml(tmp_path, monkeypatch):
    (tmp_path / "pA/p2/p3").mkdir(parents=True)
    (tmp_path / "pA/p2/p3/foo.py").touch()
    (tmp_path / "pA/p2/p3/pyproject.toml").touch()
    (tmp_path / "pX/p9").mkdir(parents=True)
    (tmp_path / "pX/p9/pyproject.toml").touch()

    assert cli.find_pyproject_toml([tmp_path / "pA/p2/p3/foo.py", tmp_path / "pX/p9"]) is None
    assert cli.find_pyproject_toml([tmp_path / "pA/p2/p3"])
    assert cli.has_black_config(tmp_path / "pA/p2/p3/pyproject.toml") is False
    assert cli.find_pyproject_toml([tmp_path]) is None
    assert cli.find_pyproject_toml([]) is None

    (tmp_path / "pX/p9/pyproject.toml").write_text("[tool.black]")
    assert cli.find_pyproject_toml([tmp_path / "pA/p2/p3/foo.py", tmp_path / "pX/p9"]) is None
    assert cli.find_pyproject_toml([tmp_path / "pX/p9"]) == tmp_path / "pX/p9/pyproject.toml"
    assert cli.has_black_config(tmp_path / "pX/p9/pyproject.toml") is True

    root_toml = tmp_path / "pyproject.toml"
    (root_toml).write_text("[tool.black]")
    assert cli.find_pyproject_toml([tmp_path / "pA/p2/p3/foo.py", tmp_path / "pX/p9"]) == root_toml

    monkeypatch.chdir(str(tmp_path / "pA/p2"))
    assert cli.find_pyproject_toml(["."]) == root_toml


def test_black_integration(tmp_path, sort_cfg_to_tmpdir):
    (tmp_path / "pyproject.toml").write_text("[tool.black]")
    input_source = "import six\n" "import os\n" "x = [1,\n" "   2,\n" "  3]\n" "\n" "\n" "\n"
    py_file = tmp_path / "foo.py"
    py_file.write_text(input_source)

    # also write a cpp file to ensure black doesn't try to touch it
    input_cpp = "namespace boost {};"
    cpp_file = tmp_path / "foo.cpp"
    cpp_file.write_text(input_cpp)

    output = run(["--check", str(tmp_path), "--verbose"], expected_exit=1)
    output.fnmatch_lines(
        [
            "Checking black on 1 files...",
            "*foo.cpp: OK*",
            "fix-format: 1 files would be changed, 1 files would be left unchanged.",
        ]
    )
    obtained = py_file.read_text()
    assert obtained == input_source

    for i in range(2):
        output = run([str(tmp_path), "--verbose"], expected_exit=0)
        output.fnmatch_lines(
            [
                "Running black on 1 files...",
                "*foo.cpp: Skipped*",
            ]
        )
        obtained = py_file.read_text()
        assert obtained == ("import os\n" "\n" "import six\n" "\n" "x = [1, 2, 3]\n")


def test_skip_git_directory(input_file, tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git/dummy.py").touch()
    (tmp_path / ".git/dummy.cpp").touch()

    output = run([str(tmp_path)], expected_exit=0)
    output.fnmatch_lines(["fix-format: 1 files changed, 0 files left unchanged."])


def test_black_operates_on_chunks_on_windows(tmp_path, mocker, sort_cfg_to_tmpdir):
    """Ensure black is being called in chunks of at most 100 files on Windows.

    On Windows there's a limit on command-line size, so we call black in chunks there. On Linux
    we don't have this problem, so we always pass all files at once.
    """
    (tmp_path / "pyproject.toml").write_text("[tool.black]")
    for i in range(521):
        (tmp_path / f"{i:03}_foo.py").touch()

    return_codes = [1, 0, 1, 0, 1, 0]  # make black return failures in some batches
    mocker.patch.object(subprocess, "call", autospec=True, side_effect=return_codes)
    output = run([str(tmp_path), "--check"], expected_exit=1)
    output.fnmatch_lines(
        ["Checking black on 521 files...", "fix-format: 521 files would be left unchanged."]
    )
    call_list = subprocess.call.call_args_list
    if sys.platform.startswith("win"):
        expected = 6  # 521 files in batches of 100.
    else:
        expected = 1  # All files are passed at once.
    assert len(call_list) == expected


def test_exclude_patterns(tmp_path, monkeypatch):
    config_content = """[tool.esss_fix_format]
    exclude = [
        "src/drafts/*.py",
        "tmp/*",
    ]
    """
    config_file = tmp_path / "pyproject.toml"
    config_file.write_text(config_content)
    include_patterns = ["*.cpp", "*.py"]
    exclude_patterns = cli.read_exclude_patterns(config_file)
    monkeypatch.chdir(tmp_path)
    assert not cli.should_format("src/drafts/foo.py", include_patterns, exclude_patterns)[0]
    assert cli.should_format("src/drafts/foo.cpp", include_patterns, exclude_patterns)[0]
    assert not cli.should_format("tmp/foo.cpp", include_patterns, exclude_patterns)[0]
    assert cli.should_format("src/python/foo.py", include_patterns, exclude_patterns)[0]


def test_invalid_exclude_patterns(tmp_path):
    config_content = """[tool.esss_fix_format]
    exclude = "src/drafts/*.py"
    """

    config_file = tmp_path / "pyproject.toml"
    config_file.write_text(config_content)
    pytest.raises(TypeError, cli.read_exclude_patterns, config_file)


def test_git_ignored_files(tmp_path):
    # Smoke test for the get_git_ignored_files() function
    root = Path(__file__).parent.parent
    assert root.joinpath(".git").is_dir()
    ignored = cli.get_git_ignored_files(root)
    assert root.joinpath("environment.yml") in ignored

    # tmp_path is not tracked by git
    assert cli.get_git_ignored_files(tmp_path) == set()


def test_git_ignored_files_integration(tmp_path, monkeypatch, sort_cfg_to_tmpdir):
    # Write a file which is not properly formatted.
    content = textwrap.dedent(
        """
        x = [1,
        2,
            3,
            ]
    """
    )
    fn = tmp_path.joinpath("foo.py")
    fn.write_text(content)

    tmp_path.joinpath("pyproject.toml").write_text("[tool.black]")

    # Mock get_git_ignored_files() to ignore the badly formatted file.
    monkeypatch.setattr(cli, "get_git_ignored_files", lambda p: {fn})
    monkeypatch.chdir(tmp_path)
    run([str(".")], expected_exit=0)

    # Ensure the file has been properly ignored.
    assert fn.read_text() == content


def test_exclude_patterns_relative_path_fix(tmp_path, monkeypatch):
    config_content = """[tool.esss_fix_format]
    exclude = [
        "src/drafts/*.py",
        "tmp/*",
    ]
    """

    config_file = tmp_path / "pyproject.toml"
    run_dir = tmp_path / "src"
    run_dir.mkdir()
    config_file.write_text(config_content)
    monkeypatch.chdir(run_dir)
    include_patterns = ["*.py"]
    exclude_patterns = cli.read_exclude_patterns(config_file)
    assert not cli.should_format("drafts/foo.py", include_patterns, exclude_patterns)[0]


@pytest.mark.skipif(os.name != "nt", reason="'subst' in only available on Windows")
def test_exclude_patterns_error_on_subst(tmp_path, request, sort_cfg_to_tmpdir):
    import subprocess

    request.addfinalizer(lambda: subprocess.check_call(["subst", "/D", "Z:"]))
    subprocess.check_call(["subst", "Z:", str(tmp_path)])

    config_content = """[tool.esss_fix_format]
    exclude = [
        "src/drafts/*.py",
        "tmp/*",
    ]
    """
    config_file = tmp_path / "pyproject.toml"
    config_file.write_text(config_content)
    (tmp_path / "foo.py").touch()
    run(["Z:", "--check"], expected_exit=0)


def test_utf8_error_handling(tmpdir):
    file_with_no_uft8 = tmpdir.join("test.cpp")
    file_with_no_uft8.write("""é""".encode("UTF-16"), "wb")

    check_utf8_error(file_with_no_uft8)


def check_utf8_error(file):

    output = run(["--check", "--verbose", str(file)], expected_exit=1)
    output.fnmatch_lines(str(file) + ": ERROR The file contents can not be decoded using UTF-8")
