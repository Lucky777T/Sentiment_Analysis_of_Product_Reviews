import sys
from difflib import get_close_matches
import csv
import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QPushButton, QComboBox, QMessageBox,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont

# Function to load words from a file
def load_words(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return set(word.strip() for word in f if word.strip())
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        return set()

# Word Lists (Optimized as sets for faster lookup)
POSITIVE_WORDS = load_words("positive_words.txt")
NEGATIVE_WORDS = load_words("negative_words.txt")

class AnalysisThread(QThread):
    update_progress = pyqtSignal(int)
    analysis_complete = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, review, use_fuzzy):
        super().__init__()
        self.review = review
        self.use_fuzzy = use_fuzzy
        self.fuzzy_cache = {}

    def run(self):
        try:
            if self.use_fuzzy:
                result = self._analyze_fuzzy()
            else:
                result = self._analyze_strict()
            
            self.analysis_complete.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _analyze_strict(self):
        review_lower = self.review.lower()
        pos_matches = [word for word in POSITIVE_WORDS if word in review_lower]
        neg_matches = [word for word in NEGATIVE_WORDS if word in review_lower]
        
        return {
            "sentiment": self._determine_sentiment(pos_matches, neg_matches),
            "pos_matches": pos_matches,
            "neg_matches": neg_matches,
            "review": self.review
        }

    def _analyze_fuzzy(self):
        words = self.review.lower().split()
        pos_matches = []
        neg_matches = []
        total_words = len(words)
        
        for i, word in enumerate(words):
            if i % 5 == 0:  # Update progress every 5 words
                self.update_progress.emit(int((i / total_words) * 100))
            
            # Check positive matches
            if word in self.fuzzy_cache:
                if self.fuzzy_cache[word] in POSITIVE_WORDS:
                    pos_matches.append(self.fuzzy_cache[word])
            else:
                closest = self._find_closest_match(word, POSITIVE_WORDS)
                if closest:
                    self.fuzzy_cache[word] = closest
                    pos_matches.append(closest)
            
            # Check negative matches
            if word in self.fuzzy_cache:
                if self.fuzzy_cache[word] in NEGATIVE_WORDS:
                    neg_matches.append(self.fuzzy_cache[word])
            else:
                closest = self._find_closest_match(word, NEGATIVE_WORDS)
                if closest:
                    self.fuzzy_cache[word] = closest
                    neg_matches.append(closest)
        
        self.update_progress.emit(100)
        return {
            "sentiment": self._determine_sentiment(pos_matches, neg_matches),
            "pos_matches": pos_matches,
            "neg_matches": neg_matches,
            "review": self.review
        }

    def _find_closest_match(self, word, word_set, cutoff=0.7):
        matches = get_close_matches(word, word_set, n=1, cutoff=cutoff)
        return matches[0] if matches else None

    def _determine_sentiment(self, pos_matches, neg_matches):
        if len(pos_matches) > len(neg_matches):
            return "Positive"
        elif len(neg_matches) > len(pos_matches):
            return "Negative"
        return "Neutral"

class SentimentAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto-Saving Sentiment Analyzer")
        self.setMinimumSize(800, 600)
        
        # Initialize CSV file
        self.csv_file = "sentiment_results.csv"
        self._init_csv()
        
        # Main UI
        self._setup_ui()
        
        # Current analysis results
        self.current_results = None

    def _init_csv(self):
        """Initialize CSV file with headers if it doesn't exist"""
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Review Excerpt", "Sentiment",
                    "Positive Words", "Negative Words", "Positive Count", "Negative Count"
                ])

    def _setup_ui(self):
        """Set up the main UI components"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Title
        title = QLabel("Sentiment Analysis with Auto-Save")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Input Section
        input_group = QWidget()
        input_layout = QVBoxLayout(input_group)
        
        input_layout.addWidget(QLabel("Enter Product Review:"))
        self.review_input = QTextEdit()
        self.review_input.setPlaceholderText("Paste your product review here...")
        input_layout.addWidget(self.review_input)
        
        # Controls
        controls = QHBoxLayout()
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Fast Strict Matching", "Fuzzy Matching (Slower)"])
        controls.addWidget(self.mode_combo)
        
        self.analyze_btn = QPushButton("Analyze & Save")
        self.analyze_btn.clicked.connect(self.start_analysis)
        controls.addWidget(self.analyze_btn)
        
        input_layout.addLayout(controls)
        layout.addWidget(input_group)
        
        # Progress Bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        # Results Display
        results_group = QWidget()
        results_layout = QVBoxLayout(results_group)
        
        results_layout.addWidget(QLabel("Analysis Results:"))
        
        # Results Table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Sentiment", "Positive Words", "Negative Words", "Counts"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        results_layout.addWidget(self.results_table)
        
        # Detailed Results
        self.details_display = QTextEdit()
        self.details_display.setReadOnly(True)
        results_layout.addWidget(self.details_display)
        
        layout.addWidget(results_group)
        
        # History Button
        self.history_btn = QPushButton("Show Analysis History")
        self.history_btn.clicked.connect(self.show_history)
        layout.addWidget(self.history_btn)

    def start_analysis(self):
        """Start the analysis process"""
        review = self.review_input.toPlainText().strip()
        
        if not review:
            QMessageBox.warning(self, "Empty Review", "Please enter a review to analyze!")
            return
        
        # Disable UI during analysis
        self._set_ui_enabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        
        # Start analysis thread
        self.analysis_thread = AnalysisThread(
            review,
            self.mode_combo.currentIndex() == 1
        )
        self.analysis_thread.update_progress.connect(self.progress.setValue)
        self.analysis_thread.analysis_complete.connect(self._on_analysis_complete)
        self.analysis_thread.error_occurred.connect(self._on_analysis_error)
        self.analysis_thread.start()

    def _on_analysis_complete(self, results):
        """Handle successful analysis completion"""
        # Save results to CSV
        self._save_to_csv(results)
        
        # Update UI with results
        self._display_results(results)
        
        # Re-enable UI
        self._set_ui_enabled(True)
        self.progress.setVisible(False)
        
        # Store current results
        self.current_results = results

    def _save_to_csv(self, results):
        """Automatically save results to CSV"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        review_excerpt = (results["review"][:100] + "...") if len(results["review"]) > 100 else results["review"]
        
        with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                review_excerpt,
                results["sentiment"],
                ", ".join(results["pos_matches"]),
                ", ".join(results["neg_matches"]),
                len(results["pos_matches"]),
                len(results["neg_matches"])
            ])

    def _display_results(self, results):
        """Display results in the table and details area"""
        # Clear previous results
        self.results_table.setRowCount(0)
        
        # Add main result row
        row_pos = self.results_table.rowCount()
        self.results_table.insertRow(row_pos)
        
        # Set sentiment with color coding
        sentiment_item = QTableWidgetItem(results["sentiment"])
        if results["sentiment"] == "Positive":
            sentiment_item.setBackground(QColor(200, 255, 200))
        elif results["sentiment"] == "Negative":
            sentiment_item.setBackground(QColor(255, 200, 200))
        else:
            sentiment_item.setBackground(QColor(240, 240, 240))
        
        self.results_table.setItem(row_pos, 0, sentiment_item)
        self.results_table.setItem(row_pos, 1, QTableWidgetItem(", ".join(results["pos_matches"]) or "None"))
        self.results_table.setItem(row_pos, 2, QTableWidgetItem(", ".join(results["neg_matches"]) or "None"))
        self.results_table.setItem(row_pos, 3, QTableWidgetItem(f"{len(results['pos_matches'])} / {len(results['neg_matches'])}"))
        
        # Display detailed results
        details = (
            f"=== Full Analysis ===\n"
            f"Sentiment: {results['sentiment']}\n\n"
            f"Positive Matches ({len(results['pos_matches'])}):\n"
            f"{', '.join(results['pos_matches']) or 'None'}\n\n"
            f"Negative Matches ({len(results['neg_matches'])}):\n"
            f"{', '.join(results['neg_matches']) or 'None'}\n\n"
            f"Review Excerpt:\n"
            f"{results['review'][:300]}{'...' if len(results['review']) > 300 else ''}"
        )
        self.details_display.setPlainText(details)

    def _on_analysis_error(self, error_msg):
        """Handle analysis errors"""
        QMessageBox.critical(self, "Analysis Error", f"An error occurred:\n{error_msg}")
        self._set_ui_enabled(True)
        self.progress.setVisible(False)

    def _set_ui_enabled(self, enabled):
        """Enable/disable UI elements during analysis"""
        self.review_input.setEnabled(enabled)
        self.mode_combo.setEnabled(enabled)
        self.analyze_btn.setEnabled(enabled)
        self.history_btn.setEnabled(enabled)

    def show_history(self):
        """Display analysis history from CSV"""
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
                data = list(reader)
            
            if not data:
                QMessageBox.information(self, "History", "No analysis history found!")
                return
            
            history_dialog = QDialog(self)
            history_dialog.setWindowTitle("Analysis History")
            history_dialog.setMinimumSize(900, 600)
            
            layout = QVBoxLayout(history_dialog)
            
            table = QTableWidget()
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.setRowCount(len(data))
            
            for row_idx, row in enumerate(data):
                for col_idx, value in enumerate(row):
                    item = QTableWidgetItem(value)
                    
                    # Color code sentiment column
                    if headers[col_idx] == "Sentiment":
                        if value == "Positive":
                            item.setBackground(QColor(200, 255, 200))
                        elif value == "Negative":
                            item.setBackground(QColor(255, 200, 200))
                    
                    table.setItem(row_idx, col_idx, item)
            
            table.resizeColumnsToContents()
            layout.addWidget(table)
            
            history_dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load history:\n{str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Set application font
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)
    
    analyzer = SentimentAnalyzer()
    analyzer.show()
    sys.exit(app.exec())