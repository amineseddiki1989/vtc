#!/usr/bin/env python3
"""Test rapide des corrections Firebase."""

import requests
import time

BASE_URL = "http://localhost:8007"

def test_quick():
    print("🔥 TEST RAPIDE FIREBASE CORRECTIONS")
    
    # 1. Test health
    response = requests.get(f"{BASE_URL}/health")
    print(f"Health: {response.status_code}")
    
    # 2. Créer utilisateur
    user_data = {
        "email": f"test_quick_{int(time.time())}@example.com",
        "password": "TestPassword123!",
        "first_name": "Test",
        "last_name": "Quick",
        "phone": "+33123456789",
        "role": "passenger"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=user_data)
    print(f"Register: {response.status_code}")
    
    if response.status_code == 200:
        # 3. Login
        login_data = {"email": user_data["email"], "password": user_data["password"]}
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
        print(f"Login: {response.status_code}")
        
        if response.status_code == 200:
            token = response.json().get("access_token")
            headers = {"Authorization": f"Bearer {token}"}
            
            # 4. Test service Firebase
            response = requests.get(f"{BASE_URL}/api/v1/notifications/test", headers=headers)
            print(f"Firebase Test: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Firebase initialized: {data.get('firebase_initialized')}")
                print(f"   Templates: {data.get('templates_count')}")
            
            # 5. Test notification
            response = requests.post(
                f"{BASE_URL}/api/v1/notifications/test-send?notification_type=driver_found",
                headers=headers
            )
            print(f"Test Send: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Success: {data.get('success')}")
                print(f"   Message ID: {data.get('message_id')}")
            else:
                print(f"   Error: {response.text}")

if __name__ == "__main__":
    test_quick()

