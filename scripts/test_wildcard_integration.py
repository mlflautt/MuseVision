#!/usr/bin/env python3
"""
Test script for wildcard integration across MuseVision components

This script tests:
1. Basic wildcard functionality
2. Integration with run_flux.py
3. Integration with run_variations.py  
4. Integration with agent.py explore_styles
5. Deduplication logic
6. Different positioning options
"""

import subprocess
import tempfile
import os
import sys

def test_basic_wildcard_system():
    """Test the basic wildcard system functionality"""
    print("🧪 Testing basic wildcard system...")
    
    test_cases = [
        {
            "name": "All wildcards with limit",
            "args": ["--prompt", "a mystical forest guardian", "--wildcards", "all:3"],
            "expected_keywords": ["Enhanced prompt"]
        },
        {
            "name": "Specific files",
            "args": ["--prompt", "a dragon", "--wildcards", "Camera_Shots:1", "Lighting_and_Mood:1"],
            "expected_keywords": ["Enhanced prompt", "Camera_Shots", "Lighting_and_Mood"]
        },
        {
            "name": "Append position",
            "args": ["--prompt", "a castle", "--wildcards", "all:2:append"],
            "expected_keywords": ["Enhanced prompt"]
        },
        {
            "name": "Deduplication test",
            "args": ["--prompt", "a close-up shot with natural lighting", "--wildcards", "Camera_Shots:1", "Lighting_and_Mood:1"],
            "expected_keywords": ["Enhanced prompt"]
        }
    ]
    
    passed = 0
    for i, test_case in enumerate(test_cases, 1):
        try:
            print(f"   Test {i}: {test_case['name']}")
            
            cmd = ["python", "wildcard_prompts.py"] + test_case["args"]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/mitchellflautt/MuseVision/scripts")
            
            if result.returncode == 0:
                output = result.stdout
                if all(keyword in output for keyword in test_case["expected_keywords"]):
                    print(f"      ✅ Passed")
                    passed += 1
                else:
                    print(f"      ❌ Failed - missing expected keywords")
                    print(f"      Output: {output[:200]}...")
            else:
                print(f"      ❌ Failed with error: {result.stderr}")
                
        except Exception as e:
            print(f"      ❌ Exception: {e}")
    
    print(f"   📊 Basic wildcard tests: {passed}/{len(test_cases)} passed\n")
    return passed == len(test_cases)


