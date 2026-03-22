"""Author name extraction from corpus documents.

Extracts author names from:
- Document metadata
- Book inventory entries
- Citation patterns
- Corpus text files

Handles name variants (Armenian script, transliteration).

Pipeline: This module produces ExtractedAuthor lists; create_author_profiles()
converts them to AuthorProfile (from author_research). AuthorProfileManager
stores and manages profiles. See author_research for schema and persistence.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from hytools.ingestion.discovery.author_research import AuthorProfile, AuthorProfileManager
from hytools.ingestion.discovery.book_inventory import BookInventoryEntry, BookInventoryManager

logger = logging.getLogger(__name__)


@dataclass
class ExtractedAuthor:
    """Author name extracted from corpus."""
    name: str  # Name as it appears in source
    source: str  # Where it was found (filename, metadata field, etc.)
    confidence: float = 1.0  # 0-1 confidence in extraction
    context: str = ""  # Surrounding text for verification
    name_variants: list[str] = field(default_factory=list)  # Other forms found


class AuthorExtractor:
    """Extract author names from various sources."""
    
    def __init__(self):
        """Initialize author extractor."""
        self.extracted_authors: dict[str, ExtractedAuthor] = {}
        self.name_frequency: Counter = Counter()
    
    def extract_from_book_inventory(
        self,
        inventory_manager: BookInventoryManager,
    ) -> list[ExtractedAuthor]:
        """Extract authors from book inventory.
        
        Args:
            inventory_manager: BookInventoryManager instance
            
        Returns:
            List of ExtractedAuthor objects
        """
        extracted = []
        
        for book in inventory_manager.books:
            for author in book.authors:
                name = author.name.strip()
                if not name or name.lower() == "unknown":
                    continue
                
                extracted_author = ExtractedAuthor(
                    name=name,
                    source=f"book_inventory:{book.title}",
                    confidence=0.95,  # High confidence from structured data
                    context=f"Author of '{book.title}' ({book.first_publication_year})",
                )
                
                # Add variants if available
                if book.title_transliteration:
                    extracted_author.name_variants.append(book.title_transliteration)
                
                extracted.append(extracted_author)
                self.name_frequency[name] += 1
        
        logger.info(f"Extracted {len(extracted)} authors from book inventory")
        return extracted
    
    def extract_from_corpus_metadata(
        self,
        metadata_file: Path,
    ) -> list[ExtractedAuthor]:
        """Extract authors from corpus metadata files.
        
        Args:
            metadata_file: Path to metadata JSON/JSONL file
            
        Returns:
            List of ExtractedAuthor objects
        """
        extracted = []
        
        if not metadata_file.exists():
            logger.warning(f"Metadata file not found: {metadata_file}")
            return extracted
        
        try:
            # Handle JSONL
            if metadata_file.suffix == ".jsonl":
                with open(metadata_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        
                        data = json.loads(line)
                        author_name = data.get("author") or data.get("creator")
                        
                        if author_name:
                            extracted.append(ExtractedAuthor(
                                name=author_name,
                                source=f"metadata:{metadata_file.name}",
                                confidence=0.9,
                                context=data.get("title", ""),
                            ))
                            self.name_frequency[author_name] += 1
            
            # Handle JSON
            elif metadata_file.suffix == ".json":
                with open(metadata_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                    # Handle different JSON structures
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        items = data.get("items", [data])
                    else:
                        items = []
                    
                    for item in items:
                        author_name = item.get("author") or item.get("creator")
                        if author_name:
                            extracted.append(ExtractedAuthor(
                                name=author_name,
                                source=f"metadata:{metadata_file.name}",
                                confidence=0.9,
                                context=item.get("title", ""),
                            ))
                            self.name_frequency[author_name] += 1
        
        except Exception as e:
            logger.error(f"Error reading metadata {metadata_file}: {e}")
        
        logger.info(f"Extracted {len(extracted)} authors from {metadata_file.name}")
        return extracted
    
    def extract_from_text_patterns(
        self,
        text: str,
        source_name: str = "corpus_text",
    ) -> list[ExtractedAuthor]:
        """Extract authors using pattern matching.
        
        Finds patterns like:
        - "Գրած՝ [Author Name]"
        - "Հեղինակ՝ [Author Name]"
        - "[Name] (հեղինակ)"
        - "By [Author Name]"
        
        Args:
            text: Text to search
            source_name: Source identifier
            
        Returns:
            List of ExtractedAuthor objects
        """
        extracted = []
        
        # Armenian patterns
        patterns = [
            r"[Գգ]րած[՝։]\s*([Ա-Ֆա-ֆ\s\.]{3,30})",  # Գրած՝ [Name]
            r"[Հհ]եղինակ[՝։]\s*([Ա-Ֆա-ֆ\s\.]{3,30})",  # Հեղինակ՝ [Name]
            r"([Ա-Ֆա-ֆ\s\.]{3,30})\s*\([Հհ]եղինակ\)",  # [Name] (հեղինակ)
            r"([Ա-Ֆ]\.\s*[Ա-Ֆա-ֆ]{3,20})",  # Օ. Թունեան pattern (initial + surname)
        ]
        
        for pattern in patterns:
            try:
                matches = re.finditer(pattern, text)
                for match in matches:
                    # Try to get capture group, fallback to full match
                    try:
                        name = match.group(1).strip()
                    except IndexError:
                        name = match.group(0).strip()
                    
                    # Basic validation
                    if len(name) < 3 or len(name) > 30:
                        continue
                    
                    # Extract context
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end]
                    
                    extracted.append(ExtractedAuthor(
                        name=name,
                        source=source_name,
                        confidence=0.7,  # Lower confidence for pattern matching
                        context=context,
                    ))
                    self.name_frequency[name] += 1
            except Exception as e:
                logger.warning(f"Pattern matching error with pattern '{pattern}': {e}")
                continue
        
        logger.info(f"Extracted {len(extracted)} authors via pattern matching from {source_name}")
        return extracted

    def deduplicate_authors(
        self,
        extracted: list[ExtractedAuthor],
    ) -> list[ExtractedAuthor]:
        """Deduplicate and merge author entries.
        
        Args:
            extracted: List of ExtractedAuthor objects
            
        Returns:
            Deduplicated list
        """
        # Group by normalized name
        groups: dict[str, list[ExtractedAuthor]] = {}
        
        for author in extracted:
            normalized = self._normalize_name(author.name)
            if normalized not in groups:
                groups[normalized] = []
            groups[normalized].append(author)
        
        # Merge groups
        merged = []
        for normalized, group in groups.items():
            if len(group) == 1:
                merged.append(group[0])
            else:
                # Merge multiple entries
                primary = max(group, key=lambda a: a.confidence)
                
                # Collect all variants
                variants = set()
                for author in group:
                    if author.name != primary.name:
                        variants.add(author.name)
                    variants.update(author.name_variants)
                
                primary.name_variants = list(variants)
                
                # Sum confidence (capped at 1.0)
                total_confidence = sum(a.confidence for a in group)
                primary.confidence = min(1.0, total_confidence / len(group) + 0.1)
                
                merged.append(primary)
        
        logger.info(f"Deduplicated {len(extracted)} → {len(merged)} authors")
        return merged
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison.
        
        Args:
            name: Author name
            
        Returns:
            Normalized name
        """
        # Remove punctuation and extra whitespace
        normalized = re.sub(r"[,\.։՝\-]", "", name)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip().lower()
    
    def create_author_profiles(
        self,
        extracted: list[ExtractedAuthor],
        min_confidence: float = 0.6,
    ) -> list[AuthorProfile]:
        """Convert extracted authors to AuthorProfile objects.
        
        Args:
            extracted: List of ExtractedAuthor objects
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of AuthorProfile objects
        """
        profiles = []
        
        for author in extracted:
            if author.confidence < min_confidence:
                continue
            
            # Generate author ID
            author_id = self._generate_author_id(author.name)
            
            # Create profile
            profile = AuthorProfile(
                author_id=author_id,
                primary_name=author.name,
                name_variants=author.name_variants or [],
                research_sources=[author.source],
                confidence_birth=0.0,  # Unknown until enriched
                confidence_death=0.0,
                confidence_writing_period=0.0,
                notes=f"Extracted from {author.source}. Context: {author.context[:100]}",
            )
            
            profiles.append(profile)
        
        logger.info(f"Created {len(profiles)} author profiles from {len(extracted)} extractions")
        return profiles
    
    def _generate_author_id(self, name: str) -> str:
        """Generate unique author ID.
        
        Args:
            name: Author name
            
        Returns:
            Author ID
        """
        import hashlib
        
        # Use first 8 chars of hash
        name_hash = hashlib.md5(name.encode("utf-8")).hexdigest()[:8]
        
        # Try to extract surname or initials
        parts = name.split()
        if len(parts) >= 2:
            prefix = parts[-1][:4].lower()  # Last name
        else:
            prefix = name[:4].lower()
        
        return f"{prefix}{name_hash}"
    
    def get_statistics(self) -> dict:
        """Get extraction statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_extracted": len(self.extracted_authors),
            "unique_authors": len(self.name_frequency),
            "top_10_authors": self.name_frequency.most_common(10),
            "avg_confidence": sum(a.confidence for a in self.extracted_authors.values()) / len(self.extracted_authors) if self.extracted_authors else 0,
        }


def extract_authors_from_corpus(
    corpus_dir: Path,
    inventory_file: Optional[Path] = None,
    metadata_patterns: Optional[list[str]] = None,
    exclude_dirs: Optional[list[str]] = None,
    return_stats: bool = False,
):
    """Extract all authors from corpus.

    Args:
        corpus_dir: Corpus directory
        inventory_file: Optional book inventory file
        metadata_patterns: Glob patterns for metadata files
        exclude_dirs: Directories to exclude (e.g., ['augmented', 'logs'])
        return_stats: If True, return (extracted, error_count, total_processed) for error threshold checks.

    Returns:
        List of ExtractedAuthor objects, or if return_stats True: (list, error_count, total_processed)
    """
    extractor = AuthorExtractor()
    all_extracted = []
    exclude_dirs = exclude_dirs or []
    error_count = 0
    total_processed = 0

    # Extract from book inventory
    if inventory_file and inventory_file.exists():
        try:
            inventory_manager = BookInventoryManager(inventory_file=str(inventory_file))
            extracted = extractor.extract_from_book_inventory(inventory_manager)
            all_extracted.extend(extracted)
            total_processed += 1
        except Exception as e:
            logger.warning("Book inventory extraction failed: %s", e)
            error_count += 1
            total_processed += 1

    # Extract from metadata files
    if metadata_patterns:
        for pattern in metadata_patterns:
            for metadata_file in corpus_dir.rglob(pattern):
                if any(excluded in metadata_file.parts for excluded in exclude_dirs):
                    continue
                total_processed += 1
                try:
                    extracted = extractor.extract_from_corpus_metadata(metadata_file)
                    all_extracted.extend(extracted)
                except Exception as e:
                    logger.warning("Metadata extraction failed for %s: %s", metadata_file.name, e)
                    error_count += 1

    # Extract from text files
    text_count = 0
    max_text_files = 100
    scanned_count = 0
    for text_file in corpus_dir.rglob("*.txt"):
        scanned_count += 1
        if any(excluded in text_file.parts for excluded in exclude_dirs):
            continue
        if text_count >= max_text_files:
            logger.info(f"Reached max text files limit ({max_text_files}), skipping remaining")
            break
        if scanned_count > 1000:
            logger.info(f"Scanned {scanned_count} files, stopping to prevent hang")
            break
        total_processed += 1
        try:
            with open(text_file, "r", encoding="utf-8") as f:
                text = f.read(50000)
            extracted = extractor.extract_from_text_patterns(text, source_name=text_file.name)
            all_extracted.extend(extracted)
            text_count += 1
        except Exception as e:
            logger.warning(f"Error reading {text_file.name}: {e}")
            error_count += 1

    # Deduplicate
    all_extracted = extractor.deduplicate_authors(all_extracted)
    logger.info(f"Extracted {len(all_extracted)} unique authors from corpus")

    if return_stats:
        return all_extracted, error_count, max(total_processed, 1)
    return all_extracted


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Example usage
    extractor = AuthorExtractor()
    
    # Example: extract from book inventory
    inventory_manager = BookInventoryManager()
    extracted = extractor.extract_from_book_inventory(inventory_manager)
    
    print(f"Extracted {len(extracted)} authors")
    print("\nTop 10 authors:")
    for name, count in extractor.name_frequency.most_common(10):
        print(f"  {name}: {count} mentions")
