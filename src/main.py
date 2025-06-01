import sys
from collections import defaultdict
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QTextEdit, QLabel, QSplitter)
from PySide6.QtCore import Qt
from P4 import P4, P4Exception

p4 = P4()
p4.connect()


class StreamSpecCreator(QMainWindow):
    def __init__(self, stream_files, parent_stream):
        super().__init__()
        self.stream_files = stream_files
        self.parent_stream = parent_stream
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle(f"Virtual Stream Spec Creator - Parent: {self.parent_stream}")
        self.setGeometry(100, 100, 1000, 700)
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Create splitter for tree and spec views
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side - Tree view
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        tree_label = QLabel("Select files and folders to include:")
        left_layout.addWidget(tree_label)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Files and Folders")
        self.tree.itemChanged.connect(self.on_item_changed)
        left_layout.addWidget(self.tree)
        
        # Right side - Stream spec
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        spec_label = QLabel("Generated Stream Spec:")
        right_layout.addWidget(spec_label)
        
        self.spec_text = QTextEdit()
        self.spec_text.setReadOnly(True)
        self.spec_text.setStyleSheet("QTextEdit { font-family: 'Consolas', 'Monaco', monospace; }")
        right_layout.addWidget(self.spec_text)
        
        # Add widgets to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([600, 400])
        
        layout.addWidget(splitter)
        
        # Build the tree from the file list
        self.build_tree()
        
        # Generate initial spec (empty)
        self.update_stream_spec()
        
    def build_tree(self):
        """Build the tree structure from the flat file list"""
        # Create a nested dictionary structure
        tree_dict = defaultdict(dict)
        
        for file_path in self.stream_files:
            parts = file_path.split('/')
            current = tree_dict
            
            for i, part in enumerate(parts):
                if i == len(parts) - 1:  # It's a file
                    current[part] = None
                else:  # It's a folder
                    if part not in current:
                        current[part] = {}
                    current = current[part]
        
        # Build the QTreeWidget from the dictionary
        self.populate_tree(tree_dict, self.tree.invisibleRootItem())
        
    def populate_tree(self, tree_dict, parent_item, path=""):
        """Recursively populate the QTreeWidget"""
        for name, children in sorted(tree_dict.items()):
            # Create the tree item
            item = QTreeWidgetItem(parent_item)
            item.setText(0, name)
            item.setCheckState(0, Qt.Unchecked)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
            
            # Store the full path in the item
            full_path = f"{path}/{name}" if path else name
            item.setData(0, Qt.UserRole, full_path)
            
            # If it has children, it's a folder
            if children is not None:
                self.populate_tree(children, item, full_path)
                item.setExpanded(True)
                
    def on_item_changed(self, item, column):
        """Handle item check state changes"""
        # Block signals to prevent recursive calls
        self.tree.blockSignals(True)
        
        # Update children if this is a folder
        self.update_children_check_state(item, item.checkState(0))
        
        # Update parent check states
        self.update_parent_check_state(item.parent())
        
        # Unblock signals
        self.tree.blockSignals(False)
        
        # Update the stream spec
        self.update_stream_spec()
        
    def update_children_check_state(self, item, check_state):
        """Recursively update all children to match parent's check state"""
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, check_state)
            self.update_children_check_state(child, check_state)
            
    def update_parent_check_state(self, parent):
        """Update parent check state based on children"""
        if parent is None:
            return
            
        checked_count = 0
        partially_checked_count = 0
        total_count = parent.childCount()
        
        for i in range(total_count):
            child = parent.child(i)
            if child.checkState(0) == Qt.Checked:
                checked_count += 1
            elif child.checkState(0) == Qt.PartiallyChecked:
                partially_checked_count += 1
                
        if checked_count == total_count:
            parent.setCheckState(0, Qt.Checked)
        elif checked_count == 0 and partially_checked_count == 0:
            parent.setCheckState(0, Qt.Unchecked)
        else:
            parent.setCheckState(0, Qt.PartiallyChecked)
            
        # Recursively update parent's parent
        self.update_parent_check_state(parent.parent())
        
    def get_checked_paths(self):
        """Get all checked paths and optimize them"""
        checked_paths = []
        
        def collect_checked(item):
            if item.checkState(0) == Qt.Checked:
                path = item.data(0, Qt.UserRole)
                # Check if this is a folder (has children)
                if item.childCount() > 0:
                    # For folders, we want to include all contents
                    checked_paths.append(f"{path}/...")
                else:
                    # For files, just include the file
                    checked_paths.append(path)
            elif item.checkState(0) == Qt.PartiallyChecked:
                # For partially checked folders, check children
                for i in range(item.childCount()):
                    collect_checked(item.child(i))
                    
        # Start from root items
        for i in range(self.tree.topLevelItemCount()):
            collect_checked(self.tree.topLevelItem(i))
            
        return self.optimize_paths(checked_paths)
        
    def optimize_paths(self, paths):
        """Optimize the paths to remove redundant entries"""
        # Sort paths to ensure parents come before children
        sorted_paths = sorted(paths)
        optimized = []
        
        for path in sorted_paths:
            # Check if this path is already covered by a parent folder
            is_covered = False
            for opt_path in optimized:
                if opt_path.endswith('/...'):
                    # This is a folder include
                    folder_prefix = opt_path[:-4] + '/'
                    if path.startswith(folder_prefix) or path + '/...' == opt_path:
                        is_covered = True
                        break
                        
            if not is_covered:
                optimized.append(path)
                
        return optimized
        
    def update_stream_spec(self):
        """Update the stream spec text based on selected items"""
        paths = self.get_checked_paths()
        
        if paths:
            spec_lines = [f"share {path}" for path in paths]
            self.stream_spec = "\n".join(spec_lines)
        else:
            self.stream_spec = "# No paths selected"
            
        self.spec_text.setPlainText(self.stream_spec)
        

def main(stream):
    print(f"The stream is {stream}")
    stream_obj = p4.run_stream("-o", f"{stream}")[0]
    parent = stream_obj["Parent"]
    paths = p4.run_files("--streamviews", f"{parent}/...")
    stream_files = [path['streamFile'].replace(f"{parent}/", '') for path in paths]
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Create and show the main window
    window = StreamSpecCreator(stream_files, parent)
    window.show()
    
    # Run the application
    sys.exit(app.exec())


if __name__ == '__main__':
    # Get argument and make sure it is a valid stream name
    if len(sys.argv) != 2:
        print("Usage: python main.py <stream>")
        sys.exit(1)
    main(sys.argv[1])