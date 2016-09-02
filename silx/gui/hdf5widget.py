# coding: utf-8
# /*##########################################################################
#
# Copyright (c) 2004-2016 European Synchrotron Radiation Facility
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# ###########################################################################*/

"""Qt tree model for a HDF5 file

.. note:: This module has a dependency on the `h5py <http://www.h5py.org/>`_
    library, which is not a mandatory dependency for `silx`. You might need
    to install it if you don't already have it.
"""

import os
import sys
import numpy
import logging
from . import qt
from . import icons
from ..utils import weakref as silxweakref

try:
    import h5py
except ImportError as e:
    _logger.error("Module %s requires h5py", __name__)
    raise e


__authors__ = ["P. Knobel"]
__license__ = "MIT"
__date__ = "02/09/2016"


_logger = logging.getLogger(__name__)


def load_file_as_h5py(filename):
    """
    Load a file as an h5py.File object

    :param str filename: A filename
    :raises: IOError if the file can't be loaded as an h5py.File like object
    :rtype: h5py.File
    """
    if not os.path.isfile(filename):
        raise IOError("Filename '%s' must be a file path" % filename)

    if h5py.is_hdf5(filename):
        return h5py.File(filename)

    try:
        from ..io import spech5
        return spech5.SpecH5(filename)
    except ImportError:
        _logger.debug("spech5 can't be loaded.", filename, exc_info=True)
    except IOError:
        _logger.debug("File '%s' can't be read as spec file.", filename, exc_info=True)

    try:
        from silx.io import fabioh5
        return fabioh5.File(filename)
    except ImportError:
        _logger.debug("fabioh5 can't be loaded.", filename, exc_info=True)
    except Exception:
        _logger.debug("File '%s' can't be read as fabio file.", filename, exc_info=True)

    raise IOError("Format of filename '%s' is not supported" % filename)


class LoadingItemRunnable(qt.QRunnable):
    """Runner to process item loading from a file"""

    def __init__(self, filename, item):
        """Constructor

        :param LoadingItemWorker worker: Object holding data and signals
        """
        super(LoadingItemRunnable, self).__init__()
        self.filename = filename
        self.oldItem = item
        class _Signals(qt.QObject):
            itemReady = qt.Signal(object, object, object)
        self.signals = _Signals()

    def setFile(self, filename, item):
        self.filenames.append((filename, item))

    @property
    def itemReady(self):
        return self.signals.itemReady

    def __loadItemTree(self, oldItem, h5obj):
        """Create an item tree used by the GUI from an h5py object.

        :param Hdf5Node oldItem: The current item displayed the GUI
        :param h5py.File h5obj: The h5py object to display in the GUI
        :rtpye: Hdf5Node
        """
        if hasattr(h5obj, "h5py_class"):
            class_ = h5obj.h5py_class
        else:
            class_ = h5obj.__class__

        if class_ == h5py.File:
            text = os.path.basename(h5obj.filename)
        else:
            filename = os.path.basename(h5obj.file.filename)
            path = h5obj.name
            text = "%s::%s" % (filename, path)
        item = Hdf5Item(text=text, obj=h5obj, parent=oldItem.parent, populateAll=True)
        return item

    @qt.Slot()
    def run(self):
        """Process the file loading. The worker is used as holder
        of the data and the signal. The result is sent as a signal.
        """
        try:
            h5file = load_file_as_h5py(self.filename)
            newItem = self.__loadItemTree(self.oldItem, h5file)
            error = None
        except IOError as e:
            # Should be logged
            error = e
            newItem = None
        self.itemReady.emit(self.oldItem, newItem, error)

    def autoDelete(self):
        return True


def htmlFromDict(input):
    """Generate a readable HTML from a dictionary

    :param input dict: A Dictionary
    :rtype: str
    """
    result = "<html><ul>"
    for key, value in input.items():
        result += "<li><b>%s</b>: %s</li>" % (key, value)
    result += "</ul></html>"
    return result


class Hdf5NodeMimeData(qt.QMimeData):
    """Mimedata class to identify an internal drag and drop of a Hdf5Node."""

    MIME_TYPE = "application/x-internal-h5py-node"

    def __init__(self, node=None):
        qt.QMimeData.__init__(self)
        self.__node = node
        self.setData(self.MIME_TYPE, "")

    def node(self):
        return self.__node


