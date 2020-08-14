import io
import os.path


def find_ancestor_dir_with(filename, begin_in=None):
    """
    Look in current and ancestor directories (parent, parent of parent, ...) for a file.

    :param unicode filename: File to find.
    :param unicode begin_in: Directory to start searching.

    :rtype: unicode
    :return: Absolute path to directory where file is located.
    """
    if begin_in is None:
        begin_in = os.curdir

    base_directory = os.path.abspath(begin_in)
    while True:
        directory = base_directory
        if os.path.exists(os.path.join(directory, filename)):
            return directory

        parent_base_directory, current_dir_name = os.path.split(base_directory)
        if not current_dir_name:
            return None
        if not parent_base_directory:
            raise RuntimeError(f'Unable to find .git in the {begin_in} hierarchy.')
        base_directory = parent_base_directory


def add_hook(parts_dir, git_hook):
    """
    Adds an individual hook file to a folder with hook parts. An added hook is going to be executed
    by Git hooks like `pre-commit`, for instance, when installed using `invoke hooks` in a project.

    When a hook is added:

    * it prefixes its part file name with an index, so order of insertion is same order hook parts
      are executed;
    * it prefixes hook file with a header containing the shebang and a message printed to let
      developers name of hook in progress.

    :param unicode parts_dir: Folder containing hook files.
    :param GitHook|unicode git_hook: A git hook or its name. Name notation can only be used
        by hooks available by default though (see `hooks` to learn more).
    """
    import glob
    import stat

    from esss_fix_format.hooks import GitHook, get_default_hook

    if not isinstance(git_hook, GitHook):
        git_hook = get_default_hook(git_hook)

    count = len(glob.glob(f'{parts_dir}/*'))
    part_path = os.path.join(parts_dir, '{:05d}_{}'.format(count + 1, git_hook.name()))
    with io.open(part_path, 'w', newline='') as f:
        f.write("#!/bin/bash\n")
        f.write("\n")
        f.write('echo \u001b[34mHook {} in progress ....\u001b[0m\n'.format(git_hook.name()))
        f.write(git_hook.script())

    os.chmod(part_path, os.stat(part_path).st_mode | stat.S_IXUSR)


def add_default_pre_commit_hooks(pre_commit_parts_dir):
    """
    :param unicode pre_commit_parts_dir: Folder containing hook files.
    """
    add_hook(pre_commit_parts_dir, 'fix-format')


def install_pre_commit_hook(git_dir=None):
    """
    Install Git hooks in a project.
    """
    import stat
    import sys
    import textwrap

    # Creates a pre-commit file that runs other scripts located in `_pre-commit-parts` folder.
    # This folder is (re)created every time hooks are installed. It runs all parts, even if one
    # of them fails. If any part fails, pre-commit exits as failure.
    git_root = find_ancestor_dir_with('.git', git_dir)

    git_root = os.path.abspath(git_root)
    project_name = os.path.basename(git_root)
    print(f'{project_name} hooks')

    if not os.path.exists(os.path.join(git_root, '.git')):
        raise ValueError('Expected to find: {}'.format(os.path.join(git_root, '.git')))

    pre_commit_file = os.path.join(git_root, '.git', 'hooks', 'pre-commit')

    # when the repository is from a submodule, ".git" is actually a file; in that case we skip hook
    # installation
    # this was encountered when building the etk-simbr package
    if os.path.isfile(os.path.join(git_root, '.git')):
        print('Skipping hook installation, %s is a file' % os.path.join(git_root, '.git'))
        return

    pre_commit_parts_dir = os.path.join(git_root, '.git', 'hooks', '_pre-commit-parts')
    if os.path.isdir(pre_commit_parts_dir):
        import shutil
        shutil.rmtree(pre_commit_parts_dir)
    os.makedirs(pre_commit_parts_dir)

    pre_commit_contents = textwrap.dedent("""\
        #!/bin/bash
        # installed automatically by the "hooks" task, changes will be lost!

        echo `pwd`
        globalreturncode=0
        for i in `ls .git/hooks/_pre-commit-parts`;
        do
            .git/hooks/_pre-commit-parts/$i
            returncode=$?
            if [ "$returncode" != "0" ]
            then
                globalreturncode=1
            fi
        done
        exit $globalreturncode
    """)

    with io.open(pre_commit_file, 'w', newline='') as f:
        f.write(pre_commit_contents)

    add_default_pre_commit_hooks(pre_commit_parts_dir)

    if sys.platform.startswith('linux'):
        os.chmod(pre_commit_file, os.stat(pre_commit_file).st_mode | stat.S_IXUSR)
    print('Pre-commit hook installed: %s' % pre_commit_file)
