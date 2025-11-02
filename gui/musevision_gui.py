#!/usr/bin/env python3
"""
MuseVision GUI - Intuitive interface for GPU-optimized batch processing
Apple-inspired design with clean, modern aesthetics
"""

import sys
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
import json

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

# Add the scripts directory to path for imports
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts'))

class AppleStyleGUI:
    """Main MuseVision GUI with Apple-inspired aesthetics"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MuseVision - Creative AI Batch Processing")
        
        # Position window on right half of screen
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = screen_width // 2
        window_height = screen_height
        x_position = screen_width // 2
        y_position = 0
        
        self.root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
        self.root.minsize(800, 600)
        
        # Dark macOS-inspired color scheme
        self.colors = {
            'bg': '#1E1E1E',           # Dark background (macOS dark)
            'card_bg': '#2D2D2D',      # Dark cards
            'sidebar_bg': '#252525',   # Darker sidebar
            'accent': '#0A84FF',       # macOS blue
            'accent_hover': '#409CFF', # Lighter blue hover
            'text': '#FFFFFF',         # White text
            'text_secondary': '#8E8E93', # Gray secondary text
            'text_muted': '#6E6E73',   # More muted text
            'success': '#30D158',      # Green
            'warning': '#FF9F0A',      # Orange
            'error': '#FF453A',        # Red
            'border': '#48484A'        # Dark border
        }
        
        # Default values (must be set before setup_ui)
        self.default_project_dir = "/home/mitchellflautt/MuseVision/projects"
        self.default_output_dir = ""
        self.gpu_script_path = "/home/mitchellflautt/MuseVision/scripts/gpu_optimized_agent.py"
        self.current_process: Optional[subprocess.Popen] = None
        self.monitoring_thread: Optional[threading.Thread] = None
        
        self.setup_style()
        self.setup_ui()
    
    def setup_style(self):
        """Configure ttk styles with Apple aesthetics"""
        style = ttk.Style()
        
        # Configure notebook (tabs)
        style.configure("Apple.TNotebook", 
                       background=self.colors['bg'],
                       borderwidth=0)
        style.configure("Apple.TNotebook.Tab",
                       background=self.colors['card_bg'],
                       foreground=self.colors['text'],
                       padding=[20, 12],
                       borderwidth=1,
                       focuscolor='none')
        style.map("Apple.TNotebook.Tab",
                 background=[('selected', self.colors['accent']),
                            ('active', self.colors['accent_hover'])],
                 foreground=[('selected', 'white'),
                            ('active', 'white')])
        
        # Configure buttons
        style.configure("Apple.TButton",
                       background=self.colors['accent'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       padding=[20, 12])
        style.map("Apple.TButton",
                 background=[('active', self.colors['accent_hover'])])
        
        # Configure labels
        style.configure("Apple.TLabel",
                       background=self.colors['bg'],
                       foreground=self.colors['text'])
        style.configure("AppleSecondary.TLabel",
                       background=self.colors['bg'],
                       foreground=self.colors['text_secondary'])
        style.configure("AppleMuted.TLabel",
                       background=self.colors['bg'],
                       foreground=self.colors['text_muted'])
        
        # Configure frames
        style.configure("Apple.TFrame", background=self.colors['bg'])
        style.configure("AppleCard.TFrame", 
                       background=self.colors['card_bg'],
                       relief='flat',
                       borderwidth=1)
        
        # Try to add rounded corners (limited support in tkinter)
        style.configure("RoundedCard.TFrame", 
                       background=self.colors['card_bg'],
                       relief='flat',
                       borderwidth=0)
        
        # Configure entries for dark theme
        style.configure("Apple.TEntry",
                       fieldbackground=self.colors['card_bg'],
                       foreground=self.colors['text'],
                       borderwidth=1,
                       insertcolor=self.colors['text'])
        
        # Configure combobox for dark theme
        style.configure("Apple.TCombobox",
                       fieldbackground=self.colors['card_bg'],
                       foreground=self.colors['text'],
                       background=self.colors['card_bg'],
                       borderwidth=1,
                       insertcolor=self.colors['text'])
        
        # Configure checkbutton for dark theme
        style.configure("Apple.TCheckbutton",
                       background=self.colors['card_bg'],
                       foreground=self.colors['text'],
                       focuscolor='none')
        
    def setup_ui(self):
        """Setup the main user interface"""
        self.root.configure(bg=self.colors['bg'])
        
        # Main container with padding
        main_frame = ttk.Frame(self.root, style="Apple.TFrame")
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title (simplified, no subtitle)
        title_label = ttk.Label(main_frame, text="MuseVision", 
                               font=('Arial', 24, 'bold'), 
                               style="Apple.TLabel")
        title_label.pack(pady=(0, 10))
        
        # Project management section
        self.setup_project_management_section(main_frame)
        
        # Notebook for different functions
        self.notebook = ttk.Notebook(main_frame, style="Apple.TNotebook")
        self.notebook.pack(fill='both', expand=True, pady=20)
        
        # Create tabs for each function  
        self.create_explore_styles_tab()
        self.create_explore_narrative_tab()
        self.create_refine_styles_tab()
        
        # Bind tab change to update output directory and fix scrolling
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        
        # Control panel at bottom
        self.setup_control_panel(main_frame)
    
    def setup_project_management_section(self, parent):
        """Setup enhanced project management with creation and selection"""
        # Card frame for project settings
        card_frame = ttk.Frame(parent, style="AppleCard.TFrame")
        card_frame.pack(fill='x', pady=(0, 10))
        
        # Inner padding
        inner_frame = ttk.Frame(card_frame, style="AppleCard.TFrame")
        inner_frame.pack(fill='x', padx=20, pady=15)
        
        # Project management title
        ttk.Label(inner_frame, text="Project Management", 
                 font=('Arial', 16, 'bold'),
                 style="Apple.TLabel").pack(anchor='w')
        
        # Project selection/creation frame
        proj_frame = ttk.Frame(inner_frame, style="AppleCard.TFrame")
        proj_frame.pack(fill='x', pady=(10, 5))
        
        # Project dropdown and controls
        proj_left_frame = ttk.Frame(proj_frame, style="AppleCard.TFrame")
        proj_left_frame.pack(side='left', fill='x', expand=True)
        
        ttk.Label(proj_left_frame, text="Project:", 
                 font=('Arial', 13), style="Apple.TLabel").pack(side='left')
        
        # Project selection combobox
        self.project_var = tk.StringVar()
        self.project_combo = ttk.Combobox(proj_left_frame, textvariable=self.project_var, 
                                         width=25, state='normal', style="Apple.TCombobox")
        self.project_combo.pack(side='left', padx=(10, 5))
        
        # Project management buttons
        ttk.Button(proj_left_frame, text="Refresh", command=self.refresh_projects,
                  width=8).pack(side='left', padx=2)
        ttk.Button(proj_left_frame, text="New", command=self.create_new_project,
                  width=6).pack(side='left', padx=2)
        ttk.Button(proj_left_frame, text="Open", command=self.open_project_dir,
                  width=6).pack(side='left', padx=2)
        
        # Load existing projects
        self.refresh_projects()
        
        # Output directory selection with auto-update
        output_frame = ttk.Frame(inner_frame, style="AppleCard.TFrame")
        output_frame.pack(fill='x', pady=5)
        
        ttk.Label(output_frame, text="Output Directory:", 
                 font=('Arial', 13), style="Apple.TLabel").pack(side='left')
        self.output_dir_var = tk.StringVar()
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_dir_var, 
                                     width=65, style="Apple.TEntry", font=('Courier', 11))
        self.output_entry.pack(side='left', padx=(10, 5))
        
        ttk.Button(output_frame, text="Browse", 
                  command=self.browse_output_dir).pack(side='left')
        ttk.Button(output_frame, text="Open", 
                  command=self.open_output_dir).pack(side='left', padx=(5, 0))
        ttk.Button(output_frame, text="Auto", 
                  command=self.auto_set_output_dir).pack(side='left', padx=(5, 0))
        
        # Bind project change to auto-update output directory and refresh images
        self.project_combo.bind('<<ComboboxSelected>>', self.on_project_changed)
        self.project_var.trace('w', self.on_project_changed)
    
    def create_explore_styles_tab(self):
        """Create the Explore Styles tab"""
        frame = ttk.Frame(self.notebook, style="Apple.TFrame")
        self.notebook.add(frame, text="Explore Styles")
        
        # Scrollable frame
        canvas = tk.Canvas(frame, bg=self.colors['bg'])
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style="Apple.TFrame")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Create horizontal layout for better space utilization
        main_layout = ttk.Frame(scrollable_frame, style="Apple.TFrame")
        main_layout.pack(fill='both', expand=True, padx=20)
        
        # Left column for main parameters
        left_column = ttk.Frame(main_layout, style="Apple.TFrame")
        left_column.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Right column for dimensions and advanced options
        right_column = ttk.Frame(main_layout, style="Apple.TFrame")
        right_column.pack(side='right', fill='y', padx=(10, 0))
        
        # Parameters card in left column
        self.create_parameter_card(left_column, "Style Exploration Parameters", [
            ("Prompt", "Base creative prompt for style exploration", "text", "prompt_styles", "A mystical forest scene with ethereal lighting"),
            ("Guidance", "Additional guidance for LLM", "text", "guidance_styles", "Focus on dramatic lighting and composition"),
            ("Dream Count", "Number of variations to generate", "int", "dream_count_styles", 5),
            ("Images per Prompt", "Images generated per variation", "int", "n_styles", 10),
            ("LoRAs per Combination", "Number of LoRAs to combine", "int", "k_styles", 2),
            ("Creativity", "LLM creativity level (0.0-1.0)", "float", "creativity_styles", 0.7),
            ("Min LoRA Strength", "Minimum LoRA strength", "float", "strength_min_styles", 0.7),
            ("Max LoRA Strength", "Maximum LoRA strength", "float", "strength_max_styles", 0.9),
        ])
        
        # Dimensions card in right column
        self.create_dimensions_card(right_column, "styles")
        
        # Advanced options in right column
        self.create_advanced_options_card(right_column, "styles")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Enable mouse wheel scrolling for this tab
        self.bind_mousewheel_scrolling(canvas, 'vertical')
    
    def create_explore_narrative_tab(self):
        """Create the Explore Narrative tab"""
        frame = ttk.Frame(self.notebook, style="Apple.TFrame")
        self.notebook.add(frame, text="Explore Narrative")
        
        # Scrollable frame
        canvas = tk.Canvas(frame, bg=self.colors['bg'])
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style="Apple.TFrame")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Source images section - full width at top
        self.create_image_selection_card(scrollable_frame, "Source Images", "selected_images_narrative")
        
        # Create horizontal layout for parameters below images
        main_layout = ttk.Frame(scrollable_frame, style="Apple.TFrame")
        main_layout.pack(fill='both', expand=True, padx=20)
        
        # Left column for main parameters
        left_column = ttk.Frame(main_layout, style="Apple.TFrame")
        left_column.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Right column for dimensions and advanced options
        right_column = ttk.Frame(main_layout, style="Apple.TFrame")
        right_column.pack(side='right', fill='y', padx=(10, 0))
        
        # Parameters card in left column
        self.create_parameter_card(left_column, "Narrative Exploration Parameters", [
            ("Guidance", "Additional guidance for LLM", "text", "guidance_narrative", "Create compelling narrative variations"),
            ("Dream Count", "Number of narrative variations", "int", "dream_count_narrative", 5),
            ("Seed Count", "Images per narrative", "int", "seed_count_narrative", 1),
            ("Creativity", "LLM creativity level (0.0-1.0)", "float", "creativity_narrative", 0.7),
            ("Per Image", "Process each source image separately (creates individual prompt sets per image)", "bool", "per_image_narrative", False),
        ])
        
        # Dimensions card in right column
        self.create_dimensions_card(right_column, "narrative")
        
        # Advanced options in right column
        self.create_advanced_options_card(right_column, "narrative")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Enable mouse wheel scrolling for this tab
        self.bind_mousewheel_scrolling(canvas, 'vertical')
    
    def create_refine_styles_tab(self):
        """Create the Refine Styles tab"""
        frame = ttk.Frame(self.notebook, style="Apple.TFrame")
        self.notebook.add(frame, text="Refine Styles")
        
        # Scrollable frame
        canvas = tk.Canvas(frame, bg=self.colors['bg'])
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style="Apple.TFrame")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Style images selection - full width at top
        self.create_image_selection_card(scrollable_frame, "Style Reference Images", "selected_styles_refine")
        
        # Create horizontal layout for parameters below images
        main_layout = ttk.Frame(scrollable_frame, style="Apple.TFrame")
        main_layout.pack(fill='both', expand=True, padx=20)
        
        # Left column for main parameters
        left_column = ttk.Frame(main_layout, style="Apple.TFrame")
        left_column.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Right column for dimensions and advanced options
        right_column = ttk.Frame(main_layout, style="Apple.TFrame")
        right_column.pack(side='right', fill='y', padx=(10, 0))
        
        # Parameters card in left column
        self.create_parameter_card(left_column, "Style Refinement Parameters", [
            ("Prompt", "Base prompt for testing styles", "text", "prompt_refine", "A character portrait with dramatic lighting"),
            ("Guidance", "Additional guidance for LLM", "text", "guidance_refine", "Focus on style consistency and quality"),
            ("Dream Count", "Number of prompt variations", "int", "dream_count_refine", 5),
            ("Test Count", "LoRA combinations to test", "int", "test_count_refine", 10),
            ("LoRAs per Combination", "Number of LoRAs to combine", "int", "k_refine", 2),
            ("Creativity", "LLM creativity level (0.0-1.0)", "float", "creativity_refine", 0.7),
            ("Min LoRA Strength", "Minimum LoRA strength", "float", "strength_min_refine", 0.5),
            ("Max LoRA Strength", "Maximum LoRA strength", "float", "strength_max_refine", 1.0),
        ])
        
        # Dimensions card in right column
        self.create_dimensions_card(right_column, "refine")
        
        # Advanced options in right column
        self.create_advanced_options_card(right_column, "refine")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Enable mouse wheel scrolling for this tab
        self.bind_mousewheel_scrolling(canvas, 'vertical')
    
    def create_parameter_card(self, parent, title, parameters):
        """Create a parameter input card"""
        card_frame = ttk.Frame(parent, style="AppleCard.TFrame")
        # Adjust padding based on parent context
        if parent.winfo_class() == 'TFrame' and parent.master.winfo_class() == 'TFrame':
            # This is in a column layout, use less horizontal padding
            card_frame.pack(fill='x', pady=10, padx=5)
        else:
            # This is full-width, use more padding
            card_frame.pack(fill='x', pady=10, padx=20)
        
        # Inner padding
        inner_frame = ttk.Frame(card_frame, style="AppleCard.TFrame")
        inner_frame.pack(fill='x', padx=20, pady=15)
        
        # Title
        ttk.Label(inner_frame, text=title, 
                 font=('Arial', 16, 'bold'),
                 style="Apple.TLabel").pack(anchor='w', pady=(0, 10))
        
        # Store variables for later access
        if not hasattr(self, 'param_vars'):
            self.param_vars = {}
        if not hasattr(self, 'dimension_buttons'):
            self.dimension_buttons = {}
        
        # Create parameter inputs
        for label, description, param_type, var_name, default_value in parameters:
            param_frame = ttk.Frame(inner_frame, style="AppleCard.TFrame")
            param_frame.pack(fill='x', pady=5)
            
            # Label with description tooltip
            label_frame = ttk.Frame(param_frame, style="AppleCard.TFrame")
            label_frame.pack(fill='x')
            
            ttk.Label(label_frame, text=f"{label}:", 
                     font=('Arial', 13), style="Apple.TLabel").pack(side='left')
            ttk.Label(label_frame, text=f"({description})", 
                     style="AppleSecondary.TLabel",
                     font=('Arial', 11)).pack(side='left', padx=(5, 0))
            
            # Input widget based on type
            if param_type == "text":
                var = tk.StringVar(value=str(default_value))
                entry = ttk.Entry(param_frame, textvariable=var, width=60, style="Apple.TEntry",
                                 font=('Arial', 12))
                entry.pack(pady=(5, 0))
            elif param_type == "int":
                var = tk.IntVar(value=int(default_value))
                entry = ttk.Entry(param_frame, textvariable=var, width=20, style="Apple.TEntry",
                                 font=('SF Pro Display', 12))
                entry.pack(pady=(5, 0))
            elif param_type == "float":
                var = tk.DoubleVar(value=float(default_value))
                entry = ttk.Entry(param_frame, textvariable=var, width=20, style="Apple.TEntry",
                                 font=('Arial', 12))
                entry.pack(pady=(5, 0))
            elif param_type == "bool":
                var = tk.BooleanVar(value=bool(default_value))
                check = ttk.Checkbutton(param_frame, variable=var)
                check.pack(pady=(5, 0))
            
            self.param_vars[var_name] = var
    
    def create_image_selection_card(self, parent, title, var_name):
        """Create an image selection card with previews and default folder loading"""
        card_frame = ttk.Frame(parent, style="AppleCard.TFrame")
        # Adjust padding based on parent context
        if parent.winfo_class() == 'TFrame' and parent.master.winfo_class() == 'TFrame':
            # This is in a column layout, use less horizontal padding
            card_frame.pack(fill='x', pady=10, padx=5)
        else:
            # This is full-width, use more padding
            card_frame.pack(fill='x', pady=10, padx=20)
        
        # Inner padding
        inner_frame = ttk.Frame(card_frame, style="AppleCard.TFrame")
        inner_frame.pack(fill='x', padx=20, pady=15)
        
        # Title with folder info
        title_frame = ttk.Frame(inner_frame, style="AppleCard.TFrame")
        title_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(title_frame, text=title, 
                 font=('Arial', 16, 'bold'),
                 style="Apple.TLabel").pack(side='left')
        
        # Default folder indicator
        folder_name = "selected_images" if "narrative" in var_name else "selected_styles"
        ttk.Label(title_frame, text=f"(Auto-loads from {folder_name}/)", 
                 style="AppleSecondary.TLabel",
                 font=('Arial', 11)).pack(side='left', padx=(10, 0))
        
        # Control buttons frame
        ctrl_frame = ttk.Frame(inner_frame, style="AppleCard.TFrame")
        ctrl_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Button(ctrl_frame, text="Refresh", 
                  command=lambda: self.refresh_folder_images(var_name)).pack(side='left', padx=(0, 5))
        ttk.Button(ctrl_frame, text="Add Images", 
                  command=lambda: self.add_images(var_name)).pack(side='left', padx=5)
        ttk.Button(ctrl_frame, text="Open Folder", 
                  command=lambda: self.open_image_folder(var_name)).pack(side='left', padx=5)
        ttk.Button(ctrl_frame, text="Clear All", 
                  command=lambda: self.clear_images(var_name)).pack(side='right')
        
        # Image display frame with scrolling
        display_frame = ttk.Frame(inner_frame, style="AppleCard.TFrame")
        display_frame.pack(fill='both', expand=True)
        
        # Create canvas for image previews (larger for bigger thumbnails)
        canvas = tk.Canvas(display_frame, height=240, 
                          bg=self.colors['card_bg'],
                          highlightthickness=0)
        scrollbar_h = ttk.Scrollbar(display_frame, orient='horizontal', command=canvas.xview)
        scrollable_img_frame = ttk.Frame(canvas, style="AppleCard.TFrame")
        
        scrollable_img_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_img_frame, anchor="nw")
        canvas.configure(xscrollcommand=scrollbar_h.set)
        
        canvas.pack(side="top", fill="both", expand=True)
        scrollbar_h.pack(side="bottom", fill="x")
        
        # Enable mouse wheel scrolling for image previews
        self.bind_mousewheel_scrolling(canvas, 'horizontal')
        
        # Store references
        setattr(self, f"{var_name}_canvas", canvas)
        setattr(self, f"{var_name}_scrollable_frame", scrollable_img_frame)
        
        # Track selected images
        self.param_vars = getattr(self, 'param_vars', {})
        self.param_vars[var_name] = []
        
        # Auto-load images from default folder
        self.refresh_folder_images(var_name)
    
    def create_dimensions_card(self, parent, tab_type):
        """Create dimension presets card"""
        card_frame = ttk.Frame(parent, style="AppleCard.TFrame")
        # Adjust padding based on parent context
        if parent.winfo_class() == 'TFrame' and parent.master.winfo_class() == 'TFrame':
            # This is in a column layout, use less horizontal padding
            card_frame.pack(fill='x', pady=10, padx=5)
        else:
            # This is full-width, use more padding
            card_frame.pack(fill='x', pady=10, padx=20)
        
        # Inner padding
        inner_frame = ttk.Frame(card_frame, style="AppleCard.TFrame")
        inner_frame.pack(fill='x', padx=20, pady=15)
        
        # Title
        ttk.Label(inner_frame, text="Image Dimensions", 
                 font=('Arial', 16, 'bold'),
                 style="Apple.TLabel").pack(anchor='w', pady=(0, 10))
        
        # Dimension controls frame
        dim_controls_frame = ttk.Frame(inner_frame, style="AppleCard.TFrame")
        dim_controls_frame.pack(fill='x', pady=5)
        
        # Preset buttons
        preset_frame = ttk.Frame(dim_controls_frame, style="AppleCard.TFrame")
        preset_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(preset_frame, text="Quick Presets:", 
                 font=('Arial', 13), style="Apple.TLabel").pack(anchor='w')
        
        btn_frame = ttk.Frame(preset_frame, style="AppleCard.TFrame")
        btn_frame.pack(fill='x', pady=(5, 0))
        
        # Create visual dimension buttons
        self.create_dimension_button(btn_frame, "1920x1080", 1920, 1080, tab_type, True)  # Horizontal
        self.create_dimension_button(btn_frame, "1080x1920", 1080, 1920, tab_type, False) # Vertical  
        self.create_dimension_button(btn_frame, "1280x720", 1280, 720, tab_type, True)   # Horizontal
        self.create_dimension_button(btn_frame, "720x1280", 720, 1280, tab_type, False)  # Vertical
        
        # Manual dimension inputs
        manual_frame = ttk.Frame(dim_controls_frame, style="AppleCard.TFrame")
        manual_frame.pack(fill='x', pady=5)
        
        # Width
        width_frame = ttk.Frame(manual_frame, style="AppleCard.TFrame")
        width_frame.pack(side='left', padx=(0, 20))
        
        ttk.Label(width_frame, text="Width:", 
                 font=('Arial', 13), style="Apple.TLabel").pack(anchor='w')
        width_var = tk.IntVar(value=720)
        ttk.Entry(width_frame, textvariable=width_var, width=10, style="Apple.TEntry",
                 font=('Arial', 12)).pack(pady=(5, 0))
        self.param_vars[f"width_{tab_type}"] = width_var
        
        # Height
        height_frame = ttk.Frame(manual_frame, style="AppleCard.TFrame")
        height_frame.pack(side='left')
        
        ttk.Label(height_frame, text="Height:", 
                 font=('Arial', 13), style="Apple.TLabel").pack(anchor='w')
        height_var = tk.IntVar(value=1280)
        ttk.Entry(height_frame, textvariable=height_var, width=10, style="Apple.TEntry",
                 font=('Arial', 12)).pack(pady=(5, 0))
        self.param_vars[f"height_{tab_type}"] = height_var
    
    def create_dimension_button(self, parent, text, width, height, tab_type, is_horizontal):
        """Create a visual dimension button that shows the aspect ratio"""
        btn_frame = ttk.Frame(parent, style="AppleCard.TFrame")
        btn_frame.pack(side='left', padx=5, pady=2)
        
        # Create a canvas to draw the visual representation
        canvas_width = 60 if is_horizontal else 40
        canvas_height = 40 if is_horizontal else 60
        
        canvas = tk.Canvas(btn_frame, width=canvas_width, height=canvas_height, 
                          bg=self.colors['card_bg'], highlightthickness=1,
                          highlightbackground=self.colors['border'])
        canvas.pack()
        
        # Draw rectangle representing the aspect ratio
        rect_margin = 8
        rect_width = canvas_width - (rect_margin * 2)
        rect_height = canvas_height - (rect_margin * 2)
        
        # Store canvas and button info for later updates
        button_key = f"{tab_type}_{width}x{height}"
        if tab_type not in self.dimension_buttons:
            self.dimension_buttons[tab_type] = {}
        
        self.dimension_buttons[tab_type][button_key] = {
            'canvas': canvas,
            'width': width,
            'height': height,
            'rect_coords': (rect_margin, rect_margin, rect_margin + rect_width, rect_margin + rect_height)
        }
        
        # Draw initial rectangle
        self.update_dimension_button_style(tab_type, button_key, selected=False)
        
        # Add click binding
        def on_click(event):
            self.set_dimensions(width, height, tab_type)
        
        canvas.bind("<Button-1>", on_click)
        
        # Add label below
        ttk.Label(btn_frame, text=text, style="AppleMuted.TLabel",
                 font=('Arial', 9)).pack(pady=(2, 0))
    
    def update_dimension_button_style(self, tab_type, button_key, selected=False):
        """Update dimension button visual style"""
        if tab_type not in self.dimension_buttons or button_key not in self.dimension_buttons[tab_type]:
            return
        
        button_info = self.dimension_buttons[tab_type][button_key]
        canvas = button_info['canvas']
        coords = button_info['rect_coords']
        
        # Clear canvas
        canvas.delete("all")
        
        if selected:
            # Selected style - outlined with accent color and filled
            canvas.create_rectangle(*coords, outline=self.colors['accent'], width=3, 
                                   fill=self.colors['accent'], stipple='gray25')
        else:
            # Unselected style - simple outline
            canvas.create_rectangle(*coords, outline=self.colors['border'], width=2, 
                                   fill=self.colors['bg'])
    
    def set_dimensions(self, width, height, tab_type):
        """Set dimensions from preset buttons with visual feedback"""
        self.param_vars[f"width_{tab_type}"].set(width)
        self.param_vars[f"height_{tab_type}"].set(height)
        
        # Update button visual states
        if tab_type in self.dimension_buttons:
            selected_key = f"{tab_type}_{width}x{height}"
            for button_key in self.dimension_buttons[tab_type]:
                is_selected = (button_key == selected_key)
                self.update_dimension_button_style(tab_type, button_key, is_selected)
    
    def create_advanced_options_card(self, parent, tab_type):
        """Create advanced options card"""
        card_frame = ttk.Frame(parent, style="AppleCard.TFrame")
        # Adjust padding based on parent context
        if parent.winfo_class() == 'TFrame' and parent.master.winfo_class() == 'TFrame':
            # This is in a column layout, use less horizontal padding
            card_frame.pack(fill='x', pady=10, padx=5)
        else:
            # This is full-width, use more padding
            card_frame.pack(fill='x', pady=10, padx=20)
        
        # Inner padding
        inner_frame = ttk.Frame(card_frame, style="AppleCard.TFrame")
        inner_frame.pack(fill='x', padx=20, pady=15)
        
        # Title
        ttk.Label(inner_frame, text="Advanced Options", 
                 font=('Arial', 16, 'bold'),
                 style="Apple.TLabel").pack(anchor='w', pady=(0, 10))
        
        # Wildcards section
        wild_frame = ttk.Frame(inner_frame, style="AppleCard.TFrame")
        wild_frame.pack(fill='x', pady=5)
        
        # Wildcards dropdown
        wild_header_frame = ttk.Frame(wild_frame, style="AppleCard.TFrame")
        wild_header_frame.pack(fill='x')
        
        ttk.Label(wild_header_frame, text="Wildcards:", 
                 font=('Arial', 13), style="Apple.TLabel").pack(side='left')
        
        # Get available wildcard files
        wildcard_options = self.get_wildcard_options()
        wildcard_var = tk.StringVar(value="None")
        wildcard_combo = ttk.Combobox(wild_header_frame, textvariable=wildcard_var,
                                     values=wildcard_options, state="readonly",
                                     width=25, style="Apple.TCombobox")
        wildcard_combo.pack(side='left', padx=(10, 0))
        
        self.param_vars[f"wildcards_{tab_type}"] = wildcard_var
        
        # Info label
        ttk.Label(wild_header_frame, text="(Select specific wildcard file or None)", 
                 style="AppleSecondary.TLabel",
                 font=('Arial', 11)).pack(side='left', padx=(10, 0))
        
        # Keep ComfyUI running (moved up since we removed timeout)
        keep_running_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(inner_frame, text="Keep ComfyUI running after completion",
                       style="Apple.TCheckbutton",
                       variable=keep_running_var).pack(anchor='w', pady=(15, 0))
        self.param_vars[f"keep_comfyui_running_{tab_type}"] = keep_running_var
    
    def bind_mousewheel_scrolling(self, canvas, direction):
        """Bind mouse wheel scrolling to a canvas"""
        def _on_mousewheel(event):
            if direction == 'vertical':
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            else:  # horizontal
                canvas.xview_scroll(int(-1*(event.delta/120)), "units")
        
        def _on_button4(event):
            if direction == 'vertical':
                canvas.yview_scroll(-1, "units")
            else:
                canvas.xview_scroll(-1, "units")
        
        def _on_button5(event):
            if direction == 'vertical':
                canvas.yview_scroll(1, "units") 
            else:
                canvas.xview_scroll(1, "units")
        
        canvas.bind("<MouseWheel>", _on_mousewheel)  # Windows/macOS
        canvas.bind("<Button-4>", _on_button4)       # Linux scroll up
        canvas.bind("<Button-5>", _on_button5)       # Linux scroll down
        
        # Also bind to the scrollable frame inside the canvas
        def bind_to_children(widget):
            widget.bind("<MouseWheel>", _on_mousewheel)
            widget.bind("<Button-4>", _on_button4)
            widget.bind("<Button-5>", _on_button5)
            for child in widget.winfo_children():
                bind_to_children(child)
        
        # Bind after a small delay to ensure widgets are created
        self.root.after(100, lambda: bind_to_children(canvas))
    
    def get_wildcard_options(self):
        """Get list of available wildcard files"""
        wildcards_dir = "/home/mitchellflautt/MuseVision/wildcards"
        options = ["None", "All Wildcards"]
        
        if os.path.exists(wildcards_dir):
            try:
                for file in os.listdir(wildcards_dir):
                    if file.endswith('.txt'):
                        # Remove .txt extension for display
                        options.append(file[:-4])
            except Exception as e:
                print(f"Error reading wildcards directory: {e}")
        
        return options
    
    def setup_control_panel(self, parent):
        """Setup the control panel with action buttons and status"""
        # Control panel card
        card_frame = ttk.Frame(parent, style="AppleCard.TFrame")
        card_frame.pack(fill='x', pady=(10, 0))
        
        # Inner padding
        inner_frame = ttk.Frame(card_frame, style="AppleCard.TFrame")
        inner_frame.pack(fill='x', padx=20, pady=15)
        
        # Action buttons
        btn_frame = ttk.Frame(inner_frame, style="AppleCard.TFrame")
        btn_frame.pack(fill='x', pady=(0, 10))
        
        self.run_btn = ttk.Button(btn_frame, text="▶ Run Process", 
                                 style="Apple.TButton",
                                 command=self.run_current_process)
        self.run_btn.pack(side='left', padx=(0, 10))
        
        self.stop_btn = ttk.Button(btn_frame, text="⏹ Stop", 
                                  command=self.stop_current_process,
                                  state='disabled')
        self.stop_btn.pack(side='left', padx=(0, 10))
        
        ttk.Button(btn_frame, text="📊 Queue Status", 
                  command=self.show_queue_status).pack(side='left', padx=(0, 10))
        
        ttk.Button(btn_frame, text="📁 Open Output", 
                  command=self.open_output_dir).pack(side='right')
        
        # Status and progress
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(inner_frame, textvariable=self.status_var, 
                                style="Apple.TLabel", font=('Arial', 12))
        status_label.pack(anchor='w')
        
        # Dual progress bars
        progress_frame = ttk.Frame(inner_frame, style="AppleCard.TFrame")
        progress_frame.pack(fill='x', pady=(5, 0))
        
        # Overall batch progress
        ttk.Label(progress_frame, text="Overall Progress:", 
                 style="Apple.TLabel", font=('Arial', 10)).pack(anchor='w')
        
        # Create frame with specific height for overall progress
        overall_frame = ttk.Frame(progress_frame, style="AppleCard.TFrame", height=25)
        overall_frame.pack(fill='x', pady=(2, 5))
        overall_frame.pack_propagate(False)
        
        self.overall_progress = ttk.Progressbar(overall_frame, mode='determinate')
        self.overall_progress.pack(fill='both', expand=True)
        
        # Current job progress
        ttk.Label(progress_frame, text="Current Job:", 
                 style="Apple.TLabel", font=('Arial', 10)).pack(anchor='w')
        
        # Create frame with specific height for current progress
        current_frame = ttk.Frame(progress_frame, style="AppleCard.TFrame", height=20)
        current_frame.pack(fill='x', pady=(2, 0))
        current_frame.pack_propagate(False)
        
        self.current_progress = ttk.Progressbar(current_frame, mode='indeterminate')
        self.current_progress.pack(fill='both', expand=True)
        
        # Keep reference to old progress for compatibility
        self.progress = self.overall_progress
        
        # Console output
        console_frame = ttk.Frame(inner_frame, style="AppleCard.TFrame")
        console_frame.pack(fill='both', expand=True, pady=(10, 0))
        
        ttk.Label(console_frame, text="Console Output:", 
                 style="Apple.TLabel", font=('Arial', 12, 'bold')).pack(anchor='w')
        
        self.console_text = ScrolledText(console_frame, height=8, 
                                        bg=self.colors['card_bg'],
                                        fg=self.colors['text'],
                                        font=('Courier', 10),
                                        insertbackground=self.colors['text'],
                                        selectbackground=self.colors['accent'],
                                        selectforeground='white',
                                        borderwidth=1,
                                        highlightthickness=0)
        # Configure text widget to properly display Unicode
        self.console_text.config(wrap='word')
        self.console_text.pack(fill='both', expand=True, pady=(5, 0))
    
    def refresh_projects(self):
        """Refresh the project list from the projects directory"""
        projects_dir = self.default_project_dir
        if not os.path.exists(projects_dir):
            os.makedirs(projects_dir, exist_ok=True)
        
        try:
            projects = [d for d in os.listdir(projects_dir) 
                       if os.path.isdir(os.path.join(projects_dir, d))]
            projects.sort()
            
            # Update combobox values
            self.project_combo['values'] = projects
            
            # Set default if no current selection
            if not self.project_var.get() and projects:
                self.project_var.set(projects[0])
                
        except Exception as e:
            print(f"Error refreshing projects: {e}")
    
    def create_new_project(self):
        """Create a new project"""
        from tkinter.simpledialog import askstring
        
        project_name = askstring("New Project", "Enter project name:")
        if project_name:
            # Clean project name (remove invalid characters)
            import re
            project_name = re.sub(r'[^\w\-_]', '_', project_name)
            
            project_dir = os.path.join(self.default_project_dir, project_name)
            try:
                os.makedirs(project_dir, exist_ok=True)
                
                # Create standard subdirectories
                subdirs = ['selected_images', 'selected_styles', 'style_explore', 
                          'narrative_explore', 'style_refine']
                for subdir in subdirs:
                    os.makedirs(os.path.join(project_dir, subdir), exist_ok=True)
                
                self.refresh_projects()
                self.project_var.set(project_name)
                self.auto_set_output_dir()
                
                messagebox.showinfo("Success", f"Project '{project_name}' created successfully!")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create project: {str(e)}")
    
    def open_project_dir(self):
        """Open the current project directory in file manager"""
        project_name = self.project_var.get()
        if not project_name:
            messagebox.showwarning("No Project", "Please select a project first")
            return
            
        project_dir = os.path.join(self.default_project_dir, project_name)
        if os.path.exists(project_dir):
            subprocess.run(['xdg-open', project_dir])
        else:
            messagebox.showwarning("Directory Not Found", 
                                 f"Project directory does not exist: {project_dir}")
    
    def on_project_changed(self, *args):
        """Handle project selection change"""
        self.auto_set_output_dir()
        # Refresh images for all tabs
        try:
            if hasattr(self, 'param_vars'):
                for var_name in ['selected_images_narrative', 'selected_styles_refine']:
                    if var_name in self.param_vars:
                        self.refresh_folder_images(var_name)
        except Exception as e:
            print(f"Error refreshing images after project change: {e}")
    
    def on_tab_changed(self, event):
        """Handle notebook tab change"""
        self.auto_set_output_dir()
        # Force canvas update to fix scrolling issues
        try:
            selected_tab = self.notebook.select()
            selected_index = self.notebook.index(selected_tab)
            # Update scrolling region for current tab
            self.root.after(100, self.update_canvas_scrolling)  # Small delay to ensure tab is loaded
        except Exception as e:
            print(f"Error handling tab change: {e}")
    
    def update_canvas_scrolling(self):
        """Update canvas scrolling regions for current tab"""
        try:
            # This will trigger a recalculation of scroll regions
            for child in self.notebook.winfo_children():
                for canvas in child.winfo_children():
                    if isinstance(canvas, tk.Canvas):
                        canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception as e:
            print(f"Error updating canvas scrolling: {e}")
    
    def auto_set_output_dir(self):
        """Automatically set output directory based on current project and tab"""
        project_name = self.project_var.get()
        if not project_name:
            return
            
        try:
            selected_tab = self.notebook.select()
            current_tab_text = self.notebook.tab(selected_tab, 'text')
            
            if 'Explore Styles' in current_tab_text:
                subdir = 'style_explore'
            elif 'Explore Narrative' in current_tab_text:
                subdir = 'narrative_explore'
            elif 'Refine Styles' in current_tab_text:
                subdir = 'style_refine'
            else:
                subdir = 'output'
            
            output_dir = os.path.join(self.default_project_dir, project_name, subdir)
            self.output_dir_var.set(output_dir)
            
            # Create directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
        except Exception as e:
            print(f"Error setting auto output directory: {e}")
    
    def browse_output_dir(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory(
            title="Select Output Directory",
            initialdir=self.default_project_dir
        )
        if directory:
            self.output_dir_var.set(directory)
    
    def open_output_dir(self):
        """Open the output directory in file manager"""
        output_dir = self.output_dir_var.get() or self.get_default_output_dir()
        if output_dir and os.path.exists(output_dir):
            subprocess.run(['xdg-open', output_dir])
        else:
            messagebox.showwarning("Directory Not Found", 
                                 f"Output directory does not exist: {output_dir}")
    
    def get_default_output_dir(self):
        """Get default output directory based on current tab"""
        project = self.project_var.get()
        if not project:
            return ""
        
        selected_tab = self.notebook.select()
        current_tab_text = self.notebook.tab(selected_tab, 'text')
        if 'Explore Styles' in current_tab_text:
            return f"{self.default_project_dir}/{project}/style_explore"
        elif 'Explore Narrative' in current_tab_text:
            return f"{self.default_project_dir}/{project}/narrative_explore"
        elif 'Refine Styles' in current_tab_text:
            return f"{self.default_project_dir}/{project}/style_refine"
        return ""
    
    
    def refresh_folder_images(self, var_name):
        """Load images from the default project folder"""
        try:
            project_name = self.project_var.get()
            if not project_name:
                return
            
            folder_name = "selected_images" if "narrative" in var_name else "selected_styles"
            folder_path = os.path.join(self.default_project_dir, project_name, folder_name)
            
            if not os.path.exists(folder_path):
                os.makedirs(folder_path, exist_ok=True)
                return
            
            # Find image files
            image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.gif']
            images = []
            for file in os.listdir(folder_path):
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    images.append(os.path.join(folder_path, file))
            
            # Update the display
            self.param_vars[var_name] = images
            self.update_image_display(var_name)
            
        except Exception as e:
            print(f"Error refreshing folder images: {e}")
    
    def update_image_display(self, var_name):
        """Update the image preview display"""
        try:
            # Clear existing display
            scrollable_frame = getattr(self, f"{var_name}_scrollable_frame")
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            
            images = self.param_vars[var_name]
            if not images:
                # Show placeholder
                ttk.Label(scrollable_frame, text="No images found in folder",
                         style="AppleMuted.TLabel",
                         font=('Arial', 12)).pack(pady=40)
                return
            
            # Display image previews
            try:
                from PIL import Image, ImageTk
                pil_available = True
            except ImportError:
                pil_available = False
            
            for i, img_path in enumerate(images):
                img_frame = ttk.Frame(scrollable_frame, style="AppleCard.TFrame")
                img_frame.pack(side='left', padx=5, pady=5)
                
                if pil_available:
                    try:
                        # Create larger thumbnail
                        img = Image.open(img_path)
                        img.thumbnail((200, 200), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        
                        img_label = tk.Label(img_frame, image=photo, 
                                            bg=self.colors['card_bg'])
                        img_label.image = photo  # Keep a reference
                        img_label.pack()
                    except Exception:
                        # Fallback to text if image can't be loaded
                        ttk.Label(img_frame, text="Image",
                                 font=('Arial', 10)).pack()
                else:
                    # No PIL - show icon
                    ttk.Label(img_frame, text="Image",
                             font=('Arial', 10)).pack()
                
                # Show filename
                filename = os.path.basename(img_path)
                ttk.Label(img_frame, text=filename[:15] + "..." if len(filename) > 15 else filename,
                         style="AppleMuted.TLabel",
                         font=('Arial', 9)).pack()
            
        except Exception as e:
            print(f"Error updating image display: {e}")
    
    def open_image_folder(self, var_name):
        """Open the image folder in file manager"""
        try:
            project_name = self.project_var.get()
            if not project_name:
                messagebox.showwarning("No Project", "Please select a project first")
                return
            
            folder_name = "selected_images" if "narrative" in var_name else "selected_styles"
            folder_path = os.path.join(self.default_project_dir, project_name, folder_name)
            
            if not os.path.exists(folder_path):
                os.makedirs(folder_path, exist_ok=True)
            
            subprocess.run(['xdg-open', folder_path])
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open folder: {str(e)}")
    
    def add_images(self, var_name):
        """Add images to the selection"""
        files = filedialog.askopenfilenames(
            title="Select Images",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif"), ("All files", "*.*")]
        )
        if files:
            current_images = self.param_vars[var_name]
            # Add new files, avoiding duplicates
            for file_path in files:
                if file_path not in current_images:
                    current_images.append(file_path)
            
            self.param_vars[var_name] = current_images
            self.update_image_display(var_name)
    
    def clear_images(self, var_name):
        """Clear all images from selection"""
        self.param_vars[var_name] = []
        self.update_image_display(var_name)
    
    def get_image_list(self, var_name):
        """Get list of selected images"""
        return self.param_vars[var_name]
    
    def run_current_process(self):
        """Run the process for the current tab"""
        selected_tab = self.notebook.select()
        current_tab = self.notebook.tab(selected_tab, 'text')
        
        # Validate inputs
        if not self.project_var.get().strip():
            messagebox.showerror("Validation Error", "Project name is required")
            return
        
        try:
            if 'Explore Styles' in current_tab:
                self.run_explore_styles()
            elif 'Explore Narrative' in current_tab:
                self.run_explore_narrative()
            elif 'Refine Styles' in current_tab:
                self.run_refine_styles()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start process: {str(e)}")
            self.log_to_console(f"Error: {str(e)}")
    
    def run_explore_styles(self):
        """Run explore_styles process"""
        cmd = [
            sys.executable, self.gpu_script_path, 'explore_styles',
            '--project', self.project_var.get(),
            '--prompt', self.param_vars['prompt_styles'].get(),
            '--guidance', self.param_vars['guidance_styles'].get(),
            '--dream-count', str(self.param_vars['dream_count_styles'].get()),
            '--n', str(self.param_vars['n_styles'].get()),
            '--k', str(self.param_vars['k_styles'].get()),
            '--creativity', str(self.param_vars['creativity_styles'].get()),
            '--width', str(self.param_vars['width_styles'].get()),
            '--height', str(self.param_vars['height_styles'].get()),
            '--strength-min', str(self.param_vars['strength_min_styles'].get()),
            '--strength-max', str(self.param_vars['strength_max_styles'].get()),
        ]
        
        if self.param_vars['keep_comfyui_running_styles'].get():
            cmd.append('--keep-comfyui-running')
        
        # Handle wildcards
        wildcard_selection = self.param_vars['wildcards_styles'].get()
        if wildcard_selection and wildcard_selection != "None":
            if wildcard_selection == "All Wildcards":
                cmd.extend(['--wildcards'])  # Empty wildcards means use all
            else:
                cmd.extend(['--wildcards', wildcard_selection])
        
        self.start_process(cmd, "Style Exploration")
    
    def run_explore_narrative(self):
        """Run explore_narrative process"""
        selected_images = self.get_image_list('selected_images_narrative')
        
        cmd = [
            sys.executable, self.gpu_script_path, 'explore_narrative',
            '--project', self.project_var.get(),
            '--guidance', self.param_vars['guidance_narrative'].get(),
            '--dream-count', str(self.param_vars['dream_count_narrative'].get()),
            '--seed-count', str(self.param_vars['seed_count_narrative'].get()),
            '--creativity', str(self.param_vars['creativity_narrative'].get()),
            '--width', str(self.param_vars['width_narrative'].get()),
            '--height', str(self.param_vars['height_narrative'].get()),
        ]
        
        if selected_images:
            cmd.extend(['--selected-images'] + selected_images)
        
        if self.param_vars['per_image_narrative'].get():
            cmd.append('--per-image')
        
        if self.param_vars['keep_comfyui_running_narrative'].get():
            cmd.append('--keep-comfyui-running')
        
        # Handle wildcards
        wildcard_selection = self.param_vars['wildcards_narrative'].get()
        if wildcard_selection and wildcard_selection != "None":
            if wildcard_selection == "All Wildcards":
                cmd.extend(['--wildcards'])  # Empty wildcards means use all
            else:
                cmd.extend(['--wildcards', wildcard_selection])
        
        self.start_process(cmd, "Narrative Exploration")
    
    def run_refine_styles(self):
        """Run refine_styles process"""
        selected_styles = self.get_image_list('selected_styles_refine')
        
        if not selected_styles:
            messagebox.showwarning("Validation Error", 
                                 "Please select at least one style reference image")
            return
        
        cmd = [
            sys.executable, self.gpu_script_path, 'refine_styles',
            '--project', self.project_var.get(),
            '--prompt', self.param_vars['prompt_refine'].get(),
            '--guidance', self.param_vars['guidance_refine'].get(),
            '--dream-count', str(self.param_vars['dream_count_refine'].get()),
            '--test-count', str(self.param_vars['test_count_refine'].get()),
            '--k', str(self.param_vars['k_refine'].get()),
            '--creativity', str(self.param_vars['creativity_refine'].get()),
            '--width', str(self.param_vars['width_refine'].get()),
            '--height', str(self.param_vars['height_refine'].get()),
            '--strength-min', str(self.param_vars['strength_min_refine'].get()),
            '--strength-max', str(self.param_vars['strength_max_refine'].get()),
            '--selected-styles'] + selected_styles
        
        if self.param_vars['keep_comfyui_running_refine'].get():
            cmd.append('--keep-comfyui-running')
        
        # Handle wildcards
        wildcard_selection = self.param_vars['wildcards_refine'].get()
        if wildcard_selection and wildcard_selection != "None":
            if wildcard_selection == "All Wildcards":
                cmd.extend(['--wildcards'])  # Empty wildcards means use all
            else:
                cmd.extend(['--wildcards', wildcard_selection])
        
        self.start_process(cmd, "Style Refinement")
    
    def start_process(self, cmd, process_name):
        """Start a background process with enhanced monitoring"""
        self.log_to_console(f"Starting {process_name}...")
        self.log_to_console(f"Command: {' '.join(cmd)}")
        self.log_to_console("="*60)
        
        self.run_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.status_var.set(f"Initializing {process_name}...")
        self.overall_progress['value'] = 0
        self.current_progress.start()
        
        # Track processing phase and job counts
        self.processing_phase = "initializing"
        self.total_jobs = 0
        self.completed_jobs = 0
        self.failed_jobs = 0
        self.last_progress_update = time.time()
        self.progress_monitor_thread = None
        
        # Start process in background thread
        def run_process():
            try:
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    universal_newlines=True,
                    bufsize=1
                )
                
                # Read output line by line with enhanced parsing
                while True:
                    output = self.current_process.stdout.readline()
                    if output == '' and self.current_process.poll() is not None:
                        break
                    if output:
                        self.root.after(0, lambda text=output.strip(): self.parse_and_log_output(text))
                
                return_code = self.current_process.wait()
                
                if return_code == 0:
                    self.root.after(0, lambda: self.process_completed(process_name, True))
                else:
                    self.root.after(0, lambda: self.process_completed(process_name, False))
                    
            except Exception as e:
                self.root.after(0, lambda: self.process_error(process_name, str(e)))
        
        self.monitoring_thread = threading.Thread(target=run_process)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()

        # Start progress monitoring
        self.start_progress_monitoring()
    
    def stop_current_process(self):
        """Stop the current process"""
        if self.current_process and self.current_process.poll() is None:
            self.current_process.terminate()
            self.log_to_console("Process terminated by user")
            self.process_completed("Process", False)
    
    def process_completed(self, process_name, success):
        """Handle process completion"""
        self.run_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self.overall_progress['value'] = 100 if success else 0
        self.current_progress.stop()
        
        if success:
            self.status_var.set(f"✅ {process_name} completed successfully!")
            self.log_to_console("="*60)
            self.log_to_console(f"✅ {process_name} COMPLETED SUCCESSFULLY")
            self.log_to_console(f"Total jobs processed: {self.completed_jobs}/{self.total_jobs}")
            self.log_to_console("="*60)
        else:
            self.status_var.set(f"❌ {process_name} failed or was stopped")
            self.log_to_console("="*60)
            self.log_to_console(f"❌ {process_name} FAILED OR STOPPED")
            self.log_to_console("="*60)
        
        self.current_process = None
        self.processing_phase = "idle"

        # Stop progress monitoring
        if self.progress_monitor_thread and self.progress_monitor_thread.is_alive():
            self.progress_monitor_thread = None
    
    def process_error(self, process_name, error_msg):
        """Handle process error"""
        self.run_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self.overall_progress['value'] = 0
        self.current_progress.stop()
        self.status_var.set(f"{process_name} error")
        self.log_to_console(f"\n❌ {process_name} error: {error_msg}")
        self.current_process = None
    
    def update_overall_progress(self, percentage, status_text=None):
        """Update the overall progress bar"""
        self.overall_progress['value'] = min(100, max(0, percentage))
        if status_text:
            self.status_var.set(status_text)

    def start_progress_monitoring(self):
        """Start background monitoring of batch progress"""
        if self.progress_monitor_thread and self.progress_monitor_thread.is_alive():
            return

        def monitor_progress():
            while self.processing_phase in ["llm", "comfyui", "monitoring"]:
                try:
                    # Check queue status every 10 seconds
                    time.sleep(10)

                    if self.processing_phase in ["comfyui", "monitoring"] and self.total_jobs > 0:
                        # Get current queue status
                        cmd = [sys.executable, self.gpu_script_path, 'queue', 'status']
                        result = subprocess.run(cmd, capture_output=True, text=True,
                                              encoding='utf-8', timeout=5)

                        # Parse queue status for live updates
                        if result.returncode == 0:
                            self.parse_queue_status(result.stdout)

                except Exception as e:
                    # Silently handle monitoring errors
                    pass

                # Stop monitoring if process is complete
                if self.processing_phase in ["cleanup", "idle"]:
                    break

        self.progress_monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
        self.progress_monitor_thread.start()

    def parse_queue_status(self, queue_output):
        """Parse queue status output for live progress updates"""
        import re

        # Look for active job counts
        lines = queue_output.split('\n')
        for line in lines:
            line = line.strip()
            if 'active' in line.lower() or 'running' in line.lower():
                # Try to extract numbers
                match = re.search(r'(\d+)', line)
                if match:
                    active_jobs = int(match.group(1))
                    if active_jobs > 0 and hasattr(self, 'total_jobs') and self.total_jobs > 0:
                        # Estimate progress based on active jobs
                        estimated_completed = self.total_jobs - active_jobs
                        if estimated_completed > self.completed_jobs:
                            self.completed_jobs = estimated_completed
                            progress = 35 + (self.completed_jobs / self.total_jobs) * 60
                            self.update_overall_progress(progress,
                                f"🎨 Active: {active_jobs} jobs processing, {self.completed_jobs}/{self.total_jobs} complete")
                            self.log_to_console(f"📊 Queue status: {active_jobs} active, {self.completed_jobs}/{self.total_jobs} complete")
    
    def parse_and_log_output(self, message):
        """Parse output for status updates and log to console"""
        import re

        # Detect processing phases with better progress tracking
        if "PHASE 1: LLM INFERENCE" in message:
            self.processing_phase = "llm"
            self.status_var.set("🤖 LLM Phase: Generating creative prompts...")
            self.update_overall_progress(5, "LLM: Analyzing requirements")
            self.current_progress.start()
            self.log_to_console("🎯 Starting LLM inference phase...")

        elif "PHASE 2: IMAGE GENERATION" in message:
            self.processing_phase = "comfyui"
            self.status_var.set("🎨 ComfyUI Phase: Initializing AI image generation...")
            self.update_overall_progress(25, "ComfyUI: Starting up")
            self.current_progress.start()
            self.log_to_console("🚀 Starting ComfyUI image generation phase...")

        elif "PHASE 3: CLEANUP" in message:
            self.processing_phase = "cleanup"
            self.status_var.set("🧹 Finalizing: Cleaning up temporary files...")
            self.update_overall_progress(98, "Finalizing results")
            self.current_progress.stop()
            self.log_to_console("✨ Processing complete, finalizing...")

        # Track batch submission with queue integration
        elif "BATCH SUBMISSION PHASE" in message:
            self.status_var.set("📤 Queue Phase: Preparing jobs for GPU processing...")
            self.update_overall_progress(30, "Queue: Preparing batch jobs")
            self.log_to_console("📋 Preparing batch submission...")

        elif "Successfully submitted:" in message:
            match = re.search(r'Successfully submitted: (\d+)', message)
            if match:
                self.total_jobs = int(match.group(1))
                self.completed_jobs = 0
                self.status_var.set(f"⚡ GPU Processing: {self.total_jobs} jobs queued for generation")
                self.update_overall_progress(35, f"GPU: {self.total_jobs} jobs queued")
                self.log_to_console(f"🎯 Submitted {self.total_jobs} jobs to ComfyUI queue")

        # Enhanced job completion tracking with better regex and status
        elif ("completed" in message.lower() and ("(" in message and ")" in message)) or \
             ("Completed:" in message and "/" in message):
            # More robust regex to catch various completion formats
            match = re.search(r'\((\d+)/(\d+)\)', message)
            if not match:
                match = re.search(r'Completed:\s*(\d+)/(\d+)', message)
            if not match:
                match = re.search(r'(\d+)/(\d+)', message)

            if match:
                self.completed_jobs = int(match.group(1))
                total = int(match.group(2))
                self.total_jobs = total

                # Calculate dynamic progress based on current phase
                if self.processing_phase == "llm":
                    # LLM phase: 5% to 25%
                    progress = 5 + (self.completed_jobs / total) * 20
                elif self.processing_phase == "comfyui":
                    # ComfyUI phase: 35% to 95%
                    progress = 35 + (self.completed_jobs / total) * 60
                else:
                    # Fallback
                    progress = 40 + (self.completed_jobs / total) * 55

                self.update_overall_progress(progress)

                # More informative status messages
                if self.completed_jobs == 0:
                    status_msg = f"🎨 Starting generation: {total} images to process"
                elif self.completed_jobs == total:
                    status_msg = f"✅ Complete: All {total} images generated successfully!"
                else:
                    remaining = total - self.completed_jobs
                    status_msg = f"🎨 Generating: {self.completed_jobs}/{total} complete ({remaining} remaining)"

                self.status_var.set(status_msg)

                # Log progress milestones
                if self.completed_jobs % 5 == 0 or self.completed_jobs == total:
                    self.log_to_console(f"📊 Progress: {self.completed_jobs}/{total} images generated")

        # Track monitoring phase with queue status
        elif "JOB MONITORING PHASE" in message:
            self.status_var.set("👀 Monitoring: Tracking job progress in real-time...")
            self.update_overall_progress(40, "Monitoring: Active processing")
            self.log_to_console("🔍 Activating real-time job monitoring...")

        # Track failures and errors
        elif "failed" in message.lower() or "error" in message.lower():
            self.status_var.set("⚠️ Issue detected - check console for details")
            self.log_to_console(f"⚠️ {message}")

        # Track queue status updates
        elif "queue" in message.lower() and ("status" in message.lower() or "active" in message.lower()):
            self.log_to_console(f"📋 {message}")

        # Log to console with proper Unicode encoding
        self.log_to_console(message)
    
    def log_to_console(self, message):
        """Log message to console output with proper Unicode support"""
        try:
            # Ensure proper Unicode display
            self.console_text.insert(tk.END, message + "\n", ())
            self.console_text.see(tk.END)
            self.console_text.update()
        except Exception as e:
            # Fallback for any encoding issues
            safe_message = message.encode('utf-8', errors='replace').decode('utf-8')
            self.console_text.insert(tk.END, safe_message + "\n")
            self.console_text.see(tk.END)
            self.console_text.update()
    
    def show_queue_status(self):
        """Show batch queue status with proper Unicode display"""
        cmd = [sys.executable, self.gpu_script_path, 'queue', 'status']
        try:
            # Run with UTF-8 encoding
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

            # Create popup window
            popup = tk.Toplevel(self.root)
            popup.title("Batch Queue Status - Real-time Processing")
            popup.geometry("800x600")
            popup.configure(bg=self.colors['bg'])

            # Header with current processing info
            header_frame = ttk.Frame(popup, style="AppleCard.TFrame")
            header_frame.pack(fill='x', padx=20, pady=(20, 10))

            ttk.Label(header_frame, text="🎨 MuseVision Batch Processing Status",
                     font=('Arial', 14, 'bold'), style="Apple.TLabel").pack()

            if hasattr(self, 'processing_phase') and self.processing_phase:
                phase_text = f"Current Phase: {self.processing_phase.upper()}"
                ttk.Label(header_frame, text=phase_text,
                         font=('Arial', 11), style="AppleSecondary.TLabel").pack(pady=(5, 0))

            if hasattr(self, 'total_jobs') and self.total_jobs > 0:
                progress_text = f"Progress: {getattr(self, 'completed_jobs', 0)}/{self.total_jobs} jobs"
                ttk.Label(header_frame, text=progress_text,
                         font=('Arial', 11), style="Apple.TLabel").pack(pady=(2, 0))

            # Text widget for status
            text_frame = ttk.Frame(popup, style="Apple.TFrame")
            text_frame.pack(fill='both', expand=True, padx=20, pady=(10, 20))

            text_widget = ScrolledText(text_frame,
                                      bg=self.colors['card_bg'],
                                      fg=self.colors['text'],
                                      font=('Courier', 10),
                                      insertbackground=self.colors['text'],
                                      selectbackground=self.colors['accent'],
                                      selectforeground='white',
                                      borderwidth=1,
                                      highlightthickness=0,
                                      wrap='word')
            text_widget.pack(fill='both', expand=True)

            # Insert text with proper Unicode handling
            try:
                text_widget.insert('1.0', result.stdout)
            except:
                # Fallback if there are encoding issues
                safe_text = result.stdout.encode('utf-8', errors='replace').decode('utf-8')
                text_widget.insert('1.0', safe_text)

            text_widget.config(state='disabled')  # Make read-only

            # Add refresh button
            button_frame = ttk.Frame(popup, style="Apple.TFrame")
            button_frame.pack(fill='x', padx=20, pady=(0, 20))

            ttk.Button(button_frame, text="🔄 Refresh Status",
                      command=lambda: self.refresh_queue_status(text_widget)).pack(side='right')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to get queue status: {str(e)}")

    def refresh_queue_status(self, text_widget):
        """Refresh the queue status in the popup window"""
        cmd = [sys.executable, self.gpu_script_path, 'queue', 'status']
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

            # Clear and update text
            text_widget.config(state='normal')
            text_widget.delete('1.0', tk.END)

            try:
                text_widget.insert('1.0', result.stdout)
            except:
                safe_text = result.stdout.encode('utf-8', errors='replace').decode('utf-8')
                text_widget.insert('1.0', safe_text)

            text_widget.config(state='disabled')

        except Exception as e:
            text_widget.config(state='normal')
            text_widget.delete('1.0', tk.END)
            text_widget.insert('1.0', f"Error refreshing status: {str(e)}")
            text_widget.config(state='disabled')
    
    def run(self):
        """Start the GUI application"""
        self.root.mainloop()


def main():
    """Main entry point"""
    # Ensure the gui directory exists
    gui_dir = os.path.dirname(__file__)
    os.makedirs(gui_dir, exist_ok=True)
    
    app = AppleStyleGUI()
    app.run()


if __name__ == "__main__":
    main()