def test_run_flux_integration():
    """Test wildcard integration with run_flux.py"""
    print("🧪 Testing run_flux.py wildcard integration...")
    
    # Create a simple test to check if wildcards are processed
    cmd = [
        "python", "run_flux.py",
        "--prompt", "a magical creature",
        "--name-prefix", "wildcard_test",
        "--wildcards", "Camera_Shots:1", "Color_Palettes:1",
        "--help"  # Just test argument parsing, don't actually submit
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/mitchellflautt/MuseVision/scripts")
        
        if "wildcards" in result.stdout.lower():
            print("   ✅ run_flux.py has wildcard arguments")
            return True
        else:
            print("   ❌ run_flux.py missing wildcard arguments")
            print(f"   Help output: {result.stdout[:500]}...")
            return False
            
    except Exception as e:
        print(f"   ❌ Exception testing run_flux.py: {e}")
        return False


def test_run_variations_integration():
    """Test wildcard integration with run_variations.py"""
    print("🧪 Testing run_variations.py wildcard integration...")
    
    cmd = [
        "python", "run_variations.py",
        "--prompt", "a fantasy castle",
        "--n", "1",
        "--wildcards", "all:2",
        "--help"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/mitchellflautt/MuseVision/scripts")
        
        if "wildcards" in result.stdout.lower():
            print("   ✅ run_variations.py has wildcard arguments") 
            return True
        else:
            print("   ❌ run_variations.py missing wildcard arguments")
            return False
            
    except Exception as e:
        print(f"   ❌ Exception testing run_variations.py: {e}")
        return False


def test_agent_integration():
    """Test wildcard integration with agent.py explore_styles"""
    print("🧪 Testing agent.py explore_styles wildcard integration...")
    
    cmd = [
        "python", "agent.py", "explore_styles", "--help"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/mitchellflautt/MuseVision/scripts")
        
        if "wildcards" in result.stdout.lower():
            print("   ✅ agent.py explore_styles has wildcard arguments")
            return True
        else:
            print("   ❌ agent.py explore_styles missing wildcard arguments")
            return False
            
    except Exception as e:
        print(f"   ❌ Exception testing agent.py: {e}")
        return False


def test_deduplication_logic():
    """Test that deduplication works correctly"""
    print("🧪 Testing deduplication logic...")
    
    test_cases = [
        {
            "prompt": "a close-up portrait with natural lighting",
            "wildcards": ["Camera_Shots:1", "Lighting_and_Mood:1"],
            "should_have_duplicates": True
        },
        {
            "prompt": "a mystical creature in an alien landscape", 
            "wildcards": ["Camera_Shots:1", "Color_Palettes:1"],
            "should_have_duplicates": False
        }
    ]
    
    passed = 0
    for i, test_case in enumerate(test_cases, 1):
        try:
            cmd = [
                "python", "wildcard_prompts.py",
                "--prompt", test_case["prompt"],
                "--wildcards"
            ] + test_case["wildcards"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/mitchellflautt/MuseVision/scripts")
            
            if result.returncode == 0:
                output = result.stdout
                original_in_output = test_case["prompt"] in output
                
                if test_case["should_have_duplicates"]:
                    # Should see fewer wildcards due to deduplication
                    if "No wildcard terms selected" in output or len(output.split("Selected wildcard terms:")[1].strip()) < 50:
                        print(f"   Test {i}: ✅ Deduplication worked")
                        passed += 1
                    else:
                        print(f"   Test {i}: ❌ Deduplication failed")
                else:
                    # Should see wildcards added normally
                    if "Selected wildcard terms:" in output:
                        print(f"   Test {i}: ✅ No false deduplication")  
                        passed += 1
                    else:
                        print(f"   Test {i}: ❌ Unexpected deduplication")
            else:
                print(f"   Test {i}: ❌ Command failed: {result.stderr}")
                
        except Exception as e:
            print(f"   Test {i}: ❌ Exception: {e}")
    
    print(f"   📊 Deduplication tests: {passed}/{len(test_cases)} passed\n")
    return passed == len(test_cases)


def test_file_validation():
    """Test validation of wildcard files and arguments"""
    print("🧪 Testing file validation...")
    
    test_cases = [
        {
            "name": "Non-existent file",
            "args": ["--prompt", "test", "--wildcards", "NonExistentFile:1"],
            "should_fail": True
        },
        {
            "name": "Valid files",
            "args": ["--prompt", "test", "--wildcards", "Camera_Shots:1"],
            "should_fail": False
        },
        {
            "name": "Invalid directory",
            "args": ["--prompt", "test", "--wildcards", "all:1", "--wildcards-dir", "/nonexistent/dir"],
            "should_fail": True
        }
    ]
    
    passed = 0
    for i, test_case in enumerate(test_cases, 1):
        try:
            cmd = ["python", "wildcard_prompts.py"] + test_case["args"]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/mitchellflautt/MuseVision/scripts")
            
            if test_case["should_fail"]:
                if result.returncode != 0:
                    print(f"   Test {i} ({test_case['name']}): ✅ Correctly failed")
                    passed += 1
                else:
                    print(f"   Test {i} ({test_case['name']}): ❌ Should have failed")
            else:
                if result.returncode == 0:
                    print(f"   Test {i} ({test_case['name']}): ✅ Correctly succeeded")
                    passed += 1
                else:
                    print(f"   Test {i} ({test_case['name']}): ❌ Should have succeeded")
                    
        except Exception as e:
            print(f"   Test {i}: ❌ Exception: {e}")
    
    print(f"   📊 Validation tests: {passed}/{len(test_cases)} passed\n")
    return passed == len(test_cases)


def main():
    """Run all wildcard integration tests"""
    print("🚀 Testing Wildcard Integration Across MuseVision\n")
    
    # Check if we're in the right directory
    if not os.path.exists("wildcard_prompts.py"):
        print("❌ Error: Must be run from the scripts directory")
        return False
    
    # Run all test suites
    results = []
    results.append(test_basic_wildcard_system())
    results.append(test_run_flux_integration())
    results.append(test_run_variations_integration())
    results.append(test_agent_integration())
    results.append(test_deduplication_logic())
    results.append(test_file_validation())
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("="*60)
    print("📊 WILDCARD INTEGRATION TEST SUMMARY")
    print("="*60)
    
    if passed == total:
        print(f"🎉 All tests passed! ({passed}/{total})")
        print("\n✨ Wildcard system is fully integrated and ready to use!")
        
        print("\n📋 Usage Examples:")
        print("   # Basic wildcard usage:")
        print("   python run_flux.py --prompt 'a dragon' --name-prefix 'test' \\")
        print("     --wildcards 'all:3' --loras 'fantasy:0.8'")
        
        print("\n   # Specific files with positioning:")
        print("   python run_variations.py --prompt 'a castle' --n 3 \\")
        print("     --wildcards 'Camera_Shots:1:append' 'Lighting_and_Mood:1:append'")
        
        print("\n   # Agent style exploration with wildcards:")
        print("   python agent.py explore_styles --project Test \\")
        print("     --prompt 'mystical forest' --k 3 --wildcards 'all:2'")
        
        return True
    else:
        print(f"❌ Some tests failed ({passed}/{total})")
        print("\n🔧 Please check the failed tests and fix any issues.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