class Hdf5Node(object):
    """Abstract tree node

    It provides link to the childs and to the parents, and a link to an
    external object.
    """
    def __init__(self, parent=None, populateAll=False):
        """
        :param text str: text displayed
        :param object obj: Pointer to h5py data. See the `obj` attribute.
        :param Hdf5Node parent: Parent of the node, else None
        """
        self.__child = None
        self.__parent = parent
        if populateAll:
            self.__child = []
            self._populateChild(populateAll=True)

    @property
    def parent(self):
        return self.__parent

    def setParent(self, parent):
        self.__parent = parent

    def appendChild(self, child):
        self.__initChild()
        self.__child.append(child)

    def deleteChild(self, index):
        return self.__child.pop(index)

    def insertChild(self, index, child):
        self.__initChild()
        self.__child.insert(index, child)

    def indexOfChild(self, child):
        self.__initChild()
        return self.__child.index(child)

    def hasChildren(self):
        """Override method to be able to generate chrildren on demand.
        The result is computed from the HDF5 model.

        :rtype: bool
        """
        return self.childCount() > 0

    def childCount(self):
        if self.__child is not None:
            return len(self.__child)
        return self._expectedChildCount()

    def child(self, index):
        """Override method to be able to generate chrildren on demand."""
        self.__initChild()
        return self.__child[index]

    def __initChild(self):
        if self.__child is None:
            self.__child = []
            self._populateChild()

    def _expectedChildCount(self):
        return 0

    def _populateChild(self):
        """Recurse through an HDF5 structure to append groups an datasets
        into the tree model.
        :param h5item: Parent :class:`Hdf5Item` or
            :class:`Hdf5ItemModel` object
        :param gr_or_ds: h5py or spech5 object (h5py.File, h5py.Group,
            h5py.Dataset, spech5.SpecH5, spech5.SpecH5Group,
            spech5.SpecH5Dataset)
        """
        pass

    def dataName(self, role):
        """Data for the name column"""
        return None

    def dataType(self, role):
        """Data for the type column"""
        return None

    def dataShape(self, role):
        """Data for the shape column"""
        return None

    def dataValue(self, role):
        """Data for the value column"""
        return None

    def dataDescription(self, role):
        """Data for the description column"""
        return None

    def dataNode(self, role):
        """Data for the node column"""
        return None


class Hdf5BrokenLinkItem(Hdf5Node):
    """Subclass of :class:`qt.QStandardItem` to represent a broken link
    in HDF5 tree structure.
    """

    def __init__(self, text, obj=None, message=None, parent=None):
        """Constructor

        :param text str: Text displayed by the item
        :param obj h5py link: HDF5 object containing link informations
        :param message str: Message to display as description
        """
        super(Hdf5BrokenLinkItem, self).__init__(parent)
        self.__text = text
        self.__obj = obj
        self.__message = message

    @property
    def obj(self):
        return self.__obj

    def _getH5pyClass(self):
        if hasattr(self.__obj, "h5py_class"):
            class_ = self.__obj.h5py_class
        else:
            class_ = self.__obj.__class__
        return class_

    def _expectedChildCount(self):
        return 0

    def dataName(self, role):
        if role == qt.Qt.DecorationRole:
            style = qt.QApplication.style()
            icon = style.standardIcon(qt.QStyle.SP_MessageBoxCritical)
            return icon
        if role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignTop | qt.Qt.AlignLeft
        if role == qt.Qt.DisplayRole:
            return self.__text
        if role == qt.Qt.ToolTipRole:
            input = {}
            if isinstance(self.obj, h5py.ExternalLink):
                input["linked path"] = self.obj.path
                input["linked file"] = self.obj.filename
            elif isinstance(self.obj, h5py.SoftLink):
                input["linked path"] = self.obj.path
            return htmlFromDict(input)
        return None

    def dataDescription(self, role):
        if role == qt.Qt.DecorationRole:
            return None
        if role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignTop | qt.Qt.AlignLeft
        if role == qt.Qt.DisplayRole:
            if self.__message is None:
                if isinstance(self.obj, h5py.ExternalLink):
                    message = "External link broken. Path %s::%s does not exist" % (self.obj.filename, self.obj.path)
                elif isinstance(self.obj, h5py.SoftLink):
                    message = "Soft link broken. Path %s does not exist" % (self.obj.path)
                else:
                    name = self.obj.__class__.__name__.split(".")[-1].capitalize()
                    message = "%s broken" % (name)
            else:
                message = self.__message
            return self.__message
        return None

    def dataNode(self, role):
        if role == qt.Qt.DecorationRole:
            return None
        if role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignTop | qt.Qt.AlignLeft
        if role == qt.Qt.DisplayRole:
            class_ = self._getH5pyClass()
            return class_.__name__.split(".")[-1]


            class_ = self._getH5pyClass()
            text = class_.__name__.split(".")[-1]
            return text
        if role == qt.Qt.ToolTipRole:

            item = qt.QStandardItem(text)
            item.setToolTip("Class name: %s" % self.__class__)
            return text
        return None


