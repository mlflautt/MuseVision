#!/usr/bin/env python3
"""
Checkpoint Architecture Detection and Management System

This module provides functionality to:
1. Detect checkpoint architectures (Flux, SDXL, SD1.5)
2. Auto-match checkpoints with compatible LoRAs
3. Validate checkpoint/LoRA compatibility
4. Manage workflow selection based on architecture
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from enum import Enum
from dataclasses import dataclass

# SafeTensors import with fallback
try:
    import safetensors
    SAFETENSORS_AVAILABLE = True
except ImportError:
    SAFETENSORS_AVAILABLE = False

class ModelArchitecture(Enum):
    """Supported model architectures"""
    FLUX = "flux"
    SDXL = "sdxl"
    SD1_5 = "sd1.5"
    UNKNOWN = "unknown"

@dataclass
class CheckpointInfo:
    """Information about a checkpoint model"""
    name: str
    path: Path
    architecture: ModelArchitecture
    confidence: float  # 0.0 to 1.0
    details: str

@dataclass
class LoRAArchitectureInfo:
    """Information about a LoRA's architecture compatibility"""
    name: str
    architecture: ModelArchitecture
    confidence: float
    details: str
    key_counts: Dict[str, int]

class CheckpointManager:
    """Manages checkpoint detection, validation, and workflow selection"""
    
    def __init__(self, comfyui_path: Union[str, Path]):
        self.comfyui_path = Path(comfyui_path)
        self.checkpoints_dir = self.comfyui_path / "models" / "checkpoints"
        self.workflows_dir = self.comfyui_path / "user" / "default" / "workflows"
        
        # Workflow mapping for different architectures
        self.workflow_mapping = {
            ModelArchitecture.FLUX: "flux_dev_multi-LoRA.api.json",
            ModelArchitecture.SDXL: "sdxl_multi-LoRA.api.json", 
            ModelArchitecture.SD1_5: "sd15_multi-LoRA.api.json"
        }
        
        # Default checkpoints for each architecture
        self.default_checkpoints = {
            ModelArchitecture.FLUX: "flux1-dev-fp8.safetensors",
            ModelArchitecture.SDXL: "raynaenvisionxl_10.safetensors",
            ModelArchitecture.SD1_5: "dreamshaper_8.safetensors"
        }
    
    def get_available_checkpoints(self) -> List[Path]:
        """Get list of available checkpoint files"""
        if not self.checkpoints_dir.exists():
            return []
        
        checkpoints = []
        for ext in ['.safetensors', '.ckpt']:
            checkpoints.extend(self.checkpoints_dir.glob(f"*{ext}"))
        
        return sorted(checkpoints)
    
    def detect_checkpoint_architecture(self, checkpoint_path: Union[str, Path]) -> CheckpointInfo:
        """Detect the architecture of a checkpoint model"""
        checkpoint_path = Path(checkpoint_path)
        
        if not SAFETENSORS_AVAILABLE:
            # Fall back to filename-based detection
            return self._detect_by_filename(checkpoint_path)
        
        if not checkpoint_path.exists():
            return CheckpointInfo(
                name=checkpoint_path.name,
                path=checkpoint_path,
                architecture=ModelArchitecture.UNKNOWN,
                confidence=0.0,
                details=f"File not found: {checkpoint_path}"
            )
        
        try:
            return self._detect_by_keys(checkpoint_path)
        except Exception as e:
            print(f"⚠️  Error analyzing {checkpoint_path.name}: {e}")
            return self._detect_by_filename(checkpoint_path)
    
    def _detect_by_keys(self, checkpoint_path: Path) -> CheckpointInfo:
        """Detect architecture by analyzing checkpoint keys"""
        st_file = safetensors.safe_open(str(checkpoint_path), framework='pt')
        keys = list(st_file.keys())
        total_keys = len(keys)
        
        # Count architecture-specific patterns
        flux_patterns = ['double_blocks', 'single_blocks', 'txt_in', 'vector_in']
        sdxl_patterns = ['input_blocks', 'middle_block', 'output_blocks', 'time_embed']
        sd15_patterns = ['input_blocks', 'middle_block', 'output_blocks']
        
        # Count matches
        flux_keys = sum(1 for k in keys for pattern in flux_patterns if pattern in k)
        sdxl_keys = sum(1 for k in keys for pattern in sdxl_patterns if pattern in k)
        
        # Look for specific SDXL vs SD1.5 indicators
        has_conditioner = any('conditioner' in k for k in keys)
        has_first_stage_model = any('first_stage_model' in k for k in keys)
        
        # Determine architecture
        if flux_keys > 50:  # Flux has many double/single blocks
            confidence = min(0.95, flux_keys / 200.0)
            return CheckpointInfo(
                name=checkpoint_path.name,
                path=checkpoint_path,
                architecture=ModelArchitecture.FLUX,
                confidence=confidence,
                details=f"Detected Flux architecture ({flux_keys} Flux-specific keys)"
            )
        
        elif sdxl_keys > 20 and (has_conditioner or 'sdxl' in checkpoint_path.name.lower()):
            confidence = min(0.9, sdxl_keys / 100.0)
            return CheckpointInfo(
                name=checkpoint_path.name,
                path=checkpoint_path,
                architecture=ModelArchitecture.SDXL,
                confidence=confidence,
                details=f"Detected SDXL architecture ({sdxl_keys} UNet keys, has conditioner: {has_conditioner})"
            )
        
        elif sdxl_keys > 10:  # Could be SD1.5
            confidence = min(0.8, sdxl_keys / 80.0)
            return CheckpointInfo(
                name=checkpoint_path.name,
                path=checkpoint_path,
                architecture=ModelArchitecture.SD1_5,
                confidence=confidence,
                details=f"Detected SD1.5 architecture ({sdxl_keys} UNet keys)"
            )
        
        else:
            return CheckpointInfo(
                name=checkpoint_path.name,
                path=checkpoint_path,
                architecture=ModelArchitecture.UNKNOWN,
                confidence=0.0,
                details=f"Unknown architecture ({total_keys} keys total, first few: {keys[:3]})"
            )
    
    def _detect_by_filename(self, checkpoint_path: Path) -> CheckpointInfo:
        """Fallback detection based on filename patterns"""
        name_lower = checkpoint_path.name.lower()
        
        if 'flux' in name_lower:
            return CheckpointInfo(
                name=checkpoint_path.name,
                path=checkpoint_path,
                architecture=ModelArchitecture.FLUX,
                confidence=0.7,
                details="Filename-based detection: contains 'flux'"
            )
        elif 'sdxl' in name_lower or 'xl' in name_lower:
            return CheckpointInfo(
                name=checkpoint_path.name,
                path=checkpoint_path,
                architecture=ModelArchitecture.SDXL,
                confidence=0.6,
                details="Filename-based detection: contains 'sdxl' or 'xl'"
            )
        else:
            return CheckpointInfo(
                name=checkpoint_path.name,
                path=checkpoint_path,
                architecture=ModelArchitecture.SD1_5,
                confidence=0.5,
                details="Filename-based detection: assuming SD1.5"
            )
    
    def analyze_lora_architecture(self, lora_path: Union[str, Path]) -> LoRAArchitectureInfo:
        """Analyze LoRA architecture for compatibility matching"""
        lora_path = Path(lora_path)
        
        if not SAFETENSORS_AVAILABLE:
            return LoRAArchitectureInfo(
                name=lora_path.name,
                architecture=ModelArchitecture.UNKNOWN,
                confidence=0.0,
                details="SafeTensors not available",
                key_counts={}
            )
        
        if not lora_path.exists():
            return LoRAArchitectureInfo(
                name=lora_path.name,
                architecture=ModelArchitecture.UNKNOWN,
                confidence=0.0,
                details=f"File not found: {lora_path}",
                key_counts={}
            )
        
        try:
            st_file = safetensors.safe_open(str(lora_path), framework='pt')
            keys = list(st_file.keys())
            
            # Count different architecture patterns
            flux_keys = [k for k in keys if 'double_blocks' in k or 'single_blocks' in k]
            sdxl_keys = [k for k in keys if 'input_blocks' in k or 'middle_block' in k or 'output_blocks' in k]
            te_keys = [k for k in keys if 'text_encoder' in k or 'te1_' in k or 'te2_' in k]
            
            key_counts = {
                'total': len(keys),
                'flux': len(flux_keys),
                'sdxl': len(sdxl_keys), 
                'text_encoder': len(te_keys)
            }
            
            # Determine architecture
            if len(flux_keys) > 0:
                confidence = len(flux_keys) / len(keys)
                return LoRAArchitectureInfo(
                    name=lora_path.name,
                    architecture=ModelArchitecture.FLUX,
                    confidence=confidence,
                    details=f"Flux LoRA ({len(flux_keys)}/{len(keys)} Flux keys, {confidence:.1%})",
                    key_counts=key_counts
                )
            
            elif len(sdxl_keys) > 0:
                confidence = len(sdxl_keys) / len(keys)
                # Try to distinguish SDXL vs SD1.5
                if 'sdxl' in lora_path.name.lower() or confidence > 0.8:
                    arch = ModelArchitecture.SDXL
                else:
                    arch = ModelArchitecture.SD1_5
                
                return LoRAArchitectureInfo(
                    name=lora_path.name,
                    architecture=arch,
                    confidence=confidence,
                    details=f"{arch.value.upper()} LoRA ({len(sdxl_keys)}/{len(keys)} UNet keys, {confidence:.1%})",
                    key_counts=key_counts
                )
            
            elif len(te_keys) > len(keys) * 0.8:
                return LoRAArchitectureInfo(
                    name=lora_path.name,
                    architecture=ModelArchitecture.UNKNOWN,
                    confidence=0.0,
                    details=f"Text-encoder-only LoRA ({len(te_keys)}/{len(keys)} TE keys)",
                    key_counts=key_counts
                )
            
            else:
                return LoRAArchitectureInfo(
                    name=lora_path.name,
                    architecture=ModelArchitecture.UNKNOWN,
                    confidence=0.0,
                    details=f"Unknown LoRA architecture ({len(keys)} keys)",
                    key_counts=key_counts
                )
                
        except Exception as e:
            return LoRAArchitectureInfo(
                name=lora_path.name,
                architecture=ModelArchitecture.UNKNOWN,
                confidence=0.0,
                details=f"Error analyzing LoRA: {e}",
                key_counts={}
            )
    
    def find_compatible_checkpoint(self, lora_architecture: ModelArchitecture) -> Optional[CheckpointInfo]:
        """Find the best compatible checkpoint for a given LoRA architecture"""
        available_checkpoints = self.get_available_checkpoints()
        
        if not available_checkpoints:
            return None
        
        # First, try to find the default checkpoint for this architecture
        default_name = self.default_checkpoints.get(lora_architecture)
        if default_name:
            for checkpoint_path in available_checkpoints:
                if checkpoint_path.name == default_name:
                    return self.detect_checkpoint_architecture(checkpoint_path)
        
        # If default not found, look for any compatible checkpoint
        compatible_checkpoints = []
        for checkpoint_path in available_checkpoints:
            checkpoint_info = self.detect_checkpoint_architecture(checkpoint_path)
            if checkpoint_info.architecture == lora_architecture:
                compatible_checkpoints.append(checkpoint_info)
        
        if compatible_checkpoints:
            # Return the one with highest confidence
            return max(compatible_checkpoints, key=lambda x: x.confidence)
        
        return None
    
    def get_workflow_path(self, architecture: ModelArchitecture) -> Optional[Path]:
        """Get the appropriate workflow file for an architecture"""
        workflow_name = self.workflow_mapping.get(architecture)
        if not workflow_name:
            return None
        
        workflow_path = self.workflows_dir / workflow_name
        if workflow_path.exists():
            return workflow_path
        
        # Fall back to Flux workflow if others don't exist
        flux_workflow = self.workflows_dir / self.workflow_mapping[ModelArchitecture.FLUX]
        if flux_workflow.exists():
            print(f"⚠️  {workflow_name} not found, falling back to Flux workflow")
            return flux_workflow
        
        return None
    
    def validate_compatibility(self, checkpoint_info: CheckpointInfo, lora_info: LoRAArchitectureInfo) -> Tuple[bool, str]:
        """Validate that a checkpoint and LoRA are compatible"""
        if checkpoint_info.architecture == ModelArchitecture.UNKNOWN:
            return False, f"Unknown checkpoint architecture: {checkpoint_info.details}"
        
        if lora_info.architecture == ModelArchitecture.UNKNOWN:
            return False, f"Unknown LoRA architecture: {lora_info.details}"
        
        if checkpoint_info.architecture != lora_info.architecture:
            return False, f"Architecture mismatch: {checkpoint_info.architecture.value.upper()} checkpoint with {lora_info.architecture.value.upper()} LoRA"
        
        # Check confidence levels
        if checkpoint_info.confidence < 0.3:
            return False, f"Low confidence checkpoint detection: {checkpoint_info.confidence:.1%}"
        
        if lora_info.confidence < 0.3:
            return False, f"Low confidence LoRA detection: {lora_info.confidence:.1%}"
        
        return True, f"Compatible {checkpoint_info.architecture.value.upper()} checkpoint and LoRA"
    
    def list_checkpoints_by_architecture(self) -> Dict[ModelArchitecture, List[CheckpointInfo]]:
        """Get all checkpoints organized by architecture"""
        checkpoints_by_arch = {arch: [] for arch in ModelArchitecture}
        
        for checkpoint_path in self.get_available_checkpoints():
            checkpoint_info = self.detect_checkpoint_architecture(checkpoint_path)
            checkpoints_by_arch[checkpoint_info.architecture].append(checkpoint_info)
        
        return checkpoints_by_arch
    
    def print_checkpoint_summary(self):
        """Print a summary of available checkpoints"""
        checkpoints_by_arch = self.list_checkpoints_by_architecture()
        
        print("📦 Available Checkpoints by Architecture:")
        for arch, checkpoints in checkpoints_by_arch.items():
            if checkpoints:
                print(f"\n🏷️  {arch.value.upper()} ({len(checkpoints)} checkpoints):")
                for checkpoint in sorted(checkpoints, key=lambda x: x.confidence, reverse=True):
                    confidence_icon = "🟢" if checkpoint.confidence >= 0.8 else "🟡" if checkpoint.confidence >= 0.5 else "🔴"
                    print(f"   {confidence_icon} {checkpoint.name} ({checkpoint.confidence:.1%} confidence)")
                    if checkpoint.details:
                        print(f"      {checkpoint.details}")


