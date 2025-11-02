#!/usr/bin/env python3
"""
test_lora_effects.py - Comprehensive LoRA Testing Script

This script systematically tests individual LoRAs across different strength levels
and prompts to evaluate their effects and find optimal settings.

Features:
- Tests LoRAs across configurable strength ranges
- Uses predefined prompts covering various categories (characters, environments, etc.)
- Fixed seed for reproducible results
- Organized output structure with summary reports
- Metadata verification to confirm LoRA application
- Quick mode for faster testing

Usage Examples:
  # Test a specific LoRA (auto-starts ComfyUI)
  python test_lora_effects.py --lora "Flux1D-CyberPunkAnime.safetensors"
  
  # Quick test with limited strengths and prompts
  python test_lora_effects.py --lora "Flux1D-mythp0rt.safetensors" --quick
  
  # Keep ComfyUI running after tests for manual use
  python test_lora_effects.py --lora "Flux1D-Prismatic_Dreams.safetensors" --keep-comfyui-running
  
  # Use existing ComfyUI instance (don't auto-start/stop)
  python test_lora_effects.py --lora "Flux1D-Glowing_And_Glossy.safetensors" --no-auto-comfyui
  
  # Test all available Flux LoRAs (will take a while!)
  python test_lora_effects.py --all-flux-loras --quick
"""

import os
import sys
import argparse
import json
import subprocess
import time
import signal
import requests
import threading
from pathlib import Path
from typing import List, Tuple, Optional
import html

try:
    import safetensors
    SAFETENSORS_AVAILABLE = True
except ImportError:
    SAFETENSORS_AVAILABLE = False

# Add the scripts directory to Python path
script_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(script_dir))

# Import checkpoint management
from checkpoint_manager import CheckpointManager, ModelArchitecture

# Default test prompts covering various categories
DEFAULT_PROMPTS = [
    "a majestic dragon perched on a crystal mountain",      # Fantasy creature
    "cyberpunk city street at night with neon lights",     # Urban environment  
    "portrait of a warrior in ornate armor",               # Character detail
    "magical forest with glowing mushrooms",               # Nature/lighting
    "futuristic spaceship interior",                       # Architecture/tech
    "ethereal goddess floating in clouds",                 # Abstract/artistic
    "ancient temple ruins at sunset",                      # Architecture/lighting
    "steampunk mechanical creature",                       # Style/design
]

# Quick mode prompts (subset for faster testing)
QUICK_PROMPTS = [
    "portrait of a warrior in ornate armor",
    "cyberpunk city street at night with neon lights", 
    "magical forest with glowing mushrooms",
]

# Default strength values
DEFAULT_STRENGTHS = [0.0, 0.25, 0.5, 0.75, 1.0]
QUICK_STRENGTHS = [0.0, 0.5, 1.0]

# Fixed seed for reproducible results
TEST_SEED = 42

