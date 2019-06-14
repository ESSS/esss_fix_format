import abc
import textwrap


class GitHook(metaclass=abc.ABCMeta):
    """
    Base class to define a Git hook usable by `hooks` task.
    """

    @abc.abstractmethod
    def name(self):
        """
        :rtype: unicode
        :return: Name of hook.
        """

    @abc.abstractmethod
    def script(self):
        """
        :rtype: unicode
        :return: Script code. Omit the shebang, as it is added later by a post-process step when
            hooks are installed in project.
        """


class FixFormatGitHook(GitHook):
    """
    A hook that prevents developer from committing unless it respects formats expected by
    our `fix-format` tool.
    """

    def name(self):
        return 'fix-format'

    def script(self):
        script = """\
        if ! which fix-format >/dev/null 2>&1
        then
            echo "fix-format not found, install in an active environment with:"
            echo "  conda install esss_fix_format"
            exit 1
        else
            git diff-index --diff-filter=ACM --name-only --cached HEAD | fix-format --check --stdin
            returncode=$?
            if [ "$returncode" != "0" ]
            then
                echo ""
                echo "fix-format check failed (status=$returncode)! To fix, execute:"
                echo "  ff -c"
                exit 1
            fi
        fi
        """
        return textwrap.dedent(script)


def _add_hook(hook):
    name = hook.name()
    if name not in _HOOKS:
        _HOOKS[name] = hook
    else:
        raise KeyError(f"A hook named '{name}' already exists")


# All hooks available by default
_HOOKS = {}
_add_hook(FixFormatGitHook())


def get_default_hook(name):
    """
    :param unicode name: Name of a hook.
    :rtype: GitHook
    :return: A Git hook object.
    """
    return _HOOKS[name]
