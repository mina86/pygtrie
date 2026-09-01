import os
import os.path
import re
import setuptools
import setuptools.command.build_py
import setuptools.command.sdist
import setuptools.errors
import shutil
import stat
import subprocess
import sys
import tempfile

import version


class BuildDocCommand(setuptools.Command):
    description = 'build Sphinx documentation'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        release = self.distribution.get_version()
        version = '.'.join(release.split('.', 2)[0:2])
        outdir = tempfile.mkdtemp() if self.dry_run else 'html'
        try:
            cmd = ('sphinx-build', '-Drelease=' + release,
                   '-n', '-Dversion=' + version, '.', outdir)
            print(' '.join(cmd), file=sys.stderr)
            subprocess.check_call(cmd)
        finally:
            if self.dry_run:
                shutil.rmtree(outdir)


class CommandMixin:
    @classmethod
    def _read_and_stat(cls, src):
        try:
            with open(src, encoding='utf-8') as fd:
                return fd.read(), os.fstat(fd.fileno())
        except OSError as e:
            raise setuptools.errors.FileError(
                "could not read from '{}': {}".format(src, e.strerror))

    @classmethod
    def _write(cls, dst, *data):
        if os.path.exists(dst):
            try:
                os.unlink(dst)
            except OSError as e:
                raise setuptools.errors.FileError(
                    "could not delete '{}': {}".format(dst, e.strerror))

        try:
            with open(dst, 'w', encoding='utf-8') as fd:
                for datum in data:
                    fd.write(datum)
        except OSError as e:
            raise FileError(
                "could not write to '{}': {}".format(dst, e.strerror))

    def copy_file(self, src, dst, preserve_mode=1, preserve_times=1,
                  link=None, level=1):
        m = None
        if src.endswith('.py'):
            data, st = self._read_and_stat(src)
            m = re.search("^(?:# *)?__version__ *= *'[^']*'(?: *#.*)?$",
                          data, re.MULTILINE)

        if not m:
            return super().copy_file(
                    src, dst, preserve_mode=preserve_mode,
                    preserve_times=preserve_times, link=link)

        if os.path.isdir(dst):
            directory = dst
            dst = os.path.join(dst, os.path.basename(src))
        else:
            directory = os.path.dirname(dst)

        if self.verbose:
            try:
                import distutils.log
                if os.path.basename(dst) != os.path.basename(src):
                    directory = dst
                distutils.log.info("generating %s -> %s", src, directory)
            except ImportError:
                # Python packaging is a mess, distuitils is deprecated or
                # something so just be prepared for the time it’s no longer
                # around.  We don’t want to fail just because we cannot output
                # log message.
                pass

        if not self.dry_run:
            self._write(dst,
                        data[:m.start(0)],
                        '__version__ = ',
                        repr(str(self.distribution.get_version())),
                        data[m.end(0):])
            if preserve_times:
                os.utime(dst, (st[stat.ST_ATIME], st[stat.ST_MTIME]))
            if preserve_mode:
                os.chmod(dst, stat.S_IMODE(st[stat.ST_MODE]))

        return (dst, 1)


class SDistCommand(CommandMixin, setuptools.command.sdist.sdist):
    pass

class BuildPyCommand(CommandMixin, setuptools.command.build_py.build_py):
    def get_data_files_without_manifest(self):
        return super().get_data_files_without_manifest()


def get_readme_lines():
    with open('README.rst', encoding='utf-8') as fd:
        skip = False
        skip_start = re.compile(r'^\.\. image:: https://'
                                r'(?:readthedocs\.org|api\.travis-ci\.com)/')
        for line in fd:
            if skip:
                skip = bool(line.strip())
            elif skip_start.search(line):
                skip = True
            else:
                yield line

    yield '\n'

    with open('version-history.rst', encoding='utf-8') as fd:
        version_re = re.compile(r'^([0-9]+)\.([0-9]+):')
        cleanup_re = re.compile(r':(?:class|func|const):`([^`]*)`')
        for line in fd:
            m = version_re.search(line)
            if m and (int(m.group(1)), int(m.group(2))) < (2, 4):
                break
            yield cleanup_re.sub(r'``\1``', line)

readme = ''.join(get_readme_lines()).rstrip()
release = version.get_version()


kwargs = {
    'name': 'pygtrie',
    'version': release,
    'description': 'A pure Python trie data structure implementation.',
    'long_description': readme,
    'long_description_content_type': 'text/x-rst',
    'author': 'Michał Nazarewicz',
    'author_email': 'mina86@mina86.com',
    'url': 'https://github.com/mina86/pygtrie',
    'py_modules': ['pygtrie'],
    'license': 'Apache-2.0',
    'platforms': 'Platform Independent',
    'keywords': ['trie', 'prefix tree', 'data structure'],
    'classifiers': [
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    'cmdclass': {
        'sdist': SDistCommand,
        'build_py': BuildPyCommand,
        'build_doc': BuildDocCommand,
    },
}

if re.search(r'(?:\d+\.)*\d+', release):
    kwargs['download_url'] = kwargs['url'] + '/tarball/v' + release

setuptools.setup(**kwargs)
