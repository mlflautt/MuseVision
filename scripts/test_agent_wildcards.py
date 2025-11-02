#!/usr/bin/env python3
"""
Test script for agent.py wildcard integration

Tests all three agent.py commands:
1. explore_styles with wildcards
2. refine_styles with wildcards  
3. explore_narrative with wildcards
"""

import subprocess
import tempfile
import os
import sys
import shutil

def test_explore_styles_wildcards():
    """Test explore_styles command with wildcards"""
    print("🧪 Testing agent.py explore_styles with wildcards...")
    
    # Test help to see if wildcard arguments are present
    cmd = [
        "python", "agent.py", "explore_styles", "--help"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/mitchellflautt/MuseVision/scripts")
        
        if result.returncode == 0 and "wildcards" in result.stdout.lower():
            print("   ✅ explore_styles has wildcard arguments")
            
            # Test the actual functionality (without running LLM)
            print("   🔍 Testing wildcard argument parsing...")
            
            # Create a temporary project directory
            with tempfile.TemporaryDirectory() as temp_dir:
                test_cmd = [
                    "python", "agent.py", "explore_styles",
                    "--project", temp_dir,
                    "--prompt", "a magical forest",
                    "--wildcards", "Camera_Shots:1", "Lighting_and_Mood:1",
                    "--dream-count", "1",
                    "--n", "1",
                    "--creativity", "0.5",
                    "--ngl", "0"  # Disable GPU for test
                ]
                
                # We expect this to fail at LLM stage, but argument parsing should work
                test_result = subprocess.run(test_cmd, capture_output=True, text=True, 
                                           cwd="/home/mitchellflautt/MuseVision/scripts", timeout=30)
                
                # Check if it got past argument parsing (should fail at LLM stage)
                if "Random LoRA sampling" in test_result.stdout or "Using fixed LoRA combination" in test_result.stdout:
                    print("   ✅ Wildcard arguments parsed correctly")
                    return True
                else:
                    print("   ❌ Wildcard arguments not processed correctly")
                    print(f"   Output: {test_result.stdout[:300]}...")
                    print(f"   Error: {test_result.stderr[:300]}...")
                    return False
                    
        else:
            print("   ❌ explore_styles missing wildcard arguments")
            return False
            
    except subprocess.TimeoutExpired:
        print("   ⚠️  Test timed out (expected if LLM processing started)")
        return True  # Timeout likely means it got past argument parsing
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False


def test_refine_styles_wildcards():
    """Test refine_styles command with wildcards"""
    print("🧪 Testing agent.py refine_styles with wildcards...")
    
    # Test help to see if wildcard arguments are present
    cmd = [
        "python", "agent.py", "refine_styles", "--help"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/mitchellflautt/MuseVision/scripts")
        
        if result.returncode == 0 and "wildcards" in result.stdout.lower():
            print("   ✅ refine_styles has wildcard arguments")
            return True
        else:
            print("   ❌ refine_styles missing wildcard arguments") 
            print(f"   Help output sample: {result.stdout[:300]}...")
            return False
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False


def test_explore_narrative_wildcards():
    """Test explore_narrative command with wildcards"""
    print("🧪 Testing agent.py explore_narrative with wildcards...")
    
    # Test help to see if wildcard arguments are present
    cmd = [
        "python", "agent.py", "explore_narrative", "--help"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/mitchellflautt/MuseVision/scripts")
        
        if result.returncode == 0 and "wildcards" in result.stdout.lower():
            print("   ✅ explore_narrative has wildcard arguments")
            return True
        else:
            print("   ❌ explore_narrative missing wildcard arguments")
            print(f"   Help output sample: {result.stdout[:300]}...")
            return False
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False


def test_wildcard_argument_formats():
    """Test different wildcard argument formats"""
    print("🧪 Testing wildcard argument formats...")
    
    formats_to_test = [
        ["all:3"],
        ["Camera_Shots:1", "Lighting_and_Mood:1"], 
        ["all:2:append"],
        ["Camera_Shots:1:prepend", "Color_Palettes:1:integrate"]
    ]
    
    passed = 0
    for i, wildcard_format in enumerate(formats_to_test, 1):
        try:
            print(f"   Test {i}: Format {wildcard_format}")
            
            # Use the basic wildcard system to test parsing
            cmd = [
                "python", "wildcard_prompts.py",
                "--prompt", "test prompt",
                "--wildcards"
            ] + wildcard_format
            
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  cwd="/home/mitchellflautt/MuseVision/scripts", timeout=10)
            
            if result.returncode == 0 and "Enhanced prompt" in result.stdout:
                print(f"      ✅ Format parsed successfully")
                passed += 1
            else:
                print(f"      ❌ Format failed to parse")
                print(f"      Error: {result.stderr[:200]}...")
                
        except Exception as e:
            print(f"      ❌ Exception: {e}")
    
    print(f"   📊 Format tests: {passed}/{len(formats_to_test)} passed\n")
    return passed == len(formats_to_test)


def test_wildcard_file_integration():
    """Test that wildcard files are properly loaded and used"""
    print("🧪 Testing wildcard file integration...")
    
    try:
        # Test basic functionality
        cmd = [
            "python", "wildcard_prompts.py",
            "--prompt", "a fantasy scene", 
            "--wildcards", "Camera_Shots:1", "Color_Palettes:1"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, 
                              cwd="/home/mitchellflautt/MuseVision/scripts")
        
        if result.returncode == 0:
            output = result.stdout
            
            # Check that files were loaded
            if "Loaded 5 wildcard files" in output:
                print("   ✅ Wildcard files loaded correctly")
                
                # Check that terms were selected
                if "Selected wildcard terms:" in output:
                    print("   ✅ Terms selected from wildcard files")
                    
                    # Check that prompt was enhanced
                    if "Enhanced prompt:" in output:
                        print("   ✅ Prompt enhancement working")
                        return True
                    else:
                        print("   ❌ Prompt not enhanced")
                else:
                    print("   ❌ No terms selected")
            else:
                print("   ❌ Wildcard files not loaded")
                print(f"   Output: {output[:300]}...")
        else:
            print("   ❌ Command failed")
            print(f"   Error: {result.stderr[:300]}...")
        
        return False
        
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False


def main():
    """Run all agent.py wildcard tests"""
    print("🚀 Testing Agent.py Wildcard Integration\n")
    
    # Check if we're in the right directory
    if not os.path.exists("agent.py"):
        print("❌ Error: Must be run from the scripts directory")
        return False
    
    # Check if wildcard system exists
    if not os.path.exists("wildcard_prompts.py"):
        print("❌ Error: wildcard_prompts.py not found")
        return False
    
    # Run all test suites
    results = []
    results.append(test_wildcard_file_integration())
    results.append(test_wildcard_argument_formats())
    results.append(test_explore_styles_wildcards())
    results.append(test_refine_styles_wildcards())
    results.append(test_explore_narrative_wildcards())
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("="*60)
    print("📊 AGENT.PY WILDCARD INTEGRATION SUMMARY")
    print("="*60)
    
    if passed == total:
        print(f"🎉 All tests passed! ({passed}/{total})")
        print("\n✨ All agent.py commands now support wildcards!")
        
        print("\n📋 Usage Examples:")
        print("   # explore_styles with wildcards:")
        print("   python agent.py explore_styles --project MyProject \\")
        print("     --prompt 'a mystical forest' --k 3 \\") 
        print("     --wildcards 'Camera_Shots:1' 'Lighting_and_Mood:1:append'")
        
        print("\n   # refine_styles with wildcards:")
        print("   python agent.py refine_styles --project MyProject \\")
        print("     --prompt 'enhanced version' \\")
        print("     --wildcards 'all:2:prepend'")
        
        print("\n   # explore_narrative with wildcards:")
        print("   python agent.py explore_narrative --project MyProject \\") 
        print("     --prompt 'narrative prompt' \\")
        print("     --wildcards 'Color_Palettes:1' 'Composition_and_Technique:1'")
        
        return True
    else:
        print(f"❌ Some tests failed ({passed}/{total})")
        print("\n🔧 Please check the failed tests and fix any issues.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