class Hdf5LoadingItem(Hdf5Node):

    def __init__(self, text, parent, animatedIcon):
        Hdf5Node.__init__(self, parent)
        self.__text = text
        self.__animatedIcon = animatedIcon
        self.__animatedIcon.register(self)

    @property
    def obj(self):
        return None

    def dataName(self, role):
        if role == qt.Qt.DecorationRole:
            return self.__animatedIcon.currentIcon()
        if role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignTop | qt.Qt.AlignLeft
        if role == qt.Qt.DisplayRole:
            return self.__text
        return None

    def dataDescription(self, role):
        if role == qt.Qt.DecorationRole:
            return None
        if role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignTop | qt.Qt.AlignLeft
        if role == qt.Qt.DisplayRole:
            return "Loading..."
        return None


class Hdf5Item(Hdf5Node):
    """Subclass of :class:`qt.QStandardItem` to represent an HDF5-like
    item (dataset, file, group or link) as an element of a HDF5-like
    tree structure.
    """

    def __init__(self, text, obj, parent, populateAll=False):
        """
        :param text str: text displayed
        :param obj object: Pointer to h5py data. See the `obj` attribute.
        """
        self.__obj = obj
        self.__text = text
        Hdf5Node.__init__(self, parent, populateAll=populateAll)

    @property
    def obj(self):
        return self.__obj

    def _getH5pyClass(self):
        if hasattr(self.__obj, "h5py_class"):
            class_ = self.__obj.h5py_class
        else:
            class_ = self.__obj.__class__
        return class_

    def _expectedChildCount(self):
        if self.isGroupObj():
            return len(self.__obj)
        return 0

    def _populateChild(self, populateAll=False):
        """Recurse through an HDF5 structure to append groups an datasets
        into the tree model.
        :param h5item: Parent :class:`Hdf5Item` or
            :class:`Hdf5ItemModel` object
        :param gr_or_ds: h5py or spech5 object (h5py.File, h5py.Group,
            h5py.Dataset, spech5.SpecH5, spech5.SpecH5Group,
            spech5.SpecH5Dataset)
        """
        if self.isGroupObj():
            for child_gr_ds_name in self.__obj:
                try:
                    child_gr_ds = self.__obj.get(child_gr_ds_name)
                except RuntimeError as e:
                    _logger.error("Internal h5py error", exc_info=True)
                    link = self.__obj.get(child_gr_ds_name, getlink=True)
                    item = Hdf5BrokenLinkItem(text=child_gr_ds_name, obj=link, message=e.args[0], parent=self)
                else:
                    if child_gr_ds is None:
                        # that's a broken link
                        link = self.__obj.get(child_gr_ds_name, getlink=True)
                        item = Hdf5BrokenLinkItem(text=child_gr_ds_name, obj=link, parent=self)
                    else:
                        item = Hdf5Item(text=child_gr_ds_name, obj=child_gr_ds, parent=self, populateAll=populateAll)
                if item is not None:
                    self.appendChild(item)

    def isGroupObj(self):
        """Is the hdf5 obj contains sub group or datasets"""
        class_ = self._getH5pyClass()
        return issubclass(class_, h5py.Group)

    def _getDefaultIcon(self):
        style = qt.QApplication.style()
        class_ = self._getH5pyClass()
        if issubclass(class_, h5py.File):
            return style.standardIcon(qt.QStyle.SP_FileIcon)
        elif issubclass(class_, h5py.Group):
            return style.standardIcon(qt.QStyle.SP_DirIcon)
        elif issubclass(class_, h5py.SoftLink):
            return style.standardIcon(qt.QStyle.SP_DirLinkIcon)
        elif issubclass(class_, h5py.ExternalLink):
            return style.standardIcon(qt.QStyle.SP_FileLinkIcon)
        elif issubclass(class_, h5py.Dataset):
            if len(self.__obj.shape) < 4:
                name = "item-%ddim" % len(self.__obj.shape)
            else:
                name = "item-ndim"
            if str(self.__obj.dtype) == "object":
                name = "item-object"
            icon = icons.getQIcon(name)
            return icon
        return None

    def _getDefaultTooltip(self):
        """Set the default tooltip"""
        class_ = self._getH5pyClass()
        attrs = dict(self.__obj.attrs)
        if issubclass(class_, h5py.Dataset):
            if self.__obj.shape == ():
                attrs["shape"] = "scalar"
            else:
                attrs["shape"] = self.__obj.shape
            attrs["dtype"] = self.__obj.dtype
            if self.__obj.shape == ():
                attrs["value"] = self.__obj.value
            else:
                attrs["value"] = "..."

        if len(attrs) > 0:
            tooltip = htmlFromDict(attrs)
        else:
            tooltip = ""

        return tooltip

    def dataName(self, role):
        """Data for the name column"""
        if role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignTop | qt.Qt.AlignLeft
        if role == qt.Qt.DisplayRole:
            return self.__text
        if role == qt.Qt.DecorationRole:
            return self._getDefaultIcon()
        if role == qt.Qt.ToolTipRole:
            return self._getDefaultTooltip()
        return None

    def dataType(self, role):
        """Data for the type column"""
        if role == qt.Qt.DecorationRole:
            return None
        if role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignTop | qt.Qt.AlignLeft
        if role == qt.Qt.DisplayRole:
            class_ = self._getH5pyClass()
            if issubclass(class_, h5py.Dataset):
                if self.__obj.dtype.type == numpy.string_:
                    text = "string"
                else:
                    text = str(self.obj.dtype)
            else:
                text = ""
            return text

        return None

    def dataShape(self, role):
        """Data for the shape column"""
        if role == qt.Qt.DecorationRole:
            return None
        if role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignTop | qt.Qt.AlignLeft
        if role == qt.Qt.DisplayRole:
            class_ = self._getH5pyClass()
            if not issubclass(class_, h5py.Dataset):
                return None
            shape = [str(i) for i in self.__obj.shape]
            text = u" \u00D7 ".join(shape)
            return text
        return None

    def dataValue(self, role):
        """Data for the value column"""
        if role == qt.Qt.DecorationRole:
            return None
        if role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignTop | qt.Qt.AlignLeft
        if role == qt.Qt.DisplayRole:
            class_ = self._getH5pyClass()
            if not issubclass(class_, h5py.Dataset):
                return None

            numpy_object = self.__obj.value

            if self.__obj.dtype.type == numpy.object_:
                text = str(numpy_object)
            elif self.__obj.dtype.type == numpy.string_:
                text = str(numpy_object)
            else:
                size = 1
                for dim in numpy_object.shape:
                    size = size * dim

                if size > 5:
                    text = "..."
                else:
                    text = str(numpy_object)
            return text
        return None

    def dataDescription(self, role):
        """Data for the description column"""
        if role == qt.Qt.DecorationRole:
            return None
        if role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignTop | qt.Qt.AlignLeft
        if role == qt.Qt.DisplayRole:
            if "desc" in self.__obj.attrs:
                text = self.__obj.attrs["desc"]
            else:
                return None
            return text
        if role == qt.Qt.ToolTipRole:
            if "desc" in self.__obj.attrs:
                text = self.__obj.attrs["desc"]
            else:
                return None
            return "Description: %s" % text
        return None

    def dataNode(self, role):
        """Data for the node column"""
        if role == qt.Qt.DecorationRole:
            return None
        if role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignTop | qt.Qt.AlignLeft
        if role == qt.Qt.DisplayRole:
            class_ = self._getH5pyClass()
            text = class_.__name__.split(".")[-1]
            return text
        if role == qt.Qt.ToolTipRole:
            class_ = self._getH5pyClass()
            return "Class name: %s" % self.__class__
        return None


