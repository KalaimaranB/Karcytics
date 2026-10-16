from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy


class FlowLayout(QLayout):
    """A layout that arranges widgets left-to-right, wrapping to the next line when needed."""

    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def __del__(self):
        """
        Release all layout items managed by the layout.
        """
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):  # noqa: N802
        """Add a layout item to the collection of managed items.

        Parameters:
                item (QLayoutItem): The layout item to add.
        """
        self.itemList.append(item)

    def count(self):
        """Return the number of layout items currently stored."""
        return len(self.itemList)

    def itemAt(self, index):  # noqa: N802
        """
        Return the layout item at the specified index.

        Parameters:
                index (int): Zero-based position of the item.

        Returns:
                QLayoutItem or None: The item at the index, or `None` when the index is out of bounds.
        """
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):  # noqa: N802
        """
        Remove and return the layout item at the specified position.

        Parameters:
                index (int): Position of the item to remove.

        Returns:
                QLayoutItem or None: The removed item, or `None` if the position is outside the list.
        """
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):  # noqa: N802
        """
        Indicate the layout's expansion directions.

        Returns:
            Qt.Orientation: No expansion directions.
        """
        return Qt.Orientation(0)

    def hasHeightForWidth(self):  # noqa: N802
        """
        Indicate that the layout supports height calculations based on its width.

        Returns:
                bool: Always `True`.
        """
        return True

    def heightForWidth(self, width):  # noqa: N802
        """
        Calculate the layout height required for the specified width.

        Parameters:
                width (int): Available layout width.

        Returns:
                int: Required layout height.
        """
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height  # noqa: RET504

    def setGeometry(self, rect):  # noqa: N802
        """
        Apply the layout geometry to the child items within the specified rectangle.

        Parameters:
            rect (QRect): Rectangle defining the layout's available area.
        """
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):  # noqa: N802
        """
        Return the layout's recommended size.

        Returns:
            QSize: The layout's minimum required size.
        """
        return self.minimumSize()

    def minimumSize(self):  # noqa: N802
        """
        Calculate the minimum size required by all layout items and the layout margins.

        Returns:
                QSize: The minimum size required by the layout contents and margins.
        """
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def doLayout(self, rect, testOnly):  # noqa: N802, N803
        """
        Lay out child items in wrapped horizontal lines within a rectangle.

        Parameters:
            rect (QRect): Rectangle available for the layout.
            testOnly (bool): Whether to calculate dimensions without applying item geometries.

        Returns:
            int: Total height required by the laid-out lines.
        """
        y = rect.y()
        lineHeight = 0  # noqa: N806
        spacing = self.spacing()

        lines = []
        current_line = []
        current_width = 0

        # Group items into lines
        for item in self.itemList:
            wid = item.widget()
            spaceX = spacing  # noqa: N806
            if spaceX == -1 and wid is not None:
                spaceX = wid.style().layoutSpacing(  # noqa: N806
                    QSizePolicy.ControlType.PushButton,
                    QSizePolicy.ControlType.PushButton,
                    Qt.Orientation.Horizontal,
                )

            item_w = item.sizeHint().width()

            if current_line and (current_width + spaceX + item_w) > rect.width():
                lines.append((current_line, current_width))
                current_line = [(item, spaceX)]
                current_width = item_w
            else:
                current_line.append((item, spaceX))
                current_width += (spaceX if len(current_line) > 1 else 0) + item_w

        if current_line:
            lines.append((current_line, current_width))

        # Calculate uniform stretch based on the most populated line
        global_stretch = 0
        if lines:
            max_items = max(len(line) for line, _ in lines)
            for line_items, line_width in lines:
                if len(line_items) == max_items:
                    extra_space = max(0, rect.width() - line_width)
                    expandable_items = [
                        i
                        for i, _ in line_items
                        if i.expandingDirections() & Qt.Orientation.Horizontal
                    ]
                    global_stretch = extra_space / len(expandable_items) if expandable_items else 0
                    break

        # Layout each line with stretching
        for line_items, _line_width in lines:
            lineHeight = 0  # noqa: N806

            expandable_items = [
                i for i, _ in line_items if i.expandingDirections() & Qt.Orientation.Horizontal
            ]

            line_x = rect.x()

            # First pass: determine heights
            for item, _spaceX in line_items:  # noqa: N806
                item_w = item.sizeHint().width()
                if item in expandable_items:
                    item_w += global_stretch

                item_h = item.sizeHint().height()
                if item.hasHeightForWidth():
                    item_h = max(item_h, item.heightForWidth(int(item_w)))

                lineHeight = max(lineHeight, item_h)  # noqa: N806

            # Second pass: set geometry
            for i, (item, spaceX) in enumerate(line_items):  # noqa: N806
                if i > 0:
                    line_x += spaceX

                item_w = item.sizeHint().width()
                if item in expandable_items:
                    item_w += global_stretch

                item_h = item.sizeHint().height()
                if item.hasHeightForWidth():
                    item_h = max(item_h, item.heightForWidth(int(item_w)))

                if not testOnly:
                    item.setGeometry(QRect(int(line_x), int(y), int(item_w), int(item_h)))

                line_x += item_w

            y += lineHeight + spacing

        return y - rect.y() - spacing if lines else 0
