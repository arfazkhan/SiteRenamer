import requests
import sys
import json
import os
from datetime import datetime
from pathlib import Path

class AntennaImageSorterAPITester:
    def __init__(self, base_url="https://telecom-imagesort.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def test_api_root(self):
        """Test API root endpoint"""
        try:
            response = requests.get(f"{self.api_url}/")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Message: {data.get('message', 'No message')}"
            self.log_test("API Root", success, details)
            return success
        except Exception as e:
            self.log_test("API Root", False, str(e))
            return False

    def test_get_component_names(self):
        """Test GET /component-names endpoint"""
        try:
            response = requests.get(f"{self.api_url}/component-names")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            
            if success:
                data = response.json()
                names = data.get('names', [])
                if len(names) == 13:
                    details += f", Got {len(names)} component names"
                else:
                    success = False
                    details += f", Expected 13 names, got {len(names)}"
            
            self.log_test("GET Component Names", success, details)
            return success, response.json() if success else {}
        except Exception as e:
            self.log_test("GET Component Names", False, str(e))
            return False, {}

    def test_update_component_names(self, names):
        """Test PUT /component-names endpoint"""
        try:
            payload = {"names": names}
            response = requests.put(
                f"{self.api_url}/component-names",
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            
            if success:
                data = response.json()
                details += f", Message: {data.get('message', 'No message')}"
            
            self.log_test("PUT Component Names", success, details)
            return success
        except Exception as e:
            self.log_test("PUT Component Names", False, str(e))
            return False

    def test_upload_image(self, site_id, category, component_name):
        """Test POST /sites/{site_id}/upload endpoint"""
        try:
            # Create a dummy image file for testing
            test_image_content = b"fake_image_data_for_testing"
            files = {
                'file': ('test_image.jpg', test_image_content, 'image/jpeg')
            }
            params = {
                'category': category,
                'component_name': component_name
            }
            
            response = requests.post(
                f"{self.api_url}/sites/{site_id}/upload",
                files=files,
                params=params
            )
            
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            
            if success:
                data = response.json()
                details += f", Message: {data.get('message', 'No message')}"
            
            self.log_test(f"Upload Image ({category}/{component_name})", success, details)
            return success
        except Exception as e:
            self.log_test(f"Upload Image ({category}/{component_name})", False, str(e))
            return False

    def test_get_category_images(self, site_id, category):
        """Test GET /sites/{site_id}/category/{category} endpoint"""
        try:
            response = requests.get(f"{self.api_url}/sites/{site_id}/category/{category}")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            
            if success:
                data = response.json()
                images = data.get('images', [])
                details += f", Found {len(images)} images"
            
            self.log_test(f"GET Category Images ({category})", success, details)
            return success, response.json() if success else {}
        except Exception as e:
            self.log_test(f"GET Category Images ({category})", False, str(e))
            return False, {}

    def test_download_site_images(self, site_id):
        """Test GET /sites/{site_id}/download endpoint"""
        try:
            response = requests.get(f"{self.api_url}/sites/{site_id}/download")
            success = response.status_code == 200 or response.status_code == 404
            details = f"Status: {response.status_code}"
            
            if response.status_code == 404:
                details += " (No images found - expected for empty site)"
            elif response.status_code == 200:
                details += f", Content-Type: {response.headers.get('content-type', 'unknown')}"
            
            self.log_test("Download Site Images", success, details)
            return success
        except Exception as e:
            self.log_test("Download Site Images", False, str(e))
            return False

    def run_comprehensive_test(self):
        """Run all API tests"""
        print("🚀 Starting Antenna Site Image Sorter API Tests")
        print("=" * 60)
        
        # Test 1: API Root
        if not self.test_api_root():
            print("❌ API Root failed - stopping tests")
            return False
        
        # Test 2: Get Component Names
        success, component_data = self.test_get_component_names()
        if not success:
            print("❌ Component names endpoint failed")
            return False
        
        # Test 3: Update Component Names
        test_names = [
            "Test Antenna 1", "Test Antenna 2", "Test Antenna 3",
            "Test Cable 1", "Test Cable 2", "Test Equipment 1",
            "Test Equipment 2", "Test Power 1", "Test Ground 1",
            "Test Overview 1", "Test Mount 1", "Test Weather 1",
            "Test Safety 1"
        ]
        self.test_update_component_names(test_names)
        
        # Test 4: Upload Images for different categories
        test_site_id = f"TEST-SITE-{datetime.now().strftime('%H%M%S')}"
        categories = ['alpha', 'beta', 'gamma']
        
        for category in categories:
            self.test_upload_image(test_site_id, category, "Test Component")
        
        # Test 5: Get Category Images
        for category in categories:
            self.test_get_category_images(test_site_id, category)
        
        # Test 6: Download Site Images
        self.test_download_site_images(test_site_id)
        
        # Test 7: Test invalid category
        try:
            response = requests.post(
                f"{self.api_url}/sites/{test_site_id}/upload",
                files={'file': ('test.jpg', b"test", 'image/jpeg')},
                params={'category': 'invalid', 'component_name': 'test'}
            )
            success = response.status_code == 400
            self.log_test("Invalid Category Handling", success, f"Status: {response.status_code}")
        except Exception as e:
            self.log_test("Invalid Category Handling", False, str(e))
        
        return True

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        if self.tests_passed < self.tests_run:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test']}: {result['details']}")
        
        return self.tests_passed == self.tests_run

def main():
    tester = AntennaImageSorterAPITester()
    
    try:
        tester.run_comprehensive_test()
        all_passed = tester.print_summary()
        return 0 if all_passed else 1
    except Exception as e:
        print(f"❌ Test suite failed with error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())