class Hdf5TreeModel(qt.QAbstractItemModel):

    def __init__(self, parent=None):
        super(Hdf5TreeModel, self).__init__(parent)

        self.treeView = parent
        self.header_labels = [
            'Name',
            'Type',
            'Shape',
            'Value',
            'Description',
            'Node',
        ]

        # Create items
        self.__root = Hdf5Node()
        self.__fileDropEnabled = True
        self.__fileMoveEnabled = True

        self.__animatedIcon = icons.getWaitIcon()
        self.__animatedIcon.iconChanged.connect(self.__updateLoadingItems)

    def __updateLoadingItems(self, icon):
        for i in range(self.__root.childCount()):
            item = self.__root.child(i)
            if isinstance(item, Hdf5LoadingItem):
                index1 = self.index(i, 0, qt.QModelIndex())
                index2 = self.index(i, self.columnCount(None) - 1, qt.QModelIndex())
                self.dataChanged.emit(index1, index2)

    def __itemReady(self, oldItem, newItem, error):
        """Called at the end of a concurent file loading, when the loading
        item is ready. AN error is defined if an exception occured when
        loading the newItem .

        :param Hdf5Node oldItem: current displayed item
        :param Hdf5Node newItem: item loaded, or None if error is defined
        :param Exception error: An exception, or None if newItem is defined
        """
        row = self.__root.indexOfChild(oldItem)
        rootIndex = qt.QModelIndex()
        self.beginRemoveRows(rootIndex, row, row)
        self.__root.deleteChild(row)
        self.endRemoveRows()
        if newItem is not None:
            self.beginInsertRows(rootIndex, row, row)
            self.__root.insertChild(row, newItem)
            self.endInsertRows()
        # FIXME the error must be displayed

    def isFileDropEnabled(self):
        return self.__fileDropEnabled

    def setFileDropEnabled(self, enabled):
        self.__fileDropEnabled = enabled

    fileDropEnabled = qt.Property(bool, isFileDropEnabled, setFileDropEnabled)
    """Property to enable/disable file dropping in the model."""

    def isFileMoveEnabled(self):
        return self.__fileMoveEnabled

    def setFileMoveEnabled(self, enabled):
        self.__fileMoveEnabled = enabled

    fileMoveEnabled = qt.Property(bool, isFileMoveEnabled, setFileMoveEnabled)
    """Property to enable/disable drag-and-drop to drag and drop files to
    change the ordering in the model."""

    def supportedDropActions(self):
        if self.__fileMoveEnabled or self.__fileDropEnabled:
            return qt.Qt.CopyAction | qt.Qt.MoveAction
        else:
            return None

    def mimeTypes(self):
        if self.__fileMoveEnabled:
            return [Hdf5NodeMimeData.MIME_TYPE]
        else:
            return []

    def mimeData(self, index):
        if self.__fileMoveEnabled:
            node = self.nodeFromIndex(index[0])
            mimeData = Hdf5NodeMimeData(node)
            return mimeData
        else:
            return None

    def flags(self, index):
        defaultFlags = qt.QAbstractItemModel.flags(self, index)

        if index.isValid():
            node = self.nodeFromIndex(index)
            if self.__fileMoveEnabled and node.parent is self.__root:
                # that's a root
                return qt.Qt.ItemIsEditable |qt.Qt.ItemIsDragEnabled | defaultFlags
            return defaultFlags
        elif self.__fileDropEnabled or self.__fileMoveEnabled:
            return qt.Qt.ItemIsDropEnabled | defaultFlags
        else:
            return defaultFlags

    def dropMimeData(self, mimedata, action, row, column, parentIndex):
        if action == qt.Qt.IgnoreAction:
            return True

        if self.__fileMoveEnabled and mimedata.hasFormat(Hdf5NodeMimeData.MIME_TYPE):
            dragNode = mimedata.node()
            parentNode = self.nodeFromIndex(parentIndex)
            if parentNode is not dragNode.parent:
                return False

            if row == -1:
                # append to the parent
                row = parentNode.childCount()
            else:
                # insert at row
                pass

            dragNodeParent = dragNode.parent
            sourceRow = dragNodeParent.indexOfChild(dragNode)
            self.moveRow(parentIndex, sourceRow, parentIndex, row)
            return True

        if self.__fileDropEnabled and mimedata.hasFormat("text/uri-list"):

            parentNode = self.nodeFromIndex(parentIndex)
            if parentNode is not self.__root:
                while(parentNode is not self.__root):
                    node = parentNode
                    parentNode = node.parent
                row = parentNode.indexOfChild(node)
            else:
                if row == -1:
                    row = self.__root.childCount()

            messages = []
            for url in mimedata.urls():
                try:
                    self.insertFileAsync(url.toLocalFile(), row)
                    row += 1
                except IOError as e:
                    messages.append(e.args[0])
            if len(messages) > 0:
                title = "Error occurred when loading files"
                message = "<html>%s:<ul><li>%s</li><ul></html>" % (title, "</li><li>".join(messages))
                qt.QMessageBox.critical(None, title, message)
            return True

        return False

    def headerData(self, section, orientation, role):
        if orientation == qt.Qt.Horizontal and role == qt.Qt.DisplayRole:
            return self.header_labels[section]
        return None

    def insertNode(self, row, node):
        if row == -1:
            row = self.__root.childCount()
        self.beginInsertRows(qt.QModelIndex(), row, row)
        self.__root.insertChild(row, node)
        self.endInsertRows()

    def moveRow(self, sourceParentIndex, sourceRow, destinationParentIndex, destinationRow):
        if sourceRow == destinationRow or sourceRow == destinationRow - 1:
            # abort move, same place
            return
        return self.moveRows(sourceParentIndex, sourceRow, 1, destinationParentIndex, destinationRow)

    def moveRows(self, sourceParentIndex, sourceRow, count, destinationParentIndex, destinationRow):
        self.beginMoveRows(sourceParentIndex, sourceRow, sourceRow, destinationParentIndex, destinationRow)
        sourceNode = self.nodeFromIndex(sourceParentIndex)
        destinationNode = self.nodeFromIndex(destinationParentIndex)

        if sourceNode is destinationNode and sourceRow < destinationRow:
            item = sourceNode.child(sourceRow)
            destinationNode.insertChild(destinationRow, item)
            sourceNode.deleteChild(sourceRow)
        else:
            item = sourceNode.deleteChild(sourceRow)
            destinationNode.insertChild(destinationRow, item)

        self.endMoveRows()
        return True

    def index(self, row, column, parent):
        try:
            node = self.nodeFromIndex(parent)
            return self.createIndex(row, column, node.child(row))
        except IndexError:
            return qt.QModelIndex()

    def data(self, index, role):
        node = self.nodeFromIndex(index)

        if index.column() == 0:
            return node.dataName(role)
        elif index.column() == 1:
            return node.dataType(role)
        elif index.column() == 2:
            return node.dataShape(role)
        elif index.column() == 3:
            return node.dataValue(role)
        elif index.column() == 4:
            return node.dataDescription(role)
        elif index.column() == 5:
            return node.dataNode(role)
        else:
            return None

    def columnCount(self, parent):
        return len(self.header_labels)

    def rowCount(self, parent):
        node = self.nodeFromIndex(parent)
        if node is None:
            return 0
        return node.childCount()

    def parent(self, child):
        if not child.isValid():
            return qt.QModelIndex()

        node = self.nodeFromIndex(child)

        if node is None:
            return qt.QModelIndex()

        parent = node.parent

        if parent is None:
            return qt.QModelIndex()

        grandparent = parent.parent
        if grandparent is None:
            return qt.QModelIndex()
        row = grandparent.indexOfChild(parent)

        assert row != - 1
        return self.createIndex(row, 0, parent)

    def nodeFromIndex(self, index):
        return index.internalPointer() if index.isValid() else self.__root

    def insertH5pyObject(self, h5pyObject, text=None, row=-1):
        """Append an HDF5 object from h5py to the tree.

        :param h5pyObject: File handle/descriptor for a :class:`h5py.File`
            or any other class of h5py file structure.
        """
        if text is None:
            if hasattr(h5pyObject, "h5py_class"):
                class_ = h5pyObject.h5py_class
            else:
                class_ = h5pyObject.__class__

            if class_ == h5py.File:
                text = os.path.basename(h5pyObject.filename)
            else:
                filename = os.path.basename(h5pyObject.file.filename)
                path = h5pyObject.name
                text = "%s::%s" % (filename, path)
        if row == -1:
            row = self.__root.childCount()
        self.insertNode(row, Hdf5Item(text=text, obj=h5pyObject, parent=self.__root))

    def insertFileAsync(self, filename, row=-1):
        if not os.path.isfile(filename):
            raise IOError("Filename '%s' must be a file path" % filename)

        # create temporary item
        text = os.path.basename(filename)
        item = Hdf5LoadingItem(text=text, parent=self.__root, animatedIcon=self.__animatedIcon)
        self.insertNode(row, item)

        # start loading the real one
        runnable = LoadingItemRunnable(filename, item)
        runnable.itemReady.connect(self.__itemReady)
        qt.QThreadPool.globalInstance().start(runnable)

    def insertFile(self, filename, row=-1):
        """Load a HDF5 file into the data model.

        :param filename: file path.
        """
        try:
            h5file = load_file_as_h5py(filename)
            self.insertH5pyObject(h5file, row=row)
        except IOError:
            _logger.debug("File '%s' can't be read.", filename, exc_info=True)
            raise IOError("File '%s' can't be read as HDF5, fabio, or SpecFile" % filename)

    def appendFile(self, filename):
        self.insertFile(filename, -1)


