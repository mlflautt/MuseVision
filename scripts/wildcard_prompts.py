#!/usr/bin/env python3
"""
Wildcard Prompt System for MuseVision

This module provides functionality to enhance prompts with randomly selected terms
from wildcard .txt files, with intelligent integration and deduplication.

Features:
- Load terms from .txt files in the wildcards directory
- Random selection from specified or all wildcard files
- Intelligent prompt integration with deduplication
- Configurable selection counts and positioning
- Support for weighted and categorized selection
"""

import os
import glob
import random
import re
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass


@dataclass
class WildcardConfig:
    """Configuration for wildcard selection and integration"""
    wildcards_dir: str = "/home/mitchellflautt/MuseVision/wildcards"
    selected_files: Optional[List[str]] = None  # None = use all files
    terms_per_file: int = 1  # Number of terms to select per file
    total_terms: Optional[int] = None  # Max total terms (overrides per_file if set)
    position: str = "prepend"  # "prepend", "append", or "integrate"
    separator: str = ", "  # Separator between wildcard terms and prompt
    avoid_duplicates: bool = True  # Check for existing terms in prompt
    case_sensitive: bool = False  # Case sensitivity for duplicate detection


class WildcardSystem:
    """Main wildcard system for prompt enhancement"""
    
    def __init__(self, config: WildcardConfig = None):
        self.config = config or WildcardConfig()
        self.wildcard_files = {}
        self.terms_cache = {}
        self._load_wildcard_files()
    
    def _load_wildcard_files(self):
        """Load and cache wildcard files from the directory"""
        if not os.path.exists(self.config.wildcards_dir):
            raise FileNotFoundError(f"Wildcards directory not found: {self.config.wildcards_dir}")
        
        # Find all .txt files in the wildcards directory
        pattern = os.path.join(self.config.wildcards_dir, "*.txt")
        txt_files = glob.glob(pattern)
        
        if not txt_files:
            raise FileNotFoundError(f"No .txt files found in wildcards directory: {self.config.wildcards_dir}")
        
        for file_path in txt_files:
            filename = os.path.basename(file_path)
            file_key = os.path.splitext(filename)[0]  # Remove .txt extension
            
            try:
                terms = self._load_terms_from_file(file_path)
                self.wildcard_files[file_key] = {
                    'path': file_path,
                    'terms': terms,
                    'count': len(terms)
                }
                self.terms_cache[file_key] = terms
                
            except Exception as e:
                print(f"⚠️  Warning: Failed to load {filename}: {e}")
        
        print(f"📁 Loaded {len(self.wildcard_files)} wildcard files:")
        for key, data in self.wildcard_files.items():
            print(f"   {key}: {data['count']} terms")
    
    def _load_terms_from_file(self, file_path: str) -> List[str]:
        """Load terms from a single wildcard file"""
        terms = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):  # Skip empty lines and comments
                    continue
                
                # Handle numbered lists (e.g., "1|term" -> "term")
                if '|' in line:
                    parts = line.split('|', 1)
                    if len(parts) > 1:
                        term = parts[1].strip()
                    else:
                        term = parts[0].strip()
                else:
                    term = line
                
                if term:  # Only add non-empty terms
                    terms.append(term)
        
        return terms
    
    def get_available_files(self) -> List[str]:
        """Get list of available wildcard file names"""
        return list(self.wildcard_files.keys())
    
    def select_wildcard_terms(self, files: Optional[List[str]] = None) -> Dict[str, List[str]]:
        """
        Select random terms from specified wildcard files
        
        Args:
            files: List of file keys to select from (None = use config or all files)
            
        Returns:
            Dictionary mapping file keys to selected terms
        """
        # Determine which files to use
        if files is None:
            files = self.config.selected_files or list(self.wildcard_files.keys())
        
        # Validate requested files exist
        missing_files = [f for f in files if f not in self.wildcard_files]
        if missing_files:
            raise ValueError(f"Wildcard files not found: {missing_files}")
        
        selected_terms = {}
        total_selected = 0
        
        for file_key in files:
            available_terms = self.terms_cache[file_key]
            
            if not available_terms:
                continue
            
            # Determine how many terms to select from this file
            if self.config.total_terms and total_selected >= self.config.total_terms:
                break
            
            if self.config.total_terms:
                # If total_terms is set, distribute remaining selections
                remaining_files = len([f for f in files[files.index(file_key):] if self.terms_cache[f]])
                remaining_budget = self.config.total_terms - total_selected
                terms_to_select = min(
                    remaining_budget // remaining_files + (1 if remaining_budget % remaining_files > 0 else 0),
                    len(available_terms),
                    self.config.terms_per_file
                )
            else:
                terms_to_select = min(self.config.terms_per_file, len(available_terms))
            
            if terms_to_select > 0:
                selected = random.sample(available_terms, terms_to_select)
                selected_terms[file_key] = selected
                total_selected += len(selected)
        
        return selected_terms
    
    def _extract_existing_terms(self, prompt: str) -> Set[str]:
        """Extract potential wildcard terms already present in the prompt"""
        if not self.config.avoid_duplicates:
            return set()
        
        # Create a set of all known wildcard terms for comparison
        all_terms = set()
        for terms_list in self.terms_cache.values():
            if self.config.case_sensitive:
                all_terms.update(terms_list)
            else:
                all_terms.update(term.lower() for term in terms_list)
        
        # Check which terms are already in the prompt
        existing_terms = set()
        prompt_check = prompt if self.config.case_sensitive else prompt.lower()
        
        for term in all_terms:
            # Use word boundaries to avoid partial matches
            # Also check for hyphenated versions (e.g., "close-up" vs "close up")
            if self.config.case_sensitive:
                # Check exact match
                pattern = r'\b' + re.escape(term) + r'\b'
                if re.search(pattern, prompt):
                    existing_terms.add(term)
                # Check hyphenated version
                hyphenated = term.replace(' ', '-')
                pattern_hyphen = r'\b' + re.escape(hyphenated) + r'\b'
                if re.search(pattern_hyphen, prompt):
                    existing_terms.add(term)
            else:
                # Check exact match
                pattern = r'\b' + re.escape(term.lower()) + r'\b'
                if re.search(pattern, prompt_check):
                    existing_terms.add(term.lower())
                # Check hyphenated version
                hyphenated = term.lower().replace(' ', '-')
                pattern_hyphen = r'\b' + re.escape(hyphenated) + r'\b'
                if re.search(pattern_hyphen, prompt_check):
                    existing_terms.add(term.lower())
        
        return existing_terms
    
    def _filter_duplicates(self, selected_terms: Dict[str, List[str]], 
                          existing_terms: Set[str]) -> Dict[str, List[str]]:
        """Filter out terms that already exist in the prompt"""
        if not existing_terms:
            return selected_terms
        
        filtered_terms = {}
        for file_key, terms in selected_terms.items():
            filtered = []
            for term in terms:
                check_term = term if self.config.case_sensitive else term.lower()
                if check_term not in existing_terms:
                    filtered.append(term)
            
            if filtered:  # Only keep files that have remaining terms
                filtered_terms[file_key] = filtered
        
        return filtered_terms
    
    def enhance_prompt(self, prompt: str, files: Optional[List[str]] = None) -> Tuple[str, Dict[str, List[str]]]:
        """
        Enhance a prompt with wildcard terms
        
        Args:
            prompt: Original prompt to enhance
            files: Specific wildcard files to use (None = use config)
            
        Returns:
            Tuple of (enhanced_prompt, selected_terms_dict)
        """
        # Select wildcard terms
        selected_terms = self.select_wildcard_terms(files)
        
        if not selected_terms:
            return prompt, {}
        
        # Check for existing terms in the prompt
        existing_terms = self._extract_existing_terms(prompt)
        
        # Filter out duplicates if enabled
        if self.config.avoid_duplicates:
            selected_terms = self._filter_duplicates(selected_terms, existing_terms)
        
        if not selected_terms:
            return prompt, {}  # All terms were duplicates
        
        # Flatten selected terms into a single list
        all_selected = []
        for terms_list in selected_terms.values():
            all_selected.extend(terms_list)
        
        if not all_selected:
            return prompt, selected_terms
        
        # Create the wildcard string
        wildcard_string = self.config.separator.join(all_selected)
        
        # Integrate with the prompt based on position setting
        if self.config.position == "prepend":
            enhanced_prompt = f"{wildcard_string}{self.config.separator}{prompt}"
        elif self.config.position == "append":
            enhanced_prompt = f"{prompt}{self.config.separator}{wildcard_string}"
        elif self.config.position == "integrate":
            # Smart integration - try to find a good insertion point
            enhanced_prompt = self._integrate_smartly(prompt, wildcard_string)
        else:
            # Default to prepend
            enhanced_prompt = f"{wildcard_string}{self.config.separator}{prompt}"
        
        return enhanced_prompt, selected_terms
    
    def _integrate_smartly(self, prompt: str, wildcard_string: str) -> str:
        """Intelligently integrate wildcard terms into the prompt"""
        # Simple smart integration - add after the main subject
        # Look for common patterns and insert appropriately
        
        # If prompt starts with "a " or "an ", insert after the first noun phrase
        if re.match(r'^(a|an)\s+\w+', prompt.lower()):
            # Find the end of the first noun phrase (simple heuristic)
            match = re.search(r'^(a|an\s+(?:\w+\s+)*\w+)', prompt, re.IGNORECASE)
            if match:
                subject = match.group(1)
                rest = prompt[match.end():].lstrip()
                if rest.startswith(','):
                    return f"{subject}, {wildcard_string}{rest}"
                else:
                    return f"{subject}, {wildcard_string}, {rest}"
        
        # Default to prepending
        return f"{wildcard_string}{self.config.separator}{prompt}"
    
    def print_summary(self, selected_terms: Dict[str, List[str]]):
        """Print a summary of selected wildcard terms"""
        if not selected_terms:
            print("🎯 No wildcard terms selected")
            return
        
        print("🎯 Selected wildcard terms:")
        for file_key, terms in selected_terms.items():
            print(f"   {file_key}: {', '.join(terms)}")


