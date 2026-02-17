import os
import asyncio
from pathlib import Path
from typing import Optional, Set
import time
import hashlib

class InputProcessor:
    """Monitors an input folder and processes new/changed files."""
    
    def __init__(self, input_dir: str = "input", processed_marker_file: str = ".processed"):
        self.input_dir = Path(input_dir)
        self.input_dir.mkdir(exist_ok=True)
        self.processed_marker_file = processed_marker_file
        self.processed_hashes = self._load_processed_hashes()
        self._docling_available = self._check_docling()
    
    def _check_docling(self) -> bool:
        """Check if Docling is available for PDF parsing."""
        try:
            import docling
            print("✓ Docling is available for PDF parsing")
            return True
        except ImportError:
            print("⚠ Docling not installed. PDF parsing will be skipped.")
            print("  Install with: pip install docling")
            return False
    
    def _load_processed_hashes(self) -> dict:
        """Load previously processed file hashes."""
        marker_path = self.input_dir / self.processed_marker_file
        if not marker_path.exists():
            return {}
        
        hashes = {}
        try:
            with open(marker_path, 'r') as f:
                for line in f:
                    if ':' in line:
                        filename, file_hash = line.strip().split(':', 1)
                        hashes[filename] = file_hash
        except Exception as e:
            print(f"Warning: Could not load processed hashes: {e}")
        return hashes
    
    def _save_processed_hashes(self):
        """Save processed file hashes to marker file."""
        marker_path = self.input_dir / self.processed_marker_file
        try:
            with open(marker_path, 'w') as f:
                for filename, file_hash in self.processed_hashes.items():
                    f.write(f"{filename}:{file_hash}\n")
        except Exception as e:
            print(f"Warning: Could not save processed hashes: {e}")
    
    def _get_file_hash(self, filepath: Path) -> str:
        """Calculate hash of file contents."""
        try:
            with open(filepath, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
    
    def get_new_or_changed_files(self) -> list:
        """Get list of new or modified files in input directory."""
        new_files = []
        
        # Supported file extensions
        supported_extensions = ['.txt', '.md', '.json', '.text', '.pdf']
        
        for filepath in self.input_dir.glob('*'):
            if filepath.is_file() and filepath.name != self.processed_marker_file:
                # Check if it's a supported file
                if filepath.suffix.lower() in supported_extensions or filepath.suffix == '':
                    file_hash = self._get_file_hash(filepath)
                    filename = filepath.name
                    
                    # Check if new or changed
                    if filename not in self.processed_hashes or self.processed_hashes[filename] != file_hash:
                        new_files.append(filepath)
        
        return new_files
    
    def _parse_pdf(self, filepath: Path) -> str:
        """Parse PDF file using Docling and return text content."""
        if not self._docling_available:
            print(f"⚠ Docling not available. Skipping PDF: {filepath.name}")
            return ""
        
        try:
            from docling.document_converter import DocumentConverter
            
            print(f"Parsing PDF with Docling: {filepath.name}")
            
            # Create converter with timeout and faster settings
            converter = DocumentConverter()
            
            # Convert PDF to document with timeout
            print("Converting PDF (this may take a moment)...")
            result = converter.convert(str(filepath))
            
            # Extract text from document as markdown
            text_content = result.document.export_to_markdown()
            
            if not text_content or len(text_content.strip()) == 0:
                print(f"⚠ PDF parsed but no text extracted from {filepath.name}")
                return ""
            
            print(f"✓ Successfully extracted text from PDF ({len(text_content)} chars)")
            return text_content
            
        except asyncio.TimeoutError:
            print(f"✗ PDF parsing timed out for {filepath.name}")
            return ""
        except Exception as e:
            print(f"✗ Error parsing PDF {filepath.name}: {e}")
            return ""
    
    def read_file_content(self, filepath: Path) -> str:
        """Read content from a file (supports txt, md, json, and pdf)."""
        try:
            # Handle PDF files
            if filepath.suffix.lower() == '.pdf':
                return self._parse_pdf(filepath)
            
            # Handle text files
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            return ""
    
    async def watch_and_process(self, callback, check_interval: float = 2.0):
        """
        Continuously watch input directory and process new files.
        
        Args:
            callback: Async function to call with file content
            check_interval: Seconds between checks
        """
        print(f"Watching {self.input_dir.absolute()} for new files...")
        print("Supported formats: .txt, .md, .json, .pdf")
        
        while True:
            try:
                new_files = self.get_new_or_changed_files()
                
                for filepath in new_files:
                    print(f"\n{'='*60}")
                    print(f"Processing new/changed file: {filepath.name}")
                    print(f"{'='*60}")
                    
                    content = self.read_file_content(filepath)
                    if content:
                        await callback(content)
                        self.mark_as_processed(filepath)
                        print(f"✓ Completed processing: {filepath.name}")
                    else:
                        print(f"⚠ Skipped empty file: {filepath.name}")
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                print(f"Error in watch loop: {e}")
                await asyncio.sleep(check_interval)
    
    def mark_as_processed(self, filepath: Path):
        """Mark a file as processed."""
        file_hash = self._get_file_hash(filepath)
        self.processed_hashes[filepath.name] = file_hash
        self._save_processed_hashes()
    
    def process_once(self) -> list:
        """
        Process all new/changed files once and return their contents.
        Returns list of (filepath, content) tuples.
        """
        results = []
        new_files = self.get_new_or_changed_files()
        
        if not new_files:
            print("No new files to process")
            return results
        
        print(f"Found {len(new_files)} file(s) to process")
        
        for filepath in new_files:
            print(f"\nProcessing: {filepath.name}")
            content = self.read_file_content(filepath)
            if content:
                results.append((filepath, content))
            else:
                print(f"⚠ Skipped empty file: {filepath.name}")
        
        return results