class Hdf5HeaderView(qt.QHeaderView):
    """
    Default HDF5 header

    Manage auto-resize and context menu to display/hide columns
    """

    def __init__(self, orientation, parent=None):
        """\
        Constructor

        :param orientation qt.Qt.Orientation: Orientation of the header
        :param parent qt.QWidget: Parent of the widget
        """
        super(Hdf5HeaderView, self).__init__(orientation, parent)
        self.setContextMenuPolicy(qt.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.__createContextMenu)

        # default initialization done by QTreeView for it's own header
        self.setClickable(True)
        self.setMovable(True)
        self.setDefaultAlignment(qt.Qt.AlignLeft | qt.Qt.AlignVCenter)
        self.setStretchLastSection(True)

        self.__auto_resize = True

    def setModel(self, model):
        """Override model to configure view when a model is expected

        `qt.QHeaderView.setResizeMode` expect already existing columns
        to work.

        :param model qt.QAbstractItemModel: A model
        """
        super(Hdf5HeaderView, self).setModel(model)
        self.__updateAutoResize()

    def __updateAutoResize(self):
        """Update the view according to the state of the auto-resize"""
        if self.__auto_resize:
            self.setResizeMode(0, qt.QHeaderView.ResizeToContents)
            self.setResizeMode(1, qt.QHeaderView.ResizeToContents)
            self.setResizeMode(2, qt.QHeaderView.ResizeToContents)
            self.setResizeMode(3, qt.QHeaderView.Interactive)
            self.setResizeMode(4, qt.QHeaderView.Interactive)
            self.setResizeMode(5, qt.QHeaderView.ResizeToContents)
        else:
            self.setResizeMode(0, qt.QHeaderView.Interactive)
            self.setResizeMode(1, qt.QHeaderView.Interactive)
            self.setResizeMode(2, qt.QHeaderView.Interactive)
            self.setResizeMode(3, qt.QHeaderView.Interactive)
            self.setResizeMode(4, qt.QHeaderView.Interactive)
            self.setResizeMode(5, qt.QHeaderView.Interactive)

    def setAutoResizeColumns(self, autoResize):
        """Enable/disable auto-resize. When auto-resized, the header take care
        of the content of the column to set fixed size of some of them, or to
        auto fix the size according to the content.

        :param autoResize bool: Enable/disable auto-resize
        """
        if self.__auto_resize == autoResize:
            return
        self.__auto_resize = autoResize
        self.__updateAutoResize()

    def hasAutoResizeColumns(self):
        """Is auto-resize enabled.

        :rtype: bool
        """
        return self.__auto_resize

    autoResizeColumns = qt.Property(bool, hasAutoResizeColumns, setAutoResizeColumns)
    """Property to enable/disable auto-resize."""

    def __createContextMenu(self, pos):
        """Callback to create and display a context menu

        :param pos qt.QPoint: Requested position for the context menu
        """
        model = self.model()
        if model.columnCount() > 1:
            menu = qt.QMenu(self)
            menu.setTitle("Display/hide columns")

            action = qt.QAction("Display/hide column", self)
            action.setEnabled(False)
            menu.addAction(action)

            for column in range(model.columnCount()):
                if column == 0:
                    # skip the main column
                    continue
                text = model.headerData(column, qt.Qt.Horizontal)
                action = qt.QAction("%s displayed" % text, self)
                action.setCheckable(True)
                action.setChecked(not self.isSectionHidden(column))
                gen_hide_section_event = lambda column: lambda checked: self.setSectionHidden(column, not checked)
                action.toggled.connect(gen_hide_section_event(column))
                menu.addAction(action)

            menu.popup(self.viewport().mapToGlobal(pos))


