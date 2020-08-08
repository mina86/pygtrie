import codecs
import distutils.command.build_py
import distutils.command.sdist
import distutils.core
import packaging.version
import os
import os.path
import re
import shutil
import subprocess
import sys
import stat
import tempfile

import version


class BuildDocCommand(distutils.core.Command):
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
            subprocess.check_call(('sphinx-build', '-Drelease=' + release,
                                   '-n', '-Dversion=' + version, '.', outdir))
        finally:
            if self.dry_run:
                shutil.rmtree(outdir)


class CommandMixin(object):
    @classmethod
    def _read_and_stat(cls, src):
        from distutils.errors import DistutilsFileError
        try:
            with codecs.open(src, 'r', 'utf-8') as fd:
                return fd.read(), os.fstat(fd.fileno())
        except OSError as e:
            raise DistutilsFileError(
                  "could not read from '%s': %s" % (src, e.strerror))

    @classmethod
    def _write(cls, dst, *data):
        from distutils.errors import DistutilsFileError

        if os.path.exists(dst):
            try:
                os.unlink(dst)
            except OSError as e:
                raise DistutilsFileError(
                      "could not delete '%s': %s" % (dst, e.strerror))

        try:
            with codecs.open(dst, 'w', 'utf-8') as fd:
                for datum in data:
                    fd.write(datum)
        except OSError as e:
            raise DistutilsFileError(
                  "could not write to '%s': %s" % (dst, e.strerror))

    def copy_file(self, src, dst, preserve_mode=1, preserve_times=1, link=None,
                  level=1):
        m = None
        if src.endswith('.py'):
            data, st = self._read_and_stat(src)
            m = re.search("^(?:# *)?__version__ *= *'[^']*'(?: *#.*)?$",
                          data, re.MULTILINE)

        if not m:
            return super(CommandMixin, self).copy_file(
                    src, dst, preserve_mode=preserve_mode,
                    preserve_times=preserve_times, link=link)

        if os.path.isdir(dst):
            dir = dst
            dst = os.path.join(dst, os.path.basename(src))
        else:
            dir = os.path.dirname(dst)

        if self.verbose:
            from distutils import log
            snd = dir if os.path.basename(dst) == os.path.basename(src) else dst
            log.info("generating %s -> %s", src, snd)

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


class SDistCommand(CommandMixin, distutils.command.sdist.sdist):
    pass

class BuildPyCommand(CommandMixin, distutils.command.build_py.build_py):
    pass


def get_readme_lines():
    with codecs.open('README.rst', 'r', 'utf-8') as fd:
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

    with codecs.open('version-history.rst', 'r', 'utf-8') as fd:
        min_version = packaging.version.parse('2.0')
        version_re = re.compile(r'^- ([0-9.]*):')
        cleanup_re = re.compile(r':(?:class|func|const):`([^`]*)`')
        for line in fd:
            m = version_re.search(line)
            if m and packaging.version.parse(m.group(1)) < min_version:
                break
            line, _ = cleanup_re.subn(r'``\1``', line)
            yield line

readme = ''.join(get_readme_lines()).rstrip()
release = version.get_version()


kwargs = {
    'name': 'pygtrie',
    'version': release,
    'description': 'A pure Python trie data structure implementation.',
    'long_description_content_type': 'text/x-rst',
    'long_description': readme,
    'author': 'Michal Nazarewicz',
    'author_email': 'mina86@mina86.com',
    'url': 'https://github.com/mina86/pygtrie',
    'py_modules': ['pygtrie'],
    'license': 'Apache-2.0',
    'platforms': 'Platform Independent',
    'keywords': ['trie', 'prefix tree', 'data structure'],
    'classifiers': [
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
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

distutils.core.setup(**kwargs)