def parse_wildcard_args(wildcard_specs: List[str]) -> Tuple[List[str], WildcardConfig]:
    """
    Parse wildcard command line arguments
    
    Args:
        wildcard_specs: List of wildcard specifications
        
    Returns:
        Tuple of (selected_files, config)
        
    Format examples:
        ["Camera_Shots", "Lighting_and_Mood"] - specific files
        ["Camera_Shots:2", "Color_Palettes:1"] - specific files with term counts
        ["all:3"] - all files, max 3 total terms
        ["all:1:append"] - all files, 1 per file, append position
        [] - empty list defaults to using all files with default settings
    """
    config = WildcardConfig()
    selected_files = []
    
    # If empty list, default to using all files
    if not wildcard_specs:
        selected_files = None  # Use all files
        config.selected_files = None
        return selected_files, config
    
    for spec in wildcard_specs:
        parts = spec.split(':')
        file_name = parts[0]
        
        if file_name.lower() == 'all':
            selected_files = None  # Use all files
        else:
            selected_files.append(file_name)
        
        # Parse optional parameters
        if len(parts) > 1 and parts[1].isdigit():
            count = int(parts[1])
            if file_name.lower() == 'all':
                config.total_terms = count
            else:
                config.terms_per_file = count
        
        if len(parts) > 2:
            position = parts[2].lower()
            if position in ['prepend', 'append', 'integrate']:
                config.position = position
    
    config.selected_files = selected_files
    return selected_files, config


if __name__ == "__main__":
    # Test the wildcard system
    import argparse
    
    parser = argparse.ArgumentParser(description="Test wildcard system")
    parser.add_argument("--prompt", default="a mystical forest guardian", help="Test prompt")
    parser.add_argument("--wildcards", nargs='*', help="Wildcard specifications")
    parser.add_argument("--wildcards-dir", default="/home/mitchellflautt/MuseVision/wildcards")
    
    args = parser.parse_args()
    
    try:
        if args.wildcards:
            files, config = parse_wildcard_args(args.wildcards)
            config.wildcards_dir = args.wildcards_dir
        else:
            config = WildcardConfig(wildcards_dir=args.wildcards_dir)
            files = None
        
        system = WildcardSystem(config)
        
        print(f"🔤 Original prompt: {args.prompt}")
        print(f"📁 Available wildcard files: {', '.join(system.get_available_files())}")
        
        enhanced_prompt, selected_terms = system.enhance_prompt(args.prompt, files)
        
        print(f"\n✨ Enhanced prompt: {enhanced_prompt}")
        system.print_summary(selected_terms)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
