import sys
from collections import defaultdict
from functools import wraps
from typing import Dict, List, Set, Tuple
import time

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QTextEdit, QLabel, QMessageBox, QPushButton, QSplitter, QDialog,
                             QProgressBar)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QObject
from P4 import P4, P4Exception

def show_error_dialog(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            QMessageBox.critical(None, "Error", str(e))
            raise
    return wrapper

p4 = P4()
p4.connect()


class LoadingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Loading...")
        self.setModal(True)
        self.setFixedSize(300, 100)
        
        layout = QVBoxLayout()
        
        self.label = QLabel("Loading stream files...")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminate progress
        layout.addWidget(self.progress)
        
        self.setLayout(layout)
        
        # Remove window decorations for cleaner look
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)


class FileTreeBuilder(QObject):
    """Worker class for building file tree structure in background"""
    progress = Signal(str)
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, stream_files):
        super().__init__()
        self.stream_files = stream_files
        
    def build_tree_structure(self):
        """Build tree structure as nested dictionaries"""
        try:
            self.progress.emit("Building file tree structure...")
            
            # Create tree structure
            tree = {}
            total_files = len(self.stream_files)
            
            for idx, file_path in enumerate(self.stream_files):
                if idx % 1000 == 0:
                    self.progress.emit(f"Processing file {idx}/{total_files}...")
                
                parts = file_path.split('/')
                
                # Handle root-level files
                if len(parts) == 1:
                    if '_files' not in tree:
                        tree['_files'] = []
                    tree['_files'].append(parts[0])
                    continue
                
                current = tree
                
                # Build nested structure
                for i, part in enumerate(parts):
                    if i == len(parts) - 1:
                        # This is a file
                        if '_files' not in current:
                            current['_files'] = []
                        current['_files'].append(part)
                    else:
                        # This is a folder
                        if part not in current:
                            current[part] = {}
                        current = current[part]
            
            self.finished.emit(tree)
            
        except Exception as e:
            self.error.emit(str(e))