class Hdf5TreeView(qt.QTreeView):
    """TreeView which allow to browse HDF5 file structure.

    It provids columns width auto-resizing and additional
    signals.

    The default model is `Hdf5TreeModel` and the default header is
    `Hdf5HeaderView`.

    Context menu is managed by the `setContextMenuPolicy` with the value
    CustomContextMenu. This policy must not be changed, else context menus
    will not work anymore. You can use `addContextMenuCallback` and
    `removeContextMenuCallback` to add your custum actions according to the
    selected objects.
    """
    def __init__(self, parent=None):
        """
        Constructor

        :param parent qt.QWidget: The parent widget
        """
        qt.QTreeView.__init__(self, parent)
        self.setModel(Hdf5TreeModel())
        self.setHeader(Hdf5HeaderView(qt.Qt.Horizontal, self))
        self.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
        # optimise the rendering
        self.setUniformRowHeights(True)

        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(qt.QAbstractItemView.DragDrop)
        self.showDropIndicator()

        self.__context_menu_callbacks = silxweakref.WeakList()
        self.setContextMenuPolicy(qt.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._createContextMenu)

    def __removeContextMenuProxies(self, ref):
        """Callback to remove dead proxy from the list"""
        self.__context_menu_callbacks.remove(ref)

    def _createContextMenu(self, pos):
        """
        Create context menu.

        :param pos qt.QPoint: Position of the context menu
        """
        selected_objects = self.selectedH5pyObjects(ignoreBrokenLinks=True)
        actions = []

        for callback in self.__context_menu_callbacks:
            try:
                new_actions = callback(self, selected_objects)
                actions.extend(new_actions)
            except KeyboardInterrupt:
                raise
            except:
                # make sure no user callback crash the application
                _logger.error("Error while calling callback", exc_info=True)
                pass

        if len(actions) > 0:
            menu = qt.QMenu(self)
            for action in actions:
                menu.addAction(action)
            menu.popup(self.viewport().mapToGlobal(pos))

    def addContextMenuCallback(self, callback):
        """Register a context menu callback.

        The callback will be called when a context menu is requested with the
        treeview and the list of selected h5py objects in parameters. The
        callback must return a list of `qt.QAction` object.

        Callbacks are stored as saferef. The object must store a reference by
        itself.
        """
        self.__context_menu_callbacks.append(callback)

    def removeContextMenuCallback(self, callback):
        """Unregister a context menu callback"""
        self.__context_menu_callbacks.remove(callback)

    def dragEnterEvent(self, event):
        if self.model().isFileDropEnabled() and event.mimeData().hasFormat("text/uri-list"):
            self.setState(qt.QAbstractItemView.DraggingState)
            event.accept()
        else:
            qt.QTreeView.dragEnterEvent(self, event)

    def dragMoveEvent(self, event):
        if self.model().isFileDropEnabled() and event.mimeData().hasFormat("text/uri-list"):
            event.setDropAction(qt.Qt.LinkAction)
            event.accept()
        else:
            qt.QTreeView.dragMoveEvent(self, event)

    def selectedH5pyObjects(self, ignoreBrokenLinks=True):
        """Returns selected h5py objects like `h5py.File`, `h5py.Group`,
        `h5py.Dataset` or mimicked objects.
        :param ignoreBrokenLinks bool: Returns objects which are not not
            broken links.
        """
        result = []
        for index in self.selectedIndexes():
            if index.column() != 0:
                continue
            item = self.model().nodeFromIndex(index)
            if item is None:
                continue
            if isinstance(item, Hdf5Item):
                result.append(item.obj)
            if not ignoreBrokenLinks and isinstance(item, Hdf5BrokenLinkItem):
                result.append(item.obj)
        return result

    def mousePressEvent(self, event):
        """Override mousePressEvent to provide a consistante compatible API
        between Qt4 and Qt5
        """
        super(Hdf5TreeView, self).mousePressEvent(event)
        if event.button() != qt.Qt.LeftButton:
            # Qt5 only sends itemClicked on left button mouse click
            if qt.qVersion() > "5":
                qindex = self.indexAt(event.pos())
                self.clicked.emit(qindex)
