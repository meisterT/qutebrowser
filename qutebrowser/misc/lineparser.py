# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Parser for line-based files like histories."""

import os
import os.path

from PyQt5.QtCore import pyqtSlot, pyqtSignal, QObject

from qutebrowser.utils import log, utils, objreg, qtutils
from qutebrowser.config import config


class BaseLineParser(QObject):

    """A LineParser without any real data.

    Attributes:
        _configdir: The directory to read the config from.
        _configfile: The config file path.
        _fname: Filename of the config.
        _binary: Whether to open the file in binary mode.

    Signals:
        changed: Emitted when the history was changed.
    """

    changed = pyqtSignal()

    def __init__(self, configdir, fname, *, binary=False, parent=None):
        """Constructor.

        Args:
            configdir: Directory to read the config from.
            fname: Filename of the config file.
            binary: Whether to open the file in binary mode.
        """
        super().__init__(parent)
        self._configdir = configdir
        self._configfile = os.path.join(self._configdir, fname)
        self._fname = fname
        self._binary = binary

    def __repr__(self):
        return utils.get_repr(self, constructor=True,
                              configdir=self._configdir, fname=self._fname,
                              binary=self._binary)

    def _prepare_save(self):
        """Prepare saving of the file."""
        log.destroy.debug("Saving to {}".format(self._configfile))
        if not os.path.exists(self._configdir):
            os.makedirs(self._configdir, 0o755)

    def _open_for_reading(self):
        """Open self._configfile for reading."""
        if self._binary:
            return open(self._configfile, 'rb')
        else:
            return open(self._configfile, 'r', encoding='utf-8')

    def _write(self, fp, data):
        """Write the data to a file.

        Args:
            fp: A file object to write the data to.
            data: The data to write.
        """
        if self._binary:
            fp.write(b'\n'.join(data))
        else:
            fp.write('\n'.join(data))

    def save(self):
        """Save the history to disk."""
        raise NotImplementedError


class LineParser(BaseLineParser):

    """Parser for configuration files which are simply line-based.

    Attributes:
        data: A list of lines.
    """

    def __init__(self, configdir, fname, *, binary=False, parent=None):
        """Constructor.

        Args:
            configdir: Directory to read the config from.
            fname: Filename of the config file.
            binary: Whether to open the file in binary mode.
        """
        super().__init__(configdir, fname, binary=binary, parent=parent)
        if not os.path.isfile(self._configfile):
            self.data = []
        else:
            log.init.debug("Reading {}".format(self._configfile))
            self._read()

    def __iter__(self):
        return iter(self.data)

    def __getitem__(self, key):
        return self.data[key]

    def _read(self):
        """Read the data from self._configfile."""
        with self._open_for_reading() as f:
            if self._binary:
                self.data = [line.rstrip(b'\n') for line in f.readlines()]
            else:
                self.data = [line.rstrip('\n') for line in f.readlines()]

    def save(self):
        """Save the config file."""
        if not os.path.exists(self._configdir):
            os.makedirs(self._configdir, 0o755)
        log.destroy.debug("Saving to {}".format(self._configfile))
        with qtutils.savefile_open(self._configfile, self._binary) as f:
            self._write(f, self.data)


class LimitLineParser(LineParser):

    """A LineParser with a limited count of lines.

    Attributes:
        _limit: The config section/option used to limit the maximum number of
                lines.
    """

    def __init__(self, configdir, fname, *, limit, binary=False, parent=None):
        """Constructor.

        Args:
            configdir: Directory to read the config from.
            fname: Filename of the config file.
            limit: Config tuple (section, option) which contains a limit.
            binary: Whether to open the file in binary mode.
        """
        super().__init__(configdir, fname, binary=binary, parent=parent)
        self._limit = limit
        if limit is not None:
            objreg.get('config').changed.connect(self.cleanup_file)

    def __repr__(self):
        return utils.get_repr(self, constructor=True,
                              configdir=self._configdir, fname=self._fname,
                              limit=self._limit, binary=self._binary)

    @pyqtSlot(str, str)
    def cleanup_file(self, section, option):
        """Delete the file if the limit was changed to 0."""
        if (section, option) != self._limit:
            return
        value = config.get(section, option)
        if value == 0:
            if os.path.exists(self._configfile):
                os.remove(self._configfile)

    def save(self):
        """Save the config file."""
        limit = config.get(*self._limit)
        if limit == 0:
            return
        self._prepare_save()
        with qtutils.savefile_open(self._configfile, self._binary) as f:
            self._write(f, self.data[-limit:])