def main():
    """CLI interface for checkpoint management"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Checkpoint Architecture Detection and Management")
    parser.add_argument("--comfyui-path", default="/home/mitchellflautt/MuseVision/ComfyUI",
                        help="Path to ComfyUI installation")
    parser.add_argument("--list", action="store_true", 
                        help="List all available checkpoints by architecture")
    parser.add_argument("--analyze-checkpoint", metavar="CHECKPOINT",
                        help="Analyze a specific checkpoint file")
    parser.add_argument("--analyze-lora", metavar="LORA",
                        help="Analyze a specific LoRA file")
    parser.add_argument("--find-compatible", metavar="ARCHITECTURE",
                        choices=['flux', 'sdxl', 'sd1.5'],
                        help="Find compatible checkpoints for given architecture")
    
    args = parser.parse_args()
    
    manager = CheckpointManager(args.comfyui_path)
    
    if args.list:
        manager.print_checkpoint_summary()
    
    if args.analyze_checkpoint:
        checkpoint_path = Path(args.analyze_checkpoint)
        if not checkpoint_path.is_absolute():
            checkpoint_path = manager.checkpoints_dir / checkpoint_path
        
        info = manager.detect_checkpoint_architecture(checkpoint_path)
        print(f"\n🔍 Checkpoint Analysis: {info.name}")
        print(f"   Architecture: {info.architecture.value.upper()}")
        print(f"   Confidence: {info.confidence:.1%}")
        print(f"   Details: {info.details}")
    
    if args.analyze_lora:
        lora_path = Path(args.analyze_lora)
        if not lora_path.is_absolute():
            lora_path = manager.comfyui_path / "models" / "loras" / lora_path
        
        info = manager.analyze_lora_architecture(lora_path)
        print(f"\n🔍 LoRA Analysis: {info.name}")
        print(f"   Architecture: {info.architecture.value.upper()}")
        print(f"   Confidence: {info.confidence:.1%}")
        print(f"   Details: {info.details}")
        print(f"   Key counts: {info.key_counts}")
    
    if args.find_compatible:
        arch_map = {
            'flux': ModelArchitecture.FLUX,
            'sdxl': ModelArchitecture.SDXL, 
            'sd1.5': ModelArchitecture.SD1_5
        }
        architecture = arch_map[args.find_compatible]
        
        compatible = manager.find_compatible_checkpoint(architecture)
        if compatible:
            print(f"\n✅ Best compatible checkpoint for {architecture.value.upper()}:")
            print(f"   Name: {compatible.name}")
            print(f"   Confidence: {compatible.confidence:.1%}")
            print(f"   Details: {compatible.details}")
        else:
            print(f"\n❌ No compatible {architecture.value.upper()} checkpoints found")


if __name__ == "__main__":
    main()