class StreamSpecCreator(QMainWindow):
    def __init__(self, stream_obj, stream_files, parent_stream):
        super().__init__()
        self.stream_obj = stream_obj
        self.stream_files = stream_files
        self.parent_stream = parent_stream
        self.tree_structure = {}
        self.file_set = set(stream_files)  # For quick file existence checks
        
        self.init_ui()
        self.start_tree_building()
        
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
        self.tree.itemExpanded.connect(self.on_item_expanded)
        left_layout.addWidget(self.tree)
        
        # Progress label for tree building
        self.progress_label = QLabel("Building file tree...")
        left_layout.addWidget(self.progress_label)
        
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

        button_layout = QHBoxLayout()
        update_button = QPushButton("Update Stream")
        update_button.clicked.connect(self.on_update_stream)
        button_layout.addStretch()
        button_layout.addWidget(update_button)
        layout.addLayout(button_layout)
        
        # Generate initial spec (empty)
        self.update_stream_spec()
        
    def start_tree_building(self):
        """Start building tree structure in background thread"""
        self.thread = QThread()
        self.worker = FileTreeBuilder(self.stream_files)
        self.worker.moveToThread(self.thread)
        
        # Connect signals
        self.thread.started.connect(self.worker.build_tree_structure)
        self.worker.progress.connect(self.on_build_progress)
        self.worker.finished.connect(self.on_tree_structure_ready)
        self.worker.error.connect(self.on_build_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        # Start the thread
        self.thread.start()
        
    def on_build_progress(self, message):
        """Update progress label"""
        self.progress_label.setText(message)
        
    def on_build_error(self, error_msg):
        """Handle build errors"""
        self.progress_label.setText(f"Error: {error_msg}")
        QMessageBox.critical(self, "Error", f"Failed to build tree: {error_msg}")
        
    def on_tree_structure_ready(self, tree_structure):
        """Tree structure is ready, now build the UI tree"""
        self.tree_structure = tree_structure
        self.progress_label.setText("Populating tree view...")
        
        # Build only the top-level items
        self.tree.setUpdatesEnabled(False)
        root = self.tree.invisibleRootItem()
        self.build_tree_level(root, self.tree_structure, "")
        self.tree.setUpdatesEnabled(True)
        
        self.progress_label.hide()
        
    def build_tree_level(self, parent_item, level_dict, parent_path):
        """Build one level of the tree with lazy loading"""
        # First add folders
        for folder_name, folder_contents in sorted(level_dict.items()):
            if folder_name.startswith('_'):
                continue
                
            current_path = f"{parent_path}/{folder_name}" if parent_path else folder_name
            
            folder_item = QTreeWidgetItem(parent_item)
            folder_item.setText(0, folder_name)
            folder_item.setCheckState(0, parent_item.checkState(0)) # set child to match parent when building
            folder_item.setData(0, Qt.UserRole, current_path)
            folder_item.setData(1, Qt.UserRole, folder_contents)  # Store contents for lazy loading
            folder_item.setFlags(folder_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            
            # Check if folder has any contents
            has_subfolders = any(k for k in folder_contents.keys() if not k.startswith('_'))
            has_files = '_files' in folder_contents and len(folder_contents['_files']) > 0
            
            if has_subfolders or has_files:
                # Add placeholder to show expand arrow
                placeholder = QTreeWidgetItem(folder_item)
                placeholder.setText(0, "Loading...")
                placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
                placeholder.setData(0, Qt.UserRole, None)
        
        # Then add files
        if '_files' in level_dict and level_dict['_files']:
            for file_name in sorted(level_dict['_files']):
                file_path = f"{parent_path}/{file_name}" if parent_path else file_name
                
                file_item = QTreeWidgetItem(parent_item)
                file_item.setText(0, file_name)
                # set check state to match parent unless p4ignore file, then always check.
                file_item.setCheckState(0, parent_item.checkState(0) if file_name not in ['p4ignore.txt', '.p4ignore'] else Qt.Checked)
                file_item.setData(0, Qt.UserRole, file_path)
                file_item.setFlags(file_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                
    def on_item_expanded(self, item):
        """Handle item expansion for lazy loading"""
        # Check if this item has a placeholder child
        if item.childCount() == 1 and item.child(0).text(0) == "Loading...":
            # Remove placeholder
            item.takeChild(0)
            
            # Get stored contents
            contents = item.data(1, Qt.UserRole)
            path = item.data(0, Qt.UserRole)
            
            if contents and path:
                # Build children
                self.tree.setUpdatesEnabled(False)
                self.build_tree_level(item, contents, path)
                self.tree.setUpdatesEnabled(True)
                
                # Enable tri-state for folders after expansion
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsAutoTristate)

    def on_item_changed(self, item, column):
        """Handle item check state changes"""
        if column != 0:
            return
            
        path = item.data(0, Qt.UserRole)
        if path is None:
            return  # Skip placeholders
            
        check_state = item.checkState(0)
        
        # Block signals to prevent recursive calls
        self.tree.blockSignals(True)
        
        # Handle folder selection
        if check_state == Qt.Checked:
            # If this is an unexpanded folder, that's fine
            if item.childCount() == 1 and item.child(0).text(0) == "Loading...":
                pass
            elif item.childCount() > 0:
                # Update all loaded children
                self.update_children_check_state(item, check_state)
        elif check_state == Qt.Unchecked:
            # Uncheck all children if they're loaded
            if item.childCount() > 0 and not (item.childCount() == 1 and item.child(0).text(0) == "Loading..."):
                self.update_children_check_state(item, check_state)
        
        # Update parent check states
        self.update_parent_check_state(item.parent())
        
        # Unblock signals
        self.tree.blockSignals(False)
        
        # Update the stream spec
        self.update_stream_spec()
        
    def update_children_check_state(self, item, check_state):
        """Update children check states"""
        for i in range(item.childCount()):
            child = item.child(i)
            if child.text(0) != "Loading...":  # Skip placeholders
                child.setCheckState(0, check_state)
                if child.childCount() > 0:
                    self.update_children_check_state(child, check_state)
            
    def update_parent_check_state(self, parent):
        """Update parent check state based on children"""
        if parent is None:
            return
            
        checked_count = 0
        partially_checked_count = 0
        total_count = 0
        
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.text(0) != "Loading...":  # Skip placeholders
                total_count += 1
                if child.checkState(0) == Qt.Checked:
                    checked_count += 1
                elif child.checkState(0) == Qt.PartiallyChecked:
                    partially_checked_count += 1
                    
        if total_count == 0:
            return
            
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
        checked_items = []
        
        def collect_checked(item):
            if item.checkState(0) == Qt.Checked:
                path = item.data(0, Qt.UserRole)
                if path:  # Skip placeholders
                    # Check if this is a folder
                    is_folder = item.childCount() > 0 or self.is_folder(path)
                    checked_items.append((path, is_folder))
            elif item.checkState(0) == Qt.PartiallyChecked:
                # For partially checked folders, check children
                for i in range(item.childCount()):
                    child = item.child(i)
                    if child.text(0) != "Loading...":  # Skip placeholders
                        collect_checked(child)
                    
        # Start from root items
        for i in range(self.tree.topLevelItemCount()):
            collect_checked(self.tree.topLevelItem(i))
            
        # Convert to path format
        result_paths = []
        for path, is_folder in checked_items:
            if is_folder:
                result_paths.append(f"{path}/...")
            else:
                result_paths.append(path)
                
        return self.optimize_paths(result_paths)
        
    def is_folder(self, path):
        """Check if a path represents a folder"""
        if path is None:
            return False
        # A path is a folder if any file in our file_set starts with path/
        prefix = path + '/'
        return any(f.startswith(prefix) for f in self.file_set)
        
    def optimize_paths(self, paths):
        """Optimize the paths to remove redundant entries"""
        sorted_paths = sorted(paths)
        optimized = []
        
        for path in sorted_paths:
            is_covered = False
            for opt_path in optimized:
                if opt_path.endswith('/...'):
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
            self.spec_lines = [f'share "{path}"' if " " in path else f"share {path}" for path in paths]
            self.stream_spec = "\n".join(self.spec_lines)
        else:
            self.stream_spec = "# No paths selected"
            self.spec_lines = []
            
        self.spec_text.setPlainText(self.stream_spec)

    @show_error_dialog
    def on_update_stream(self):
        """Update the stream based on selected items"""
        new_spec = self.stream_obj
        new_spec["Paths"] = self.spec_lines
        p4.save_stream(new_spec)
        self.close()

        
@show_error_dialog
def main(stream):
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Show loading dialog
    loading = LoadingDialog()
    loading.show()
    QApplication.processEvents()
    
    print(f"The stream is {stream}")
    stream_obj = p4.run_stream("-o", f"{stream}")[0]
    if stream_obj["Type"] != "virtual":
        raise Exception(f"Stream {stream} is not a virtual stream")
    parent = stream_obj["Parent"]
    
    loading.label.setText(f"Loading files from {parent}...")
    QApplication.processEvents()
    
    paths = p4.run_files("--streamviews", f"{parent}/...")
    stream_files = [path['streamFile'].replace(f"{parent}/", '') for path in paths]
    
    loading.label.setText("Building interface...")
    QApplication.processEvents()
    
    # Create and show the main window
    window = StreamSpecCreator(stream_obj, stream_files, parent)

    def show_main_window():
        # Close loading dialog and show main window
        loading.close()
        window.show()

    QTimer.singleShot(100, show_main_window)
    
    # Run the application
    return app.exec()


if __name__ == '__main__':
    # Get argument and make sure it is a valid stream name
    if len(sys.argv) != 2:
        print("Usage: python main.py <stream>")
        sys.exit(1)
    main(sys.argv[1])