class LoRAEffectTester:
    def __init__(self, output_base_dir: str = "LoRA_tests", auto_manage_comfyui: bool = True, skip_validation: bool = False):
        self.output_base_dir = Path(output_base_dir)
        self.script_dir = script_dir
        self.run_flux_path = self.script_dir / "run_flux.py"
        self.show_loras_path = self.script_dir / "show_loras.py"
        self.auto_manage_comfyui = auto_manage_comfyui
        self.skip_validation = skip_validation
        self.comfyui_process: Optional[subprocess.Popen] = None
        self.comfyui_dir = self.script_dir.parent / "ComfyUI"
        
        # Ensure run_flux.py exists
        if not self.run_flux_path.exists():
            raise FileNotFoundError(f"run_flux.py not found at {self.run_flux_path}")
        
        # Find LoRA models directory
        self.lora_dirs = []
        for possible_path in [
            Path("/home/mitchellflautt/MuseVision/models/LoRAs/Flux"),
            Path("/home/mitchellflautt/MuseVision/ComfyUI/models/loras"),
            script_dir.parent / "models" / "LoRAs" / "Flux",
            script_dir.parent / "ComfyUI" / "models" / "loras",
        ]:
            if possible_path.exists():
                self.lora_dirs.append(possible_path)
        
        # Keep the first one as primary for backwards compatibility
        self.lora_dir = self.lora_dirs[0] if self.lora_dirs else None
                
        if not self.lora_dirs:
            print("⚠️  Warning: Could not find LoRA models directory")
        
        # Ensure ComfyUI directory exists if auto-managing
        if self.auto_manage_comfyui and not self.comfyui_dir.exists():
            print(f"❌ ComfyUI directory not found at: {self.comfyui_dir}")
            self.auto_manage_comfyui = False
        
        # Initialize checkpoint manager
        self.checkpoint_manager = CheckpointManager(self.comfyui_dir)
    
    def get_available_flux_loras(self) -> List[str]:
        """Get list of available Flux LoRA files"""
        if not self.lora_dirs:
            return []
        
        loras = set()  # Use set to avoid duplicates
        for lora_dir in self.lora_dirs:
            if lora_dir.exists():
                for file in lora_dir.glob("*.safetensors"):
                    # Only include Flux LoRAs (filter out SDXL etc)
                    if "flux" in file.name.lower() or "Flux" in file.name:
                        loras.add(file.name)
                    # Also include files that don't have obvious model indicators
                    elif not any(model in file.name.lower() for model in ['sdxl', 'sd15', 'sd1.5']):
                        loras.add(file.name)
        return sorted(list(loras))
    
    def validate_lora(self, lora_name: str) -> str:
        """Validate LoRA exists and return full filename"""
        if not lora_name.endswith('.safetensors'):
            lora_name += '.safetensors'
            
        # Check all LoRA directories
        for lora_dir in self.lora_dirs:
            lora_path = lora_dir / lora_name
            if lora_path.exists():
                return lora_name
        
        # Also check if it's just a base name we need to find
        available = self.get_available_flux_loras()
        matches = [name for name in available if lora_name.lower() in name.lower()]
        
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            print(f"❌ Multiple LoRAs match '{lora_name}':")
            for match in matches:
                print(f"   - {match}")
            sys.exit(1)
        else:
            print(f"❌ LoRA '{lora_name}' not found")
            if available:
                print("Available Flux LoRAs:")
                for name in available:
                    print(f"   - {name}")
            else:
                print("No Flux LoRAs found in any directory")
                print(f"Searched directories: {[str(d) for d in self.lora_dirs]}")
            sys.exit(1)
    
    def validate_lora_architecture(self, lora_name: str) -> Tuple[bool, str, Optional[ModelArchitecture]]:
        """Validate LoRA architecture and return compatibility info"""
        if not SAFETENSORS_AVAILABLE:
            return True, "SafeTensors not available - skipping architecture validation", None
        
        # Find the LoRA file
        lora_path = None
        for lora_dir in self.lora_dirs:
            candidate_path = lora_dir / lora_name
            if candidate_path.exists():
                lora_path = candidate_path
                break
        
        if not lora_path:
            return False, f"LoRA file not found: {lora_name}", None
        
        try:
            # Use checkpoint manager for detailed analysis
            lora_info = self.checkpoint_manager.analyze_lora_architecture(lora_path)
            
            if lora_info.architecture == ModelArchitecture.UNKNOWN:
                return False, lora_info.details, lora_info.architecture
            else:
                return True, lora_info.details, lora_info.architecture
                
        except Exception as e:
            return False, f"Error analyzing LoRA architecture: {e}", None
    
    def is_comfyui_running(self) -> bool:
        """Check if ComfyUI is running and responsive"""
        try:
            response = requests.get("http://127.0.0.1:8188/system_stats", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def start_comfyui(self) -> bool:
        """Start ComfyUI process and wait for it to be ready"""
        if not self.auto_manage_comfyui:
            return False
            
        if self.is_comfyui_running():
            print("ℹ️  ComfyUI is already running")
            return True
        
        print("🚀 Starting ComfyUI...")
        
        try:
            # Start ComfyUI process
            self.comfyui_process = subprocess.Popen(
                [sys.executable, "main.py", "--listen"],
                cwd=self.comfyui_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Monitor ComfyUI output in a separate thread
            def monitor_output():
                if self.comfyui_process and self.comfyui_process.stdout:
                    for line in iter(self.comfyui_process.stdout.readline, ''):
                        if line.strip():
                            print(f"[ComfyUI] {line.strip()}")
                        if self.comfyui_process.poll() is not None:
                            break
            
            output_thread = threading.Thread(target=monitor_output, daemon=True)
            output_thread.start()
            
            print("⏳ Waiting for ComfyUI to be ready...")
            
            # Wait for ComfyUI to be ready (max 120 seconds)
            for i in range(120):
                if self.is_comfyui_running():
                    print(f"✅ ComfyUI is ready! (took {i+1} seconds)")
                    return True
                
                # Check if process died
                if self.comfyui_process.poll() is not None:
                    print(f"❌ ComfyUI process died with return code: {self.comfyui_process.returncode}")
                    return False
                
                time.sleep(1)
                
                # Show progress every 10 seconds
                if (i + 1) % 10 == 0:
                    print(f"⏳ Still waiting for ComfyUI... ({i+1}s)")
            
            print("❌ ComfyUI failed to start within 120 seconds")
            self.stop_comfyui()
            return False
            
        except Exception as e:
            print(f"❌ Error starting ComfyUI: {e}")
            return False
    
    def stop_comfyui(self):
        """Stop the ComfyUI process if we started it"""
        if self.comfyui_process:
            print("🛑 Stopping ComfyUI...")
            try:
                # Try graceful shutdown first
                self.comfyui_process.terminate()
                try:
                    self.comfyui_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    print("⚠️  ComfyUI didn't stop gracefully, force killing...")
                    self.comfyui_process.kill()
                    self.comfyui_process.wait()
            except Exception as e:
                print(f"⚠️  Error stopping ComfyUI: {e}")
            finally:
                self.comfyui_process = None
            print("✅ ComfyUI stopped")
    
    def cleanup(self):
        """Clean up resources, especially ComfyUI process"""
        if self.auto_manage_comfyui:
            self.stop_comfyui()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
    
    def generate_image(self, prompt: str, lora_name: str, strength: float, 
                      output_path: Path, prompt_index: int, checkpoint: str = None, workflow: str = None) -> Tuple[bool, str]:
        """Generate a single image with specified LoRA and strength"""
        
        # Create output filename for our organized structure
        lora_base = lora_name.replace('.safetensors', '')
        strength_str = f"{strength:.2f}".replace('.', 'p')
        filename = f"prompt_{prompt_index:02d}_strength_{strength_str}.png"
        final_output_path = output_path / filename
        
        # ComfyUI output directory (where images are actually saved)
        comfyui_output_dir = self.script_dir.parent / "ComfyUI" / "output"
        
        # Prepare run_flux.py command (without output-dir to keep files in ComfyUI/output)
        name_prefix = f"test_{lora_base}_{strength_str}"
        cmd = [
            sys.executable, str(self.run_flux_path),
            "--prompt", prompt,
            "--seed", str(TEST_SEED),
            "--name-prefix", name_prefix
        ]
        
        # Add LoRA specification if strength > 0
        if strength > 0:
            lora_spec = f"{lora_name}:{strength}"
            cmd.extend(["--loras", lora_spec])
        
        # Add checkpoint if specified
        if checkpoint:
            cmd.extend(["--checkpoint", checkpoint])
        
        # Add workflow if specified  
        if workflow:
            cmd.extend(["--workflow", workflow])
        
        try:
            print(f"   🎨 Generating: strength={strength:.2f}")
            
            # Count existing files to detect new ones
            existing_files = set(comfyui_output_dir.glob("*.png")) if comfyui_output_dir.exists() else set()
            
            # Submit workflow
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                return False, f"run_flux.py failed: {result.stderr}"
            
            # Wait for image to be generated (ComfyUI processes asynchronously)
            print(f"      ⏳ Waiting for generation to complete...")
            max_wait_time = 120  # 2 minutes
            wait_interval = 2   # Check every 2 seconds
            
            for i in range(0, max_wait_time, wait_interval):
                if comfyui_output_dir.exists():
                    current_files = set(comfyui_output_dir.glob("*.png"))
                    new_files = current_files - existing_files
                    
                    # Look for files matching our prefix pattern
                    matching_files = [
                        f for f in new_files 
                        if name_prefix in f.name or f.name.startswith(name_prefix)
                    ]
                    
                    if matching_files:
                        # Found our generated image!
                        source_file = matching_files[0]  # Take the first match
                        
                        # Copy to our organized structure
                        final_output_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Read and copy the file
                        with open(source_file, 'rb') as src, open(final_output_path, 'wb') as dst:
                            dst.write(src.read())
                        
                        print(f"      ✅ Generated and saved to {filename}")
                        return True, str(final_output_path)
                
                time.sleep(wait_interval)
                
                # Show progress every 10 seconds
                if (i + wait_interval) % 10 == 0:
                    print(f"      ⏳ Still waiting... ({i + wait_interval}s)")
            
            # Timeout - check if any files were created at all
            if comfyui_output_dir.exists():
                current_files = set(comfyui_output_dir.glob("*.png"))
                new_files = current_files - existing_files
                if new_files:
                    # Some file was generated, but didn't match our pattern
                    new_file_names = [f.name for f in list(new_files)[:3]]  # Show first 3
                    return False, f"Images generated but naming mismatch. Expected prefix: {name_prefix}, Found: {new_file_names}"
                else:
                    return False, "No new images found in ComfyUI output directory after 2 minutes"
            else:
                return False, "ComfyUI output directory not found"
                
        except subprocess.TimeoutExpired:
            return False, "Workflow submission timed out (1 minute)"
        except Exception as e:
            return False, f"Generation error: {e}"
    
    def verify_lora_metadata(self, image_path: Path, expected_lora: str, 
                           expected_strength: float) -> Tuple[bool, str]:
        """Verify that the image contains expected LoRA metadata"""
        if not self.show_loras_path.exists():
            return True, "show_loras.py not available - skipping verification"
        
        try:
            result = subprocess.run([
                sys.executable, str(self.show_loras_path), str(image_path)
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return False, f"Metadata extraction failed: {result.stderr}"
            
            output = result.stdout
            if "no LoRAs found" in output and expected_strength == 0:
                return True, "No LoRA expected and none found"
            elif "no LoRAs found" in output and expected_strength > 0:
                return False, f"Expected LoRA {expected_lora} but none found"
            
            # Parse the output to check LoRA name and strength
            lines = output.split('\n')
            for line in lines:
                if expected_lora in line or expected_lora.replace('.safetensors', '') in line:
                    # Extract strength value
                    if "strength=" in line:
                        strength_part = line.split("strength=")[1].split()[0]
                        try:
                            actual_strength = float(strength_part)
                            if abs(actual_strength - expected_strength) < 0.01:
                                return True, f"LoRA verified: {expected_lora} @ {actual_strength}"
                            else:
                                return False, f"Strength mismatch: expected {expected_strength}, got {actual_strength}"
                        except ValueError:
                            return False, f"Could not parse strength from: {strength_part}"
                    elif "model=" in line:
                        # Handle model/clip format
                        model_part = line.split("model=")[1].split()[0]
                        try:
                            actual_strength = float(model_part)
                            if abs(actual_strength - expected_strength) < 0.01:
                                return True, f"LoRA verified: {expected_lora} @ {actual_strength}"
                            else:
                                return False, f"Strength mismatch: expected {expected_strength}, got {actual_strength}"
                        except ValueError:
                            return False, f"Could not parse model strength from: {model_part}"
            
            if expected_strength > 0:
                return False, f"LoRA {expected_lora} not found in metadata"
            else:
                return True, "No LoRA expected"
                
        except subprocess.TimeoutExpired:
            return False, "Metadata verification timed out"
        except Exception as e:
            return False, f"Metadata verification error: {e}"
    
    def test_lora(self, lora_name: str, prompts: List[str], strengths: List[float]) -> dict:
        """Test a single LoRA across all prompts and strengths"""
        
        lora_name = self.validate_lora(lora_name)
        lora_base = lora_name.replace('.safetensors', '')
        
        print(f"\n🧪 Testing LoRA: {lora_name}")
        
        # Validate LoRA architecture before testing (unless skipped)
        selected_checkpoint = None
        selected_workflow = None
        
        if not self.skip_validation:
            is_valid, validation_msg, lora_architecture = self.validate_lora_architecture(lora_name)
            print(f"🔍 Architecture Check: {validation_msg}")
            
            if not is_valid:
                print(f"⚠️  Skipping incompatible LoRA: {lora_name}")
                return {
                    'lora_name': lora_name,
                    'test_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'prompts': prompts,
                    'strengths': strengths,
                    'validation_error': validation_msg,
                    'results': [],
                    'skipped': True
                }
            
            # Auto-select compatible checkpoint and workflow if architecture detected
            if lora_architecture and lora_architecture != ModelArchitecture.UNKNOWN:
                compatible_checkpoint = self.checkpoint_manager.find_compatible_checkpoint(lora_architecture)
                if compatible_checkpoint:
                    selected_checkpoint = compatible_checkpoint.name
                    print(f"🎯 Auto-selected checkpoint: {selected_checkpoint} ({lora_architecture.value.upper()})")
                    
                    # Get appropriate workflow
                    workflow_path = self.checkpoint_manager.get_workflow_path(lora_architecture)
                    if workflow_path:
                        selected_workflow = str(workflow_path)
                        print(f"📋 Using {lora_architecture.value.upper()} workflow: {workflow_path.name}")
                else:
                    print(f"⚠️  No compatible {lora_architecture.value.upper()} checkpoints found, using default")
        else:
            print(f"⚠️  Architecture validation skipped (--skip-validation flag)")
        
        print(f"📋 Prompts: {len(prompts)}")
        print(f"💪 Strengths: {strengths}")
        
        # Create output directory
        test_dir = self.output_base_dir / lora_base
        test_dir.mkdir(parents=True, exist_ok=True)
        
        results = {
            'lora_name': lora_name,
            'test_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'prompts': prompts,
            'strengths': strengths,
            'results': []
        }
        
        total_tests = len(prompts) * len(strengths)
        current_test = 0
        
        for prompt_idx, prompt in enumerate(prompts):
            print(f"\n📝 Prompt {prompt_idx + 1}/{len(prompts)}: {prompt[:60]}{'...' if len(prompt) > 60 else ''}")
            
            prompt_results = {
                'prompt': prompt,
                'prompt_index': prompt_idx,
                'strength_results': []
            }
            
            for strength in strengths:
                current_test += 1
                print(f"   [{current_test}/{total_tests}] ", end="")
                
                success, result_info = self.generate_image(
                    prompt, lora_name, strength, test_dir, prompt_idx, selected_checkpoint, selected_workflow
                )
                
                strength_result = {
                    'strength': strength,
                    'success': success,
                    'info': result_info
                }
                
                if success:
                    # Verify metadata
                    image_path = Path(result_info)
                    if image_path.exists():
                        verified, verify_info = self.verify_lora_metadata(
                            image_path, lora_name, strength
                        )
                        strength_result['metadata_verified'] = verified
                        strength_result['metadata_info'] = verify_info
                        
                        if verified:
                            print(f"✅ {verify_info}")
                        else:
                            print(f"⚠️  Generated but {verify_info}")
                    else:
                        print(f"❌ File not found: {result_info}")
                        strength_result['success'] = False
                else:
                    print(f"❌ {result_info}")
                
                prompt_results['strength_results'].append(strength_result)
            
            results['results'].append(prompt_results)
        
        # Save results JSON
        results_file = test_dir / "test_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Generate HTML summary
        self.generate_html_summary(results, test_dir)
        
        return results
    
    def generate_html_summary(self, results: dict, output_dir: Path):
        """Generate an HTML summary report"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>LoRA Test Results: {results['lora_name']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .prompt-section {{ margin: 20px 0; border: 1px solid #ddd; padding: 15px; }}
        .strength-grid {{ display: flex; flex-wrap: wrap; gap: 10px; }}
        .strength-item {{ text-align: center; }}
        .strength-item img {{ max-width: 200px; max-height: 200px; border: 2px solid #ddd; }}
        .success {{ border-color: #4CAF50; }}
        .failed {{ border-color: #f44336; }}
        .metadata-issue {{ border-color: #ff9800; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>LoRA Test Results</h1>
        <p><strong>LoRA:</strong> {results['lora_name']}</p>
        <p><strong>Test Date:</strong> {results['test_timestamp']}</p>
        <p><strong>Prompts Tested:</strong> {len(results['prompts'])}</p>
        <p><strong>Strengths Tested:</strong> {results['strengths']}</p>
    </div>
"""
        
        for prompt_result in results['results']:
            prompt = prompt_result['prompt']
            prompt_idx = prompt_result['prompt_index']
            
            html_content += f"""
    <div class="prompt-section">
        <h2>Prompt {prompt_idx + 1}: {html.escape(prompt)}</h2>
        <div class="strength-grid">
"""
            
            for strength_result in prompt_result['strength_results']:
                strength = strength_result['strength']
                success = strength_result['success']
                
                # Determine image file name
                lora_base = results['lora_name'].replace('.safetensors', '')
                strength_str = f"{strength:.2f}".replace('.', 'p')
                img_filename = f"prompt_{prompt_idx:02d}_strength_{strength_str}.png"
                
                css_class = "success"
                if not success:
                    css_class = "failed"
                elif not strength_result.get('metadata_verified', True):
                    css_class = "metadata-issue"
                
                status_info = strength_result.get('metadata_info', 
                                                strength_result.get('info', 'Unknown'))
                
                html_content += f"""
            <div class="strength-item">
                <p><strong>Strength: {strength:.2f}</strong></p>
"""
                
                if success and Path(output_dir / img_filename).exists():
                    html_content += f"""
                <img src="{img_filename}" class="{css_class}" 
                     title="{html.escape(status_info)}" alt="Strength {strength:.2f}">
"""
                else:
                    html_content += f"""
                <div class="failed" style="width: 200px; height: 200px; 
                     display: flex; align-items: center; justify-content: center; 
                     background-color: #f0f0f0;">
                    Failed
                </div>
"""
                
                html_content += f"""
                <p style="font-size: 12px;">{html.escape(status_info[:50])}{'...' if len(status_info) > 50 else ''}</p>
            </div>
"""
            
            html_content += """
        </div>
    </div>
"""
        
        html_content += """
</body>
</html>
"""
        
        html_file = output_dir / "test_results.html"
        with open(html_file, 'w') as f:
            f.write(html_content)
        
        print(f"📊 HTML summary saved to: {html_file}")

def main():
    parser = argparse.ArgumentParser(
        description="Test LoRA effects across different strengths and prompts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test a specific LoRA (auto-starts ComfyUI)
  %(prog)s --lora "Flux1D-CyberPunkAnime.safetensors"
  
  # Quick test with limited strengths and prompts  
  %(prog)s --lora "Flux1D-mythp0rt.safetensors" --quick
  
  # Keep ComfyUI running after tests
  %(prog)s --lora "Flux1D-Prismatic_Dreams.safetensors" --keep-comfyui-running
  
  # Use existing ComfyUI (don't auto-manage)
  %(prog)s --lora "Flux1D-Glowing_And_Glossy.safetensors" --no-auto-comfyui
  
  # Force test incompatible LoRA (skip validation)
  %(prog)s --lora "SDXL-LoRA.safetensors" --skip-validation
  
  # Only validate LoRA compatibility (no image generation)
  %(prog)s --all-flux-loras --validate-only
  
  # Test all Flux LoRAs (will take a while!)
  %(prog)s --all-flux-loras --quick
"""
    )
    
    # List option (separate from main options)
    parser.add_argument('--list-loras', action='store_true',
                       help='List available Flux LoRAs and exit')
    
    # LoRA selection options
    lora_group = parser.add_mutually_exclusive_group(required=False)
    lora_group.add_argument('--lora', type=str,
                           help='Specific LoRA file to test (e.g., "Flux1D-CyberPunkAnime.safetensors")')
    lora_group.add_argument('--all-flux-loras', action='store_true',
                           help='Test all available Flux LoRAs')
    
    # Test configuration options  
    parser.add_argument('--prompts', nargs='+', type=str,
                       help='Custom prompts to test (default: predefined set)')
    parser.add_argument('--strengths', nargs='+', type=float,
                       help='LoRA strengths to test (default: 0.0 0.25 0.5 0.75 1.0)')
    parser.add_argument('--quick', action='store_true',
                       help='Quick mode: fewer prompts and strengths')
    
    # Output options
    parser.add_argument('--output-dir', type=str, default='LoRA_tests',
                       help='Base output directory (default: LoRA_tests)')
    
    # ComfyUI management options
    parser.add_argument('--no-auto-comfyui', action='store_true',
                       help='Disable automatic ComfyUI startup/shutdown')
    parser.add_argument('--keep-comfyui-running', action='store_true',
                       help='Keep ComfyUI running after tests complete')
    
    # Validation options
    parser.add_argument('--skip-validation', action='store_true',
                       help='Skip LoRA architecture validation (force test incompatible LoRAs)')
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate LoRA architecture (don\'t generate images)')
    
    args = parser.parse_args()
    
    # Initialize tester
    try:
        auto_manage = not args.no_auto_comfyui
        tester = LoRAEffectTester(args.output_dir, auto_manage_comfyui=auto_manage, skip_validation=args.skip_validation)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    # Handle list option
    if args.list_loras:
        available = tester.get_available_flux_loras()
        if available:
            print("Available Flux LoRAs:")
            for lora in available:
                print(f"  - {lora}")
        else:
            print("No Flux LoRAs found")
        sys.exit(0)
    
    # Validate that either --lora or --all-flux-loras is provided
    if not args.lora and not args.all_flux_loras:
        parser.error("Must specify either --lora LORA_NAME or --all-flux-loras")
    
    # Set up signal handlers for clean shutdown
    def signal_handler(signum, frame):
        print(f"\n⚠️  Received signal {signum}, shutting down...")
        tester.cleanup()
        sys.exit(1)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start ComfyUI if auto-management is enabled
    if tester.auto_manage_comfyui:
        if not tester.start_comfyui():
            print("❌ Failed to start ComfyUI. Exiting.")
            sys.exit(1)
    elif not tester.is_comfyui_running():
        print("⚠️  ComfyUI is not running and auto-management is disabled.")
        print("Please start ComfyUI manually or remove --no-auto-comfyui flag.")
        sys.exit(1)
    
    # Set up prompts
    if args.prompts:
        prompts = args.prompts
    elif args.quick:
        prompts = QUICK_PROMPTS
    else:
        prompts = DEFAULT_PROMPTS
    
    # Set up strengths
    if args.strengths:
        strengths = sorted(args.strengths)
    elif args.quick:
        strengths = QUICK_STRENGTHS
    else:
        strengths = DEFAULT_STRENGTHS
    
    # Determine which LoRAs to test
    if args.lora:
        loras_to_test = [args.lora]
    else:  # --all-flux-loras
        loras_to_test = tester.get_available_flux_loras()
        if not loras_to_test:
            print("❌ No Flux LoRAs found to test")
            sys.exit(1)
        print(f"🚀 Testing all {len(loras_to_test)} Flux LoRAs")
    
    # Handle validate-only mode
    if args.validate_only:
        print(f"🔍 Validation-only mode: checking {len(loras_to_test)} LoRAs")
        valid_count = 0
        invalid_count = 0
        
        for lora in loras_to_test:
            try:
                validated_name = tester.validate_lora(lora)
                is_valid, validation_msg = tester.validate_lora_architecture(validated_name)
                
                status = "✅" if is_valid else "❌"
                print(f"{status} {lora}: {validation_msg}")
                
                if is_valid:
                    valid_count += 1
                else:
                    invalid_count += 1
                    
            except SystemExit:
                print(f"❌ {lora}: Not found")
                invalid_count += 1
        
        print(f"\n📈 Validation Summary: {valid_count} valid, {invalid_count} invalid")
        sys.exit(0)
    
    # Run tests
    print(f"🎯 Test Configuration:")
    print(f"   📂 Output directory: {args.output_dir}")
    print(f"   📝 Prompts: {len(prompts)}")
    print(f"   💪 Strengths: {strengths}")
    print(f"   🧬 Seed: {TEST_SEED}")
    
    all_results = []
    successful_tests = 0
    
    for i, lora in enumerate(loras_to_test):
        print(f"\n{'='*60}")
        print(f"Testing LoRA {i+1}/{len(loras_to_test)}: {lora}")
        print('='*60)
        
        try:
            results = tester.test_lora(lora, prompts, strengths)
            all_results.append(results)
            
            # Check if LoRA was skipped due to validation
            if results.get('skipped', False):
                print(f"\n⚠️  Skipped {lora}: {results.get('validation_error', 'Unknown reason')}")
            else:
                # Count successful generations
                total_generations = sum(len(pr['strength_results']) for pr in results['results'])
                successful_generations = sum(
                    1 for pr in results['results'] 
                    for sr in pr['strength_results'] 
                    if sr['success']
                )
                
                print(f"\n✅ Completed {lora}: {successful_generations}/{total_generations} successful")
                if successful_generations > 0:
                    successful_tests += 1
                
        except KeyboardInterrupt:
            print(f"\n⚠️  Testing interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error testing {lora}: {e}")
    
    # Final summary
    print(f"\n🏁 Testing Complete!")
    print(f"   ✅ Successfully tested: {successful_tests}/{len(loras_to_test)} LoRAs")
    print(f"   📂 Results saved in: {args.output_dir}")
    print(f"\nNext steps:")
    print(f"   - Review HTML summaries in each LoRA subdirectory")
    print(f"   - Compare strength effects across different prompts")
    print(f"   - Identify optimal strength ranges for each LoRA")
    
    # Clean up ComfyUI unless user wants to keep it running
    if tester.auto_manage_comfyui and not args.keep_comfyui_running:
        tester.stop_comfyui()
    elif args.keep_comfyui_running:
        print(f"\nℹ️  ComfyUI is still running at http://127.0.0.1:8188")
        print(f"   Stop it manually when done: Ctrl+C in ComfyUI terminal or kill the process")

if __name__ == "__main__":
    main()